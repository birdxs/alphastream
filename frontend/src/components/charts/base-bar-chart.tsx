// Input: data数组(name/value), height, color, showSign
// Output: 响应式柱状图（Recharts BarChart），支持正负值配色
// Pos: components/charts/base-bar-chart.tsx - 基础柱状图，用于对比/涨跌展示
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { useThemeStore } from "@/lib/stores/theme-store";

interface Props {
  data: Array<{ name: string; value: number }>;
  height?: number;
  color?: string;
  showSign?: boolean;
}

export function BaseBarChart({ data, height = 200, color = "#3b82f6", showSign = false }: Props) {
  const { theme, stockColorScheme } = useThemeStore();
  const gridColor = theme === 'dark' ? '#374151' : '#e5e7eb';
  const textColor = theme === 'dark' ? '#9ca3af' : '#4b5563';
  const upColor = stockColorScheme === 'cn' ? '#ef4444' : '#22c55e';
  const downColor = stockColorScheme === 'cn' ? '#22c55e' : '#ef4444';

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
        <XAxis dataKey="name" tick={{ fontSize: 10, fill: textColor }} />
        <YAxis tick={{ fontSize: 10, fill: textColor }} />
        <Tooltip contentStyle={{ background: theme === 'dark' ? '#1f2937' : '#fff', border: 'none', borderRadius: 8, fontSize: 12 }} />
        <Bar dataKey="value">
          {showSign ? data.map((entry, i) => (
            <Cell key={i} fill={entry.value >= 0 ? upColor : downColor} />
          )) : data.map((_, i) => <Cell key={i} fill={color} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
