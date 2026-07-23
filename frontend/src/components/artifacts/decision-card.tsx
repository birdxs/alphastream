// Input: 决策数据（action/confidence/reasoning/risk/price_targets/position/degradations）
// Output: 增强版决策卡片，含置信度进度条、风险评分、价格目标、决策理由、降级条
// Pos: artifact-renderer.tsx 的子组件，decision_card 类型 Artifact 渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Badge } from "@/components/ui/badge";

interface DegradationView {
  level?: string;
  cause?: string;
  message?: string;
  confidence_cap?: number;
  source?: string;
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
  };
}

export function DecisionCardArtifact({ data }: Props) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        暂无决策数据
      </div>
    );
  }

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
        bg: "bg-[#46BEA3]/10 border-[#46BEA3]/30",
        text_color: "text-[#46BEA3]",
      },
      SELL: {
        text: "\u5356\u51FA",
        emoji: "\uD83D\uDD34",
        bg: "bg-[#FF8767]/10 border-[#FF8767]/30",
        text_color: "text-[#FF8767]",
      },
      HOLD: {
        text: "\u6301\u6709",
        emoji: "\uD83D\uDFE1",
        bg: "bg-[#F59E0B]/10 border-[#F59E0B]/30",
        text_color: "text-[#F59E0B]",
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
          <div className="text-2xl font-bold font-mono text-[#6B5EE4]">{(confidence * 100).toFixed(0)}%</div>
        </div>
      </div>

      {/* 置信度进度条 */}
      <div className="w-full bg-foreground/[0.06] dark:bg-white/[0.06] rounded-full h-2">
        <div
          className="h-2 rounded-full transition-all duration-1000 bg-gradient-to-r from-[#3737CC] to-[#6B5EE4]"
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

      {/* 价格目标 */}
      {data.price_targets && (
        <div className="grid grid-cols-3 gap-2 text-center text-sm">
          {data.price_targets.support && (
            <div className="bg-foreground/[0.03] dark:bg-white/[0.03] border border-foreground/[0.08] dark:border-white/[0.08] rounded-lg p-2 hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors">
              <div className="text-xs text-muted-foreground">支撑位</div>
              <div className="font-mono text-2xl font-medium text-[#FF8767]">{data.price_targets.support}</div>
            </div>
          )}
          {data.price_targets.target && (
            <div className="bg-foreground/[0.03] dark:bg-white/[0.03] border border-foreground/[0.08] dark:border-white/[0.08] rounded-lg p-2 hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors">
              <div className="text-xs text-muted-foreground">目标价</div>
              <div className="font-mono text-2xl font-medium text-[#6B5EE4]">{data.price_targets.target}</div>
            </div>
          )}
          {data.price_targets.resistance && (
            <div className="bg-foreground/[0.03] dark:bg-white/[0.03] border border-foreground/[0.08] dark:border-white/[0.08] rounded-lg p-2 hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors">
              <div className="text-xs text-muted-foreground">阻力位</div>
              <div className="font-mono text-2xl font-medium text-[#46BEA3]">{data.price_targets.resistance}</div>
            </div>
          )}
        </div>
      )}

      {/* 决策理由 */}
      {data.reasoning && <p className="text-sm leading-relaxed">{data.reasoning}</p>}
    </div>
  );
}
