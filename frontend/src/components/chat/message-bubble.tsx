// Input: ChatMessage对象（含role、content、artifacts、created_at）
// Output: 单条消息气泡UI（渐变头像、圆角气泡、artifact专业badge、时间戳、新消息弹跳入场）
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
  candlestick_chart: { icon: BarChart3, color: "text-orange-500 bg-orange-500/10 border-orange-500/20" },
  technical_indicators: { icon: Activity, color: "text-cyan-500 bg-cyan-500/10 border-cyan-500/20" },
  fundamental_metrics: { icon: Building2, color: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20" },
  capital_flow_chart: { icon: ArrowDownUp, color: "text-violet-500 bg-violet-500/10 border-violet-500/20" },
  news_feed: { icon: Newspaper, color: "text-amber-500 bg-amber-500/10 border-amber-500/20" },
  risk_gauge: { icon: ShieldAlert, color: "text-rose-500 bg-rose-500/10 border-rose-500/20" },
  search_results: { icon: Search, color: "text-blue-500 bg-blue-500/10 border-blue-500/20" },
  decision_card: { icon: Lightbulb, color: "text-yellow-500 bg-yellow-500/10 border-yellow-500/20" },
  investor_consensus: { icon: Users, color: "text-teal-500 bg-teal-500/10 border-teal-500/20" },
  agent_pipeline: { icon: Workflow, color: "text-purple-500 bg-purple-500/10 border-purple-500/20" },
};

interface Props {
  message: ChatMessage;
}

export const MessageBubble = memo(function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const isNew = Date.now() - new Date(message.created_at).getTime() < 2000;

  return (
    <div className={`flex gap-3 group ${isNew ? "animate-fade-in" : ""} ${isUser ? "flex-row-reverse" : ""}`}>
      {/* 头像 */}
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 shadow-sm ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gradient-to-br from-blue-500 to-purple-600 text-white"
        }`}
      >
        {isUser ? "我" : "AI"}
      </div>

      {/* 内容 */}
      <div className={`flex-1 min-w-0 ${isUser ? "text-right" : ""}`}>
        <div
          className={`inline-block text-sm px-4 py-2.5 max-w-[90%] shadow-sm ${
            isUser
              ? "bg-gradient-to-r from-blue-600 to-blue-500 text-white rounded-2xl rounded-br-md"
              : "bg-card border border-border/30 text-foreground rounded-2xl rounded-bl-md"
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

        {/* AI消息：重新生成按钮 */}
        {!isUser && (
          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1 mt-1.5">
            <button className="text-[10px] text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-md px-1.5 py-0.5 flex items-center gap-1 transition-colors">
              <RefreshCw className="h-2.5 w-2.5" /> 重新生成
            </button>
          </div>
        )}

        {/* 时间戳 */}
        <div className={`text-[10px] text-muted-foreground/50 mt-1 font-finance ${isUser ? "text-right" : ""}`}>
          {new Date(message.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </div>
  );
});
