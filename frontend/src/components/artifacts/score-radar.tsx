// Input: 多维度评分数据（趋势/动量/成交量/支撑/风险/综合）
// Output: Recharts雷达图可视化组件
// Pos: artifact-renderer.tsx的子组件，technical_indicators类型Artifact辅助渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";
import { useThemeStore } from "@/lib/stores/theme-store";

interface Props {
  data: {
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

  const radarData = [
    { subject: "趋势", value: Number(data.trend_score || data.score || 50) },
    { subject: "动量", value: Number(data.momentum_score || 50) },
    { subject: "成交量", value: Number(data.volume_score || 50) },
    { subject: "支撑", value: Number(data.support_score || 50) },
    { subject: "风险", value: 100 - Number(data.risk_score || 50) },
    { subject: "综合", value: Number(data.score || 50) },
  ];

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={radarData}>
        <PolarGrid
          stroke={theme === "dark" ? "#374151" : "#e5e7eb"}
        />
        <PolarAngleAxis
          dataKey="subject"
          tick={{
            fill: theme === "dark" ? "#9ca3af" : "#4b5563",
            fontSize: 12,
          }}
        />
        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} />
        <Radar
          name="评分"
          dataKey="value"
          stroke="#3b82f6"
          fill="#3b82f6"
          fillOpacity={0.3}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
