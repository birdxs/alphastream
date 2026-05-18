// Input: 股票代码列表 + market_type
// Output: Record<code, { price, change_pct, change, name? }>
// Pos: 自选股 / 持仓概览 / 看板 / 选股结果 → 批量轻量 quote 数据源
//
// FIX-E5: 旧实现对每只股票串行调 /api/stock_data?period=1y（取整年K线再算 change_pct），
// 在自选股 10+ 只时极慢，导致看板长时间空白。改为单次批量调用 /api/stock_quote_batch。
// 保持返回签名为 Record<code, {price, change_pct, ...}>，消费者无需改动。
'use client';

import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api/client';

export type StockPrice = {
  price: number;
  change_pct: number;
  change?: number;
  name?: string;
};

type BatchResp = {
  results: Array<{
    code: string;
    name?: string;
    latest_price: number;
    change_pct: number;
    change: number;
  }>;
  errors?: Array<{ code: string; msg: string }>;
  ts?: number;
};

// 老接口的回退响应形态（单只 /api/stock_data?period=1y → { data: [{open,close},...] }）
type LegacyResp = {
  data?: Array<{ open: number; close: number }>;
};

export function useStockPrices(
  codes: string[],
  marketType: string = 'A',
  refreshIntervalMs: number = 60000,
): Record<string, StockPrice> {
  const [prices, setPrices] = useState<Record<string, StockPrice>>({});
  const codesKey = codes.slice().sort().join(',');

  useEffect(() => {
    if (!codesKey) {
      setPrices({});
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const run = async () => {
      try {
        const resp = await apiClient.get<BatchResp | LegacyResp>('/api/stock_quote_batch', {
          codes: codesKey,
          market_type: marketType,
        });
        if (cancelled) return;
        const map: Record<string, StockPrice> = {};

        // 新接口（批量）
        if (resp && Array.isArray((resp as BatchResp).results)) {
          for (const r of (resp as BatchResp).results) {
            map[r.code] = {
              price: r.latest_price,
              change_pct: r.change_pct,
              change: r.change,
              name: r.name,
            };
          }
        }
        // 老接口/单只回退：data 数组
        else if (resp && Array.isArray((resp as LegacyResp).data) && (resp as LegacyResp).data!.length > 0) {
          const data = (resp as LegacyResp).data!;
          const last = data[data.length - 1];
          const prev = data.length > 1 ? data[data.length - 2] : last;
          const price = last.close;
          const change_pct = prev.close ? ((last.close - prev.close) / prev.close) * 100 : 0;
          const code = codesKey.split(',')[0];
          map[code] = { price, change_pct };
        }

        setPrices(map);
      } catch {
        // 网络/批量失败 → 兜底逐只调 /api/stock_data?period=1y
        if (cancelled) return;
        try {
          const codesList = codesKey.split(',');
          const results = await Promise.allSettled(
            codesList.map((code) =>
              apiClient.get<LegacyResp>('/api/stock_data', {
                stock_code: code,
                market_type: marketType,
                period: '1y',
              }),
            ),
          );
          if (cancelled) return;
          const map: Record<string, StockPrice> = {};
          results.forEach((r, idx) => {
            if (r.status !== 'fulfilled') return;
            const code = codesList[idx];
            const data = r.value?.data ?? [];
            if (!data.length) return;
            const last = data[data.length - 1];
            const prev = data.length > 1 ? data[data.length - 2] : last;
            const price = last.close;
            const change_pct = prev.close ? ((last.close - prev.close) / prev.close) * 100 : 0;
            map[code] = { price, change_pct };
          });
          setPrices(map);
        } catch {
          // 全失败保持空 map
        }
      } finally {
        if (!cancelled && refreshIntervalMs > 0) {
          timer = setTimeout(run, refreshIntervalMs);
        }
      }
    };

    run();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [codesKey, marketType, refreshIntervalMs]);

  return prices;
}
