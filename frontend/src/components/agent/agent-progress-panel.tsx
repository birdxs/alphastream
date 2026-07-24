/**
 * Input: agent-store中的agentProgresses、overallProgress、isAnalyzing、toolCalls、events流
 * Output: 实时数据流面板（总进度条 + 实时事件时间线流水 + 可选Agent状态网格）
 * Pos: chat-panel.tsx子组件，AgentSidePanel展开时显示，作为分析过程数据流主视图
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

"use client";
import { useState, useRef, useEffect, useMemo } from "react";
import { useAgentStore, type AgentEvent, type AgentEventType } from "@/lib/stores/agent-store";
import { AgentStatusBadge } from "./agent-status-badge";
import { ChevronUp, ChevronDown, Bot, Wrench, Brain, CheckCircle2, Activity, ArrowDownCircle, AlertTriangle, Scale } from "lucide-react";

// 10个Agent的标准顺序
const AGENT_ORDER = [
  "技术分析师", "基本面分析师", "资金流分析师", "情绪分析师",
  "多头研究员", "空头研究员", "风险管理师",
  "投资者人格分析师", "决策分析师", "反思分析师"
];

type EventVisualConfig = {
  Icon: typeof Bot;
  color: string;       // text颜色class
  bg: string;          // 背景色class
  border: string;      // 边框色class
  label: string;
};

const EVENT_VISUAL: Record<AgentEventType, EventVisualConfig> = {
  agent_started: {
    Icon: Bot,
    color: 'text-[#A78BFA]',
    bg: 'bg-[#A78BFA]/10',
    border: 'border-[#A78BFA]/30',
    label: '启动',
  },
  agent_progress: {
    Icon: Activity,
    color: 'text-[#A78BFA]',
    bg: 'bg-[#A78BFA]/8',
    border: 'border-[#A78BFA]/20',
    label: '进度',
  },
  agent_completed: {
    Icon: CheckCircle2,
    color: 'text-[#46BEA3]',
    bg: 'bg-[#46BEA3]/10',
    border: 'border-[#46BEA3]/30',
    label: '完成',
  },
  tool_call_start: {
    Icon: Wrench,
    color: 'text-[#3737CC]',
    bg: 'bg-[#3737CC]/10',
    border: 'border-[#3737CC]/30',
    label: '工具',
  },
  tool_call_result: {
    Icon: CheckCircle2,
    color: 'text-[#46BEA3]',
    bg: 'bg-[#46BEA3]/8',
    border: 'border-[#46BEA3]/25',
    label: '结果',
  },
  reasoning: {
    Icon: Brain,
    color: 'text-[#FF8767]',
    bg: 'bg-[#FF8767]/10',
    border: 'border-[#FF8767]/30',
    label: '推理',
  },
  debate_turn: {
    Icon: Scale,
    color: 'text-[#F59E0B]',
    bg: 'bg-[#F59E0B]/10',
    border: 'border-[#F59E0B]/30',
    label: '辩论',
  },
  // P0-2 降级事件时间线条目
  degraded: {
    Icon: AlertTriangle,
    color: 'text-amber-600 dark:text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    label: '降级',
  },
  done: {
    Icon: CheckCircle2,
    color: 'text-[#46BEA3]',
    bg: 'bg-[#46BEA3]/10',
    border: 'border-[#46BEA3]/30',
    label: '完成',
  },
  error: {
    Icon: AlertTriangle,
    color: 'text-[#FF8767]',
    bg: 'bg-[#FF8767]/10',
    border: 'border-[#FF8767]/30',
    label: '错误',
  },
  // Plan DAG / 写仓提案 timeline 条目（Sprint4+）
  'plan.created': {
    Icon: Bot,
    color: 'text-[#A78BFA]',
    bg: 'bg-[#A78BFA]/10',
    border: 'border-[#A78BFA]/30',
    label: '计划',
  },
  'plan.step': {
    Icon: Activity,
    color: 'text-[#3737CC]',
    bg: 'bg-[#3737CC]/10',
    border: 'border-[#3737CC]/30',
    label: '计划步骤',
  },
  write_proposal: {
    Icon: Scale,
    color: 'text-[#F59E0B]',
    bg: 'bg-[#F59E0B]/10',
    border: 'border-[#F59E0B]/30',
    label: '写仓提案',
  },
};

function fmtTs(ts: number): string {
  const d = new Date(ts);
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${d.getMilliseconds().toString().padStart(3, '0').slice(0, 2)}`;
}

function truncate(s: string | undefined, n: number): string {
  if (!s) return '';
  return s.length > n ? s.slice(0, n) + '…' : s;
}

function EventRow({ ev, prevTs }: { ev: AgentEvent; prevTs?: number }) {
  const cfg = EVENT_VISUAL[ev.type] ?? EVENT_VISUAL.degraded;
  const Icon = cfg.Icon;
  const [open, setOpen] = useState(false);
  const hasDetail = !!(ev.detail && ev.detail.length > 0);
  const delta = prevTs ? ev.ts - prevTs : 0;

  return (
    <div className="relative pl-7 pr-1 group">
      {/* 节点圆点 */}
      <div className={`absolute left-[10px] top-2 flex items-center justify-center w-4 h-4 rounded-full ${cfg.bg} border ${cfg.border}`}>
        <Icon className={`w-2.5 h-2.5 ${cfg.color}`} />
      </div>

      <div className="flex flex-col gap-0.5 py-1 animate-[glass-enter_220ms_ease-out_both]">
        <div className="flex items-baseline gap-1.5 flex-wrap">
          <span className="font-mono text-[9px] text-muted-foreground/70 tabular-nums">{fmtTs(ev.ts)}</span>
          {delta > 0 && (
            <span className="font-mono text-[9px] text-muted-foreground/40 tabular-nums">+{delta < 1000 ? `${delta}ms` : `${(delta / 1000).toFixed(1)}s`}</span>
          )}
          <span className={`text-[9px] px-1 py-0 rounded ${cfg.bg} ${cfg.color} font-medium`}>{cfg.label}</span>
          {ev.agent && (
            <span className="text-[10px] text-foreground/85 font-medium truncate">{ev.agent}</span>
          )}
        </div>

        <div className="flex items-start gap-1">
          <button
            type="button"
            onClick={() => hasDetail && setOpen(o => !o)}
            disabled={!hasDetail}
            className={`flex-1 text-left text-[11px] leading-tight text-foreground/90 ${hasDetail ? 'cursor-pointer hover:text-foreground' : 'cursor-default'} break-words`}
          >
            {ev.title}
            {hasDetail && !open && (
              <span className="text-muted-foreground/60 ml-1">— {truncate(ev.detail, 60)}</span>
            )}
          </button>
          {hasDetail && (
            <ChevronDown className={`h-3 w-3 text-muted-foreground/50 shrink-0 mt-0.5 transition-transform ${open ? 'rotate-180' : ''}`} />
          )}
        </div>

        {open && hasDetail && (
          <div className={`mt-1 p-2 rounded ${cfg.bg} border ${cfg.border} text-[10px] font-mono text-foreground/85 whitespace-pre-wrap break-all max-h-48 overflow-y-auto`}>
            {ev.detail}
          </div>
        )}
      </div>
    </div>
  );
}

