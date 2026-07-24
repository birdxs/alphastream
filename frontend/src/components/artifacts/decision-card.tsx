"use client";

import type { ProvenanceEntry } from '@/lib/types';
import { normalizeProvenanceList } from '@/lib/types';
// Input: 决策数据（action/confidence/reasoning/risk/price_targets/position/degradations/scorecard/memo/reflection/memory）
// Output: 增强版决策卡片，含置信度进度条、风险评分、价格目标、决策理由、降级条、评分卡/备忘/反思只读/记忆预取
// Pos: artifact-renderer.tsx 的子组件，decision_card 类型 Artifact 渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import { Badge } from "@/components/ui/badge";

interface DegradationView {
  level?: string;
  cause?: string;
  message?: string;
  confidence_cap?: number;
  source?: string;
}

interface ScorecardView {
  data_coverage?: number | null;
  tool_success_rate?: number | null;
  role_agreement?: number | null;
  confidence_cap?: number | null;
}

interface DecisionMemoView {
  action?: string;
  veto_reasons?: string[];
  risk_reasons?: string[];
  evidence_pointers?: Array<{ slot: string; label: string; status: string }>;
  reasoning?: string | null;
  disclaimer?: string;
  /** G1 数据血统摘要（与 final_decision.provenance 对齐，无假行情） */
  provenance?: ProvenanceEntry[];
}

interface ReflectionSummaryView {
  count?: number;
  items?: Array<{
    timestamp?: string;
    accuracy_score?: number | null;
    lessons?: string | null;
    what_went_well?: string | null;
    what_went_wrong?: string | null;
  }>;
  note?: string;
  readonly?: boolean;
}

interface MemoryContextView {
  history_count?: number;
  recent?: Array<{
    timestamp?: string;
    action?: string | null;
    confidence?: number | null;
    reasoning?: string | null;
  }>;
  semantic_context?: string | null;
}

interface Props {
  data: {
    action?: string;
    confidence?: number;
    reasoning?: string;
    risk_score?: number;
    risk_level?: string;
    price_targets?: {
      support?: number;
      resistance?: number;
      target?: number;
    };
    position_suggestion?: string;
    /** P0-2 结构化降级（零假值） */
    degradations?: DegradationView[];
    confidence_cap?: number;
    /** G1 数据血统摘要（无假行情） */
    provenance?: ProvenanceEntry[];
    approval_status?: string;
    /** G6 */
    scorecard?: ScorecardView | null;
    /** G5 */
    decision_memo?: DecisionMemoView | null;
    /** G7 只读 */
    reflection_summary?: ReflectionSummaryView | null;
    /** G8 空则不展示 */
    memory_context?: MemoryContextView | null;
  };
}

function pctLabel(v: number | null | undefined): string {
  if (typeof v !== 'number' || Number.isNaN(v)) return '—';
  return `${Math.round(Math.max(0, Math.min(1, v)) * 100)}%`;
}

// G1：normalize 统一走 @/lib/types.normalizeProvenanceList，禁止本地重复实现绕过

