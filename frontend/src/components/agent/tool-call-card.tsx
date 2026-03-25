/**
 * Input: 工具调用事件(ToolCallStart + 可选ToolCallResult)
 * Output: 可展开的工具调用详情卡片（图标、名称、耗时、参数、结果摘要）
 * Pos: tool-call-timeline.tsx子组件，展示单次工具调用的完整信息
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

"use client";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import type { ToolCallStart, ToolCallResult } from "@/lib/types";

interface Props {
  toolCall: ToolCallStart & { result?: ToolCallResult };
}

const TOOL_ICONS: Record<string, string> = {
  get_stock_data: "\uD83D\uDCCA",
  get_technical_indicators: "\uD83D\uDCC8",
  get_fundamental_data: "\uD83D\uDCB0",
  get_capital_flow: "\uD83D\uDCB9",
  get_stock_news: "\uD83D\uDCF0",
  search_web: "\uD83D\uDD0D",
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

export function ToolCallCard({ toolCall }: Props) {
  const [expanded, setExpanded] = useState(false);
  const icon = TOOL_ICONS[toolCall.tool_name] || "\uD83D\uDD27";
  const name = TOOL_NAMES[toolCall.tool_name] || toolCall.tool_name;
  const hasResult = !!toolCall.result;

  return (
    <div
      className={`border rounded-lg p-2 text-xs cursor-pointer transition-all hover:bg-accent/50 ${
        hasResult ? 'border-green-500/30' : 'border-yellow-500/30 animate-pulse'
      }`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span>{icon}</span>
          <span className="font-medium">{name}</span>
          {toolCall.agent && <Badge variant="outline" className="text-[10px]">{toolCall.agent}</Badge>}
        </div>
        {hasResult ? (
          <span className="text-green-600">
            {toolCall.result?.duration_ms ? `${toolCall.result.duration_ms}ms` : '\u2713'}
          </span>
        ) : (
          <span className="text-yellow-600">{"\u6267\u884C\u4E2D..."}</span>
        )}
      </div>

      {expanded && (
        <div className="mt-2 space-y-1 border-t pt-2">
          <div>
            <span className="text-muted-foreground">{"\u53C2\u6570: "}</span>
            <code className="text-[10px] bg-muted px-1 rounded">
              {JSON.stringify(toolCall.arguments)}
            </code>
          </div>
          {toolCall.result?.result_summary && (
            <div>
              <span className="text-muted-foreground">{"\u7ED3\u679C: "}</span>
              <span>{toolCall.result.result_summary}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
