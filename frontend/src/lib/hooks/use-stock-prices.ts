// Input: 股票代码数组
// Output: {code: {price, change_pct}}映射，从后端/api/stock_data获取最新收盘价与涨跌幅
// Pos: 持仓/自选/对比共用，实时补全价格数据
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

interface PriceInfo {
  price: number;
  change_pct: number;
}

const priceCache: Record<string, PriceInfo> = {};

interface KlineRow { close?: number; open?: number; [k: string]: unknown }

async function fetchPrice(code: string): Promise<PriceInfo | undefined> {
  if (priceCache[code]) return priceCache[code];
  try {
    const r = await apiClient.get<{ data?: KlineRow[] }>("/api/stock_data", {
      stock_code: code, market_type: "A", period: "1y",
    });
    const rows = r.data || [];
    if (rows.length < 1) return undefined;
    const last = rows[rows.length - 1];
    const prev = rows.length > 1 ? rows[rows.length - 2] : last;
    const close = typeof last.close === "number" ? last.close : undefined;
    const prevClose = typeof prev.close === "number" ? prev.close : close;
    if (close === undefined || prevClose === undefined) return undefined;
    const pct = prevClose > 0 ? ((close - prevClose) / prevClose) * 100 : 0;
    const info = { price: close, change_pct: pct };
    priceCache[code] = info;
    return info;
  } catch {
    return undefined;
  }
}

export function useStockPrices(codes: string[]): Record<string, PriceInfo> {
  const [prices, setPrices] = useState<Record<string, PriceInfo>>(() => ({ ...priceCache }));

  useEffect(() => {
    const missing = codes.filter((c) => !priceCache[c]);
    if (missing.length === 0) {
      const cached: Record<string, PriceInfo> = {};
      codes.forEach((c) => { if (priceCache[c]) cached[c] = priceCache[c]; });
      if (Object.keys(cached).some((k) => prices[k] !== cached[k])) {
        setPrices((prev) => ({ ...prev, ...cached }));
      }
      return;
    }
    let cancelled = false;
    (async () => {
      const CONCURRENCY = 5;
      const acc: Record<string, PriceInfo> = {};
      for (let i = 0; i < missing.length; i += CONCURRENCY) {
        const batch = missing.slice(i, i + CONCURRENCY);
        const resolved = await Promise.all(batch.map(fetchPrice));
        batch.forEach((code, idx) => {
          if (resolved[idx]) acc[code] = resolved[idx] as PriceInfo;
        });
        if (cancelled) return;
        if (Object.keys(acc).length > 0) setPrices((prev) => ({ ...prev, ...acc }));
      }
    })();
    return () => { cancelled = true; };
  }, [codes.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  return prices;
}
