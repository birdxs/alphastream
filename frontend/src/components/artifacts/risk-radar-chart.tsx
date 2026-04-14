// Input: 风险评分数据（total_risk_score、各维度risk dict/level、alerts列表）
// Output: 专业风险雷达图组件（风险评分头部、进度条、雷达图、风险因素列表）
// Pos: artifact-renderer.tsx的子组件，risk_gauge类型Artifact渲染器
// 契约: 兼容 total_risk_score / risk_score 双字段, volatility_risk可为dict{score,risk_level}或字符串'低/中/高'
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import dynamic from "next/dynamic";
import { Badge } from "@/components/ui/badge";

const ScoreRadarArtifact = dynamic(
  () => import("./score-radar").then(m => ({ default: m.ScoreRadarArtifact })),
  { ssr: false }
);

// 后端返回格式 (见 app/core/artifact_wrapper.py::_get_risk_structured):
//   {
//     total_risk_score: number,            // 0-100加权分
//     risk_score: number,                   // 同上(别名)
//     risk_level: string,                   // 极低/低/中等/高/极高
//     volatility_risk_level: '低'|'中'|'高',  // 扁平映射字段
//     trend_risk_level, reversal_risk_level, volume_risk_level,
//     volatility_risk: {score, value, risk_level},  // 详细dict
//     trend_risk: {score, trend, risk_level},
//     reversal_risk: {score, direction, risk_level},
//     volume_risk: {score, pattern, risk_level},
//     alerts: [{type, level, message}]
//   }
interface RiskSub {
  score?: number;
  risk_level?: string;
  value?: number;
  trend?: string;
  direction?: string;
  pattern?: string;
}
interface Props {
  data: {
    risk_score?: number;
    total_risk_score?: number;
    risk_level?: string;
    volatility_risk_level?: string;
    trend_risk_level?: string;
    reversal_risk_level?: string;
    volume_risk_level?: string;
    volatility_risk?: RiskSub | string;
    trend_risk?: RiskSub | string;
    reversal_risk?: RiskSub | string;
    volume_risk?: RiskSub | string;
    alerts?: Array<{ type?: string; level?: string; message?: string }>;
    risk_factors?: string[];
    stop_loss_suggestion?: number;
    position_suggestion?: string;
    stock_name?: string;
    [key: string]: unknown;
  };
}

/** 从 string | RiskSub 中提取 score(0-100) */
function extractScore(field: RiskSub | string | undefined, fallbackLevel?: string): number {
  if (field == null) {
    return levelToScore(fallbackLevel);
  }
  if (typeof field === 'string') {
    return levelToScore(field);
  }
  if (typeof field.score === 'number') {
    return field.score;
  }
  return levelToScore(field.risk_level || fallbackLevel);
}

function levelToScore(level?: string): number {
  if (!level) return 50;
  if (level.includes('极高')) return 90;
  if (level.includes('高')) return 75;
  if (level.includes('极低')) return 10;
  if (level.includes('低')) return 25;
  return 50; // 中
}

export function RiskRadarArtifact({ data }: Props) {
  // 兼容 total_risk_score (后端真实字段) 与 risk_score (旧字段)
  const rawScore = data.total_risk_score ?? data.risk_score;
  const riskScore = typeof rawScore === 'number' ? Math.round(rawScore * 10) / 10 : 50;
  const riskLevel = data.risk_level || '中等风险';

  const riskColor = 'from-[#3737CC] to-[#6B5EE4]';
  const riskBg = riskScore >= 70 ? 'bg-[#FF8767]/10 text-[#FF8767]' : riskScore >= 40 ? 'bg-[#F59E0B]/10 text-[#F59E0B]' : 'bg-[#46BEA3]/10 text-[#46BEA3]';

  const radarData = {
    volatility_risk: extractScore(data.volatility_risk, data.volatility_risk_level),
    trend_risk: extractScore(data.trend_risk, data.trend_risk_level),
    reversal_risk: extractScore(data.reversal_risk, data.reversal_risk_level),
    volume_risk: extractScore(data.volume_risk, data.volume_risk_level),
    risk_score: riskScore,
  };

  // alerts => risk_factors 派生, 保持UI不变
  const derivedFactors: string[] = Array.isArray(data.risk_factors) && data.risk_factors.length > 0
    ? data.risk_factors
    : (data.alerts || []).map(a => a.message || '').filter(Boolean);

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
      {derivedFactors.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">风险因素</p>
          {derivedFactors.map((f, i) => (
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