function EventStream() {
  const events = useAgentStore(s => s.events);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoFollow, setAutoFollow] = useState(true);
  const lastLenRef = useRef(0);

  // 自动滚到底部（仅当autoFollow开启且有新事件）
  useEffect(() => {
    if (events.length === lastLenRef.current) return;
    lastLenRef.current = events.length;
    if (!autoFollow) return;
    const el = scrollRef.current;
    if (el) {
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    }
  }, [events.length, autoFollow]);

  // 用户手动滚动检测
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    if (nearBottom && !autoFollow) setAutoFollow(true);
    else if (!nearBottom && autoFollow) setAutoFollow(false);
  };

  if (events.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-[11px] text-muted-foreground/60">
        <Activity className="h-3 w-3 mr-1.5 animate-pulse" />
        <span>等待Agent数据流…</span>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* 时间线竖线 */}
      <div className="relative">
        <div className="absolute left-[12px] top-2 bottom-2 w-px bg-gradient-to-b from-[#3737CC]/30 via-white/10 to-[#46BEA3]/30 rounded-full pointer-events-none" />

        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="max-h-80 overflow-y-auto pr-1 -mr-1 scrollbar-thin"
        >
          <div className="space-y-0.5">
            {events.map((ev, i) => (
              <EventRow key={ev.id} ev={ev} prevTs={i > 0 ? events[i - 1].ts : undefined} />
            ))}
          </div>
        </div>
      </div>

      {/* 跟随到底部按钮（暂停时显示） */}
      {!autoFollow && (
        <button
          onClick={() => {
            setAutoFollow(true);
            const el = scrollRef.current;
            if (el) el.scrollTop = el.scrollHeight;
          }}
          className="absolute bottom-2 right-2 flex items-center gap-1 px-2 py-1 rounded-full bg-[#3737CC] text-white text-[10px] font-medium shadow-lg hover:bg-[#3737CC]/90 transition-colors animate-[glass-enter_180ms_ease-out_both]"
        >
          <ArrowDownCircle className="h-3 w-3" />
          <span>跟随到最新</span>
        </button>
      )}
    </div>
  );
}

