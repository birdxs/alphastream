/**
 * Input: 工具调用事件(ToolCallStart + 可选ToolCallResult)
 * Output: glass-card风格的工具调用详情卡片（时间线节点内容：名称、耗时、状态、可展开参数/结果）
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
  get_stock_data: "📊",
  get_technical_indicators: "📈",
  get_fundamental_data: "💰",
  get_capital_flow: "💹",
  get_stock_news: "📰",
  search_web: "🔍",
  get_risk_assessment: "⚠️",
};

const TOOL_NAMES: Record<string, string> = {
  get_stock_data: "获取K线数据",
  get_technical_indicators: "计算技术指标",
  get_fundamental_data: "获取基本面数据",
  get_capital_flow: "获取资金流向",
  get_stock_news: "获取新闻",
  search_web: "搜索网络",
  get_risk_assessment: "评估风险",
};

export function ToolCallCard({ toolCall }: Props) {
  const [expanded, setExpanded] = useState(false);
  const icon = TOOL_ICONS[toolCall.tool_name] || "🔧";
  const name = TOOL_NAMES[toolCall.tool_name] || toolCall.tool_name;
  const hasResult = !!toolCall.result;
  // 通过 result_summary 判断是否为错误（包含"error"/"失败"/"异常"关键词）
  const isError = hasResult && /error|失败|异常|错误/i.test(toolCall.result?.result_summary || "");

  // 状态标签
  const statusLabel = !hasResult
    ? "执行中..."
    : isError
      ? "失败"
      : "完成";

  const statusColor = !hasResult
    ? "text-[#3737CC]"
    : isError
      ? "text-[#FF8767]"
      : "text-[#46BEA3]";

  return (
    <div
      className={`
        backdrop-blur-md bg-white/[0.04] border border-white/[0.08]
        rounded-lg p-2.5 text-xs cursor-pointer
        transition-all duration-200
        hover:bg-white/[0.08] hover:border-white/[0.15]
        ${!hasResult ? "shadow-[0_0_8px_rgba(55,55,204,0.15)]" : ""}
      `}
      onClick={() => setExpanded(!expanded)}
    >
      {/* 主行：工具名称 | 耗时 | 状态 */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="shrink-0">{icon}</span>
          <span className="font-medium truncate">{name}</span>
          {toolCall.agent && (
            <Badge variant="outline" className="text-[10px] shrink-0 border-white/10">
              {toolCall.agent}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {hasResult && toolCall.result?.duration_ms && (
            <span className="text-muted-foreground tabular-nums">
              {toolCall.result.duration_ms}ms
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
          <div className="h-2.5 w-3/4 bg-white/[0.06] rounded animate-pulse" />
          <div className="h-2.5 w-1/2 bg-white/[0.04] rounded animate-pulse" />
        </div>
      )}

      {/* 展开详情：输入参数 + 结果摘要 */}
      {expanded && hasResult && (
        <div className="mt-2 space-y-1.5 border-t border-white/[0.08] pt-2">
          <div>
            <span className="text-muted-foreground">{"参数: "}</span>
            <code className="text-[10px] bg-white/[0.06] px-1 py-0.5 rounded break-all">
              {JSON.stringify(toolCall.arguments)}
            </code>
          </div>
          {toolCall.result?.result_summary && (
            <div>
              <span className="text-muted-foreground">{"结果: "}</span>
              <span className="text-foreground/80">{toolCall.result.result_summary}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
