// Input: chat-store的messages、isStreaming、streamingContent状态
// Output: 消息列表UI（含流式渲染、Agent进度、加载指示器、毛玻璃新消息按钮、50+条虚拟滚动(rowHeight=120)）
// Pos: chat-panel.tsx的子组件，负责消息列表渲染与自动滚动
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useRef, useEffect, useState, useCallback, type CSSProperties, type ReactElement } from "react";
import { List } from "react-window";
import { useChatStore } from "@/lib/stores/chat-store";
import { MessageBubble } from "./message-bubble";
import { StreamMarkdown } from "./stream-markdown";
import { AgentProgressPanel } from "@/components/agent/agent-progress-panel";
import { ArrowDown } from "lucide-react";
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
  /** 唯一滚动容器：原生 overflow，避免 ScrollArea 根节点非滚动导致 isAtBottom 失效与双滚动条 */
  const containerRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [containerHeight, setContainerHeight] = useState(600);
  const messages = useChatStore(s => s.messages);
  const isStreaming = useChatStore(s => s.isStreaming);
  const streamingContent = useChatStore(s => s.streamingContent);

  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    setIsAtBottom(atBottom);
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
    setContainerHeight(el.clientHeight);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (isAtBottom) {
      scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages, streamingContent, isStreaming, isAtBottom]);

  const scrollToBottom = () => {
    const el = containerRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    } else {
      scrollRef.current?.scrollIntoView({ behavior: "smooth" });
    }
    setIsAtBottom(true);
  };

  const useVirtualScroll = messages.length > 50;
  // 等待态：流已启动但正文未到（进度面板可并行）
  const showWaitingStatus = isStreaming && !streamingContent;

  return (
    <div
      ref={containerRef}
      className="flex-1 min-h-0 overflow-y-auto overscroll-contain p-4 relative"
      onScroll={handleScroll}
      role="log"
      aria-live="polite"
      aria-label="对话消息"
    >
      <div className="space-y-4">
        {messages.length > 30 && (
          <div className="text-center text-[10px] text-muted-foreground py-1">
            显示最近 {messages.length} 条消息
          </div>
        )}

        {useVirtualScroll ? (
          <List
            rowComponent={VirtualRow}
            rowCount={messages.length}
            rowHeight={120}
            rowProps={{ messages }}
            style={{ height: containerHeight, width: "100%" }}
          />
        ) : (
          messages.map((msg, i) => (
            <div
              key={msg.message_id}
              className="animate-[glass-enter_300ms_ease-out_both]"
              style={{ animationDelay: `${Math.min(i * 30, 300)}ms` }}
            >
              <MessageBubble
                message={msg}
                onRegenerate={
                  msg.role === "assistant" && onRegenerate
                    ? () => {
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

        {showWaitingStatus && (
          <div
            className="flex items-center gap-2 text-sm animate-[glass-enter_300ms_ease-out_both]"
            role="status"
            aria-live="polite"
            data-testid="chat-waiting-status"
          >
            <div className="ai-thinking h-5 w-5 rounded-full" />
            <span className="bg-gradient-to-r from-[#3737CC] to-[#46BEA3] bg-clip-text text-transparent font-medium">
              AI 正在分析中，请稍候
              <span className="inline-flex ml-0.5">
                <span className="inline-block w-1 h-1 rounded-full bg-[#3737CC] animate-[ai-dot-bounce_1.2s_ease-in-out_infinite]" />
                <span className="inline-block w-1 h-1 rounded-full bg-[#4F4FE6] ml-0.5 animate-[ai-dot-bounce_1.2s_ease-in-out_0.2s_infinite]" />
                <span className="inline-block w-1 h-1 rounded-full bg-[#46BEA3] ml-0.5 animate-[ai-dot-bounce_1.2s_ease-in-out_0.4s_infinite]" />
              </span>
            </span>
          </div>
        )}

        <div ref={scrollRef} />
      </div>
      {!isAtBottom && messages.length > 0 && (
        <button
          type="button"
          className="sticky bottom-4 left-1/2 -translate-x-1/2 mx-auto bg-[#3737CC]/80 backdrop-blur-sm text-white px-3 py-1.5 rounded-full text-xs shadow-lg z-10 animate-fade-in flex items-center gap-1"
          onClick={scrollToBottom}
          aria-label="滚动到最新消息"
        >
          <ArrowDown className="h-3 w-3" />
          新消息
        </button>
      )}
    </div>
  );
}
