// Input: agent-store中的Agent执行状态
// Output: 侧边抽屉展示Agent分析日志（Sheet形式）
// Pos: artifact-panel.tsx头部按钮，打开右侧Agent日志抽屉
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { AgentProgressPanel } from "./agent-progress-panel";
import { useAgentStore } from "@/lib/stores/agent-store";
import { Activity, Bot } from "lucide-react";

const AGENT_INTROS = [
  { name: "技术分析师", desc: "K线形态 / 均线系统 / MACD / RSI" },
  { name: "基本面分析师", desc: "财务三表 / ROE / PE-PB / 成长性" },
  { name: "资金流分析师", desc: "主力净流入 / 大单行为 / 北向资金" },
  { name: "情绪分析师", desc: "舆情评分 / 新闻面 / 机构观点" },
  { name: "风险管理师", desc: "波动率 / VaR / 相关性 / 最大回撤" },
  { name: "多头研究员 / 空头研究员", desc: "牛熊对撞双视角" },
  { name: "投资者人格分析师", desc: "巴菲特 / 索罗斯 / 彼得林奇 / 格雷厄姆" },
  { name: "决策分析师 / 反思分析师", desc: "综合决策 + 风险复盘" },
];

export function AgentLogDrawer() {
  const isAnalyzing = useAgentStore(s => s.isAnalyzing);
  const agentProgresses = useAgentStore(s => s.agentProgresses);
  const isEmpty = !isAnalyzing && agentProgresses.length === 0;

  return (
    <Sheet>
      <SheetTrigger
        render={
          <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" />
        }
      >
        <Activity className="h-3 w-3" />
        Agent日志
      </SheetTrigger>
      <SheetContent
        side="right"
        className="bg-background/95 dark:bg-[#0A0A1A]/95 text-foreground backdrop-blur-2xl border-l border-border dark:border-white/[0.08]"
      >
        <SheetHeader>
          <SheetTitle className="text-foreground">Agent 执行日志</SheetTitle>
          <SheetDescription className="text-muted-foreground">Multi-Agent分析进度与工具调用详情</SheetDescription>
        </SheetHeader>
        <div className="p-4 overflow-auto flex-1 font-mono text-xs leading-relaxed text-foreground">
          {isEmpty ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 p-3 rounded-lg bg-foreground/[0.04] dark:bg-white/[0.04] border border-foreground/[0.08] dark:border-white/[0.08]">
                <Bot className="h-4 w-4 text-[#6B5EE4] shrink-0" />
                <div>
                  <div className="text-xs font-sans font-medium">暂无运行中的 Agent 任务</div>
                  <div className="text-[10px] text-muted-foreground font-sans mt-0.5">在左侧发起一次 AI 分析，这里将实时显示 10 个 Agent 的执行进度与工具调用</div>
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
                        <div className="text-[10px] text-muted-foreground font-sans">{a.desc}</div>
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
      </SheetContent>
    </Sheet>
  );
}
