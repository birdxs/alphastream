/**
 * Input: agent-store中的agentProgresses、overallProgress、isAnalyzing、toolCalls状态
 * Output: 完整的Agent分析进度面板（流程图 + 总进度条 + Agent状态网格 + 工具调用Timeline）
 * Pos: chat-panel.tsx子组件，替代简单的AgentProgressBar，展示Agent执行流程与状态
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

"use client";
import { useState } from "react";
import { useAgentStore } from "@/lib/stores/agent-store";
import { AgentStatusBadge } from "./agent-status-badge";
import { ToolCallTimeline } from "./tool-call-timeline";
import { ChevronUp, ChevronDown } from "lucide-react";

// 10个Agent的标准顺序
const AGENT_ORDER = [
  "\u6280\u672F\u5206\u6790\u5E08", "\u57FA\u672C\u9762\u5206\u6790\u5E08", "\u8D44\u91D1\u6D41\u5206\u6790\u5E08", "\u60C5\u7EEA\u5206\u6790\u5E08",
  "\u591A\u5934\u7814\u7A76\u5458", "\u7A7A\u5934\u7814\u7A76\u5458", "\u98CE\u9669\u7BA1\u7406\u5E08",
  "\u6295\u8D44\u8005\u4EBA\u683C\u5206\u6790\u5E08", "\u51B3\u7B56\u5206\u6790\u5E08", "\u53CD\u601D\u5206\u6790\u5E08"
];

// 流程图节点定义
const FLOW_PARALLEL = ["\u6280\u672F\u5206\u6790\u5E08", "\u57FA\u672C\u9762\u5206\u6790\u5E08", "\u8D44\u91D1\u6D41\u5206\u6790\u5E08", "\u60C5\u7EEA\u5206\u6790\u5E08"];
const FLOW_SEQUENTIAL = ["\u51B3\u7B56\u5206\u6790\u5E08", "\u53CD\u601D\u5206\u6790\u5E08"];

type AgentStatus = 'pending' | 'started' | 'completed' | 'error';

function FlowDot({ status }: { status: AgentStatus }) {
  const base = "w-2 h-2 rounded-full shrink-0";
  if (status === 'completed') return <span className={`${base} bg-[#46BEA3]`} />;
  if (status === 'started') return <span className={`${base} bg-[#3737CC] animate-[pulse_1.2s_ease-in-out_infinite]`} />;
  if (status === 'error') return <span className={`${base} bg-[#FF8767]`} />;
  return <span className={`${base} bg-white/20`} />;
}

function FlowNode({ name, status }: { name: string; status: AgentStatus }) {
  const borderColor =
    status === 'completed' ? 'border-[#46BEA3]/50' :
    status === 'started' ? 'border-[#3737CC]/60' :
    status === 'error' ? 'border-[#FF8767]/50' :
    'border-white/10';
  return (
    <div className={`flex items-center gap-1.5 px-2 py-1 rounded border ${borderColor} bg-foreground/[0.03] dark:bg-white/[0.03] text-[10px] whitespace-nowrap`}>
      <FlowDot status={status} />
      <span className={status === 'pending' ? 'text-muted-foreground' : 'text-foreground/90'}>{name}</span>
    </div>
  );
}

function AgentFlowChart({ agentProgresses }: { agentProgresses: Array<{ agent_name: string; status: string }> }) {
  const getStatus = (name: string): AgentStatus =>
    (agentProgresses.find(p => p.agent_name === name)?.status as AgentStatus) || 'pending';

  return (
    <div className="flex items-center gap-0 text-[10px] overflow-x-auto py-1">
      {/* 并行分支 */}
      <div className="flex flex-col gap-1 shrink-0">
        {FLOW_PARALLEL.map(name => (
          <div key={name} className="flex items-center gap-1">
            <FlowNode name={name.replace('\u5206\u6790\u5E08', '')} status={getStatus(name)} />
            <span className="text-white/20 font-mono">{"\u2192"}</span>
          </div>
        ))}
      </div>

      {/* 汇聚竖线 */}
      <div className="flex flex-col items-center shrink-0 -mx-0.5">
        <div className="w-px h-2 bg-white/15" />
        <div className="w-px h-8 bg-white/15" />
        <div className="w-px h-2 bg-white/15" />
      </div>

      {/* 顺序节点 */}
      <div className="flex items-center gap-1 shrink-0">
        <span className="text-white/20 font-mono">{"\u2192"}</span>
        {FLOW_SEQUENTIAL.map((name, i) => (
          <div key={name} className="flex items-center gap-1">
            <FlowNode name={name.replace('\u5206\u6790\u5E08', '')} status={getStatus(name)} />
            <span className="text-white/20 font-mono">{"\u2192"}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded border border-[#3737CC]/30 bg-[#3737CC]/[0.08] text-[10px] whitespace-nowrap">
          <span className="w-2 h-2 rounded-full bg-[#3737CC]/60 shrink-0" />
          <span>{"\u6700\u7EC8\u7ED3\u679C"}</span>
        </div>
      </div>
    </div>
  );
}

export function AgentProgressPanel() {
  const agentProgresses = useAgentStore(s => s.agentProgresses);
  const overallProgress = useAgentStore(s => s.overallProgress);
  const isAnalyzing = useAgentStore(s => s.isAnalyzing);
  const toolCalls = useAgentStore(s => s.toolCalls);
  const [expanded, setExpanded] = useState(false);
  const [flowExpanded, setFlowExpanded] = useState(false);

  if (!isAnalyzing && agentProgresses.length === 0) return null;

  return (
    <>
      {!expanded && (
        <button onClick={() => setExpanded(true)} className="glass-card w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors animate-[glass-enter_300ms_ease-out_both]">
          <span className="flex items-center gap-2">
            <span className="agent-pending">{"\uD83E\uDD16"}</span>
            <span className="font-mono">Agent{"\u5206\u6790\u4E2D"}... {Math.round(overallProgress)}%</span>
          </span>
          <span className="text-muted-foreground font-mono">{agentProgresses.filter(p => p.status === 'completed').length}/{agentProgresses.length} {"\u5B8C\u6210"}</span>
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
          <div className="w-full bg-foreground/[0.06] dark:bg-white/[0.06] rounded-full h-1.5">
            <div className="bg-[#3737CC] h-1.5 rounded-full transition-all duration-500"
                 style={{ width: `${overallProgress}%` }} />
          </div>

          {/* 执行流程图（可折叠，默认折叠） */}
          <div>
            <button
              onClick={(e) => { e.stopPropagation(); setFlowExpanded(!flowExpanded); }}
              className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground/80 transition-colors"
            >
              {flowExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronDown className="h-3 w-3 -rotate-90" />}
              <span>{"\u67E5\u770B\u6267\u884C\u6D41\u7A0B"}</span>
            </button>
            {flowExpanded && (
              <div className="mt-1.5 p-2 rounded-lg bg-foreground/[0.02] dark:bg-white/[0.02] border border-foreground/[0.06] dark:border-white/[0.06] animate-[glass-enter_200ms_ease-out_both]">
                <AgentFlowChart agentProgresses={agentProgresses} />
              </div>
            )}
          </div>

          {/* Agent状态网格 */}
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
