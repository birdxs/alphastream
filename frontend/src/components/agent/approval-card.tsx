/**
 * Input: 待审批项（task_id / kind / approval_id / reason / risk_level / action / confidence / decision）
 * Output: 确认卡 UI + approve/reject；写仓批准后二次「本地标记应用」（executed=false，禁止已成交文案）
 * Pos: Agent 侧栏 / 主对话区 HITL 确认面（P0-5 一等公民 + Sprint4 apply）
 *
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。
 */
"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useAgentStore } from "@/lib/stores/agent-store";
import type { AgentEvent } from "@/lib/stores/agent-store";

/** 与后端 HITLManager.get_pending_approvals 的 kind 对齐 */
export type ApprovalKind = "agent_decision" | "portfolio_write_proposal" | string;

export type PendingApproval = {
  task_id: string;
  decision?: {
    action?: string;
    recommendation?: string;
    confidence?: number;
    risk_level?: string;
    reasoning?: string;
    /** 写仓提案结构字段（零假价） */
    code?: string;
    name?: string;
    shares?: number;
    weight?: number;
    proposal_id?: string;
    kind?: string;
    [key: string]: unknown;
  };
  risk_level?: string;
  created_at?: string;
  reason?: string;
  action_type?: string;
  confidence?: number | null;
  timeout_seconds?: number;
  status?: string;
  /** agent_decision | portfolio_write_proposal */
  kind?: ApprovalKind;
  /** 写仓审批 id（appr_*）；与 task_id 可能相同 */
  approval_id?: string | null;
  proposal_id?: string | null;
};

type Props = {
  approval: PendingApproval;
  onResolved?: (taskId: string, approved: boolean) => void;
  submitting?: boolean;
  className?: string;
};

function riskTone(level?: string): string {
  const s = (level || "").toLowerCase();
  if (s.includes("高") || s === "high" || s === "critical") {
    return "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40";
  }
  if (s.includes("中") || s === "medium" || s === "mid") {
    return "bg-yellow-500/10 text-yellow-800 dark:text-yellow-200 border-yellow-500/30";
  }
  return "bg-muted text-muted-foreground border-border";
}

function kindLabel(kind?: ApprovalKind): string {
  if (kind === "portfolio_write_proposal") return "写仓提案";
  if (kind === "agent_decision") return "决策确认";
  return kind ? String(kind) : "";
}

function shortId(id: string | null | undefined, head = 14): string {
  if (!id) return "";
  return id.length > head ? `${id.slice(0, head)}…` : id;
}

/** 外部 status / timeline write_proposal 事件 → 卡片 phase（不依赖 3s 轮询） */
type CardPhase = "pending" | "approved_waiting_apply" | "applied" | "rejected";

function mapStatusToPhase(status?: string | null): CardPhase | null {
  const s = (status || "").toLowerCase().trim();
  if (!s || s === "pending" || s === "awaiting_approval") return null;
  if (s === "approved") return "approved_waiting_apply";
  if (s === "rejected" || s === "timeout_reject") return "rejected";
  if (s === "applied" || s === "applied_local") return "applied";
  return null;
}

function pickWriteProposalStatus(ev: AgentEvent): string {
  const d = (ev.meta || {}) as Record<string, unknown>;
  return String(d.status || d.resolution || "").toLowerCase().trim();
}

function matchesWriteProposalEvent(ev: AgentEvent, approval: PendingApproval): boolean {
  if (ev.type !== "write_proposal") return false;
  const d = (ev.meta || {}) as Record<string, unknown>;
  const pid = String(d.proposal_id || d.id || "").trim();
  const aid = String(d.approval_id || "").trim();
  const targets = [approval.proposal_id, approval.approval_id, approval.task_id]
    .filter(Boolean)
    .map((x) => String(x));
  if (pid && targets.includes(pid)) return true;
  if (aid && targets.includes(aid)) return true;
  if (approval.task_id && String(d.task_id || "") === approval.task_id) {
    const st = pickWriteProposalStatus(ev);
    return ["approved", "rejected", "applied", "applied_local", "timeout_reject"].includes(st);
  }
  return false;
}

