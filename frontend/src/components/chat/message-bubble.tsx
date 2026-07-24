// Input: ChatMessage对象（含role、content、artifacts、created_at）
// Output: 单条消息气泡UI（渐变头像、圆角气泡、artifact专业badge（可点击滚动至右栏对应卡片）、数据溯源引用、时间戳、新消息弹跳入场、AI消息hover复制按钮）
// Pos: message-list.tsx的子组件，负责单条消息渲染
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { memo, useState, useCallback, useRef, useEffect } from "react";
import type { ChatMessage } from "@/lib/types";
import type { ArtifactType } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { StreamMarkdown } from "./stream-markdown";
import {
  RefreshCw,
  Copy,
  Check,
  BarChart3,
  Activity,
  Building2,
  ArrowDownUp,
  Newspaper,
  ShieldAlert,
  Search,
  Lightbulb,
  Scale,
  Users,
  Workflow,
  Layers,
  Ship,
  Leaf,
  Briefcase,
  Network,
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
  debate_card: { icon: Scale, color: "text-[#F59E0B] bg-[#F59E0B]/10 border-[#F59E0B]/20", label: "多空辩论" },
  investor_consensus: { icon: Users, color: "text-[#46BEA3] bg-[#46BEA3]/10 border-[#46BEA3]/20" },
  investor_opinions: { icon: Users, color: "text-[#6B5EE4] bg-[#6B5EE4]/10 border-[#6B5EE4]/20" },
  agent_pipeline: { icon: Workflow, color: "text-[#6B5EE4] bg-[#6B5EE4]/10 border-[#6B5EE4]/20" },
  // P3 另类数据 (E4 — 2026-04-15)
  alt_data: { icon: Layers, color: "text-[#6B5EE4] bg-[#6B5EE4]/10 border-[#6B5EE4]/20" },
  shipping: { icon: Ship, color: "text-[#6B5EE4] bg-[#6B5EE4]/10 border-[#6B5EE4]/20" },
  esg: { icon: Leaf, color: "text-[#46BEA3] bg-[#46BEA3]/10 border-[#46BEA3]/20" },
  hiring: { icon: Briefcase, color: "text-[#F59E0B] bg-[#F59E0B]/10 border-[#F59E0B]/20" },
  corporate_network: { icon: Network, color: "text-[#3737CC] bg-[#3737CC]/10 border-[#3737CC]/20" },
};

interface Props {
  message: ChatMessage;
  onRegenerate?: () => void;
}

