// Input: chat-store的followUpQuestions和isStreaming状态
// Output: 预判性追问建议按钮列表UI
// Pos: chat-panel.tsx的子组件，位于消息列表与输入框之间
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useChatStore } from "@/lib/stores/chat-store";
import { Button } from "@/components/ui/button";
import { MessageSquare } from "lucide-react";

interface Props {
  onSelect: (question: string) => void;
}

export function SuggestedQuestions({ onSelect }: Props) {
  const { followUpQuestions, isStreaming } = useChatStore();

  if (followUpQuestions.length === 0 || isStreaming) return null;

  return (
    <div className="px-3 py-2 border-t bg-muted/20">
      <div className="flex items-center gap-1.5 mb-1.5">
        <MessageSquare className="h-3 w-3 text-muted-foreground" />
        <span className="text-[10px] text-muted-foreground font-medium">继续探索</span>
      </div>
      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {followUpQuestions.map((q, i) => (
          <Button
            key={i}
            variant="outline"
            size="sm"
            className="whitespace-nowrap text-xs h-7 rounded-full border-dashed hover:border-primary/50 hover:bg-primary/5 transition-all"
            onClick={() => onSelect(q)}
          >
            {q}
          </Button>
        ))}
      </div>
    </div>
  );
}
