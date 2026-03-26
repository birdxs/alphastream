/**
 * Input: agent-store中的toolCalls数组
 * Output: 工具调用时间线UI（左侧竖线+节点圆点+状态脉冲）
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
        {"🔧 工具调用"} <span className="text-primary">({toolCalls.length})</span>
      </h4>
      {/* 时间线容器 */}
      <div className="relative pl-5">
        {/* 左侧竖线 */}
        <div className="absolute left-[7px] top-2 bottom-2 w-[2px] bg-[#3737CC]/20 rounded-full" />
        {/* 节点列表 */}
        <div className="space-y-2">
          {toolCalls.map((tc) => {
            const hasResult = !!tc.result;
            const isError = hasResult && /error|失败|异常|错误/i.test(tc.result?.result_summary || "");
            return (
              <div key={tc.tool_call_id} className="relative">
                {/* 时间线节点圆点 */}
                <div className="absolute -left-5 top-3 flex items-center justify-center">
                  {!hasResult ? (
                    /* calling 状态：脉冲蓝 */
                    <span className="relative flex h-3 w-3">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#3737CC]/60" />
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-[#3737CC] border-2 border-background" />
                    </span>
                  ) : isError ? (
                    /* error 状态：红点 */
                    <span className="inline-flex rounded-full h-3 w-3 bg-[#FF8767] border-2 border-background" />
                  ) : (
                    /* completed 状态：绿点 */
                    <span className="inline-flex rounded-full h-3 w-3 bg-[#46BEA3] border-2 border-background" />
                  )}
                </div>
                {/* 卡片 */}
                <ToolCallCard toolCall={tc} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
