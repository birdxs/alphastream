// Input: 用户输入文本 + 选择回调 + 可见性标志
// Output: 快捷命令提示面板（/开头触发，展示可用命令列表）
// Pos: chat-panel.tsx输入框上方的浮层组件
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

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
  if (!visible || !input.startsWith("/")) return null;

  const filtered = COMMANDS.filter(
    (c) => c.trigger.includes(input) || input === "/"
  );

  if (filtered.length === 0) return null;

  return (
    <div className="absolute bottom-full left-0 right-0 mb-1 bg-popover border rounded-lg shadow-lg p-1 z-50">
      {filtered.map((cmd) => (
        <button
          key={cmd.trigger}
          className="w-full text-left px-3 py-2 rounded hover:bg-accent text-sm flex justify-between items-center"
          onClick={() => onSelect(cmd.example)}
        >
          <span>
            <span className="font-mono text-primary">{cmd.trigger}</span>
            <span className="ml-2 text-muted-foreground">
              {cmd.description}
            </span>
          </span>
          <span className="text-xs text-muted-foreground">{cmd.example}</span>
        </button>
      ))}
    </div>
  );
}
