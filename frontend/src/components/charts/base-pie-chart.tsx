/**
 * Input: pie chart data array with name and value
 * Output: pie/donut chart component
 * Pos: base chart components, used by risk distribution and other proportion charts
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */
"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { stockPalette } from "@/lib/utils/css-var";

interface DataPoint {
  name: string;
  value: number;
  [key: string]: string | number;
}

interface BasePieChartProps {
  data: DataPoint[];
  height?: number;
  className?: string;
  colors?: string[];
}

function defaultPalette(): string[] {
  const p = stockPalette();
  return [p.chart1, p.chart4, p.chart2, p.chart3, p.chart5, p.accent];
}

export function BasePieChart({
  data,
  height = 300,
  className,
  colors,
}: BasePieChartProps) {
  const palette = colors && colors.length > 0 ? colors : defaultPalette();

  return (
    <div className={className} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={palette[index % palette.length]}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
            }}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
