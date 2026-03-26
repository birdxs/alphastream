// Input: chat-store artifacts数组
// Output: Artifacts工作区 — 头部 + 内容/空态（精致capability卡片 + 脉冲动画）
// Pos: 首页右栏

"use client";
import { useChatStore } from "@/lib/stores/chat-store";
import { Button } from "@/components/ui/button";
import { ArtifactRenderer } from "./artifact-renderer";
import { AgentLogDrawer } from "@/components/agent/agent-log-drawer";
import { Trash2, TrendingUp, DollarSign, Users, Bot } from "lucide-react";

const capabilities = [
  {
    icon: TrendingUp,
    title: "K线分析",
    desc: "AI驱动技术指标识别",
    bg: "bg-emerald-500/8",
    iconColor: "text-emerald-500",
  },
  {
    icon: DollarSign,
    title: "基本面",
    desc: "智能财务健康评估",
    bg: "bg-amber-500/8",
    iconColor: "text-amber-500",
  },
  {
    icon: Bot,
    title: "Agent协作",
    desc: "13个专业Agent联动",
    bg: "bg-blue-500/8",
    iconColor: "text-blue-500",
  },
  {
    icon: Users,
    title: "大师视角",
    desc: "四大投资风格解读",
    bg: "bg-purple-500/8",
    iconColor: "text-purple-500",
  },
] as const;

export function ArtifactPanel() {
  const artifacts = useChatStore(s => s.artifacts);

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-10 border-b border-border/40 bg-background shrink-0">
        <span className="text-xs font-medium text-foreground/80">分析结果</span>
        <div className="flex items-center gap-1">
          {artifacts.length > 0 && (
            <>
              <span className="text-[10px] text-muted-foreground">{artifacts.length}</span>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => useChatStore.getState().clearArtifacts()}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </>
          )}
          <AgentLogDrawer />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3">
        {artifacts.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-xs space-y-5">
              {/* 主图标 — 带脉冲动画表示等待中 */}
              <div className="flex justify-center">
                <div className="relative">
                  <div className="absolute inset-0 rounded-xl bg-primary/20 animate-pulse" />
                  <div className="relative w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                    <Bot className="h-6 w-6 text-primary" />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold mb-1">AI智能分析工作区</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  AI将为您生成交互式分析组件
                </p>
              </div>

              {/* Capability 卡片 — 视觉层次差异化 */}
              <div className="grid grid-cols-2 gap-2">
                {capabilities.map(item => (
                  <div
                    key={item.title}
                    className={`${item.bg} rounded-lg p-2.5 text-left border border-border/10 transition-colors duration-200 hover:border-border/30`}
                  >
                    <item.icon className={`h-4 w-4 ${item.iconColor} mb-1.5`} />
                    <p className="text-xs font-medium">{item.title}</p>
                    <p className="text-[10px] text-muted-foreground leading-snug">{item.desc}</p>
                  </div>
                ))}
              </div>

              <p className="text-[10px] text-muted-foreground/60">
                在左侧输入问题即可开始
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {artifacts.map((artifact, i) => (
              <ArtifactRenderer key={`${artifact.artifact_type}_${i}`} artifact={artifact} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
