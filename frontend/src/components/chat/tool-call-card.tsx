// Input: ToolCallSegment (含 name, args, partial)
// Output: 折叠卡片 UI - 工具名 chip + 参数 JSON + 状态
// Pos: frontend/src/components/chat/tool-call-card.tsx - FIX-9 mimo tool_call 模板化渲染

// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Wrench, Loader2 } from "lucide-react";
import type { ToolCallSegment } from "@/lib/parsers/tool-call-parser";

interface Props {
  segment: ToolCallSegment;
}

export function ToolCallCard({ segment }: Props) {
  const [open, setOpen] = useState(false);

  const argsText =
    typeof segment.args === "string"
      ? segment.args
      : JSON.stringify(segment.args, null, 2);

  return (
    <div
      className="my-2 rounded-md border border-slate-200/60 bg-slate-50/70
                 dark:border-slate-700/60 dark:bg-slate-800/40
                 text-xs font-mono overflow-hidden"
      data-testid="tool-call-card"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-slate-100/70
                   dark:hover:bg-slate-700/60 transition-colors text-left"
      >
        {open ? (
          <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
        )}
        {segment.partial ? (
          <Loader2 className="w-3.5 h-3.5 text-amber-500 animate-spin" />
        ) : (
          <Wrench className="w-3.5 h-3.5 text-emerald-600" />
        )}
        <span className="font-semibold text-slate-700 dark:text-slate-200">
          {segment.name}
        </span>
        <span className="text-slate-400 dark:text-slate-500">
          {segment.partial ? "调用中…" : "工具调用"}
        </span>
      </button>
      {open && (
        <pre
          className="px-3 py-2 border-t border-slate-200/60 dark:border-slate-700/60
                     text-[11px] text-slate-600 dark:text-slate-300
                     whitespace-pre-wrap break-all max-h-72 overflow-auto"
        >
          {argsText}
        </pre>
      )}
    </div>
  );
}
