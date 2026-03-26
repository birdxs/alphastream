/**
 * Input: agent-store中的agentProgresses、overallProgress、isAnalyzing、toolCalls状态
 * Output: 完整的Agent分析进度面板（总进度条 + Agent状态网格 + 工具调用Timeline）
 * Pos: chat-panel.tsx子组件，替代简单的AgentProgressBar，展示13Agent完整执行状态
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

"use client";
import { useState } from "react";
import { useAgentStore } from "@/lib/stores/agent-store";
import { AgentStatusBadge } from "./agent-status-badge";
import { ToolCallTimeline } from "./tool-call-timeline";
import { ChevronUp } from "lucide-react";

// 10个Agent的标准顺序
const AGENT_ORDER = [
  "\u6280\u672F\u5206\u6790\u5E08", "\u57FA\u672C\u9762\u5206\u6790\u5E08", "\u8D44\u91D1\u6D41\u5206\u6790\u5E08", "\u60C5\u7EEA\u5206\u6790\u5E08",
  "\u591A\u5934\u7814\u7A76\u5458", "\u7A7A\u5934\u7814\u7A76\u5458", "\u98CE\u9669\u7BA1\u7406\u5E08",
  "\u6295\u8D44\u8005\u4EBA\u683C\u5206\u6790\u5E08", "\u51B3\u7B56\u5206\u6790\u5E08", "\u53CD\u601D\u5206\u6790\u5E08"
];

export function AgentProgressPanel() {
  const agentProgresses = useAgentStore(s => s.agentProgresses);
  const overallProgress = useAgentStore(s => s.overallProgress);
  const isAnalyzing = useAgentStore(s => s.isAnalyzing);
  const toolCalls = useAgentStore(s => s.toolCalls);
  const [expanded, setExpanded] = useState(false);

  if (!isAnalyzing && agentProgresses.length === 0) return null;

  return (
    <>
      {!expanded && (
        <button onClick={() => setExpanded(true)} className="glass-card w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-white/[0.06] transition-colors animate-[glass-enter_300ms_ease-out_both]">
          <span className="flex items-center gap-2">
            <span className="agent-pending">{"\uD83E\uDD16"}</span>
            <span className="font-mono">Agent分析中... {Math.round(overallProgress)}%</span>
          </span>
          <span className="text-muted-foreground font-mono">{agentProgresses.filter(p => p.status === 'completed').length}/{agentProgresses.length} 完成</span>
        </button>
      )}

      {expanded && (
        <div className="glass-card rounded-xl p-3 space-y-3 animate-[glass-enter_300ms_ease-out_both]">
          {/* 总进度 */}
          <div className="flex justify-between items-center cursor-pointer" onClick={() => setExpanded(false)}>
            <span className="text-xs font-medium">{"\uD83E\uDD16 Multi-Agent\u5206\u6790"}</span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground font-mono">{Math.round(overallProgress)}%</span>
              <ChevronUp className="h-3 w-3 text-muted-foreground" />
            </div>
          </div>
          <div className="w-full bg-white/[0.06] rounded-full h-1.5">
            <div className="bg-[#3737CC] h-1.5 rounded-full transition-all duration-500"
                 style={{ width: `${overallProgress}%` }} />
          </div>

          {/* Agent状态网格 — stagger入场 + 状态动效 */}
          <div className="flex flex-wrap gap-1">
            {AGENT_ORDER.map((agentName, i) => {
              const progress = agentProgresses.find(p => p.agent_name === agentName);
              const status = progress?.status || 'pending';
              const statusClass = status === 'pending' ? 'agent-pending' : status === 'started' ? 'agent-running' : status === 'completed' ? 'agent-done' : '';
              return (
                <div key={agentName} className={`animate-[glass-enter_300ms_ease-out_both] ${statusClass}`} style={{ animationDelay: `${i * 60}ms` }}>
                  <AgentStatusBadge
                    name={agentName.replace('\u5206\u6790\u5E08', '').replace('\u7814\u7A76\u5458', '')}
                    status={status}
                  />
                </div>
              );
            })}
          </div>

          {/* 工具调用Timeline */}
          {toolCalls.length > 0 && <ToolCallTimeline />}
        </div>
      )}
    </>
  );
}
