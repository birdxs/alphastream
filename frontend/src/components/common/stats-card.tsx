// Input: 标签+数值+格式+变动+趋势数据+图标
// Output: 统计指标卡片（大数字+趋势sparkline）
// Pos: components/common/stats-card.tsx - 金融统计指标卡片
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { ReactNode } from "react";
import { GlassCard } from "./glass-card";
import { Sparkline } from "./sparkline";
import { useCountUp } from "@/lib/hooks/use-count-up";

interface StatsCardProps {
  label: string;
  value: number;
  format?: "number" | "percent" | "currency" | "large";
  decimals?: number;
  change?: number;
  sparklineData?: number[];
  icon?: ReactNode;
  className?: string;
}

function formatLarge(val: number, decimals: number): string {
  const abs = Math.abs(val);
  if (abs >= 1_0000_0000) {
    return (val / 1_0000_0000).toFixed(decimals) + "亿";
  }
  if (abs >= 1_0000) {
    return (val / 1_0000).toFixed(decimals) + "万";
  }
  return val.toLocaleString("zh-CN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function StatsCard({
  label,
  value,
  format = "number",
  decimals = 2,
  change,
  sparklineData,
  icon,
  className = "",
}: StatsCardProps) {
  const animatedRaw = useCountUp(
    format === "large" ? value : value,
    { decimals, enabled: true }
  );

  // 根据format生成最终展示文本
  const displayValue = (() => {
    switch (format) {
      case "percent": {
        const sign = value > 0 ? "+" : "";
        return `${sign}${animatedRaw}%`;
      }
      case "currency":
        return `\u00a5${animatedRaw}`;
      case "large":
        // large格式不使用countUp的格式化，直接用formatLarge
        return formatLarge(value, decimals);
      case "number":
      default:
        return animatedRaw;
    }
  })();

  const changeColor =
    change !== undefined && change >= 0 ? "text-[#46BEA3]" : "text-[#FF8767]";
  const changeArrow =
    change !== undefined && change >= 0 ? "\u2191" : "\u2193";

  return (
    <GlassCard padding="md" className={`hover:scale-[1.02] hover:shadow-lg transition-transform duration-200 ${className}`}>
      <div className="flex flex-col gap-1.5">
        {/* 顶部: icon + label */}
        <div className="flex items-center gap-1.5">
          {icon && <span className="text-sm">{icon}</span>}
          <span className="text-[#8888A0] text-xs">{label}</span>
        </div>

        {/* 中部: 大数字 + 右下角sparkline */}
        <div className="flex items-end justify-between">
          <div className="flex flex-col gap-0.5">
            <span className="text-2xl font-mono font-bold text-[#F0F0F5]">
              {displayValue}
            </span>

            {/* 变动值 */}
            {change !== undefined && (
              <span className={`font-mono text-xs ${changeColor}`}>
                {changeArrow}
                {Math.abs(change).toFixed(decimals)}
                {format === "percent" ? "%" : ""}
              </span>
            )}
          </div>

          {/* 右下角sparkline */}
          {sparklineData && sparklineData.length >= 2 && (
            <Sparkline data={sparklineData} width={40} height={20} />
          )}
        </div>
      </div>
    </GlassCard>
  );
}
