/**
 * Input: 工具调用事件(ToolCallStart + 可选ToolCallResult)
 * Output: glass-card风格的工具调用详情卡片（时间线节点内容：名称、耗时、状态圆点、可展开参数/结果）
 * Pos: tool-call-timeline.tsx子组件，展示单次工具调用的完整信息
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

"use client";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { ToolCallStart, ToolCallResult } from "@/lib/types";

interface Props {
  toolCall: ToolCallStart & { result?: ToolCallResult };
}

const TOOL_ICONS: Record<string, string> = {
  get_stock_data: "\u{1F4CA}",
  get_technical_indicators: "\u{1F4C8}",
  get_fundamental_data: "\u{1F4B0}",
  get_capital_flow: "\u{1F4B9}",
  get_stock_news: "\u{1F4F0}",
  search_web: "\u{1F50D}",
  get_risk_assessment: "\u26A0\uFE0F",
};

const TOOL_NAMES: Record<string, string> = {
  get_stock_data: "\u83B7\u53D6K\u7EBF\u6570\u636E",
  get_technical_indicators: "\u8BA1\u7B97\u6280\u672F\u6307\u6807",
  get_fundamental_data: "\u83B7\u53D6\u57FA\u672C\u9762\u6570\u636E",
  get_capital_flow: "\u83B7\u53D6\u8D44\u91D1\u6D41\u5411",
  get_stock_news: "\u83B7\u53D6\u65B0\u95FB",
  search_web: "\u641C\u7D22\u7F51\u7EDC",
  get_risk_assessment: "\u8BC4\u4F30\u98CE\u9669",
};

function formatDuration(ms: number | undefined): string {
  if (!ms) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function ToolCallCard({ toolCall }: Props) {
  const [expanded, setExpanded] = useState(false);
  // P0-4：契约字段 name/args_digest/ok/error/duration_ms/source（兼容旧 tool_name/arguments/result）
  const toolKey = toolCall.name || toolCall.tool_name || "unknown";
  const icon = TOOL_ICONS[toolKey] || "\u{1F527}";
  const name = TOOL_NAMES[toolKey] || toolKey;
  const hasResult = !!toolCall.result || toolCall.status === "done" || toolCall.status === "error";
  const summary =
    toolCall.result?.result_summary ||
    toolCall.result?.result ||
    toolCall.result?.error ||
    "";
  const isError =
    toolCall.result?.ok === false ||
    !!toolCall.result?.error ||
    toolCall.status === "error" ||
    (hasResult && /error|\u5931\u8D25|\u5F02\u5E38|\u9519\u8BEF/i.test(summary));

  // 状态圆点颜色
  const dotColor = !hasResult
    ? "bg-[#3737CC] animate-[pulse_1.2s_ease-in-out_infinite]"
    : isError
      ? "bg-[#FF8767]"
      : "bg-[#46BEA3]";

  // 状态标签
  const statusLabel = !hasResult
    ? "\u6267\u884C\u4E2D..."
    : isError
      ? "\u5931\u8D25"
      : "\u5B8C\u6210";

  const statusColor = !hasResult
    ? "text-[#3737CC]"
    : isError
      ? "text-[#FF8767]"
      : "text-[#46BEA3]";

  const sourceLabel = toolCall.source || toolCall.agent || toolCall.result?.source;

  return (
    <div
      className={`
        backdrop-blur-md bg-foreground/[0.04] dark:bg-white/[0.04] border border-foreground/[0.08] dark:border-white/[0.08]
        rounded-lg p-2.5 text-xs cursor-pointer
        transition-all duration-200
        hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08] hover:border-foreground/[0.15] dark:hover:border-white/[0.15]
        ${!hasResult ? "shadow-[0_0_8px_rgba(55,55,204,0.15)]" : ""}
      `}
      onClick={() => setExpanded(!expanded)}
    >
      {/* 主行：状态圆点 | 工具名称 | 耗时 | 状态 */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
          <span className="shrink-0">{icon}</span>
          <span className="font-medium truncate">{name}</span>
          {toolCall.args_digest && (
            <span className="font-mono text-[10px] text-muted-foreground shrink-0">
              {toolCall.args_digest}
            </span>
          )}
          {sourceLabel && (
            <Badge variant="outline" className="text-[10px] shrink-0 border-white/10">
              {sourceLabel}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {hasResult && toolCall.result?.duration_ms != null && (
            <span className="font-mono text-muted-foreground tabular-nums">
              {formatDuration(toolCall.result.duration_ms)}
            </span>
          )}
          <span className={`font-medium ${statusColor}`}>{statusLabel}</span>
          {hasResult && (
            expanded
              ? <ChevronDown className="h-3 w-3 text-muted-foreground" />
              : <ChevronRight className="h-3 w-3 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* 执行中骨架 */}
      {!hasResult && (
        <div className="mt-2 space-y-1.5">
          <div className="h-2.5 w-3/4 bg-foreground/[0.06] dark:bg-white/[0.06] rounded animate-pulse" />
          <div className="h-2.5 w-1/2 bg-foreground/[0.04] dark:bg-white/[0.04] rounded animate-pulse" />
        </div>
      )}

      {/* 展开详情：glass-card背景 + 代码块样式 */}
      {expanded && hasResult && (
        <div className="mt-2 space-y-2 border-t border-foreground/[0.08] dark:border-white/[0.08] pt-2">
          <div className="backdrop-blur-sm bg-foreground/[0.03] dark:bg-white/[0.03] rounded-lg p-2 border border-foreground/[0.06] dark:border-white/[0.06]">
            <span className="text-[10px] text-muted-foreground block mb-1">{"\u53C2\u6570"}</span>
            <pre className="bg-foreground/[0.03] dark:bg-white/[0.03] rounded px-2 py-1.5 font-mono text-[10px] text-foreground/80 overflow-x-auto whitespace-pre-wrap break-all">
              {toolCall.args_digest
                ? `args_digest: ${toolCall.args_digest}\n${
                    toolCall.arguments ? JSON.stringify(toolCall.arguments, null, 2) : ""
                  }`.trim()
                : JSON.stringify(toolCall.arguments ?? {}, null, 2)}
            </pre>
          </div>
          {(summary || toolCall.result?.error) && (
            <div className="backdrop-blur-sm bg-foreground/[0.03] dark:bg-white/[0.03] rounded-lg p-2 border border-foreground/[0.06] dark:border-white/[0.06]">
              <span className="text-[10px] text-muted-foreground block mb-1">
                {isError ? "\u9519\u8BEF" : "\u7ED3\u679C"}
              </span>
              <pre className="bg-foreground/[0.03] dark:bg-white/[0.03] rounded px-2 py-1.5 font-mono text-[10px] text-foreground/80 overflow-x-auto whitespace-pre-wrap break-all">
                {toolCall.result?.error || summary}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
