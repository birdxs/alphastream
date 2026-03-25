// Input: chat-store的messages、isStreaming、streamingContent状态
// Output: 消息列表UI（含流式渲染、Agent进度、加载指示器）
// Pos: chat-panel.tsx的子组件，负责消息列表渲染与自动滚动
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useRef, useEffect } from "react";
import { useChatStore } from "@/lib/stores/chat-store";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./message-bubble";
import { StreamMarkdown } from "./stream-markdown";
import { AgentProgressPanel } from "@/components/agent/agent-progress-panel";
import { Loader2 } from "lucide-react";

export function MessageList() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { messages, isStreaming, streamingContent } = useChatStore();

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  return (
    <ScrollArea className="flex-1 p-4">
      <div className="space-y-4">
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
    </ScrollArea>
  );
}
