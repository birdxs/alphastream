// Input: 无（静态展示框架）
// Output: 紧凑市场ticker条 (h-7)
// Pos: 首页顶部，显示主要指数占位

"use client";

const INDICES = [
  { name: "上证", code: "000001" },
  { name: "深证", code: "399001" },
  { name: "创业板", code: "399006" },
  { name: "沪深300", code: "000300" },
];

export function MarketOverview() {
  return (
    <div className="flex items-center gap-3 px-3 h-7 bg-[#06060F]/80 backdrop-blur-sm border-b border-white/[0.06] text-[11px] shrink-0 overflow-x-auto">
      {INDICES.map((idx, i) => (
        <div key={idx.code} className="flex items-center gap-1 shrink-0">
          <span className="text-[#8888A0]">{idx.name}</span>
          <span className="text-[#F0F0F5]/60 font-mono">---</span>
          {i < INDICES.length - 1 && <span className="text-white/[0.08] ml-1">·</span>}
        </div>
      ))}
      <span className="ml-auto text-[#555570] text-[10px] shrink-0">实时数据待接入</span>
    </div>
  );
}
