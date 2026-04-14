// Input: 决策数据（action/confidence/reasoning/risk/price_targets/position）
// Output: 增强版决策卡片，含置信度进度条、风险评分、价格目标、决策理由
// Pos: artifact-renderer.tsx 的子组件，decision_card 类型 Artifact 渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Badge } from "@/components/ui/badge";

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
          style={{ width: `${confidence * 100}%` }}
        />
      </div>

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
