/**
 * Input: 待审批项（task_id / reason / risk_level / action / confidence）
 * Output: 确认卡 UI + approve/reject 回调
 * Pos: Agent 侧栏 / 主对话区 HITL 确认面（P0-5 一等公民）
 *
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。
 */
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type PendingApproval = {
  task_id: string;
  decision?: {
    action?: string;
    recommendation?: string;
    confidence?: number;
    risk_level?: string;
    reasoning?: string;
    [key: string]: unknown;
  };
  risk_level?: string;
  created_at?: string;
  reason?: string;
  action_type?: string;
  confidence?: number | null;
  timeout_seconds?: number;
  status?: string;
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

export function ApprovalCard({
  approval,
  onResolved,
  submitting = false,
  className,
}: Props) {
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const action =
    approval.action_type ||
    approval.decision?.action ||
    approval.decision?.recommendation ||
    "决策";
  const conf =
    approval.confidence ??
    approval.decision?.confidence ??
    null;
  const confPct =
    typeof conf === "number" && Number.isFinite(conf)
      ? `${Math.round(conf * 100)}%`
      : null;
  const risk = approval.risk_level || approval.decision?.risk_level || "高";
  const reason =
    approval.reason ||
    approval.decision?.reasoning ||
    "高风险决策需人工确认";

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
      aria-label="待人工确认"
      className={cn(
        "rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 space-y-2 shadow-sm",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-semibold text-amber-800 dark:text-amber-200 shrink-0">
            人工确认
          </span>
          <Badge
            variant="outline"
            className={cn("text-[10px] font-mono", riskTone(risk))}
          >
            风险 {risk}
          </Badge>
        </div>
        <span className="text-[10px] font-mono text-muted-foreground truncate max-w-[40%]" title={approval.task_id}>
          {approval.task_id}
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
        高风险路径不会静默通过；超时默认拒绝（timeout_reject）。
      </p>
    </div>
  );
}
