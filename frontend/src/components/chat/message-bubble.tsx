// Input: ChatMessage对象（含role、content、artifacts、created_at）
// Output: 单条消息气泡UI（渐变头像、圆角气泡、artifact专业badge、数据溯源引用、时间戳、新消息弹跳入场）
// Pos: message-list.tsx的子组件，负责单条消息渲染
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { memo } from "react";
import type { ChatMessage } from "@/lib/types";
import type { ArtifactType } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { StreamMarkdown } from "./stream-markdown";
import {
  RefreshCw,
  BarChart3,
  Activity,
  Building2,
  ArrowDownUp,
  Newspaper,
  ShieldAlert,
  Search,
  Lightbulb,
  Users,
  Workflow,
} from "lucide-react";

/* Artifact 类型 → 图标 + 颜色映射 */
const artifactMeta: Record<
  ArtifactType,
  { icon: React.ElementType; color: string; label?: string }
> = {
  candlestick_chart: { icon: BarChart3, color: "text-[#3737CC] bg-[#3737CC]/10 border-[#3737CC]/20" },
  technical_indicators: { icon: Activity, color: "text-[#46BEA3] bg-[#46BEA3]/10 border-[#46BEA3]/20" },
  fundamental_metrics: { icon: Building2, color: "text-[#F59E0B] bg-[#F59E0B]/10 border-[#F59E0B]/20" },
  capital_flow_chart: { icon: ArrowDownUp, color: "text-[#6B5EE4] bg-[#6B5EE4]/10 border-[#6B5EE4]/20" },
  news_feed: { icon: Newspaper, color: "text-[#46BEA3] bg-[#46BEA3]/10 border-[#46BEA3]/20" },
  risk_gauge: { icon: ShieldAlert, color: "text-[#FF8767] bg-[#FF8767]/10 border-[#FF8767]/20" },
  search_results: { icon: Search, color: "text-[#3737CC] bg-[#3737CC]/10 border-[#3737CC]/20" },
  decision_card: { icon: Lightbulb, color: "text-[#F59E0B] bg-[#F59E0B]/10 border-[#F59E0B]/20" },
  investor_consensus: { icon: Users, color: "text-[#46BEA3] bg-[#46BEA3]/10 border-[#46BEA3]/20" },
  agent_pipeline: { icon: Workflow, color: "text-[#6B5EE4] bg-[#6B5EE4]/10 border-[#6B5EE4]/20" },
};

interface Props {
  message: ChatMessage;
}

export const MessageBubble = memo(function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const isNew = Date.now() - new Date(message.created_at).getTime() < 2000;

  return (
    <div className={`flex gap-3 group ${isNew ? "animate-[glass-enter_250ms_ease-out_both]" : ""} ${isUser ? "flex-row-reverse" : ""}`}>
      {/* 头像 */}
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 shadow-sm ${
          isUser
            ? "bg-[#3737CC] text-white"
            : "bg-gradient-to-br from-[#6B5EE4] to-[#3737CC] text-white animate-[breathe_3s_ease-in-out_infinite]"
        }`}
      >
        {isUser ? "我" : "AI"}
      </div>

      {/* 内容 */}
      <div className={`flex-1 min-w-0 ${isUser ? "text-right" : ""}`}>
        <div
          className={`inline-block text-sm px-4 py-2.5 max-w-[90%] shadow-sm ${
            isUser
              ? "bg-gradient-to-br from-[#3737CC] to-[#4F4FE6] text-white rounded-2xl rounded-br-md"
              : "bg-white/[0.04] backdrop-blur-sm border border-white/[0.08] text-foreground rounded-2xl rounded-bl-md"
          }`}
        >
          {isUser ? (
            <span className="whitespace-pre-wrap">{message.content}</span>
          ) : (
            <StreamMarkdown content={message.content} />
          )}
        </div>

        {/* Artifact标签 */}
        {message.artifacts && message.artifacts.length > 0 && (
          <div className={`flex gap-1.5 mt-2 flex-wrap ${isUser ? "justify-end" : ""}`}>
            {message.artifacts.map((art, i) => {
              const meta = artifactMeta[art.artifact_type as ArtifactType] ?? {
                icon: BarChart3,
                color: "text-muted-foreground bg-muted/60 border-border/40",
              };
              const Icon = meta.icon;
              return (
                <Badge
                  key={i}
                  variant="outline"
                  className={`text-[10px] gap-1 rounded-md px-2 py-0.5 border ${meta.color}`}
                >
                  <Icon className="h-3 w-3" />
                  {art.title}
                </Badge>
              );
            })}
          </div>
        )}

        {/* 数据溯源引用 */}
        {!isUser && message.artifacts && message.artifacts.length > 0 && (
          <div className="text-[10px] text-[#555570] mt-1.5">
            数据来源: akshare · 东方财富 · 财联社
          </div>
        )}

        {/* AI消息：重新生成按钮 */}
        {!isUser && (
          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1 mt-1.5">
            <button className="text-[10px] text-muted-foreground hover:text-primary hover:bg-white/[0.06] rounded-md px-1.5 py-0.5 flex items-center gap-1 transition-colors">
              <RefreshCw className="h-2.5 w-2.5" /> 重新生成
            </button>
          </div>
        )}

        {/* 时间戳 */}
        <div className={`text-[10px] text-[#555570] mt-1 font-mono ${isUser ? "text-right" : ""}`}>
          {new Date(message.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </div>
  );
});
