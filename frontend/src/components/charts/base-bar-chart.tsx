/**
 * Input: chart data array, dataKey, optional color and stock color scheme
 * Output: bar chart component with up/down color differentiation
 * Pos: base chart components, used by capital flow and other positive/negative value charts
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */
"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { stockPalette } from "@/lib/utils/css-var";

interface DataPoint {
  [key: string]: string | number;
}

interface BaseBarChartProps {
  data: DataPoint[];
  dataKey: string;
  xKey?: string;
  color?: string;
  height?: number;
  className?: string;
  /** 使用涨跌语义色：正=stock-up，负=stock-down（跟随 data-color-scheme） */
  useStockColors?: boolean;
}

export function BaseBarChart({
  data,
  dataKey,
  xKey = "name",
  color,
  height = 300,
  className,
  useStockColors = false,
}: BaseBarChartProps) {
  const palette = stockPalette();
  const defaultColor = color || palette.chart1;
  const upColor = palette.up;
  const downColor = palette.down;

  return (
    <div className={className} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
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
          <Bar dataKey={dataKey} radius={[4, 4, 0, 0]}>
            {data.map((entry, index) => {
              const value = Number(entry[dataKey]);
              const fillColor = useStockColors
                ? value >= 0
                  ? upColor
                  : downColor
                : defaultColor;
              return <Cell key={`cell-${index}`} fill={fillColor} />;
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
