// Input: onQuestionSelect回调
// Output: 紧凑欢迎引导
// Pos: ChatPanel子组件，无消息时显示

"use client";
import { Bot } from "lucide-react";

interface Props {
  onQuestionSelect: (message: string, options: { stock_code?: string }) => void;
}

const QUICK_START = [
  { text: "分析600519贵州茅台", desc: "综合分析", stock: "600519" },
  { text: "对比银行板块龙头", desc: "行业对比", stock: "" },
  { text: "今日大盘走势", desc: "市场概览", stock: "" },
  { text: "600519风险评估", desc: "风险分析", stock: "600519" },
];

export function WelcomeScreen({ onQuestionSelect }: Props) {
  return (
    <div className="flex items-center justify-center h-full p-4">
      <div className="text-center space-y-4 max-w-xs animate-fade-in">
        <div className="flex justify-center">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <Bot className="h-5 w-5 text-primary" />
          </div>
        </div>
        <div>
          <h3 className="text-sm font-semibold">AI金融分析助手</h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">13个Agent · 实时数据 · 大师视角</p>
        </div>
        <div className="space-y-1.5 text-left">
          {QUICK_START.map((q) => (
            <button
              key={q.text}
              onClick={() => onQuestionSelect(q.text, { stock_code: q.stock })}
              className="w-full flex items-center justify-between p-2 rounded-md border border-border/40 hover:border-primary/30 hover:bg-muted/30 transition-all"
            >
              <span className="text-xs">{q.text}</span>
              <span className="text-[10px] text-muted-foreground ml-2">{q.desc}</span>
            </button>
          ))}
        </div>
        <div className="flex gap-1.5 justify-center flex-wrap">
          {["沪深300走势", "北向资金", "板块轮动"].map(topic => (
            <button
              key={topic}
              onClick={() => onQuestionSelect(topic, {})}
              className="text-[10px] px-2 py-0.5 rounded-full bg-muted/40 hover:bg-muted text-muted-foreground transition-colors"
            >
              {topic}
            </button>
          ))}
        </div>
        <p className="text-[9px] text-muted-foreground/60">
          <kbd className="px-0.5 rounded bg-muted/60">/</kbd> 命令 · <kbd className="px-0.5 rounded bg-muted/60">⌘K</kbd> 搜索 · <kbd className="px-0.5 rounded bg-muted/60">Enter</kbd> 发送
        </p>
      </div>
    </div>
  );
}
