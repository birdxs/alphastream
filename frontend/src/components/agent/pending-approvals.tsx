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
        // 写仓批准后保留卡片，供 ApprovalCard 二次「本地标记应用」；拒绝/普通决策立即刷新
        if (!(approved && isWrite)) {
          await refresh();
        } else {
          // 仅从 pending 语义上标掉，但本地仍展示该卡直到 apply / 下次轮询自然消失
          setItems((prev) =>
            prev.map((x) =>
              x.task_id === taskId || x.approval_id === taskId
                ? { ...x, status: "approved" }
                : x,
            ),
          );
        }
      } finally {
        setSubmittingId(null);
      }
    },
    [items, refresh],
  );

  if (!loading && items.length === 0) return null;

  return (
    <div className={className} data-testid="pending-approvals-panel">
      <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        待确认 ({items.length})
      </div>
      <div className="space-y-2">
        {items.map((it) => (
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
