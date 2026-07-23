/**
 * Input: Agent名称 + 状态(pending/started/completed/error + HITL terminal 态) + 可选进度百分比
 * Output: 带图标和颜色的Agent状态徽章UI
 * Pos: agent-progress-panel.tsx子组件，展示单个Agent的执行状态
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

"use client";

import { normalizeTaskStatus } from "@/lib/stores/agent-store";

interface Props {
  name: string;
  status:
    | "pending"
    | "started"
    | "running"
    | "completed"
    | "error"
    | "failed"
    | "awaiting_approval"
    | "timeout_reject"
    | "rejected"
    | "approved"
    | "cancelled"
    | string;
  progress?: number;
}

const STATUS_CONFIG: Record<string, { icon: string; color: string; label: string }> = {
  pending: { icon: "\u23F3", color: "text-[#555570] bg-foreground/[0.03] dark:bg-white/[0.03] animate-[pulse_2s_ease-in-out_infinite]", label: "等待中" },
  started: { icon: "\u26A1", color: "text-[#3737CC] bg-foreground/[0.05] dark:bg-white/[0.05]", label: "执行中" },
  running: { icon: "\u26A1", color: "text-[#3737CC] bg-foreground/[0.05] dark:bg-white/[0.05]", label: "执行中" },
  completed: { icon: "\u2705", color: "text-[#46BEA3] bg-foreground/[0.05] dark:bg-white/[0.05]", label: "完成" },
  approved: { icon: "\u2705", color: "text-[#46BEA3] bg-foreground/[0.05] dark:bg-white/[0.05]", label: "已批准" },
  error: { icon: "\u274C", color: "text-[#FF8767] bg-foreground/[0.05] dark:bg-white/[0.05]", label: "错误" },
  failed: { icon: "\u274C", color: "text-[#FF8767] bg-foreground/[0.05] dark:bg-white/[0.05]", label: "失败" },
  awaiting_approval: { icon: "\u23F8", color: "text-amber-500 bg-amber-500/10", label: "待审批" },
  timeout_reject: { icon: "\u23F1", color: "text-[#FF8767] bg-foreground/[0.05] dark:bg-white/[0.05]", label: "超时拒绝" },
  rejected: { icon: "\u274C", color: "text-[#FF8767] bg-foreground/[0.05] dark:bg-white/[0.05]", label: "已拒绝" },
  cancelled: { icon: "\u23F9", color: "text-[#555570] bg-foreground/[0.03] dark:bg-white/[0.03]", label: "已取消" },
};

export function AgentStatusBadge({ name, status }: Props) {
  const key = normalizeTaskStatus(status);
  // started 保持进行中语义（normalize 不映射 started）
  const resolved = status === "started" || status === "running" ? status : key;
  const config = STATUS_CONFIG[resolved] || STATUS_CONFIG[key] || STATUS_CONFIG.pending;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs transition-all duration-300 ${config.color}`} title={config.label}>
      <span>{config.icon}</span>
      <span>{name}</span>
    </span>
  );
}
