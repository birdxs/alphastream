// Input: 多维度评分数据（趋势/动量/成交量/支撑/风险/综合，或 success=false 失败结构）
// Output: Recharts雷达图可视化组件；失败时显示 ErrorState
// Pos: artifact-renderer.tsx的子组件，technical_indicators类型Artifact辅助渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Tooltip,
} from "recharts";
import { SafeResponsiveContainer } from "@/components/charts/safe-responsive-container";
import { useThemeStore } from "@/lib/stores/theme-store";

interface Props {
  data: {
    success?: boolean;
    error?: string;
    message?: string;
    score?: number;
    trend_score?: number;
    momentum_score?: number;
    volume_score?: number;
    support_score?: number;
    risk_score?: number;
    [key: string]: unknown;
  };
}

export function ScoreRadarArtifact({ data }: Props) {
  const { theme } = useThemeStore();

  if (data.success === false) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        {data.message ?? 'AI 分析不可用，请稍后重试'}
      </div>
    );
  }

  const radarData = [
    { subject: "趋势", value: Number(data.trend_score ?? data.score ?? 0) },
    { subject: "动量", value: Number(data.momentum_score ?? 0) },
    { subject: "成交量", value: Number(data.volume_score ?? 0) },
    { subject: "支撑", value: Number(data.support_score ?? 0) },
    { subject: "风险", value: 100 - Number(data.risk_score ?? 50) },
    { subject: "综合", value: Number(data.score ?? 0) },
  ];

  const avgScore = Math.round(radarData.reduce((sum, d) => sum + d.value, 0) / radarData.length);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between px-1">
        <span className="text-muted-foreground dark:text-[#8888A0] text-xs">综合评分</span>
        <span className={`font-mono text-lg font-bold ${avgScore >= 60 ? 'text-[#46BEA3]' : avgScore >= 40 ? 'text-[#F59E0B]' : 'text-[#FF8767]'}`}>
          {avgScore}
        </span>
      </div>
      <SafeResponsiveContainer width="100%" height={300} aria-label="多维度评分雷达图">
        <RadarChart data={radarData}>
          <PolarGrid
            stroke={theme === "dark" ? "rgba(255,255,255,0.08)" : "#e5e7eb"}
          />
          <PolarAngleAxis
            dataKey="subject"
            tick={{
              fill: theme === "dark" ? "#8888A0" : "#4b5563",
              fontSize: 12,
            }}
          />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} />
          <Tooltip
            contentStyle={{
              background: theme === 'dark' ? 'rgba(10,10,26,0.85)' : 'rgba(255,255,255,0.85)',
              border: theme === 'dark' ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.08)',
              borderRadius: 12,
              fontSize: 12,
              fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              color: theme === 'dark' ? '#F0F0F5' : '#1f2937',
              padding: '8px 12px',
              boxShadow: theme === 'dark' ? '0 4px 24px rgba(0,0,0,0.4)' : '0 4px 16px rgba(0,0,0,0.1)',
            }}
            formatter={(value, _name, entry) => {
              return [`${value}分`, entry.payload?.subject || '评分'];
            }}
            labelStyle={{ display: 'none' }}
            itemStyle={{ fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace' }}
          />
          <Radar
            name="评分"
            dataKey="value"
            stroke="#3737CC"
            fill="#3737CC"
            fillOpacity={0.25}
          />
        </RadarChart>
      </SafeResponsiveContainer>
      <div className="grid grid-cols-3 gap-1 px-1">
        {radarData.map((d) => (
          <div key={d.subject} className="flex items-center justify-between text-[10px] px-1.5 py-0.5 rounded bg-foreground/[0.04] dark:bg-white/[0.04] border border-foreground/[0.08] dark:border-white/[0.08]">
            <span className="text-muted-foreground dark:text-[#8888A0]">{d.subject}</span>
            <span className={`font-mono ${d.value >= 60 ? 'text-[#46BEA3]' : d.value >= 40 ? 'text-[#F59E0B]' : 'text-[#FF8767]'}`}>
              {d.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
