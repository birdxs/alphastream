// Input: ChatMessage对象（含role、content、artifacts）
// Output: 单条消息气泡UI（区分用户/AI，展示artifact标签）
// Pos: chat-panel.tsx的子组件，负责单条消息渲染
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import type { ChatMessage } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs shrink-0 ${
        isUser ? "bg-blue-500/20 text-blue-600" : "bg-primary/20 text-primary"
      }`}>
        {isUser ? "我" : "AI"}
      </div>
      <div className={`flex-1 ${isUser ? "text-right" : ""}`}>
        <div className={`inline-block text-sm whitespace-pre-wrap rounded-lg px-3 py-2 max-w-[90%] ${
          isUser ? "bg-blue-500/10 text-foreground" : "bg-muted text-foreground"
        }`}>
          {message.content}
        </div>
        {/* Artifact标签 */}
        {message.artifacts && message.artifacts.length > 0 && (
          <div className="flex gap-1 mt-1 flex-wrap">
            {message.artifacts.map((art, i) => (
              <Badge key={i} variant="secondary" className="text-xs">
                {art.title}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
