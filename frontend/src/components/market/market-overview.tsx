// Input: 后端API市场数据
// Output: 紧凑市场ticker条 (h-7)
// Pos: 首页顶部，显示主要指数

"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

interface MarketIndex {
  name: string;
  code: string;
  price: number;
  change: number;
}

export function MarketOverview() {
  const [indices, setIndices] = useState<MarketIndex[]>([
    { name: "上证", code: "000001", price: 0, change: 0 },
    { name: "深证", code: "399001", price: 0, change: 0 },
    { name: "创业板", code: "399006", price: 0, change: 0 },
    { name: "沪深300", code: "000300", price: 0, change: 0 },
  ]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await apiClient.get<Record<string, unknown>>('/api/stock_data?stock_code=000001&market_type=A&period=1m');
        if (data && Array.isArray((data as Record<string, unknown>).data)) {
          const dataArr = (data as Record<string, unknown>).data as Record<string, number>[];
          if (dataArr.length > 0) {
            const latest = dataArr[dataArr.length - 1];
            const prev = dataArr.length > 1 ? dataArr[dataArr.length - 2] : latest;
            if (latest.close) {
              setIndices(prev_indices => prev_indices.map((idx, i) => {
                if (i === 0) return { ...idx, price: latest.close, change: ((latest.close - prev.close) / prev.close) * 100 };
                return idx;
              }));
            }
          }
        }
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    fetchData();
  }, []);

  return (
    <div className="flex items-center gap-3 px-3 h-7 border-b border-border/40 bg-muted/20 text-[11px] shrink-0 overflow-x-auto">
      {indices.map((idx, i) => (
        <div key={idx.code} className="flex items-center gap-1 shrink-0">
          <span className="text-muted-foreground">{idx.name}</span>
          {loading ? (
            <span className="text-muted-foreground/50">--</span>
          ) : (
            <>
              <span className="font-finance text-foreground/90">{idx.price ? idx.price.toFixed(2) : '--'}</span>
              {idx.change !== 0 && (
                <span className={`font-finance ${idx.change > 0 ? 'stock-up' : 'stock-down'}`}>
                  {idx.change > 0 ? '+' : ''}{idx.change.toFixed(2)}%
                </span>
              )}
            </>
          )}
          {i < indices.length - 1 && <span className="text-border ml-1">│</span>}
        </div>
      ))}
    </div>
  );
}