export function AgentProgressPanel() {
  const agentProgresses = useAgentStore(s => s.agentProgresses);
  const overallProgress = useAgentStore(s => s.overallProgress);
  const isAnalyzing = useAgentStore(s => s.isAnalyzing);
  const events = useAgentStore(s => s.events);
  const [expanded, setExpanded] = useState(true);
  const [agentsExpanded, setAgentsExpanded] = useState(false);

  const completedCount = useMemo(
    () => agentProgresses.filter(p => p.status === 'completed').length,
    [agentProgresses]
  );

  if (!isAnalyzing && agentProgresses.length === 0 && events.length === 0) return null;

  return (
    <>
      {!expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="glass-card w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors animate-[glass-enter_300ms_ease-out_both]"
        >
          <span className="flex items-center gap-2">
            <Bot className="h-3.5 w-3.5 text-[#3737CC] animate-pulse" />
            <span className="font-mono">Agent分析中… {Math.round(overallProgress)}%</span>
          </span>
          <span className="text-muted-foreground font-mono">
            {completedCount}/{agentProgresses.length || 10} · {events.length} 事件
          </span>
        </button>
      )}

      {expanded && (
        <div className="glass-card rounded-xl p-3 space-y-2.5 animate-[glass-enter_300ms_ease-out_both]">
          {/* 头部：标题 + 折叠 */}
          <div className="flex justify-between items-center cursor-pointer" onClick={() => setExpanded(false)}>
            <span className="text-xs font-medium flex items-center gap-1.5">
              <Bot className={`h-3.5 w-3.5 text-[#3737CC] ${isAnalyzing ? 'animate-pulse' : ''}`} />
              Multi-Agent 实时数据流
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground font-mono tabular-nums">{Math.round(overallProgress)}%</span>
              <ChevronUp className="h-3 w-3 text-muted-foreground" />
            </div>
          </div>

          {/* 总进度条 + 统计 */}
          <div className="space-y-1">
            <div className="w-full bg-foreground/[0.06] dark:bg-white/[0.06] rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-gradient-to-r from-[#3737CC] via-[#A78BFA] to-[#46BEA3] h-1.5 rounded-full transition-all duration-500 shadow-[0_0_8px_rgba(55,55,204,0.5)]"
                style={{ width: `${overallProgress}%` }}
              />
            </div>
            <div className="flex justify-between items-center text-[10px] text-muted-foreground font-mono tabular-nums">
              <span>{completedCount}/{agentProgresses.length || 10} Agent 完成</span>
              <span>{events.length} 事件 · 实时</span>
            </div>
          </div>

          {/* Agent状态网格（可折叠） */}
          <div>
            <button
              onClick={(e) => { e.stopPropagation(); setAgentsExpanded(!agentsExpanded); }}
              className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground/80 transition-colors w-full"
            >
              <ChevronDown className={`h-3 w-3 transition-transform ${agentsExpanded ? '' : '-rotate-90'}`} />
              <span>Agent 状态总览</span>
            </button>
            {agentsExpanded && (
              <div className="mt-1.5 flex flex-wrap gap-1 animate-[glass-enter_200ms_ease-out_both]">
                {AGENT_ORDER.map((agentName, i) => {
                  const progress = agentProgresses.find(p => p.agent_name === agentName);
                  const status = progress?.status || 'pending';
                  const statusClass =
                    status === 'pending' ? 'agent-pending' :
                    status === 'started' ? 'agent-running' :
                    status === 'completed' ? 'agent-done' : '';
                  return (
                    <div key={agentName} className={statusClass} style={{ animationDelay: `${i * 30}ms` }}>
                      <AgentStatusBadge
                        name={agentName.replace('分析师', '').replace('研究员', '')}
                        status={status as 'pending' | 'started' | 'completed' | 'error'}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 实时事件流时间线（核心） */}
          <div className="pt-1 border-t border-foreground/[0.06] dark:border-white/[0.06]">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-medium text-muted-foreground flex items-center gap-1">
                <Activity className="h-3 w-3" />
                数据流
              </span>
              <div className="flex items-center gap-1.5 text-[9px] text-muted-foreground/60 font-mono">
                <span className="flex items-center gap-0.5"><Bot className="h-2.5 w-2.5 text-[#A78BFA]" /></span>
                <span className="flex items-center gap-0.5"><Wrench className="h-2.5 w-2.5 text-[#3737CC]" /></span>
                <span className="flex items-center gap-0.5"><Brain className="h-2.5 w-2.5 text-[#FF8767]" /></span>
                <span className="flex items-center gap-0.5"><CheckCircle2 className="h-2.5 w-2.5 text-[#46BEA3]" /></span>
              </div>
            </div>
            <EventStream />
          </div>
        </div>
      )}
    </>
  );
}
