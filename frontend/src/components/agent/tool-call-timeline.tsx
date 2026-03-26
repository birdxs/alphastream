/**
 * Input: agent-store中的toolCalls数组
 * Output: 工具调用时间线列表UI
 * Pos: agent-progress-panel.tsx子组件，展示所有工具调用的执行序列
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

"use client";
import { useAgentStore } from "@/lib/stores/agent-store";
import { ToolCallCard } from "./tool-call-card";

export function ToolCallTimeline() {
  const toolCalls = useAgentStore(s => s.toolCalls);

  if (toolCalls.length === 0) return null;

  return (
    <div className="space-y-1.5">
      <h4 className="text-xs font-medium text-muted-foreground flex items-center gap-1">
        {"\uD83D\uDD27 \u5DE5\u5177\u8C03\u7528"} <span className="text-primary">({toolCalls.length})</span>
      </h4>
      <div className="space-y-1">
        {toolCalls.map((tc) => (
          <ToolCallCard key={tc.tool_call_id} toolCall={tc} />
        ))}
      </div>
    </div>
  );
}