export const MessageBubble = memo(function MessageBubble({ message, onRegenerate }: Props) {
  const isUser = message.role === "user";
  // 挂载时捕获时间，避免在渲染期调用 Date.now()（purity 规则）
  const [mountTime] = useState(() => Date.now());
  const isNew = mountTime - new Date(message.created_at).getTime() < 2000;
  const [copied, setCopied] = useState(false);

  // 定时器 refs 防泄漏
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const handleCopy = useCallback(() => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true);
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
      copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
    });
  }, [message.content]);

  // 组件卸载时清理定时器
  useEffect(() => {
    return () => {
      if (copyTimerRef.current) {
        clearTimeout(copyTimerRef.current);
      }
      if (highlightTimerRef.current) {
        clearTimeout(highlightTimerRef.current);
      }
    };
  }, []);

  return (
    <div className={`flex gap-3 group ${isNew ? "animate-[glass-enter_250ms_ease-out_both]" : ""} ${isUser ? "flex-row-reverse" : ""}`}>
      {/* 头像 */}
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 shadow-sm ${
          isUser
            ? "bg-gradient-to-br from-[#3737CC] to-[#5252E0] text-white ring-1 ring-white/10"
            : "bg-gradient-to-br from-[#6B5EE4] to-[#3737CC] text-white animate-[breathe_3s_ease-in-out_infinite]"
        }`}
      >
        {isUser ? (
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="8" cy="5" r="3" fill="currentColor" opacity="0.9"/>
            <path d="M2.5 14.5C2.5 11.5 5 9.5 8 9.5C11 9.5 13.5 11.5 13.5 14.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.9"/>
          </svg>
        ) : (
          <span className="text-[10px] font-bold">AI</span>
        )}
      </div>

      {/* 内容 */}
      <div className={`flex-1 min-w-0 ${isUser ? "text-right" : ""}`}>
        <div className="relative inline-block max-w-[90%]">
          {/* AI消息hover复制按钮 */}
          {!isUser && message.content && (
            <button
              onClick={handleCopy}
              className="absolute -top-2 -right-2 z-10 h-6 w-6 rounded-md flex items-center justify-center bg-popover/95 dark:bg-[#14142B]/90 border border-border dark:border-white/[0.12] text-muted-foreground hover:text-foreground hover:bg-foreground/[0.08] dark:hover:bg-white/[0.12] opacity-0 group-hover:opacity-100 transition-all duration-200 shadow-sm"
              aria-label="复制消息"
              title="复制消息"
            >
              {copied ? <Check className="h-3 w-3 text-[#10B981]" /> : <Copy className="h-3 w-3" />}
            </button>
          )}
        <div
          className={`px-4 py-2.5 shadow-sm ${
            isUser
              ? "ui-bubble-user"
              : "ui-bubble-ai"
          }`}
        >
          {isUser ? (
            <span className="whitespace-pre-wrap">{message.content}</span>
          ) : message.content ? (
            <StreamMarkdown content={message.content} />
          ) : message.artifacts && message.artifacts.length > 0 ? (
            <span className="text-muted-foreground text-xs">分析已完成，请查看下方决策卡片</span>
          ) : (
            <span className="text-muted-foreground italic text-xs">（无文本输出）</span>
          )}
        </div>
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
                  className={`text-[10px] gap-1 rounded-md px-2 py-0.5 border cursor-pointer hover:brightness-125 transition-all ${meta.color}`}
                  onClick={() => {
                    // 在右栏artifact面板中查找匹配的artifact卡片并滚动到可视区域
                    // 先按类型精确匹配，遍历所有同类型artifact找到对应的DOM节点
                    const candidates = document.querySelectorAll(`[id^="artifact-${art.artifact_type}-"]`);
                    const target = candidates[0] as HTMLElement | null;
                    if (target) {
                      target.scrollIntoView({ behavior: "smooth", block: "center" });
                      // 闪烁高亮提示用户
                      target.style.outline = "2px solid rgba(55,55,204,0.6)";
                      target.style.outlineOffset = "4px";
                      target.style.borderRadius = "12px";
                      if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
                      highlightTimerRef.current = setTimeout(() => {
                        target.style.outline = "none";
                        target.style.outlineOffset = "0";
                      }, 1500);
                    }
                  }}
                >
                  <Icon className="h-3 w-3" />
                  {art.title}
                </Badge>
              );
            })}
          </div>
        )}

        {/* 数据溯源引用 — 从artifacts动态提取唯一来源 */}
        {!isUser && message.artifacts && message.artifacts.length > 0 && (() => {
          const seen = new Set<string>();
          const uniqueSources: { name: string; type: string }[] = [];
          for (const art of message.artifacts) {
            if (art.sources) {
              for (const src of art.sources) {
                if (!seen.has(src.name)) {
                  seen.add(src.name);
                  uniqueSources.push(src);
                }
              }
            }
          }
          if (uniqueSources.length === 0) return null;
          return (
            <div className="text-[10px] text-muted-foreground mt-1.5">
              数据来源:{" "}
              {uniqueSources.map((src, idx) => (
                <span
                  key={src.name}
                  className="cursor-default hover:text-[#6B5EE4] transition-colors"
                  title={src.type}
                >
                  <span className="text-[#6B5EE4] font-medium">[{idx + 1}]</span>
                  {src.name}
                  {idx < uniqueSources.length - 1 ? " " : ""}
                </span>
              ))}
            </div>
          );
        })()}

        {/* AI消息：重新生成按钮 */}
        {!isUser && (
          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1 mt-1.5">
            <button
              onClick={onRegenerate}
              className="text-[10px] text-muted-foreground hover:text-primary hover:bg-foreground/[0.05] dark:hover:bg-white/[0.06] rounded-md px-1.5 py-0.5 flex items-center gap-1 transition-colors"
            >
              <RefreshCw className="h-2.5 w-2.5" /> 重新生成
            </button>
          </div>
        )}

        {/* 时间戳 */}
        <div className={`text-[10px] text-muted-foreground/70 mt-1 font-mono ${isUser ? "text-right" : ""}`}>
          {new Date(message.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </div>
  );
});
