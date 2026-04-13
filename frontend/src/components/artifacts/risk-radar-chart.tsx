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

  const riskColor = 'from-[#3737CC] to-[#6B5EE4]';
  const riskLevelColor = riskScore >= 70 ? 'text-[#FF8767]' : riskScore >= 40 ? 'text-[#F59E0B]' : 'text-[#46BEA3]';
  const riskBg = riskScore >= 70 ? 'bg-[#FF8767]/10 text-[#FF8767]' : riskScore >= 40 ? 'bg-[#F59E0B]/10 text-[#F59E0B]' : 'bg-[#46BEA3]/10 text-[#46BEA3]';

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
            <span className="text-xl font-bold font-mono text-white">{riskScore}</span>
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
            <div className="text-sm font-mono font-bold text-[#FF8767]">{data.stop_loss_suggestion}</div>
          </div>
        )}
      </div>

      {/* 风险进度条 */}
      <div className="w-full bg-foreground/[0.06] dark:bg-white/[0.06] rounded-full h-3 overflow-hidden">
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
              <span className="text-[#FF8767] mt-0.5">&#9888;</span>
              <span>{f}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
