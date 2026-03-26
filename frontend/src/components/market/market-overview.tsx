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
    <div className="flex items-center gap-3 px-3 h-7 border-b border-border/40 bg-[var(--surface-0,hsl(var(--muted)/0.15))] text-[11px] shrink-0 overflow-x-auto">
      {INDICES.map((idx, i) => (
        <div key={idx.code} className="flex items-center gap-1 shrink-0">
          <span className="text-muted-foreground">{idx.name}</span>
          <span className="font-finance text-foreground/60">---</span>
          {i < INDICES.length - 1 && <span className="text-border ml-1">·</span>}
        </div>
      ))}
      <span className="ml-auto text-muted-foreground/50 text-[10px] shrink-0">实时数据待接入</span>
    </div>
  );
}
