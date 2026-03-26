// Input: chat-store + useChatStream
// Output: 完整Chat面板 — 头部 + 消息/欢迎 + 建议 + 输入
// Pos: 首页中栏

"use client";
import { useChatStore } from "@/lib/stores/chat-store";
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { MessageList } from "./message-list";
import { ChatInput } from "./chat-input";
import { SuggestedQuestions } from "./suggested-questions";
import { WelcomeScreen } from "./welcome-screen";

export function ChatPanel() {
  const { sendMessage, stopGeneration } = useChatStream();
  const messages = useChatStore(s => s.messages);
  const isStreaming = useChatStore(s => s.isStreaming);

  const handleSend = (message: string, options: { stock_code?: string; market_type?: string }) => {
    sendMessage(message, options);
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-10 border-b border-white/[0.08] bg-[rgba(10,10,26,0.6)] backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-2">
          <div className="relative w-1.5 h-1.5">
            <div className="absolute inset-0 rounded-full bg-[#3737CC] animate-ping opacity-75" />
            <div className="relative w-1.5 h-1.5 rounded-full bg-[#3737CC]" />
          </div>
          <span className="text-xs font-medium text-foreground/80">AI分析助手</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {messages.length === 0 && !isStreaming ? (
          <WelcomeScreen onQuestionSelect={handleSend} />
        ) : (
          <MessageList />
        )}
      </div>

      {/* Follow-ups */}
      <SuggestedQuestions onSelect={(q) => handleSend(q, {})} />

      {/* Input */}
      <ChatInput onSend={handleSend} onStop={stopGeneration} />
    </div>
  );
}
