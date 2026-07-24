/**
 * Input: GET /api/agent_pending_approvals 轮询结果（含 kind / approval_id / proposal_id）
 * Output: 待确认 ApprovalCard 列表 + 提交审批（写仓提案与决策确认同闸）
 * Pos: agent 侧栏 HITL 确认面
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApprovalCard,
  type ApprovalKind,
  type PendingApproval,
} from "@/components/agent/approval-card";
import { useAgentStore } from "@/lib/stores/agent-store";
import type { AgentEvent } from "@/lib/stores/agent-store";

function normalizePending(raw: unknown): PendingApproval | null {
  if (!raw || typeof raw !== "object") return null;
  const x = raw as Record<string, unknown>;
  const taskId = String(x.task_id || x.taskId || x.approval_id || "").trim();
  if (!taskId) return null;

  const decision =
    x.decision && typeof x.decision === "object"
      ? (x.decision as PendingApproval["decision"])
      : undefined;

  const kindRaw =
    (typeof x.kind === "string" && x.kind) ||
    (decision && typeof decision.kind === "string" && decision.kind) ||
    undefined;

  const approvalId =
    (typeof x.approval_id === "string" && x.approval_id) ||
    (typeof x.approvalId === "string" && x.approvalId) ||
    (kindRaw === "portfolio_write_proposal" ? taskId : null);

  const proposalId =
    (typeof x.proposal_id === "string" && x.proposal_id) ||
    (typeof x.proposalId === "string" && x.proposalId) ||
    (decision && typeof decision.proposal_id === "string" && decision.proposal_id) ||
    null;

  const confRaw = x.confidence;
  const confidence =
    typeof confRaw === "number" && Number.isFinite(confRaw) ? confRaw : null;

  return {
    task_id: taskId,
    risk_level: typeof x.risk_level === "string" ? x.risk_level : undefined,
    reason: typeof x.reason === "string" ? x.reason : undefined,
    action_type:
      (typeof x.action_type === "string" && x.action_type) ||
      (decision && typeof decision.action === "string" && decision.action) ||
      undefined,
    confidence,
    created_at: typeof x.created_at === "string" ? x.created_at : undefined,
    timeout_seconds:
      typeof x.timeout_seconds === "number"
        ? x.timeout_seconds
        : typeof x.timeout === "number"
          ? x.timeout
          : undefined,
    status: typeof x.status === "string" ? x.status : undefined,
    kind: kindRaw as ApprovalKind | undefined,
    approval_id: approvalId,
    proposal_id: proposalId,
    decision,
  };
}

async function fetchPending(): Promise<PendingApproval[]> {
  try {
    const res = await fetch("/api/agent_pending_approvals", {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return [];
    const body = await res.json();
    const list =
      (Array.isArray(body?.data) && body.data) ||
      (Array.isArray(body?.approvals) && body.approvals) ||
      (Array.isArray(body) && body) ||
      [];
    return list
      .map(normalizePending)
      .filter((x: PendingApproval | null): x is PendingApproval => x != null);
  } catch {
    return [];
  }
}

async function submitApproval(
  taskId: string,
  approved: boolean,
  feedback?: string,
): Promise<void> {
  const res = await fetch("/api/agent_submit_approval", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      task_id: taskId,
      approved,
      feedback: feedback || "",
    }),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      msg = j?.error?.message || j?.message || j?.error || msg;
    } catch {
      /* ignore */
    }
    throw new Error(typeof msg === "string" ? msg : "提交失败");
  }
}

