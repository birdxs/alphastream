/**
 * Input: agent-store中的agentProgresses、overallProgress、isAnalyzing、toolCalls状态
 * Output: 完整的Agent分析进度面板（总进度条 + Agent状态网格 + 工具调用Timeline）
 * Pos: chat-panel.tsx子组件，替代简单的AgentProgressBar，展示13Agent完整执行状态
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

"use client";
import { useAgentStore } from "@/lib/stores/agent-store";
import { AgentStatusBadge } from "./agent-status-badge";
import { ToolCallTimeline } from "./tool-call-timeline";

// 10个Agent的标准顺序
const AGENT_ORDER = [
  "\u6280\u672F\u5206\u6790\u5E08", "\u57FA\u672C\u9762\u5206\u6790\u5E08", "\u8D44\u91D1\u6D41\u5206\u6790\u5E08", "\u60C5\u7EEA\u5206\u6790\u5E08",
  "\u591A\u5934\u7814\u7A76\u5458", "\u7A7A\u5934\u7814\u7A76\u5458", "\u98CE\u9669\u7BA1\u7406\u5E08",
  "\u6295\u8D44\u8005\u4EBA\u683C\u5206\u6790\u5E08", "\u51B3\u7B56\u5206\u6790\u5E08", "\u53CD\u601D\u5206\u6790\u5E08"
];

export function AgentProgressPanel() {
  const { agentProgresses, overallProgress, isAnalyzing, toolCalls } = useAgentStore();

  if (!isAnalyzing && agentProgresses.length === 0) return null;

  return (
    <div className="bg-muted/30 rounded-lg p-3 space-y-3 border">
      {/* 总进度 */}
      <div className="flex justify-between items-center">
        <span className="text-xs font-medium">{"\uD83E\uDD16 Multi-Agent\u5206\u6790"}</span>
        <span className="text-xs text-muted-foreground">{Math.round(overallProgress)}%</span>
      </div>
      <div className="w-full bg-muted rounded-full h-1.5">
        <div className="bg-primary h-1.5 rounded-full transition-all duration-500"
             style={{ width: `${overallProgress}%` }} />
      </div>

      {/* Agent状态网格 */}
      <div className="flex flex-wrap gap-1">
        {AGENT_ORDER.map((agentName) => {
          const progress = agentProgresses.find(p => p.agent_name === agentName);
          return (
            <AgentStatusBadge
              key={agentName}
              name={agentName.replace('\u5206\u6790\u5E08', '').replace('\u7814\u7A76\u5458', '')}
              status={progress?.status || 'pending'}
            />
          );
        })}
      </div>

      {/* 工具调用Timeline */}
      {toolCalls.length > 0 && <ToolCallTimeline />}
    </div>
  );
}
