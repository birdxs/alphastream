// Input: AgentProgress数组 + overall进度百分比
// Output: Agent分析进度条UI（总进度条 + 各Agent状态标签）
// Pos: chat-panel.tsx的子组件，流式分析时显示Agent执行进度
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import type { AgentProgress } from "@/lib/types";

interface Props {
  progresses: AgentProgress[];
  overall: number;
}

export function AgentProgressBar({ progresses, overall }: Props) {
  return (
    <div className="bg-muted/50 rounded-lg p-3 space-y-2">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Agent分析进度</span>
        <span>{Math.round(overall)}%</span>
      </div>
      <div className="w-full bg-muted rounded-full h-2">
        <div className="bg-primary h-2 rounded-full transition-all duration-500" style={{ width: `${overall}%` }} />
      </div>
      <div className="flex flex-wrap gap-1">
        {progresses.map((p) => (
          <span key={p.agent_name} className={`text-xs px-1.5 py-0.5 rounded ${
            p.status === 'completed' ? 'bg-green-500/20 text-green-600' :
            p.status === 'started' ? 'bg-yellow-500/20 text-yellow-600' :
            'bg-red-500/20 text-red-600'
          }`}>
            {p.agent_name}
            {p.status === 'completed' ? ' \u2713' : p.status === 'started' ? ' \u22EF' : ' \u2717'}
          </span>
        ))}
      </div>
    </div>
  );
}