export function PendingApprovalsPanel({
  pollMs = 4000,
  className,
}: {
  pollMs?: number;
  className?: string;
}) {
  const [items, setItems] = useState<PendingApproval[]>([]);
  /** 写仓批准后 sticky：轮询不再覆盖掉待二次 apply 卡片 */
  const [stickyItems, setStickyItems] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [submittingId, setSubmittingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const list = await fetchPending();
    setItems(list);
    setLoading(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await refresh();
    };
    void tick();
    const id = window.setInterval(tick, Math.max(1500, pollMs));
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [pollMs, refresh]);

  // timeline write_proposal 终态 → sticky 即时同步（不只依赖 3s 轮询）
  const storeEvents = useAgentStore((s) => s.events);
  useEffect(() => {
    if (!storeEvents.length) return;
    for (let i = storeEvents.length - 1; i >= 0; i--) {
      const ev = storeEvents[i] as AgentEvent;
      if (ev.type !== "write_proposal") continue;
      const d = (ev.meta || {}) as Record<string, unknown>;
      const st = String(d.status || d.resolution || "").toLowerCase().trim();
      if (!["approved", "rejected", "applied", "applied_local", "timeout_reject"].includes(st)) {
        continue;
      }
      const pid = String(d.proposal_id || d.id || "").trim();
      const aid = String(d.approval_id || "").trim();
      const tid = String(d.task_id || "").trim();
      const matchKey = (x: PendingApproval) => {
        const keys = [x.proposal_id, x.approval_id, x.task_id].filter(Boolean).map(String);
        return (
          (pid && keys.includes(pid)) ||
          (aid && keys.includes(aid)) ||
          (tid && (x.task_id === tid || x.approval_id === tid))
        );
      };

      if (st === "approved") {
        setStickyItems((prev) => {
          const existing = prev.find(matchKey);
          const fromList = items.find(matchKey);
          const base = existing || fromList;
          if (!base) return prev;
          const key = base.approval_id || base.task_id;
          const filtered = prev.filter((x) => (x.approval_id || x.task_id) !== key);
          return [
            ...filtered,
            {
              ...base,
              status: "approved",
              kind: base.kind || "portfolio_write_proposal",
            },
          ];
        });
      } else if (st === "applied" || st === "applied_local") {
        setStickyItems((prev) =>
          prev.map((x) =>
            matchKey(x)
              ? { ...x, status: st === "applied_local" ? "applied_local" : "applied" }
              : x,
          ),
        );
      } else if (st === "rejected" || st === "timeout_reject") {
        setStickyItems((prev) => prev.filter((x) => !matchKey(x)));
        setItems((prev) => prev.filter((x) => !matchKey(x)));
      }
      // 只处理最新一条匹配终态
      break;
    }
  }, [storeEvents, items]);

  const onResolved = useCallback(
    async (taskId: string, approved: boolean) => {
      setSubmittingId(taskId);
      try {
        const item = items.find(
          (x) => x.task_id === taskId || x.approval_id === taskId,
        );
        const isWrite =
          item?.kind === "portfolio_write_proposal" ||
          Boolean(item?.proposal_id);
        await submitApproval(taskId, approved);
        // 写仓批准后 sticky 保留，供 ApprovalCard 二次「本地标记应用」
        if (approved && isWrite && item) {
          setStickyItems((prev) => {
            const key = item.approval_id || item.task_id;
            const filtered = prev.filter(
              (x) => (x.approval_id || x.task_id) !== key,
            );
            // status=approved 供 ApprovalCard 切到二次「本地标记应用」
            return [
              ...filtered,
              {
                ...item,
                status: "approved",
                kind: item.kind || "portfolio_write_proposal",
              },
            ];
          });
        } else {
          setStickyItems((prev) =>
            prev.filter(
              (x) => x.task_id !== taskId && x.approval_id !== taskId,
            ),
          );
          await refresh();
        }
      } finally {
        setSubmittingId(null);
      }
    },
    [items, refresh],
  );

  const displayItems = (() => {
    const map = new Map<string, PendingApproval>();
    // 服务器 pending 先入；sticky 写仓批准卡覆盖，防轮询摘掉二次 apply 入口
    for (const it of items) {
      map.set(it.approval_id || it.task_id, it);
    }
    for (const it of stickyItems) {
      map.set(it.approval_id || it.task_id, it);
    }
    return Array.from(map.values());
  })();

  if (!loading && displayItems.length === 0) return null;

  return (
    <div className={className} data-testid="pending-approvals-panel">
      <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        待确认 ({displayItems.length})
      </div>
      <div className="space-y-2">
        {displayItems.map((it) => (
          <ApprovalCard
            key={it.approval_id || it.task_id}
            approval={it}
            submitting={submittingId === it.task_id}
            onResolved={(id, approved) => void onResolved(id, approved)}
          />
        ))}
      </div>
    </div>
  );
}
