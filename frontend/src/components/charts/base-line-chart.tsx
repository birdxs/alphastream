/**
 * Input: chart data array, dataKey for Y values
 * Output: line chart component using Recharts
 * Pos: base chart components, used by various artifact panels
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */
"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { stockPalette } from "@/lib/utils/css-var";

interface DataPoint {
  [key: string]: string | number;
}

interface BaseLineChartProps {
  data: DataPoint[];
  dataKey: string;
  xKey?: string;
  color?: string;
  height?: number;
  className?: string;
}

export function BaseLineChart({
  data,
  dataKey,
  xKey = "date",
  color,
  height = 300,
  className,
}: BaseLineChartProps) {
  const lineColor = color || stockPalette().chart1;

  return (
    <div className={className} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis
            dataKey={xKey}
            tick={{ fontSize: 12 }}
            className="text-muted-foreground"
          />
          <YAxis tick={{ fontSize: 12 }} className="text-muted-foreground" />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
            }}
          />
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={lineColor}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
