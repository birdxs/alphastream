// Input: 资金流向数据（每日净流入、主力/北向/机构/散户资金）
// Output: Recharts柱状图 + 资金汇总卡片
// Pos: artifact-renderer.tsx的子组件，capital_flow_chart类型Artifact渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

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
import { useThemeStore } from "@/lib/stores/theme-store";

interface Props {
  data: {
    daily_flow?: Array<{ date: string; net_flow: number }>;
    main_force_net?: number;
    north_flow?: number;
    institutional_flow?: number;
    retail_flow?: number;
    [key: string]: unknown;
  };
}

export function CapitalFlowArtifact({ data }: Props) {
  const { theme, stockColorScheme } = useThemeStore();
  const upColor = stockColorScheme === "cn" ? "#ef4444" : "#22c55e";
  const downColor = stockColorScheme === "cn" ? "#22c55e" : "#ef4444";

  // 柱状图数据
  const chartData =
    data.daily_flow?.map((d) => ({
      date: d.date.slice(5), // MM-DD
      value: d.net_flow / 10000, // 转万元
    })) || [];

  // 汇总数据
  const summaryItems = [
    { label: "主力净流入", value: data.main_force_net },
    { label: "北向资金", value: data.north_flow },
    { label: "机构资金", value: data.institutional_flow },
    { label: "散户资金", value: data.retail_flow },
  ].filter((item) => item.value !== undefined);

  return (
    <div className="space-y-3">
      {/* 汇总 */}
      {summaryItems.length > 0 && (
        <div className="grid grid-cols-2 gap-2">
          {summaryItems.map((item) => (
            <div
              key={item.label}
              className="bg-muted/50 rounded px-2 py-1.5 text-sm"
            >
              <span className="text-muted-foreground">{item.label}</span>
              <span
                className={`ml-2 font-mono ${
                  Number(item.value) >= 0 ? "text-green-500" : "text-red-500"
                }`}
              >
                {(Number(item.value) / 10000).toFixed(1)}万
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 柱状图 */}
      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={theme === "dark" ? "#374151" : "#e5e7eb"}
            />
            <XAxis
              dataKey="date"
              tick={{
                fontSize: 10,
                fill: theme === "dark" ? "#9ca3af" : "#4b5563",
              }}
            />
            <YAxis
              tick={{
                fontSize: 10,
                fill: theme === "dark" ? "#9ca3af" : "#4b5563",
              }}
            />
            <Tooltip />
            <Bar dataKey="value" name="净流入(万)">
              {chartData.map((entry, index) => (
                <Cell
                  key={index}
                  fill={entry.value >= 0 ? upColor : downColor}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
