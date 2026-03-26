// Input: chat-store artifacts数组
// Output: Artifacts工作区 — Dark Glassmorphism头部 + 内容/空态（glass capability卡片 + 脉冲动画）
// Pos: 首页右栏
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useChatStore } from "@/lib/stores/chat-store";
import { ArtifactRenderer } from "./artifact-renderer";
import { AgentLogDrawer } from "@/components/agent/agent-log-drawer";
import { Trash2, TrendingUp, DollarSign, Users, Bot } from "lucide-react";

const capabilities = [
  {
    icon: TrendingUp,
    title: "K线分析",
    desc: "AI驱动技术指标识别",
    bg: "bg-[#46BEA3]/5",
    iconColor: "text-[#46BEA3]",
  },
  {
    icon: DollarSign,
    title: "基本面",
    desc: "智能财务健康评估",
    bg: "bg-[#F59E0B]/5",
    iconColor: "text-[#F59E0B]",
  },
  {
    icon: Bot,
    title: "Agent协作",
    desc: "13个专业Agent联动",
    bg: "bg-[#3737CC]/5",
    iconColor: "text-[#3737CC]",
  },
  {
    icon: Users,
    title: "大师视角",
    desc: "四大投资风格解读",
    bg: "bg-[#6B5EE4]/5",
    iconColor: "text-[#6B5EE4]",
  },
] as const;

export function ArtifactPanel() {
  const artifacts = useChatStore(s => s.artifacts);
  const isStreaming = useChatStore(s => s.isStreaming);

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header — Dark Glassmorphism */}
      <div className="relative flex items-center justify-between px-3 h-10 bg-[rgba(10,10,26,0.6)] backdrop-blur-sm border-b border-white/[0.08] shrink-0">
        {/* 不确定进度条 — AI分析中时显示 */}
        {isStreaming && (
          <div className="progress-indeterminate absolute bottom-0 left-0 right-0" />
        )}
        <span className="text-xs font-medium text-[#F0F0F5]/80">分析结果</span>
        <div className="flex items-center gap-1">
          {artifacts.length > 0 && (
            <>
              <span className="inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-full bg-[#3737CC]/20 text-[10px] font-medium text-[#3737CC]">{artifacts.length}</span>
              <button
                className="h-6 w-6 flex items-center justify-center rounded-md text-[#8888A0] hover:bg-white/[0.08] hover:text-[#F0F0F5] transition-all duration-200"
                onClick={() => useChatStore.getState().clearArtifacts()}
              >
                <Trash2 className="h-3 w-3" />
              </button>
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
                <h3 className="text-sm font-semibold text-[#F0F0F5] mb-1">AI智能分析工作区</h3>
                <p className="text-xs text-[#8888A0] leading-relaxed">
                  AI将为您生成交互式分析组件
                </p>
              </div>

              {/* Capability 卡片 — Dark Glassmorphism */}
              <div className="grid grid-cols-2 gap-2">
                {capabilities.map(item => (
                  <div
                    key={item.title}
                    className={`${item.bg} rounded-xl p-2.5 text-left border border-white/[0.06] hover:border-white/[0.12] transition-all duration-200`}
                  >
                    <item.icon className={`h-4 w-4 ${item.iconColor} mb-1.5`} />
                    <p className="text-xs font-medium text-[#F0F0F5]">{item.title}</p>
                    <p className="text-[10px] text-[#8888A0] leading-snug">{item.desc}</p>
                  </div>
                ))}
              </div>

              <p className="text-[10px] text-[#555570]">
                在左侧输入问题即可开始
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {artifacts.map((artifact, i) => (
              <div key={`${artifact.artifact_type}_${i}`} className="animate-[glass-enter_300ms_ease-out_both]" style={{ animationDelay: `${i * 80}ms` }}>
                <ArtifactRenderer artifact={artifact} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