function phaseRank(p: CardPhase): number {
  if (p === "pending") return 0;
  if (p === "approved_waiting_apply") return 1;
  if (p === "rejected") return 2;
  return 3; // applied
}

export function ApprovalCard({
  approval,
  onResolved,
  submitting = false,
  className,
}: Props) {
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const kind: ApprovalKind | undefined =
    approval.kind ||
    (typeof approval.decision?.kind === "string"
      ? (approval.decision.kind as ApprovalKind)
      : undefined);
  const isWriteProposal = kind === "portfolio_write_proposal";
  const action =
    approval.action_type ||
    approval.decision?.action ||
    approval.decision?.recommendation ||
    (isWriteProposal ? "写仓" : "决策");
  const conf =
    approval.confidence ??
    approval.decision?.confidence ??
    null;
  const confPct =
    typeof conf === "number" && Number.isFinite(conf)
      ? `${Math.round(conf <= 1 ? conf * 100 : conf)}%`
      : null;
  const risk = approval.risk_level || approval.decision?.risk_level || "高";
  const reason =
    approval.reason ||
    approval.decision?.reasoning ||
    (isWriteProposal
      ? "组合写仓提案需人工批准后才会落账（零假数，无自动成交）。"
      : "高风险决策需人工确认");
  const approvalId =
    approval.approval_id ||
    (isWriteProposal ? approval.task_id : null) ||
    null;
  const proposalId =
    approval.proposal_id ||
    (typeof approval.decision?.proposal_id === "string"
      ? approval.decision.proposal_id
      : null) ||
    null;
  const code =
    typeof approval.decision?.code === "string" ? approval.decision.code : null;
  const name =
    typeof approval.decision?.name === "string" ? approval.decision.name : null;
  const shares =
    typeof approval.decision?.shares === "number" &&
    Number.isFinite(approval.decision.shares)
      ? approval.decision.shares
      : null;
  const weight =
    typeof approval.decision?.weight === "number" &&
    Number.isFinite(approval.decision.weight)
      ? approval.decision.weight
      : null;

  const [phase, setPhase] = useState<CardPhase>(
    () => mapStatusToPhase(approval.status) || "pending",
  );
  const [applyBusy, setApplyBusy] = useState(false);
  const [applyMsg, setApplyMsg] = useState<string | null>(null);
  const [applyMeta, setApplyMeta] = useState<{
    executed: boolean;
    local_mark_only: boolean;
    status?: string | null;
  } | null>(null);
  const storeEvents = useAgentStore((s) => s.events);
  const lastSyncedEventId = useRef<string>("");

  // sticky / 父组件 status 推进时即时刷新 phase（不依赖轮询）
  useEffect(() => {
    const mapped = mapStatusToPhase(approval.status);
    if (!mapped) return;
    setPhase((prev) => (phaseRank(mapped) >= phaseRank(prev) ? mapped : prev));
  }, [approval.status]);

  // 订阅 store 最近 write_proposal 终态事件（approved / rejected / applied_local）
  // 仅推进 phase，不触发 onResolved（避免重复 submitApproval）
  useEffect(() => {
    if (!storeEvents.length) return;
    for (let i = storeEvents.length - 1; i >= 0; i--) {
      const ev = storeEvents[i];
      if (!matchesWriteProposalEvent(ev, approval)) continue;
      const mapped = mapStatusToPhase(pickWriteProposalStatus(ev));
      if (!mapped) continue;
      const eid = String(ev.id || `${ev.type}-${ev.ts}-${mapped}`);
      if (lastSyncedEventId.current === eid) break;
      lastSyncedEventId.current = eid;
      setPhase((prev) => (phaseRank(mapped) >= phaseRank(prev) ? mapped : prev));
      break;
    }
  }, [storeEvents, approval]);

  const handle = async (approved: boolean) => {
    if (busy || submitting || phase !== "pending") return;
    setBusy(approved ? "approve" : "reject");
    try {
      await onResolved?.(approval.task_id, approved);
      if (approved && isWriteProposal) {
        setPhase("approved_waiting_apply");
        setApplyMsg("已批准（未下单）。可调用 apply_portfolio_proposal 做本地标记应用。");
      } else if (approved) {
        setPhase("applied");
      } else {
        setPhase("rejected");
      }
    } finally {
      setBusy(null);
    }
  };

  const handleLocalApply = async () => {
    if (!proposalId || applyBusy || phase === "applied") return;
    setApplyBusy(true);
    setApplyMsg(null);
    try {
      const res = await fetch("/api/agent_apply_portfolio_proposal", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          proposal_id: proposalId,
          ...(approvalId ? { approval_id: approvalId } : {}),
        }),
      });
      let body: Record<string, unknown> = {};
      try {
        body = (await res.json()) as Record<string, unknown>;
      } catch {
        body = {};
      }
      const data =
        body && typeof body.data === "object" && body.data
          ? (body.data as Record<string, unknown>)
          : body;
      const executed = Boolean(data.executed ?? body.executed);
      const localMark = Boolean(
        data.local_mark_only ?? body.local_mark_only ?? true,
      );
      // 硬守卫：UI 永远按未成交展示
      const safeExecuted = false;
      const status =
        (typeof data.status === "string" && data.status) ||
        (typeof body.status === "string" && body.status) ||
        null;
      const msg =
        (typeof data.message === "string" && data.message) ||
        (typeof body.message === "string" && body.message) ||
        (typeof data.error === "string" && data.error) ||
        (res.ok ? "本地标记已应用（未下单、未成交）" : `HTTP ${res.status}`);
      setApplyMeta({
        executed: safeExecuted,
        local_mark_only: localMark || !executed,
        status,
      });
      if (res.ok && body.success !== false && data.success !== false) {
        setPhase("applied");
        setApplyMsg(
          `${msg} · executed=${String(safeExecuted)} · local_mark_only=true`,
        );
      } else {
        setApplyMsg(`本地标记失败：${msg}（仍未下单）`);
      }
    } catch (e) {
      setApplyMsg(
        `本地标记失败：${e instanceof Error ? e.message : "网络错误"}（仍未下单）`,
      );
    } finally {
      setApplyBusy(false);
    }
  };

  return (
    <div
      role="region"
      aria-label={isWriteProposal ? "写仓人工确认" : "待人工确认"}
      data-testid="approval-card"
      data-task-id={approval.task_id}
      data-kind={kind || "agent_decision"}
      data-approval-id={approvalId || undefined}
      data-proposal-id={proposalId || undefined}
      data-phase={phase}
      className={cn(
        "rounded-lg border p-3 space-y-2 shadow-sm",
        isWriteProposal
          ? "border-violet-500/40 bg-violet-500/5"
          : "border-amber-500/40 bg-amber-500/5",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-wrap">
          <span
            className={cn(
              "text-sm font-semibold shrink-0",
              isWriteProposal
                ? "text-violet-800 dark:text-violet-200"
                : "text-amber-800 dark:text-amber-200",
            )}
          >
            {isWriteProposal ? "写仓需确认" : "人工确认"}
          </span>
          <Badge
            variant="outline"
            className={cn("text-[10px] font-mono", riskTone(risk))}
          >
            风险 {risk}
          </Badge>
          {kind ? (
            <Badge
              variant="outline"
              data-testid="approval-kind-badge"
              className={cn(
                "text-[10px] font-mono",
                isWriteProposal
                  ? "bg-violet-500/15 text-violet-800 dark:text-violet-200 border-violet-500/40"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {kindLabel(kind)}
            </Badge>
          ) : null}
        </div>
        <span
          className="text-[10px] font-mono text-muted-foreground truncate max-w-[40%]"
          title={approval.task_id}
        >
          {shortId(approval.task_id)}
        </span>
      </div>

      <div className="text-sm">
        <span className="text-muted-foreground">动作 </span>
        <span className="font-semibold">{String(action)}</span>
        {confPct ? (
          <>
            <span className="text-muted-foreground"> · 置信度 </span>
            <span className="font-mono">{confPct}</span>
          </>
        ) : null}
      </div>

      <p className="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap break-words">
        {reason}
      </p>

      {isWriteProposal && (code || name || shares != null || weight != null) ? (
        <div
          className="flex flex-wrap gap-x-3 gap-y-0.5 rounded-md border border-violet-500/20 bg-violet-500/5 px-2 py-1.5 font-mono text-[10px] text-muted-foreground"
          data-testid="approval-proposal-summary"
        >
          {/* 与 timeline write_proposal meta.summary 同形只读摘要（零假数，无价格） */}
          <span data-testid="approval-readonly-summary">
            {[action, code, shares != null ? `×${shares}` : null, weight != null ? `w=${weight}` : null]
              .filter(Boolean)
              .join(" ")}
          </span>
          {code ? <span>code: {code}</span> : null}
          {name && name !== code ? <span>name: {name}</span> : null}
          {shares != null ? <span>shares: {shares}</span> : null}
          {weight != null ? <span>weight: {weight}</span> : null}
          <span className="text-violet-700/80 dark:text-violet-300/80">未成交</span>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[10px] text-muted-foreground">
        {kind ? (
          <span data-testid="approval-kind-text" title={kind}>
            kind: {kind}
          </span>
        ) : null}
        {approvalId ? (
          <span title={approvalId} data-testid="approval-id-text">
            approval_id: {shortId(approvalId, 16)}
          </span>
        ) : null}
        {proposalId ? (
          <span title={proposalId} data-testid="proposal-id-text">
            proposal_id: {shortId(proposalId, 16)}
          </span>
        ) : null}
        {typeof approval.timeout_seconds === "number" ? (
          <span>timeout: {approval.timeout_seconds}s</span>
        ) : null}
        {approval.created_at ? <span>at: {approval.created_at}</span> : null}
      </div>

      {phase === "pending" ? (
        <div className="flex gap-2 pt-1">
          <Button
            size="sm"
            variant="default"
            disabled={!!busy || submitting}
            className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
            onClick={() => void handle(true)}
          >
            {busy === "approve" ? "提交中…" : "批准"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!!busy || submitting}
            className="flex-1 border-rose-400/50 text-rose-700 dark:text-rose-300 hover:bg-rose-500/10"
            onClick={() => void handle(false)}
          >
            {busy === "reject" ? "提交中…" : "拒绝"}
          </Button>
        </div>
      ) : null}

      {isWriteProposal && phase === "approved_waiting_apply" ? (
        <div
          className="space-y-2 rounded-md border border-violet-500/30 bg-violet-500/10 p-2"
          data-testid="approval-apply-confirm"
        >
          <p className="text-[11px] text-violet-900 dark:text-violet-100 leading-relaxed">
            已批准，仍未下单。可调用 apply_portfolio_proposal，或点击下方二次确认做
            <span className="font-semibold">本地标记应用</span>
            （executed=false / local_mark_only）。
          </p>
          <Button
            size="sm"
            variant="default"
            disabled={applyBusy || !proposalId}
            className="w-full bg-violet-600 hover:bg-violet-700 text-white"
            data-testid="approval-local-apply-btn"
            onClick={() => void handleLocalApply()}
          >
            {applyBusy ? "标记中…" : "本地标记应用"}
          </Button>
          {!proposalId ? (
            <p className="text-[10px] text-rose-600">缺少 proposal_id，无法本地标记。</p>
          ) : null}
        </div>
      ) : null}

      {applyMsg ? (
        <p
          className="text-[10px] font-mono text-muted-foreground whitespace-pre-wrap"
          data-testid="approval-apply-result"
          data-executed={String(applyMeta?.executed ?? false)}
          data-local-mark-only={String(applyMeta?.local_mark_only ?? true)}
        >
          {applyMsg}
        </p>
      ) : null}

      <p className="text-[10px] text-muted-foreground">
        {isWriteProposal
          ? phase === "applied"
            ? "本地标记完成：未成交、未下单（local_mark_only）。"
            : "写仓提案批准≠成交；须二次本地标记应用；超时默认拒绝（timeout_reject）。"
          : "高风险路径不会静默通过；超时默认拒绝（timeout_reject）。"}
      </p>
    </div>
  );
}
