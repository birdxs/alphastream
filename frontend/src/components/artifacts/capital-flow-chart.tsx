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
import { formatLargeNumber } from "@/lib/utils/format";

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
  const { theme } = useThemeStore();
  const upColor = "#46BEA3";   // 流入 — design token --color-up
  const downColor = "#FF8767"; // 流出 — design token --color-down

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
              className="bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1.5 text-sm"
            >
              <span className="text-[#8888A0]">{item.label}</span>
              <span
                className={`ml-2 font-mono ${
                  Number(item.value) >= 0 ? "text-[#46BEA3]" : "text-[#FF8767]"
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
              stroke={theme === "dark" ? "rgba(255,255,255,0.04)" : "#e5e7eb"}
            />
            <XAxis
              dataKey="date"
              tick={{
                fontSize: 10,
                fill: theme === "dark" ? "#8888A0" : "#4b5563",
              }}
            />
            <YAxis
              tick={{
                fontSize: 10,
                fill: theme === "dark" ? "#8888A0" : "#4b5563",
              }}
            />
            <Tooltip
              content={(props) => {
                const { active, payload } = props as { active?: boolean; payload?: ReadonlyArray<{ value?: number; payload?: { date?: string } }> };
                if (!active || !payload?.length) return null;
                const val = payload[0].value as number;
                return (
                  <div className="bg-[#0A0A1A]/90 border border-white/[0.08] rounded-lg px-3 py-2 text-xs shadow-lg backdrop-blur-sm">
                    <p className="text-[#8888A0]">{payload[0].payload?.date}</p>
                    <p className={`font-mono font-bold ${val >= 0 ? 'text-[#46BEA3]' : 'text-[#FF8767]'}`}>
                      净流入: {formatLargeNumber(val * 10000)}
                    </p>
                  </div>
                );
              }}
            />
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
