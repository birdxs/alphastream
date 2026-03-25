// Input: ChatMessage对象（含role、content、artifacts、created_at）
// Output: 单条消息气泡UI（渐变头像、圆角气泡、artifact标签、时间戳）
// Pos: message-list.tsx的子组件，负责单条消息渲染
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import type { ChatMessage } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { StreamMarkdown } from "./stream-markdown";

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 message-enter ${isUser ? "flex-row-reverse" : ""}`}>
      {/* 头像 */}
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${
        isUser
          ? "bg-gradient-to-br from-cyan-500 to-blue-600 text-white"
          : "bg-gradient-to-br from-blue-500 to-purple-600 text-white"
      }`}>
        {isUser ? "我" : "AI"}
      </div>

      {/* 内容 */}
      <div className={`flex-1 min-w-0 ${isUser ? "text-right" : ""}`}>
        <div className={`inline-block text-sm rounded-2xl px-4 py-2.5 max-w-[90%] ${
          isUser
            ? "bg-primary text-primary-foreground rounded-br-md"
            : "bg-muted/60 border border-border/40 rounded-bl-md"
        }`}>
          {isUser ? (
            <span className="whitespace-pre-wrap">{message.content}</span>
          ) : (
            <StreamMarkdown content={message.content} />
          )}
        </div>

        {/* Artifact标签 */}
        {message.artifacts && message.artifacts.length > 0 && (
          <div className={`flex gap-1 mt-1.5 flex-wrap ${isUser ? 'justify-end' : ''}`}>
            {message.artifacts.map((art, i) => (
              <Badge key={i} variant="secondary" className="text-[10px] gap-1 rounded-full">
                {"\u{1F4CA}"} {art.title}
              </Badge>
            ))}
          </div>
        )}

        {/* 时间戳 */}
        <div className={`text-[10px] text-muted-foreground/50 mt-1 ${isUser ? 'text-right' : ''}`}>
          {new Date(message.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  );
}
