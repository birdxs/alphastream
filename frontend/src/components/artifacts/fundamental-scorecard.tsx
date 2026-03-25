// Input: 基本面评分数据（score、财务指标、定性评估）
// Output: 专业基本面评分卡组件（评分头部、定性评估标签、财务指标网格）
// Pos: artifact-renderer.tsx的子组件，fundamental_metrics类型Artifact渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Badge } from "@/components/ui/badge";

interface Props {
  data: {
    score?: number;
    financial_health?: string;
    profitability?: string;
    growth_potential?: string;
    valuation?: string;
    financial_indicators?: {
      pe_ratio?: number;
      pb_ratio?: number;
      roe?: number;
      debt_ratio?: number;
      revenue_growth?: number;
      profit_growth?: number;
    };
    recommendation?: string;
    [key: string]: unknown;
  };
}

export function FundamentalScorecardArtifact({ data }: Props) {
  const score = Number(data.score || 50);
  const indicators = data.financial_indicators || {};

  const scoreColor = score >= 80 ? 'from-green-500 to-emerald-600' : score >= 60 ? 'from-blue-500 to-cyan-600' : score >= 40 ? 'from-yellow-500 to-orange-600' : 'from-red-500 to-rose-600';

  const metrics = [
    { label: "PE(TTM)", value: indicators.pe_ratio, suffix: "倍", good: (v: number) => v > 0 && v < 30 },
    { label: "PB", value: indicators.pb_ratio, suffix: "倍", good: (v: number) => v > 0 && v < 5 },
    { label: "ROE", value: indicators.roe, suffix: "%", good: (v: number) => v > 15 },
    { label: "资产负债率", value: indicators.debt_ratio, suffix: "%", good: (v: number) => v < 60 },
    { label: "营收增长", value: indicators.revenue_growth, suffix: "%", good: (v: number) => v > 10 },
    { label: "利润增长", value: indicators.profit_growth, suffix: "%", good: (v: number) => v > 10 },
  ].filter(m => m.value != null);

  const qualitative = [
    { label: "财务健康", value: data.financial_health },
    { label: "盈利能力", value: data.profitability },
    { label: "成长潜力", value: data.growth_potential },
    { label: "估值水平", value: data.valuation },
  ].filter(q => q.value);

  return (
    <div className="space-y-4">
      {/* 评分头部 */}
      <div className="flex items-center gap-4">
        <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${scoreColor} flex items-center justify-center shadow-lg`}>
          <span className="text-2xl font-bold text-white">{score}</span>
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold">基本面评分</span>
            {data.recommendation && (
              <Badge variant="outline" className="text-xs">{data.recommendation}</Badge>
            )}
          </div>
          <div className="w-32 bg-muted rounded-full h-2 mt-1">
            <div className={`h-2 rounded-full bg-gradient-to-r ${scoreColor} transition-all duration-1000`} style={{ width: `${score}%` }} />
          </div>
        </div>
      </div>

      {/* 定性评估 */}
      {qualitative.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {qualitative.map(q => {
            const isGood = ['健康', '强', '高', '低估'].includes(q.value || '');
            const isBad = ['较差', '弱', '低', '高估'].includes(q.value || '');
            return (
              <div key={q.label} className={`px-2.5 py-1 rounded-lg text-xs border ${
                isGood ? 'bg-green-500/10 border-green-500/30 text-green-600' :
                isBad ? 'bg-red-500/10 border-red-500/30 text-red-600' :
                'bg-muted/50 border-border/50'
              }`}>
                <span className="text-muted-foreground">{q.label}</span>
                <span className="ml-1 font-medium">{q.value}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* 财务指标网格 */}
      {metrics.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {metrics.map(m => {
            const val = Number(m.value);
            const isGood = m.good(val);
            return (
              <div key={m.label} className="bg-muted/30 rounded-lg p-2.5 text-center border border-border/30">
                <div className="text-[10px] text-muted-foreground mb-0.5">{m.label}</div>
                <div className={`text-sm font-mono font-bold ${isGood ? 'text-green-500' : 'text-foreground'}`}>
                  {val.toFixed(1)}{m.suffix}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
