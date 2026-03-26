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

function getQuestionCategory(q: string): { icon: string; category: string } {
  if (q.includes('估值') || q.includes('基本面') || q.includes('财务')) return { icon: '💰', category: '深入' };
  if (q.includes('对比') || q.includes('行业')) return { icon: '🔍', category: '对比' };
  if (q.includes('风险') || q.includes('止损')) return { icon: '⚠️', category: '风险' };
  if (q.includes('资金') || q.includes('主力')) return { icon: '💹', category: '资金' };
  if (q.includes('重试')) return { icon: '🔄', category: '重试' };
  return { icon: '💡', category: '相关' };
}

export function SuggestedQuestions({ onSelect }: Props) {
  const followUpQuestions = useChatStore(s => s.followUpQuestions);
  const isStreaming = useChatStore(s => s.isStreaming);

  if (followUpQuestions.length === 0 || isStreaming) return null;

  return (
    <div className="px-3 py-2 border-t border-white/[0.08] bg-white/[0.02]">
      <div className="flex items-center gap-1.5 mb-1.5">
        <MessageSquare className="h-3 w-3 text-[#3737CC]" />
        <span className="text-[10px] text-muted-foreground font-medium">继续探索</span>
      </div>
      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {followUpQuestions.map((q, i) => {
          const { icon } = getQuestionCategory(q);
          return (
            <Button
              key={i}
              variant="outline"
              size="sm"
              style={{ animationDelay: `${i * 60}ms` }}
              className="whitespace-nowrap text-xs h-7 bg-white/[0.04] border border-white/[0.08] rounded-full hover:border-[#3737CC]/30 hover:bg-white/[0.06] transition-all animate-fade-in opacity-0 [animation-fill-mode:forwards]"
              onClick={() => onSelect(q)}
            >
              <span className="mr-1">{icon}</span>
              {q}
            </Button>
          );
        })}
      </div>
    </div>
  );
}
