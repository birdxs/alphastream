// Input: 用户点击快速开始问题
// Output: 欢迎屏幕UI（含快速开始问题列表、使用提示）
// Pos: chat-panel.tsx的子组件，消息为空时显示
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Bot } from "lucide-react";

interface Props {
  onQuestionSelect: (message: string, options: { stock_code?: string }) => void;
}

const QUICK_START = [
  { icon: "\u{1F4C8}", text: "分析600519贵州茅台", desc: "技术面+基本面综合分析", stock: "600519" },
  { icon: "\u{1F50D}", text: "对比银行板块龙头", desc: "行业对比分析", stock: "" },
  { icon: "\u{1F4CA}", text: "今日大盘走势如何", desc: "市场概览", stock: "" },
  { icon: "\u26A0\uFE0F", text: "600519有哪些风险", desc: "全面风险评估", stock: "600519" },
  { icon: "\u{1F4B0}", text: "分析000858五粮液基本面", desc: "财务健康+估值分析", stock: "000858" },
  { icon: "\u{1F4B9}", text: "查看600519资金流向", desc: "主力资金动向", stock: "600519" },
];

export function WelcomeScreen({ onQuestionSelect }: Props) {
  return (
    <div className="flex-1 flex items-center justify-center p-6 overflow-y-auto">
      <div className="text-center space-y-8 max-w-md animate-fade-in">
        <div>
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-500/20">
            <Bot className="h-8 w-8 text-white" />
          </div>
          <h3 className="font-bold text-xl mb-1">AI金融分析助手</h3>
          <p className="text-sm text-muted-foreground">
            13个AI Agent协作 · 实时数据分析 · 投资大师视角
          </p>
        </div>

        <div className="grid grid-cols-1 gap-2 text-left">
          {QUICK_START.map((q) => (
            <button
              key={q.text}
              onClick={() => onQuestionSelect(q.text, { stock_code: q.stock })}
              className="flex items-center gap-3 p-3 rounded-xl border border-border/50 hover:border-primary/30 hover:bg-primary/5 transition-all group"
            >
              <span className="text-xl group-hover:scale-110 transition-transform">{q.icon}</span>
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{q.text}</p>
                <p className="text-xs text-muted-foreground">{q.desc}</p>
              </div>
            </button>
          ))}
        </div>

        <div className="mt-6 pt-4 border-t">
          <p className="text-xs text-muted-foreground mb-2 text-center">📰 热门分析</p>
          <div className="flex gap-2 justify-center">
            {["沪深300走势", "北向资金动向", "热门板块轮动"].map(topic => (
              <button
                key={topic}
                onClick={() => onQuestionSelect(topic, {})}
                className="text-[10px] px-2.5 py-1 rounded-full bg-muted/50 hover:bg-muted text-muted-foreground transition-colors"
              >
                {topic}
              </button>
            ))}
          </div>
        </div>

        <p className="text-[10px] text-muted-foreground">
          输入 <kbd className="px-1 py-0.5 rounded bg-muted text-[10px]">/</kbd> 查看快捷命令 · <kbd className="px-1 py-0.5 rounded bg-muted text-[10px]">Enter</kbd> 发送 · <kbd className="px-1 py-0.5 rounded bg-muted text-[10px]">Shift+Enter</kbd> 换行
        </p>
      </div>
    </div>
  );
}
