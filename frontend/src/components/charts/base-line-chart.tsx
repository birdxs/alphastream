// Input: data数组(name/value), height, color, dataKey
// Output: 响应式折线图（Recharts LineChart）
// Pos: components/charts/base-line-chart.tsx - 基础折线图，用于趋势展示
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { useThemeStore } from "@/lib/stores/theme-store";

interface Props {
  data: Array<{ name: string; value: number; [key: string]: unknown }>;
  height?: number;
  color?: string;
  dataKey?: string;
}

export function BaseLineChart({ data, height = 200, color = "#3b82f6", dataKey = "value" }: Props) {
  const { theme } = useThemeStore();
  const gridColor = theme === 'dark' ? '#374151' : '#e5e7eb';
  const textColor = theme === 'dark' ? '#9ca3af' : '#4b5563';

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
        <XAxis dataKey="name" tick={{ fontSize: 10, fill: textColor }} />
        <YAxis tick={{ fontSize: 10, fill: textColor }} />
        <Tooltip contentStyle={{ background: theme === 'dark' ? '#1f2937' : '#fff', border: 'none', borderRadius: 8, fontSize: 12 }} />
        <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