export function DecisionCardArtifact({ data }: Props) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        暂无决策数据
      </div>
    );
  }
  const isDegraded =
    Boolean(data.degradations && data.degradations.length > 0) ||
    (data.confidence_cap != null && Number(data.confidence_cap) < 1);
  // G12：降级时禁止展示价位数字（铁律 #1）
  const showPriceTargets = !isDegraded;

  const action = String(data.action || "HOLD").toUpperCase();
  const confidence = Number(data.confidence || 0);
  const riskScore = Number(data.risk_score || 1 - confidence);
  const degradations = Array.isArray(data.degradations) ? data.degradations : [];
  const confCap =
    typeof data.confidence_cap === "number" && !Number.isNaN(data.confidence_cap)
      ? data.confidence_cap
      : undefined;

  const actionConfig =
    {
      BUY: {
        text: "\u4E70\u5165",
        emoji: "\uD83D\uDFE2",
        bg: "bg-ok/10 border-ok/30",
        text_color: "text-ok",
      },
      SELL: {
        text: "\u5356\u51FA",
        emoji: "\uD83D\uDD34",
        bg: "bg-danger/10 border-danger/30",
        text_color: "text-danger",
      },
      HOLD: {
        text: "\u6301\u6709",
        emoji: "\uD83D\uDFE1",
        bg: "bg-warn/10 border-warn/30",
        text_color: "text-warn",
      },
    }[action] || {
      text: action,
      emoji: "\u26AA",
      bg: "bg-muted",
      text_color: "text-foreground",
    };

  return (
    <div className={`rounded-xl bg-gradient-to-br from-white/[0.04] to-white/[0.02] border border-foreground/[0.08] dark:border-white/[0.08] backdrop-blur-sm p-4 space-y-3`}>
      {/* 决策头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-3xl">{actionConfig.emoji}</span>
          <div>
            <span className={`text-2xl font-bold ${actionConfig.text_color}`}>{actionConfig.text}</span>
            <p className="text-xs text-muted-foreground">AI综合决策</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm">置信度</div>
          <div className="text-2xl font-bold font-mono text-accent">{(confidence * 100).toFixed(0)}%</div>
        </div>
      </div>

      {/* 置信度进度条 */}
      <div className="w-full bg-foreground/[0.06] dark:bg-white/[0.06] rounded-full h-2">
        <div
          className="h-2 rounded-full transition-all duration-1000 bg-gradient-to-r from-accent to-accent/80"
          style={{ width: `${Math.max(0, Math.min(1, confidence)) * 100}%` }}
        />
      </div>

      {/* P0-2 降级可视化：有降级时明示上界帽与 cause，不显示假数 */}
      {(degradations.length > 0 || confCap != null) && (
        <div
          className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 space-y-1.5"
          data-testid="decision-degradation-banner"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-amber-700 dark:text-amber-300">
              数据降级（未使用假行情）
            </span>
            {confCap != null && (
              <Badge variant="outline" className="text-[10px] border-amber-500/40 text-amber-700 dark:text-amber-300">
                置信上限 {(confCap * 100).toFixed(0)}%
              </Badge>
            )}
          </div>
          {degradations.slice(0, 4).map((d, i) => (
            <p key={i} className="text-[11px] leading-snug text-amber-800/90 dark:text-amber-200/90">
              <span className="font-mono opacity-80">{d.cause || "tool_failure"}</span>
              {d.source ? ` · ${d.source}` : ""}
              {d.message ? ` — ${d.message}` : ""}
            </p>
          ))}
          {degradations.length > 4 && (
            <p className="text-[10px] text-muted-foreground">另有 {degradations.length - 4} 条降级记录</p>
          )}
        </div>
      )}

      {/* 风险评分 */}
      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground">风险:</span>
          <Badge variant={riskScore > 0.6 ? "destructive" : riskScore > 0.3 ? "secondary" : "default"}>
            {data.risk_level || `${(riskScore * 100).toFixed(0)}%`}
          </Badge>
        </div>
        {data.position_suggestion && (
          <div className="flex items-center gap-1">
            <span className="text-muted-foreground">仓位:</span>
            <span className="font-medium">{data.position_suggestion}</span>
          </div>
        )}
      </div>

      {/* 价格目标：G12 降级态隐藏价位数字（铁律 #1） */}
      {showPriceTargets && data.price_targets && (
        <div className="grid grid-cols-3 gap-2 text-center text-sm">
          {data.price_targets.support && (
            <div className="bg-foreground/[0.03] dark:bg-white/[0.03] border border-foreground/[0.08] dark:border-white/[0.08] rounded-lg p-2 hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors">
              <div className="text-xs text-muted-foreground">支撑位</div>
              <div className="font-mono text-2xl font-medium text-danger">{data.price_targets.support}</div>
            </div>
          )}
          {data.price_targets.target && (
            <div className="bg-foreground/[0.03] dark:bg-white/[0.03] border border-foreground/[0.08] dark:border-white/[0.08] rounded-lg p-2 hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors">
              <div className="text-xs text-muted-foreground">目标价</div>
              <div className="font-mono text-2xl font-medium text-accent">{data.price_targets.target}</div>
            </div>
          )}
          {data.price_targets.resistance && (
            <div className="bg-foreground/[0.03] dark:bg-white/[0.03] border border-foreground/[0.08] dark:border-white/[0.08] rounded-lg p-2 hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors">
              <div className="text-xs text-muted-foreground">阻力位</div>
              <div className="font-mono text-2xl font-medium text-ok">{data.price_targets.resistance}</div>
            </div>
          )}
        </div>
      )}

      {isDegraded && data.price_targets && (
        <p className="text-xs text-muted-foreground">
          降级运行中：目标价位已隐藏
          {data.confidence_cap != null
            ? `（置信上限 ${(Number(data.confidence_cap) * 100).toFixed(0)}%）`
            : ''}
        </p>
      )}

      {/* 决策理由 */}
      {data.reasoning && <p className="text-sm leading-relaxed">{data.reasoning}</p>}

      {/* G1 数据血统（可折叠，仅摘要无假行情；memo.provenance 与顶层对齐，经 normalize 同一 schema） */}
      {(() => {
        const raw =
          (Array.isArray(data.provenance) && data.provenance.length > 0
            ? data.provenance
            : null) ||
          (data.decision_memo &&
          Array.isArray(data.decision_memo.provenance) &&
          data.decision_memo.provenance.length > 0
            ? data.decision_memo.provenance
            : null);
        const prov = normalizeProvenanceList(raw);
        if (!prov.length) return null;
        return (
          <details className="mt-3 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
            <summary className="cursor-pointer select-none text-xs text-muted-foreground hover:text-foreground">
              数据血统 · {prov.length} 源
            </summary>
            <ul className="mt-2 space-y-1.5 text-[11px] font-mono text-muted-foreground">
              {prov.map((p, i) => (
                <li
                  key={`${p.source || ''}-${p.tool || ''}-${p.digest || ''}-${i}`}
                  className="flex flex-wrap gap-x-2 gap-y-0.5"
                >
                  <span className="text-foreground/80">{p.source || p.tool || 'unknown'}</span>
                  {p.tool && p.source && p.tool !== p.source && (
                    <span className="opacity-70">tool={p.tool}</span>
                  )}
                  {p.digest && <span className="opacity-60">#{p.digest.slice(0, 8)}</span>}
                  {p.ts && <span className="opacity-50">{p.ts}</span>}
                </li>
              ))}
            </ul>
          </details>
        );
      })()}

      {/* G6 Run scorecard */}
      {data.scorecard && (
        <div className="rounded-lg border border-border/60 bg-muted/20 p-3 space-y-2">
          <div className="text-xs font-medium text-muted-foreground">运行评分卡</div>
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            {(
              [
                ['数据覆盖', data.scorecard.data_coverage],
                ['工具成功', data.scorecard.tool_success_rate],
                ['角色一致', data.scorecard.role_agreement],
                ['置信帽', data.scorecard.confidence_cap],
              ] as Array<[string, number | null | undefined]>
            ).map(([label, val]) => (
              <div key={label} className="rounded-md bg-background/60 px-2 py-1.5">
                <div className="text-[10px] text-muted-foreground">{label}</div>
                <div className="font-semibold tabular-nums">{pctLabel(val)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* G5 决策备忘 */}
      {data.decision_memo && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 space-y-2">
          <div className="text-xs font-medium text-amber-700 dark:text-amber-400">决策备忘</div>
          {Array.isArray(data.decision_memo.veto_reasons) &&
            data.decision_memo.veto_reasons.length > 0 && (
              <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                {data.decision_memo.veto_reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          {Array.isArray(data.decision_memo.evidence_pointers) &&
            data.decision_memo.evidence_pointers.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {data.decision_memo.evidence_pointers.map((ep) => (
                  <span
                    key={ep.slot}
                    className={
                      ep.status === 'present'
                        ? 'rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] text-emerald-700 dark:text-emerald-400'
                        : 'rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground'
                    }
                  >
                    {ep.label}:{ep.status === 'present' ? '有' : '缺'}
                  </span>
                ))}
              </div>
            )}
          {data.decision_memo.disclaimer && (
            <p className="text-[10px] text-muted-foreground/80">{data.decision_memo.disclaimer}</p>
          )}
        </div>
      )}

      {/* G7 反思只读 */}
      {data.reflection_summary &&
        Array.isArray(data.reflection_summary.items) &&
        data.reflection_summary.items.length > 0 && (
          <div className="space-y-2 rounded-lg border border-border/60 bg-muted/10 p-3">
            <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
              <span>历史反思（只读）</span>
              <span className="text-[10px]">{data.reflection_summary.note || '不写生产权重'}</span>
            </div>
            <div className="space-y-2">
              {data.reflection_summary.items.slice(0, 3).map((it, i) => (
                <div key={i} className="space-y-0.5 border-l-2 border-border pl-2 text-xs">
                  {it.timestamp && (
                    <div className="text-[10px] text-muted-foreground">{it.timestamp}</div>
                  )}
                  {it.lessons && <p className="text-muted-foreground">{it.lessons}</p>}
                  {!it.lessons && it.what_went_wrong && (
                    <p className="text-muted-foreground">问题: {it.what_went_wrong}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

      {/* G8 Memory 预取：空历史不渲染假值 */}
      {data.memory_context &&
      (data.memory_context.history_count || data.memory_context.semantic_context) ? (
        <div className="space-y-1.5 rounded-lg border border-border/60 p-3">
          <div className="text-xs font-medium text-muted-foreground">
            同标的记忆
            {typeof data.memory_context.history_count === 'number'
              ? ` · ${data.memory_context.history_count} 次`
              : ''}
          </div>
          {data.memory_context.semantic_context && (
            <p className="line-clamp-3 text-xs text-muted-foreground">
              {data.memory_context.semantic_context}
            </p>
          )}
          {Array.isArray(data.memory_context.recent) && data.memory_context.recent.length > 0 && (
            <ul className="space-y-1 text-[11px] text-muted-foreground">
              {data.memory_context.recent.slice(0, 3).map((h, i) => (
                <li key={i} className="flex gap-2">
                  <span className="font-medium">{h.action || '—'}</span>
                  <span className="truncate">{h.reasoning || h.timestamp || ''}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

    </div>
  );
}
