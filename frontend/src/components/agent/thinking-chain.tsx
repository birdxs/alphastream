// Input: content(思考内容文本), agent?(Agent名称)
// Output: 可折叠的AI思考过程展示面板
// Pos: components/agent/thinking-chain.tsx - 思考链展示组件，用于透明化AI推理
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight, Brain } from "lucide-react";

interface Props {
  content: string;
  agent?: string;
}

export function ThinkingChain({ content, agent }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border rounded-lg overflow-hidden text-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-muted/50 hover:bg-muted transition-colors"
      >
        <Brain className="h-3 w-3 text-purple-500" />
        <span className="text-muted-foreground">
          {agent ? `${agent} 思考过程` : 'AI思考过程'}
        </span>
        {expanded ? <ChevronDown className="h-3 w-3 ml-auto" /> : <ChevronRight className="h-3 w-3 ml-auto" />}
      </button>
      {expanded && (
        <div className="px-3 py-2 text-muted-foreground whitespace-pre-wrap animate-fade-in">
          {content}
        </div>
      )}
    </div>
  );
}
