/**
 * Input: Agent名称 + 状态(pending/started/completed/error) + 可选进度百分比
 * Output: 带图标和颜色的Agent状态徽章UI
 * Pos: agent-progress-panel.tsx子组件，展示单个Agent的执行状态
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

"use client";

interface Props {
  name: string;
  status: 'pending' | 'started' | 'completed' | 'error';
  progress?: number;
}

const STATUS_CONFIG = {
  pending: { icon: "\u23F3", color: "text-[#555570] bg-foreground/[0.03] dark:bg-white/[0.03] animate-[pulse_2s_ease-in-out_infinite]", label: "\u7B49\u5F85\u4E2D" },
  started: { icon: "\u26A1", color: "text-[#3737CC] bg-foreground/[0.05] dark:bg-white/[0.05] animate-spin", label: "\u6267\u884C\u4E2D" },
  completed: { icon: "\u2705", color: "text-[#46BEA3] bg-foreground/[0.05] dark:bg-white/[0.05]", label: "\u5B8C\u6210" },
  error: { icon: "\u274C", color: "text-[#FF8767] bg-foreground/[0.05] dark:bg-white/[0.05]", label: "\u9519\u8BEF" },
};

export function AgentStatusBadge({ name, status }: Props) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs transition-all duration-300 ${config.color}`}>
      <span>{config.icon}</span>
      <span>{name}</span>
    </span>
  );
}
