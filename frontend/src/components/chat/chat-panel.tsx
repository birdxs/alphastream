// Input: chat-store + useChatStream
// Output: 完整Chat面板 — 头部 + 消息/欢迎 + 建议 + 输入，含微妙渐变背景与滚动阴影
// Pos: 首页中栏

"use client";
import { Suspense, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useChatStore } from "@/lib/stores/chat-store";
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { MessageList } from "./message-list";
import { ChatInput } from "./chat-input";
import { SuggestedQuestions } from "./suggested-questions";
import { WelcomeScreen } from "./welcome-screen";

// 模块级guard — 桌面+移动双ChatPanel共享，防止?q=触发两次sendMessage
// key记录已处理的URL查询串，新URL会重置触发
let lastHandledQueryKey: string | null = null;

function ChatPanelInner() {
  const { sendMessage, stopGeneration } = useChatStream();
  const messages = useChatStore(s => s.messages);
  const isStreaming = useChatStore(s => s.isStreaming);
  const searchParams = useSearchParams();
  const prefillHandled = useRef(false);

  const handleSend = (message: string, options: { stock_code?: string; market_type?: string }) => {
    sendMessage(message, options);
  };

  // 处理 URL 查询参数预填充：?q= 直接发送，?prefill= 预填输入框
  useEffect(() => {
    const q = searchParams.get("q");
    const prefill = searchParams.get("prefill");
    const currentKey = q ? `q:${q}` : prefill ? `p:${prefill}` : null;
    if (!currentKey || currentKey === lastHandledQueryKey) return;
    lastHandledQueryKey = currentKey;
    prefillHandled.current = true;
    if (q) {
      setTimeout(() => sendMessage(q, {}), 300);
      window.history.replaceState({}, "", "/");
    } else if (prefill) {
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent("chat-prefill", { detail: prefill }));
      }, 300);
      window.history.replaceState({}, "", "/");
    }
  }, [searchParams, sendMessage]);

  return (
    <div className="flex flex-col h-full min-h-0 border-l-2 border-[#3737CC]/20 bg-gradient-to-b from-foreground/[0.02] dark:from-white/[0.02] to-transparent">
      {/* Header */}
      <div className="relative z-20 flex items-center justify-between px-3 min-h-[40px] border-b border-border/60 dark:border-white/[0.08] bg-background dark:bg-[#0A0A1A] shrink-0">
        <div className="flex items-center gap-2">
          <div className="relative w-1.5 h-1.5 group/indicator cursor-default">
            <div className="absolute inset-0 rounded-full bg-[#3737CC] animate-ping opacity-75" />
            <div className="relative w-1.5 h-1.5 rounded-full bg-[#3737CC]" />
            <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2 px-2 py-1 rounded-md bg-popover dark:bg-[#1a1a2e] border border-border dark:border-white/[0.1] text-[10px] text-[#46BEA3] whitespace-nowrap opacity-0 group-hover/indicator:opacity-100 transition-opacity duration-200 pointer-events-none z-50 shadow-lg">
              AI服务在线
            </div>
          </div>
          <span className="text-xs font-medium text-foreground/80">AI分析助手</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto scroll-shadow-top">
        {messages.length === 0 && !isStreaming ? (
          <WelcomeScreen onQuestionSelect={handleSend} />
        ) : (
          <MessageList onRegenerate={(content) => handleSend(content, {})} />
        )}
      </div>

      {/* Follow-ups */}
      <SuggestedQuestions onSelect={(q) => handleSend(q, {})} />

      {/* Input */}
      <ChatInput onSend={handleSend} onStop={stopGeneration} />
    </div>
  );
}

export function ChatPanel() {
  return (
    <Suspense fallback={
      <div className="flex flex-col h-full min-h-0 border-l-2 border-[#3737CC]/20">
        <div className="flex items-center px-3 h-10 border-b border-border/60 dark:border-white/[0.08] bg-card/80 dark:bg-[rgba(10,10,26,0.6)] backdrop-blur-sm shrink-0">
          <span className="text-xs text-foreground/40">加载中...</span>
        </div>
      </div>
    }>
      <ChatPanelInner />
    </Suspense>
  );
}
