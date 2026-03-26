// Input: children + 配置选项 (hover, glow, padding, className, onClick)
// Output: 通用毛玻璃卡片容器
// Pos: components/common/glass-card.tsx - 所有毛玻璃卡片的复用基类
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  glow?: "brand" | "ai" | "none";
  padding?: "sm" | "md" | "lg";
  onClick?: () => void;
}

const paddingMap: Record<string, string> = {
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
};

const glowMap: Record<string, string> = {
  brand: "shadow-[0_0_20px_rgba(55,55,204,0.15)]",
  ai: "shadow-[0_0_20px_rgba(107,94,228,0.15)]",
  none: "",
};

export function GlassCard({
  children,
  className = "",
  hover = true,
  glow = "none",
  padding = "md",
  onClick,
}: GlassCardProps) {
  const base =
    "bg-white/[0.04] backdrop-blur-sm border border-white/[0.08] rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.36)]";

  const hoverStyles = hover
    ? "hover:bg-white/[0.08] hover:border-white/[0.15] hover:shadow-[0_12px_40px_rgba(0,0,0,0.45)] hover:-translate-y-px"
    : "";

  const glowStyle = glowMap[glow] ?? "";
  const pad = paddingMap[padding] ?? paddingMap.md;

  return (
    <div
      className={`${base} ${hoverStyles} ${glowStyle} ${pad} transition-all duration-300 ${className}`}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") onClick();
            }
          : undefined
      }
    >
      {children}
    </div>
  );
}
