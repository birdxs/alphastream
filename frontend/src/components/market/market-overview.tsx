// Input: 后端 /api/stock_data API 返回的股票历史数据
// Output: 紧凑市场ticker条 (h-7)，显示贵州茅台实时价格
// Pos: 首页顶部，显示主要股票/指数数据
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

interface StockRecord {
  date: string;
  close: number;
  open: number;
  high: number;
  low: number;
  [key: string]: unknown;
}

interface StockQuote {
  name: string;
  code: string;
  price: number | null;
  change: number | null;
  loading: boolean;
  error: boolean;
}

const WATCHED_STOCKS: { name: string; code: string; market: string }[] = [
  { name: "贵州茅台", code: "600519", market: "A" },
  { name: "上证指数", code: "000001", market: "A" },
  { name: "深证成指", code: "399001", market: "A" },
  { name: "创业板指", code: "399006", market: "A" },
];

export function MarketOverview() {
  const [quotes, setQuotes] = useState<StockQuote[]>(
    WATCHED_STOCKS.map((s) => ({
      name: s.name,
      code: s.code,
      price: null,
      change: null,
      loading: true,
      error: false,
    }))
  );

  useEffect(() => {
    let cancelled = false;

    async function fetchQuote(idx: number) {
      const stock = WATCHED_STOCKS[idx];
      try {
        const res = await apiClient.get<{ data?: StockRecord[] }>(
          "/api/stock_data",
          { stock_code: stock.code, market_type: stock.market, period: "daily" }
        );
        if (cancelled) return;

        const records = res?.data;
        if (records && records.length >= 2) {
          const latest = records[records.length - 1];
          const prev = records[records.length - 2];
          const price = latest.close;
          const change =
            prev.close > 0 ? ((price - prev.close) / prev.close) * 100 : 0;

          setQuotes((prev) => {
            const next = [...prev];
            next[idx] = {
              ...next[idx],
              price,
              change,
              loading: false,
              error: false,
            };
            return next;
          });
        } else {
          // 数据不够或为空
          setQuotes((prev) => {
            const next = [...prev];
            next[idx] = { ...next[idx], loading: false, error: true };
            return next;
          });
        }
      } catch {
        if (cancelled) return;
        setQuotes((prev) => {
          const next = [...prev];
          next[idx] = { ...next[idx], loading: false, error: true };
          return next;
        });
      }
    }

    // 并发拉取所有股票，但限制只获取第一个(茅台)确保成功
    // 其余指数可能后端不支持，失败时静默显示 ---
    WATCHED_STOCKS.forEach((_, i) => fetchQuote(i));

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex items-center gap-3 px-3 h-7 bg-[#06060F]/80 backdrop-blur-sm border-b border-white/[0.06] text-[11px] shrink-0 overflow-x-auto">
      {quotes.map((q, i) => (
        <div key={q.code} className="flex items-center gap-1 shrink-0">
          <span className="text-[#8888A0]">{q.name}</span>
          {q.loading ? (
            <span className="text-[#F0F0F5]/40 font-mono animate-pulse">···</span>
          ) : q.price !== null ? (
            <>
              <span className="font-mono text-[#F0F0F5]">
                {q.price.toFixed(2)}
              </span>
              {q.change !== null && (
                <span
                  className={`font-mono ${
                    q.change >= 0 ? "text-[#EF4444]" : "text-[#10B981]"
                  }`}
                >
                  {q.change >= 0 ? "+" : ""}
                  {q.change.toFixed(2)}%
                </span>
              )}
            </>
          ) : (
            <span className="text-[#F0F0F5]/60 font-mono">---</span>
          )}
          {i < quotes.length - 1 && (
            <span className="text-white/[0.08] ml-1">·</span>
          )}
        </div>
      ))}
    </div>
  );
}
