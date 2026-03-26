// Input: 用户输入文本 + 选择回调 + 可见性标志
// Output: 快捷命令提示面板（/开头触发，展示可用命令列表，支持键盘导航）
// Pos: chat-panel.tsx输入框上方的浮层组件
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect } from "react";

interface Props {
  input: string;
  onSelect: (command: string) => void;
  visible: boolean;
}

const COMMANDS = [
  { trigger: "/分析", description: "深度分析股票", example: "/分析 600519" },
  { trigger: "/对比", description: "对比两只股票", example: "/对比 600519 000858" },
  { trigger: "/行业", description: "分析行业趋势", example: "/行业 白酒" },
  { trigger: "/风险", description: "风险评估", example: "/风险 600519" },
  { trigger: "/资金", description: "资金流向分析", example: "/资金 600519" },
  { trigger: "/新闻", description: "最新新闻", example: "/新闻 600519" },
];

export function CommandPalette({ input, onSelect, visible }: Props) {
  const [activeIndex, setActiveIndex] = useState(0);

  const filtered = visible && input.startsWith("/")
    ? COMMANDS.filter((c) => c.trigger.includes(input) || input === "/")
    : [];

  // 输入变化时重置高亮索引
  useEffect(() => {
    setActiveIndex(0);
  }, [input]);

  // P0-3: 键盘导航
  useEffect(() => {
    if (!visible || filtered.length === 0) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((prev) => Math.min(prev + 1, filtered.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === 'Enter' && filtered[activeIndex]) {
        e.preventDefault();
        onSelect(filtered[activeIndex].example);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [visible, filtered, activeIndex, onSelect]);

  if (!visible || !input.startsWith("/") || filtered.length === 0) return null;

  return (
    <div className="absolute bottom-full left-0 right-0 mb-1 bg-[#0F0F23] border border-white/[0.1] rounded-xl shadow-2xl p-1 z-50">
      {filtered.map((cmd, i) => (
        <button
          key={cmd.trigger}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm flex justify-between items-center transition-colors ${
            i === activeIndex ? 'bg-[#3737CC]/15 border-l-2 border-[#3737CC]' : 'hover:bg-white/[0.06]'
          }`}
          onClick={() => onSelect(cmd.example)}
        >
          <span>
            <span className="font-mono text-primary">{cmd.trigger}</span>
            <span className="ml-2 text-[#8888A0]">
              {cmd.description}
            </span>
          </span>
          <span className="text-xs text-[#8888A0]">{cmd.example}</span>
        </button>
      ))}
    </div>
  );
}
