// Input: 风险评分数据（risk_score、各维度风险、风险因素列表）
// Output: 专业风险雷达图组件（风险评分头部、进度条、雷达图、风险因素列表）
// Pos: artifact-renderer.tsx的子组件，risk_gauge类型Artifact渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import dynamic from "next/dynamic";
import { Badge } from "@/components/ui/badge";

const ScoreRadarArtifact = dynamic(
  () => import("./score-radar").then(m => ({ default: m.ScoreRadarArtifact })),
  { ssr: false }
);

interface Props {
  data: {
    risk_score?: number;
    risk_level?: string;
    volatility_risk?: string;
    trend_risk?: string;
    reversal_risk?: string;
    volume_risk?: string;
    max_drawdown_risk?: string;
    risk_factors?: string[];
    stop_loss_suggestion?: number;
    position_suggestion?: string;
    [key: string]: unknown;
  };
}

export function RiskRadarArtifact({ data }: Props) {
  const riskScore = Number(data.risk_score || 50);
  const riskLevel = data.risk_level || '中等风险';

  const riskColor = riskScore >= 70 ? 'from-red-500 to-rose-600' : riskScore >= 40 ? 'from-yellow-500 to-orange-600' : 'from-green-500 to-emerald-600';
  const riskBg = riskScore >= 70 ? 'bg-red-500/10' : riskScore >= 40 ? 'bg-yellow-500/10' : 'bg-green-500/10';

  const riskMap: Record<string, number> = { '低': 20, '中': 50, '高': 80 };
  const radarData = {
    volatility_risk: riskMap[data.volatility_risk || '中'] || 50,
    trend_risk: riskMap[data.trend_risk || '中'] || 50,
    reversal_risk: riskMap[data.reversal_risk || '中'] || 50,
    volume_risk: riskMap[data.volume_risk || '中'] || 50,
    risk_score: riskScore,
  };

  return (
    <div className="space-y-4">
      {/* 风险头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${riskColor} flex items-center justify-center shadow-lg`}>
            <span className="text-xl font-bold text-white">{riskScore}</span>
          </div>
          <div>
            <span className="text-lg font-bold">风险评分</span>
            <div className="flex items-center gap-2 mt-0.5">
              <Badge className={riskBg}>{riskLevel}</Badge>
              {data.position_suggestion && (
                <span className="text-xs text-muted-foreground">建议{data.position_suggestion}</span>
              )}
            </div>
          </div>
        </div>
        {data.stop_loss_suggestion && (
          <div className="text-right">
            <div className="text-[10px] text-muted-foreground">止损建议</div>
            <div className="text-sm font-mono font-bold text-red-500">{data.stop_loss_suggestion}</div>
          </div>
        )}
      </div>

      {/* 风险进度条 */}
      <div className="w-full bg-muted rounded-full h-3 overflow-hidden">
        <div className={`h-3 rounded-full bg-gradient-to-r ${riskColor} transition-all duration-1000`} style={{ width: `${riskScore}%` }} />
      </div>

      {/* 雷达图 */}
      <ScoreRadarArtifact data={radarData} />

      {/* 风险因素 */}
      {data.risk_factors && data.risk_factors.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">风险因素</p>
          {data.risk_factors.map((f, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <span className="text-red-500 mt-0.5">&#9888;</span>
              <span>{f}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
