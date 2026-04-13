// Input: chat-store artifacts数组
// Output: Artifacts工作区 — Dark Glassmorphism头部 + 内容/空态（glass capability卡片 + 脉冲动画）
// Pos: 首页右栏
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState } from "react";
import { useChatStore } from "@/lib/stores/chat-store";
import { useAgentStore } from "@/lib/stores/agent-store";
import { ArtifactRenderer } from "./artifact-renderer";
import { AgentLogDrawer } from "@/components/agent/agent-log-drawer";
import { AgentProgressPanel } from "@/components/agent/agent-progress-panel";
import { Trash2, TrendingUp, DollarSign, Users, Bot, ChevronUp, ChevronDown } from "lucide-react";

const capabilities = [
  {
    icon: TrendingUp,
    title: "K线分析",
    desc: "AI驱动技术指标识别",
    bg: "bg-[#46BEA3]/5",
    iconColor: "text-[#46BEA3]",
    prompt: "对600519做一次完整的K线技术分析：均线系统、MACD、RSI、成交量、支撑阻力",
  },
  {
    icon: DollarSign,
    title: "基本面",
    desc: "智能财务健康评估",
    bg: "bg-[#F59E0B]/5",
    iconColor: "text-[#F59E0B]",
    prompt: "分析600519的基本面：ROE、净利润增速、毛利率、现金流、负债率",
  },
  {
    icon: Bot,
    title: "Agent协作",
    desc: "13个专业Agent联动",
    bg: "bg-[#3737CC]/5",
    iconColor: "text-[#3737CC]",
    prompt: "启动多Agent协作深度分析600519，技术/基本面/资金/情绪/风险全维度",
  },
  {
    icon: Users,
    title: "大师视角",
    desc: "巴菲特·索罗斯·林奇·格雷厄姆",
    bg: "bg-[#6B5EE4]/5",
    iconColor: "text-[#6B5EE4]",
    prompt: "用巴菲特、索罗斯、彼得林奇、格雷厄姆四位大师的投资哲学分别解读600519",
  },
] as const;

export function ArtifactPanel() {
  const artifacts = useChatStore(s => s.artifacts);
  const isStreaming = useChatStore(s => s.isStreaming);
  const isAnalyzing = useAgentStore(s => s.isAnalyzing);
  const agentProgresses = useAgentStore(s => s.agentProgresses);
  const [agentInlineCollapsed, setAgentInlineCollapsed] = useState(false);
  const showInlineAgent = (isAnalyzing || agentProgresses.length > 0);

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header — Dark Glassmorphism */}
      <div className="relative flex items-center justify-between px-3 h-10 bg-card/80 dark:bg-[rgba(10,10,26,0.6)] backdrop-blur-sm border-b border-border/60 dark:border-white/[0.08] shrink-0">
        {/* 不确定进度条 — AI分析中时显示 */}
        {isStreaming && (
          <div className="progress-indeterminate absolute bottom-0 left-0 right-0" />
        )}
        <span className="text-xs font-medium text-foreground/80">分析结果</span>
        <div className="flex items-center gap-1">
          {artifacts.length > 0 && (
            <>
              <span className="inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-full bg-[#3737CC]/20 text-[10px] font-medium text-[#3737CC]">{artifacts.length}</span>
              <button
                className="h-6 w-6 flex items-center justify-center rounded-md text-muted-foreground hover:bg-foreground/[0.06] dark:hover:bg-white/[0.08] hover:text-foreground transition-all duration-200"
                onClick={() => useChatStore.getState().clearArtifacts()}
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </>
          )}
          <AgentLogDrawer />
        </div>
      </div>

      {/* Content — 填满剩余高度 */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3 bg-gradient-to-b from-transparent dark:to-[#06060F]/30">
        {/* 内联Agent进度面板 — 发送消息后自动显示，实时各agent进度，可折叠 */}
        {showInlineAgent && (
          <div className="mb-3 rounded-xl border border-[#3737CC]/25 bg-foreground/[0.03] dark:bg-white/[0.03]">
            <button
              onClick={() => setAgentInlineCollapsed(v => !v)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-foreground/[0.04] dark:hover:bg-white/[0.04] transition-colors rounded-t-xl"
            >
              <span className="flex items-center gap-2 font-medium">
                <span className="relative w-2 h-2 rounded-full bg-[#3737CC]">
                  {isAnalyzing && <span className="absolute inset-0 rounded-full bg-[#3737CC] animate-ping" />}
                </span>
                Multi-Agent 实时进度
                <span className="text-muted-foreground font-mono text-[10px]">
                  {agentProgresses.filter(p => p.status === 'completed').length}/{agentProgresses.length || 10}
                </span>
              </span>
              {agentInlineCollapsed ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />}
            </button>
            {!agentInlineCollapsed && (
              <div className="px-3 pb-3">
                <AgentProgressPanel />
              </div>
            )}
          </div>
        )}
        {artifacts.length === 0 && !showInlineAgent ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center w-full max-w-md space-y-5">
              {/* 主图标 — 大圆形 glass 容器 + 脉冲动画 */}
              <div className="flex justify-center">
                <div className="relative">
                  <div className="absolute inset-0 rounded-3xl bg-[#3737CC]/10 animate-pulse" />
                  <div className="relative w-16 h-16 rounded-3xl bg-[#3737CC]/10 border border-[#3737CC]/20 p-5 flex items-center justify-center">
                    <Bot className="h-7 w-7 text-[#3737CC]" />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-foreground mb-1">AI智能分析工作区</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  AI将为您生成交互式分析组件
                </p>
              </div>

              {/* Capability 卡片 — 2x2 网格，点击向AI发送预置问题 */}
              <div className="grid grid-cols-2 gap-2.5 w-full">
                {capabilities.map(item => (
                  <button
                    key={item.title}
                    onClick={() => window.dispatchEvent(new CustomEvent("chat-prefill", { detail: item.prompt }))}
                    className={`${item.bg} rounded-xl p-3 text-left border border-border/60 dark:border-white/[0.06] hover:border-[#3737CC]/30 dark:hover:border-[#6B5EE4]/30 hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 min-w-0 cursor-pointer`}
                  >
                    <item.icon className={`h-4 w-4 ${item.iconColor} mb-1.5 shrink-0`} />
                    <p className="text-xs font-medium text-foreground truncate">{item.title}</p>
                    <p className="text-[10px] text-muted-foreground leading-snug mt-0.5 break-words">{item.desc}</p>
                  </button>
                ))}
              </div>

              <p className="text-[10px] text-muted-foreground/70">
                点击卡片或在左侧输入问题即可开始
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {artifacts.map((artifact, i) => (
              <div id={`artifact-${artifact.artifact_type}-${i}`} key={`${artifact.artifact_type}_${i}`} className="animate-[glass-enter_300ms_ease-out_both]" style={{ animationDelay: `${i * 80}ms` }}>
                <ArtifactRenderer artifact={artifact} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
