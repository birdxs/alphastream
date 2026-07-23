// Input: 辩论数据（bull_case/bear_case/debate_summary/divergence_points）
// Output: 双栏多空对比 + 分歧点短扫摘要（不读长文也能抓冲突）
// Pos: artifact-renderer.tsx 的子组件，debate_card 类型 Artifact 渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { Badge } from "@/components/ui/badge";
import { useMemo } from "react";

interface Props {
  data: {
    bull_case?: string;
    bear_case?: string;
    debate_summary?: string;
    divergence_points?: string[];
    bull_confidence?: string;
    bear_confidence?: string;
  };
}

function extractConf(text?: string, explicit?: string): string {
  if (explicit) return explicit;
  if (!text) return "—";
  const m = text.match(/置信度[:：]\s*([高中低]|\d+(?:\.\d+)?)/);
  return m?.[1] ?? "—";
}

function extractDivergence(summary?: string, points?: string[]): string[] {
  if (points && points.length > 0) return points.slice(0, 5);
  if (!summary) return [];
  const line = summary.split("\n").find((l) => l.includes("分歧"));
  if (!line) return [];
  const body = line.replace(/^.*?[：:]/, "").trim();
  return body
    .split(/[；;|]/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 5);
}

export function DebateCardArtifact({ data }: Props) {
  const bull = (data?.bull_case || "").trim();
  const bear = (data?.bear_case || "").trim();
  const summary = (data?.debate_summary || "").trim();

  const bullConf = useMemo(
    () => extractConf(summary.includes("多方置信") ? summary : bull, data?.bull_confidence),
    [bull, summary, data?.bull_confidence]
  );
  const bearConf = useMemo(
    () => extractConf(summary.includes("空方置信") ? summary : bear, data?.bear_confidence),
    [bear, summary, data?.bear_confidence]
  );
  const points = useMemo(
    () => extractDivergence(summary, data?.divergence_points),
    [summary, data?.divergence_points]
  );

  // 综合研判一行
  const tendency = useMemo(() => {
    if (!summary) return "";
    const line = summary.split("\n").find((l) => l.includes("综合研判") || l.includes("综合倾向"));
    return line ? line.replace(/^.*?[：:]/, "").trim() : "";
  }, [summary]);

  if (!bull && !bear && !summary) {
    return (
      <div className="flex items-center justify-center h-24 text-sm text-muted-foreground">
        暂无辩论数据
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* 双栏：多方 / 空方 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">
              多方
            </span>
            <Badge variant="outline" className="text-[10px] border-emerald-500/40">
              置信 {bullConf}
            </Badge>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground whitespace-pre-wrap line-clamp-8">
            {bull || "—"}
          </p>
        </div>
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold text-rose-600 dark:text-rose-400">空方</span>
            <Badge variant="outline" className="text-[10px] border-rose-500/40">
              置信 {bearConf}
            </Badge>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground whitespace-pre-wrap line-clamp-8">
            {bear || "—"}
          </p>
        </div>
      </div>

      {/* 分歧点短扫 */}
      {points.length > 0 && (
        <div className="rounded-md border bg-muted/40 px-3 py-2">
          <div className="text-[11px] font-medium text-muted-foreground mb-1.5">分歧点（扫读）</div>
          <ul className="space-y-1">
            {points.map((pt, i) => (
              <li key={i} className="text-xs flex gap-2">
                <span className="text-amber-500 shrink-0">●</span>
                <span className="leading-snug">{pt}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {tendency && (
        <div className="text-xs rounded-md border border-border/60 px-3 py-2 bg-background/60">
          <span className="font-medium text-foreground">综合：</span>
          <span className="text-muted-foreground ml-1">{tendency}</span>
        </div>
      )}
    </div>
  );
}
