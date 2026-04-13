// Input: agent-store 实时Agent进度状态
// Output: 固定在首页最右侧的Agent实时进度面板，默认展开，可折叠为竖条
// Pos: 首页第4列，取代原来的AgentLogDrawer抽屉
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect } from "react";
import { useAgentStore } from "@/lib/stores/agent-store";
import { AgentProgressPanel } from "./agent-progress-panel";
import { Activity, ChevronRight, ChevronLeft, Bot } from "lucide-react";

const AGENT_INTROS = [
  { name: "技术分析师", desc: "K线形态 / 均线 / MACD / RSI" },
  { name: "基本面分析师", desc: "财务三表 / ROE / PE-PB / 成长" },
  { name: "资金流分析师", desc: "主力净流入 / 大单 / 北向" },
  { name: "情绪分析师", desc: "舆情 / 新闻 / 机构观点" },
  { name: "风险管理师", desc: "波动率 / VaR / 最大回撤" },
  { name: "多头/空头研究员", desc: "牛熊对撞双视角" },
  { name: "投资者人格分析师", desc: "巴菲特 / 索罗斯 / 林奇 / 格雷厄姆" },
  { name: "决策/反思分析师", desc: "综合决策 + 风险复盘" },
];

const STORAGE_KEY = "agent-panel-collapsed";

export function AgentSidePanel() {
  const [collapsed, setCollapsed] = useState(false);
  const isAnalyzing = useAgentStore(s => s.isAnalyzing);
  const agentProgresses = useAgentStore(s => s.agentProgresses);
  const completedCount = agentProgresses.filter(p => p.status === 'completed').length;
  const totalCount = agentProgresses.length || 10;
  const isEmpty = !isAnalyzing && agentProgresses.length === 0;

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'true') setCollapsed(true);
  }, []);

  const toggle = () => {
    setCollapsed(v => {
      const next = !v;
      localStorage.setItem(STORAGE_KEY, String(next));
      return next;
    });
  };

  if (collapsed) {
    return (
      <div className="hidden md:flex w-10 shrink-0 border-l border-foreground/[0.08] dark:border-white/[0.08] bg-background dark:bg-[#0A0A1A] flex-col items-center py-2 gap-2">
        <button
          onClick={toggle}
          className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-foreground/[0.06] dark:hover:bg-white/[0.08] text-muted-foreground hover:text-foreground transition-colors"
          title="展开 Agent 日志"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="flex flex-col items-center gap-1 mt-2">
          <Activity className={`h-4 w-4 ${isAnalyzing ? 'text-[#3737CC] animate-pulse' : 'text-muted-foreground'}`} />
          <span className="text-[9px] font-mono text-muted-foreground rotate-90 origin-center whitespace-nowrap mt-8">
            Agent 日志
          </span>
        </div>
        {isAnalyzing && (
          <div className="mt-2 text-[9px] font-mono text-[#3737CC] writing-vertical">
            {completedCount}/{totalCount}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="hidden md:flex w-72 xl:w-80 shrink-0 flex-col border-l border-foreground/[0.08] dark:border-white/[0.08] bg-background dark:bg-[#0A0A1A]">
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-10 border-b border-border/60 dark:border-white/[0.08] shrink-0">
        <div className="flex items-center gap-2">
          <Activity className={`h-3.5 w-3.5 ${isAnalyzing ? 'text-[#3737CC] animate-pulse' : 'text-muted-foreground'}`} />
          <span className="text-xs font-medium">Agent 实时进度</span>
          {!isEmpty && (
            <span className="text-[10px] font-mono text-muted-foreground">
              {completedCount}/{totalCount}
            </span>
          )}
        </div>
        <button
          onClick={toggle}
          className="h-6 w-6 flex items-center justify-center rounded-md hover:bg-foreground/[0.06] dark:hover:bg-white/[0.08] text-muted-foreground hover:text-foreground transition-colors"
          title="折叠"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3 font-mono text-xs leading-relaxed text-foreground">
        {isEmpty ? (
          <div className="space-y-3">
            <div className="flex items-start gap-2 p-3 rounded-lg bg-foreground/[0.04] dark:bg-white/[0.04] border border-foreground/[0.08] dark:border-white/[0.08]">
              <Bot className="h-4 w-4 text-[#6B5EE4] shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-sans font-medium">暂无运行中的 Agent</div>
                <div className="text-[10px] text-muted-foreground font-sans mt-0.5">
                  在左侧发起 AI 分析，这里实时显示 10 个 Agent 的执行进度与工具调用
                </div>
              </div>
            </div>
            <div>
              <div className="text-[10px] text-muted-foreground mb-2 font-sans">系统内置 Agent 阵容</div>
              <div className="space-y-1.5">
                {AGENT_INTROS.map((a, i) => (
                  <div key={i} className="flex items-start gap-2 p-2 rounded-md bg-foreground/[0.02] dark:bg-white/[0.02] border border-foreground/[0.05] dark:border-white/[0.05]">
                    <span className="text-[10px] w-5 h-5 rounded-full bg-[#3737CC]/20 text-[#6B5EE4] flex items-center justify-center shrink-0 font-sans">{i + 1}</span>
                    <div className="min-w-0">
                      <div className="text-[11px] font-sans font-medium">{a.name}</div>
                      <div className="text-[10px] text-muted-foreground font-sans truncate">{a.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <AgentProgressPanel />
        )}
      </div>
    </div>
  );
}
