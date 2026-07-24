/**
 * Input: 待审批项（task_id / kind / approval_id / reason / risk_level / action / confidence / decision）
 * Output: 确认卡 UI + approve/reject 回调（区分 agent_decision 与 portfolio_write_proposal）
 * Pos: Agent 侧栏 / 主对话区 HITL 确认面（P0-5 一等公民）
 *
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。
 */
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

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

  const handle = async (approved: boolean) => {
    if (busy || submitting) return;
    setBusy(approved ? "approve" : "reject");
    try {
      await onResolved?.(approval.task_id, approved);
    } finally {
      setBusy(null);
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
          {code ? <span>code: {code}</span> : null}
          {name && name !== code ? <span>name: {name}</span> : null}
          {shares != null ? <span>shares: {shares}</span> : null}
          {weight != null ? <span>weight: {weight}</span> : null}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[10px] text-muted-foreground">
        {approvalId ? (
          <span title={approvalId} data-testid="approval-id-text">
            approval: {shortId(approvalId, 16)}
          </span>
        ) : null}
        {proposalId ? (
          <span title={proposalId} data-testid="proposal-id-text">
            proposal: {shortId(proposalId, 16)}
          </span>
        ) : null}
        {typeof approval.timeout_seconds === "number" ? (
          <span>timeout: {approval.timeout_seconds}s</span>
        ) : null}
        {approval.created_at ? <span>at: {approval.created_at}</span> : null}
      </div>

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
      <p className="text-[10px] text-muted-foreground">
        {isWriteProposal
          ? "写仓提案未批准前不会改组合；超时默认拒绝（timeout_reject）。"
          : "高风险路径不会静默通过；超时默认拒绝（timeout_reject）。"}
      </p>
    </div>
  );
}
