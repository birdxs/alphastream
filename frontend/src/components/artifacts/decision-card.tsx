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
  const action = String(data.action || "HOLD").toUpperCase();
  const confidence = Number(data.confidence || 0);
  const riskScore = Number(data.risk_score || 1 - confidence);

  const actionConfig =
    {
      BUY: {
        text: "\u4E70\u5165",
        emoji: "\uD83D\uDFE2",
        bg: "bg-green-500/10 border-green-500/30",
        text_color: "text-green-600",
      },
      SELL: {
        text: "\u5356\u51FA",
        emoji: "\uD83D\uDD34",
        bg: "bg-red-500/10 border-red-500/30",
        text_color: "text-red-600",
      },
      HOLD: {
        text: "\u6301\u6709",
        emoji: "\uD83D\uDFE1",
        bg: "bg-yellow-500/10 border-yellow-500/30",
        text_color: "text-yellow-600",
      },
    }[action] || {
      text: action,
      emoji: "\u26AA",
      bg: "bg-muted",
      text_color: "text-foreground",
    };

  return (
    <div className={`rounded-lg border-2 p-4 space-y-3 ${actionConfig.bg}`}>
      {/* 决策头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-3xl">{actionConfig.emoji}</span>
          <div>
            <span className={`text-2xl font-bold ${actionConfig.text_color}`}>{actionConfig.text}</span>
            <p className="text-xs text-muted-foreground">AI\u7EFC\u5408\u51B3\u7B56</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm">\u7F6E\u4FE1\u5EA6</div>
          <div className="text-2xl font-bold font-mono">{(confidence * 100).toFixed(0)}%</div>
        </div>
      </div>

      {/* 置信度进度条 */}
      <div className="w-full bg-muted rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-1000 ${
            confidence > 0.7 ? "bg-green-500" : confidence > 0.4 ? "bg-yellow-500" : "bg-red-500"
          }`}
          style={{ width: `${confidence * 100}%` }}
        />
      </div>

      {/* 风险评分 */}
      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground">\u98CE\u9669:</span>
          <Badge variant={riskScore > 0.6 ? "destructive" : riskScore > 0.3 ? "secondary" : "default"}>
            {data.risk_level || `${(riskScore * 100).toFixed(0)}%`}
          </Badge>
        </div>
        {data.position_suggestion && (
          <div className="flex items-center gap-1">
            <span className="text-muted-foreground">\u4ED3\u4F4D:</span>
            <span className="font-medium">{data.position_suggestion}</span>
          </div>
        )}
      </div>

      {/* 价格目标 */}
      {data.price_targets && (
        <div className="grid grid-cols-3 gap-2 text-center text-sm">
          {data.price_targets.support && (
            <div className="bg-background/50 rounded p-2">
              <div className="text-xs text-muted-foreground">\u652F\u6491\u4F4D</div>
              <div className="font-mono font-medium text-red-500">{data.price_targets.support}</div>
            </div>
          )}
          {data.price_targets.target && (
            <div className="bg-background/50 rounded p-2">
              <div className="text-xs text-muted-foreground">\u76EE\u6807\u4EF7</div>
              <div className="font-mono font-medium text-primary">{data.price_targets.target}</div>
            </div>
          )}
          {data.price_targets.resistance && (
            <div className="bg-background/50 rounded p-2">
              <div className="text-xs text-muted-foreground">\u963B\u529B\u4F4D</div>
              <div className="font-mono font-medium text-green-500">{data.price_targets.resistance}</div>
            </div>
          )}
        </div>
      )}

      {/* 决策理由 */}
      {data.reasoning && <p className="text-sm leading-relaxed">{data.reasoning}</p>}
    </div>
  );
}
