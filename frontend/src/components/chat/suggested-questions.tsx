// Input: chat-store的followUpQuestions和isStreaming状态
// Output: 预判性追问建议按钮列表UI（含智能分类图标+颜色）
// Pos: chat-panel.tsx的子组件，位于消息列表与输入框之间
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useChatStore } from "@/lib/stores/chat-store";
import { Button } from "@/components/ui/button";
import { MessageSquare, Search, Scale, AlertTriangle, Wallet, MessageCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface Props {
  onSelect: (question: string) => void;
}

interface QuestionCategory {
  Icon: LucideIcon;
  label: string;
  color: string;       // 文字/图标颜色
  borderColor: string;  // hover边框颜色
  bgColor: string;      // 图标背景色
}

function getQuestionCategory(q: string): QuestionCategory {
  if (/深入|详细|分析/.test(q))
    return { Icon: Search, label: "深入分析", color: "#3737CC", borderColor: "rgba(55,55,204,0.3)", bgColor: "rgba(55,55,204,0.12)" };
  if (/对比|比较/.test(q))
    return { Icon: Scale, label: "对比", color: "#46BEA3", borderColor: "rgba(70,190,163,0.3)", bgColor: "rgba(70,190,163,0.12)" };
  if (/风险|预警|止损/.test(q))
    return { Icon: AlertTriangle, label: "风险", color: "#FF8767", borderColor: "rgba(255,135,103,0.3)", bgColor: "rgba(255,135,103,0.12)" };
  if (/资金|流向|主力/.test(q))
    return { Icon: Wallet, label: "资金", color: "#6B5EE4", borderColor: "rgba(107,94,228,0.3)", bgColor: "rgba(107,94,228,0.12)" };
  return { Icon: MessageCircle, label: "相关", color: "#8888A0", borderColor: "rgba(136,136,160,0.3)", bgColor: "rgba(136,136,160,0.12)" };
}

export function SuggestedQuestions({ onSelect }: Props) {
  const followUpQuestions = useChatStore(s => s.followUpQuestions);
  const isStreaming = useChatStore(s => s.isStreaming);

  if (followUpQuestions.length === 0 || isStreaming) return null;

  return (
    <div className="px-3 py-2 border-t border-foreground/[0.08] dark:border-white/[0.08] bg-foreground/[0.02] dark:bg-white/[0.02]">
      <div className="flex items-center gap-1.5 mb-1.5">
        <MessageSquare className="h-3 w-3 text-[#3737CC]" />
        <span className="text-[10px] text-muted-foreground font-medium">继续探索</span>
      </div>
      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {followUpQuestions.map((q, i) => {
          const { Icon, label, color, borderColor, bgColor } = getQuestionCategory(q);
          return (
            <Button
              key={i}
              variant="outline"
              size="sm"
              style={{ animationDelay: `${i * 60}ms`, ['--cat-color' as string]: color }}
              className="whitespace-nowrap text-xs h-7 bg-foreground/[0.04] dark:bg-white/[0.04] border border-foreground/[0.08] dark:border-white/[0.08] rounded-full hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] hover:-translate-x-0.5 transition-all duration-200 animate-[glass-enter_300ms_ease-out_both] opacity-0 [animation-fill-mode:forwards]"
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = borderColor; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = ''; }}
              onClick={() => onSelect(q)}
            >
              <span
                className="inline-flex items-center justify-center h-4 w-4 rounded-full mr-1 shrink-0"
                style={{ backgroundColor: bgColor }}
              >
                <Icon className="h-2.5 w-2.5" style={{ color }} />
              </span>
              <span className="text-[10px] font-medium mr-1" style={{ color }}>{label}</span>
              <span className="text-white/70">{q}</span>
            </Button>
          );
        })}
      </div>
    </div>
  );
}
