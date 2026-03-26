// Input: chat-store的messages、isStreaming、streamingContent状态
// Output: 消息列表UI（含流式渲染、Agent进度、加载指示器、新消息提示按钮、50+条虚拟滚动）
// Pos: chat-panel.tsx的子组件，负责消息列表渲染与自动滚动
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useRef, useEffect, useState, useCallback, type CSSProperties, type ReactElement } from "react";
import { List } from "react-window";
import { useChatStore } from "@/lib/stores/chat-store";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./message-bubble";
import { StreamMarkdown } from "./stream-markdown";
import { AgentProgressPanel } from "@/components/agent/agent-progress-panel";
import { Loader2 } from "lucide-react";
import type { ChatMessage } from "@/lib/types";

/** react-window v2 行渲染组件props类型 */
interface VirtualRowProps {
  messages: ChatMessage[];
}

/** react-window v2 行渲染组件 */
function VirtualRow({ index, style, messages }: {
  ariaAttributes: { "aria-posinset": number; "aria-setsize": number; role: "listitem" };
  index: number;
  style: CSSProperties;
} & VirtualRowProps): ReactElement | null {
  const msg = messages[index];
  if (!msg) return null;
  return (
    <div style={style}>
      <MessageBubble message={msg} />
    </div>
  );
}

interface MessageListProps {
  onRegenerate?: (userContent: string) => void;
}

export function MessageList({ onRegenerate }: MessageListProps = {}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [containerHeight, setContainerHeight] = useState(600);
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

  // 测量容器高度用于虚拟滚动
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        setContainerHeight(entry.contentRect.height);
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (isAtBottom) {
      scrollRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streamingContent, isAtBottom]);

  const useVirtualScroll = messages.length > 50;

  return (
    <ScrollArea className="flex-1 p-4 relative" ref={containerRef}>
      <div className="space-y-4" ref={scrollAreaRef} onScroll={handleScroll} role="log" aria-live="polite" aria-label="对话消息">
        {messages.length > 30 && (
          <div className="text-center text-[10px] text-muted-foreground py-1">
            显示最近 {messages.length} 条消息
          </div>
        )}

        {useVirtualScroll ? (
          <List
            rowComponent={VirtualRow}
            rowCount={messages.length}
            rowHeight={80}
            rowProps={{ messages }}
            style={{ height: containerHeight, width: '100%' }}
          />
        ) : (
          messages.map((msg, i) => (
            <div key={msg.message_id} className="animate-[glass-enter_300ms_ease-out_both]" style={{ animationDelay: `${Math.min(i * 30, 300)}ms` }}>
              <MessageBubble
                message={msg}
                onRegenerate={
                  msg.role === "assistant" && onRegenerate
                    ? () => {
                        // 找到该AI消息之前最近的用户消息
                        const prevMsgs = messages.slice(0, i);
                        const lastUserMsg = [...prevMsgs].reverse().find((m) => m.role === "user");
                        if (lastUserMsg) {
                          onRegenerate(lastUserMsg.content);
                        }
                      }
                    : undefined
                }
              />
            </div>
          ))
        )}

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
          <div className="flex items-center gap-2 text-sm animate-[glass-enter_300ms_ease-out_both]">
            <div className="ai-thinking h-5 w-5 rounded-full" />
            <span className="text-muted-foreground">AI正在分析中...</span>
          </div>
        )}

        <div ref={scrollRef} />
      </div>
      {!isAtBottom && messages.length > 0 && (
        <button
          className="absolute bottom-20 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground px-3 py-1.5 rounded-full text-xs shadow-lg z-10 animate-fade-in"
          onClick={() => scrollRef.current?.scrollIntoView({ behavior: "smooth" })}
        >
          ↓ 新消息
        </button>
      )}
    </ScrollArea>
  );
}
