// Input: chat-store的messages、isStreaming、streamingContent状态
// Output: 消息列表UI（含流式渲染、Agent进度、加载指示器、新消息提示按钮）
// Pos: chat-panel.tsx的子组件，负责消息列表渲染与自动滚动
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useRef, useEffect, useState, useCallback } from "react";
import { useChatStore } from "@/lib/stores/chat-store";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./message-bubble";
import { StreamMarkdown } from "./stream-markdown";
import { AgentProgressPanel } from "@/components/agent/agent-progress-panel";
import { Loader2 } from "lucide-react";

export function MessageList() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const messages = useChatStore(s => s.messages);
  const isStreaming = useChatStore(s => s.isStreaming);
  const streamingContent = useChatStore(s => s.streamingContent);

  const handleScroll = useCallback(() => {
    const el = scrollAreaRef.current;
    if (el) {
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
      setIsAtBottom(atBottom);
    }
  }, []);

  useEffect(() => {
    if (isAtBottom) {
      scrollRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streamingContent, isAtBottom]);

  return (
    <ScrollArea className="flex-1 p-4">
      <div className="space-y-4" ref={scrollAreaRef} onScroll={handleScroll} role="log" aria-live="polite" aria-label="对话消息">
        {messages.length > 30 && (
          <div className="text-center text-[10px] text-muted-foreground py-1">
            显示最近 {messages.length} 条消息
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.message_id} message={msg} />
        ))}

        {isStreaming && streamingContent && (
          <div className="flex gap-3 animate-fade-in">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-[10px] text-white font-bold shrink-0">
              AI
            </div>
            <div className="flex-1 min-w-0">
              <StreamMarkdown content={streamingContent} isStreaming={true} />
            </div>
          </div>
        )}

        {isStreaming && <AgentProgressPanel />}

        {isStreaming && !streamingContent && (
          <div className="flex items-center gap-2 text-muted-foreground text-sm animate-pulse-gentle">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>AI正在分析中...</span>
          </div>
        )}

        <div ref={scrollRef} />
      </div>
      {!isAtBottom && messages.length > 0 && (
        <button
          className="fixed bottom-20 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground px-3 py-1.5 rounded-full text-xs shadow-lg z-10 animate-fade-in"
          onClick={() => scrollRef.current?.scrollIntoView({ behavior: "smooth" })}
        >
          ↓ 新消息
        </button>
      )}
    </ScrollArea>
  );
}
