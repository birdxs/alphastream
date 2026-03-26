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
import { TrendingDown } from "lucide-react";

interface DailyFlowItem {
  date: string;
  // 后端返回的字段名
  main_net_inflow?: number;
  main_net_inflow_percent?: number;
  super_large_net_inflow?: number;
  large_net_inflow?: number;
  medium_net_inflow?: number;
  small_net_inflow?: number;
  price?: number;
  change_percent?: number;
  // 兼容旧格式
  net_flow?: number;
}

interface Props {
  data: {
    daily_flow?: DailyFlowItem[];
    // 后端summary字段
    summary?: {
      recent_days?: number;
      total_main_net_inflow?: number;
      avg_main_net_inflow_percent?: number;
      positive_days?: number;
      negative_days?: number;
    };
    // 兼容旧格式的顶层字段
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

  // 柱状图数据：兼容两种后端格式
  const chartData =
    data.daily_flow?.map((d) => {
      // 优先使用 main_net_inflow（新格式），回退到 net_flow（旧格式）
      const rawValue = d.main_net_inflow ?? d.net_flow ?? 0;
      return {
        date: d.date.length > 5 ? d.date.slice(5) : d.date, // MM-DD
        value: rawValue / 10000, // 转万元
      };
    }) || [];

  // 汇总数据：优先从summary提取，回退到旧的顶层字段
  const summaryItems: { label: string; value: number }[] = [];

  if (data.summary) {
    const s = data.summary;
    if (s.total_main_net_inflow !== undefined) {
      summaryItems.push({ label: "主力净流入", value: s.total_main_net_inflow });
    }
    if (s.positive_days !== undefined && s.negative_days !== undefined) {
      // 添加正/负天数统计信息
      summaryItems.push({ label: `净流入天数 (${s.recent_days ?? '?'}日)`, value: s.positive_days });
    }
    if (s.avg_main_net_inflow_percent !== undefined) {
      summaryItems.push({ label: "日均主力占比%", value: s.avg_main_net_inflow_percent });
    }
  }

  // 回退到旧格式的顶层字段
  if (summaryItems.length === 0) {
    const oldItems = [
      { label: "主力净流入", value: data.main_force_net },
      { label: "北向资金", value: data.north_flow },
      { label: "机构资金", value: data.institutional_flow },
      { label: "散户资金", value: data.retail_flow },
    ].filter((item) => item.value !== undefined) as { label: string; value: number }[];
    summaryItems.push(...oldItems);
  }

  // 如果没有任何数据，从daily_flow中计算汇总
  if (summaryItems.length === 0 && data.daily_flow && data.daily_flow.length > 0) {
    const totalMainNet = data.daily_flow.reduce((sum, d) => sum + (d.main_net_inflow ?? d.net_flow ?? 0), 0);
    const totalSuperLarge = data.daily_flow.reduce((sum, d) => sum + (d.super_large_net_inflow ?? 0), 0);
    const totalSmall = data.daily_flow.reduce((sum, d) => sum + (d.small_net_inflow ?? 0), 0);
    summaryItems.push(
      { label: "主力净流入", value: totalMainNet },
      { label: "超大单净流入", value: totalSuperLarge },
      { label: "散户净流入", value: totalSmall },
    );
  }

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
                {Math.abs(item.value) >= 10000
                  ? `${(Number(item.value) / 10000).toFixed(1)}万`
                  : `${Number(item.value).toFixed(1)}`
                }
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

      {/* 无数据提示 */}
      {chartData.length === 0 && summaryItems.length === 0 && (
        <div className="flex flex-col items-center justify-center py-10 text-[#8888A0]">
          <TrendingDown className="h-8 w-8 mb-2 opacity-40" />
          <p className="text-sm">暂无资金流向数据</p>
        </div>
      )}
    </div>
  );
}
