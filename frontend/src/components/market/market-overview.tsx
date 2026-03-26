// Input: 后端 /api/market_indices API 返回的实时指数数据
// Output: 紧凑市场ticker条 (h-7)，显示上证/深证/创业板/沪深300实时行情
// Pos: 首页顶部，显示主要市场指数数据
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { useEffect, useState, useCallback } from "react";
import { apiClient } from "@/lib/api/client";

interface IndexQuote {
  name: string;
  code: string;
  price: number;
  change_pct: number;
}

interface MarketIndicesResponse {
  indices: IndexQuote[];
}

const FALLBACK_NAMES = ["上证指数", "深证成指", "创业板指", "沪深300"];

export function MarketOverview() {
  const [quotes, setQuotes] = useState<IndexQuote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchIndices = useCallback(async () => {
    try {
      const res = await apiClient.get<MarketIndicesResponse>("/api/market_indices");
      if (res?.indices && res.indices.length > 0) {
        setQuotes(res.indices);
        setError(false);
      } else {
        setError(true);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIndices();
    // 每30秒自动刷新
    const interval = setInterval(fetchIndices, 30000);
    return () => clearInterval(interval);
  }, [fetchIndices]);

  // 加载中或错误时显示占位
  if (loading) {
    return (
      <div className="flex items-center gap-3 px-3 h-7 bg-[#06060F]/80 backdrop-blur-sm border-b border-white/[0.06] text-[11px] shrink-0">
        {FALLBACK_NAMES.map((name) => (
          <div key={name} className="flex items-center gap-1 shrink-0">
            <span className="text-[#8888A0]">{name}</span>
            <span className="text-[#F0F0F5]/40 font-mono animate-pulse">···</span>
          </div>
        ))}
      </div>
    );
  }

  const displayItems = error || quotes.length === 0
    ? FALLBACK_NAMES.map((name) => ({ name, code: "", price: 0, change_pct: 0, isError: true }))
    : quotes.map((q) => ({ ...q, isError: false }));

  return (
    <div className="flex items-center gap-3 px-3 h-7 bg-[#06060F]/80 backdrop-blur-sm border-b border-white/[0.06] text-[11px] shrink-0 overflow-x-auto">
      {displayItems.map((q, i) => (
        <div key={q.name} className="flex items-center gap-1 shrink-0">
          <span className="text-[#8888A0]">{q.name}</span>
          {q.isError ? (
            <span className="text-[#F0F0F5]/60 font-mono">---</span>
          ) : (
            <>
              <span className="font-mono text-[#F0F0F5]">
                {q.price.toFixed(2)}
              </span>
              <span
                className={`font-mono ${
                  q.change_pct >= 0 ? "text-[#EF4444]" : "text-[#10B981]"
                }`}
              >
                {q.change_pct >= 0 ? "+" : ""}
                {q.change_pct.toFixed(2)}%
              </span>
            </>
          )}
          {i < displayItems.length - 1 && (
            <span className="text-white/[0.08] ml-1">·</span>
          )}
        </div>
      ))}
    </div>
  );
}
