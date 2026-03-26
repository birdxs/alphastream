// Input: 后端API市场数据
// Output: 市场指数概览条（沪指/深指/创业板/沪深300实时数据），含错误提示
// Pos: 首页顶部ticker bar，展示主要市场指数
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/api/client";

interface MarketIndex {
  name: string;
  code: string;
  price: number;
  change: number;
}

export function MarketOverview() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [indices, setIndices] = useState<MarketIndex[]>([
    { name: "上证指数", code: "000001", price: 0, change: 0 },
    { name: "深证成指", code: "399001", price: 0, change: 0 },
    { name: "创业板指", code: "399006", price: 0, change: 0 },
    { name: "沪深300", code: "000300", price: 0, change: 0 },
  ]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // 尝试从后端获取上证指数数据
        const data = await apiClient.get<Record<string, unknown>>('/api/stock_data?stock_code=000001&market_type=A&period=1m');
        if (data && Array.isArray((data as Record<string, unknown>).data) && ((data as Record<string, unknown>).data as unknown[]).length > 0) {
          const dataArr = (data as Record<string, unknown>).data as Record<string, number>[];
          const latest = dataArr[dataArr.length - 1];
          const prev = dataArr.length > 1 ? dataArr[dataArr.length - 2] : latest;
          setIndices(prevIndices => prevIndices.map((idx, i) => {
            if (i === 0 && latest.close) {
              return { ...idx, price: latest.close, change: ((latest.close - prev.close) / prev.close) * 100 };
            }
            return idx;
          }));
        }
      } catch {
        setError('市场数据加载失败');
        setTimeout(() => setError(null), 3000);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // 自动轮播滚动
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    let scrollPos = 0;
    const interval = setInterval(() => {
      scrollPos += 1;
      if (scrollPos >= el.scrollWidth - el.clientWidth) scrollPos = 0;
      el.scrollTo({ left: scrollPos, behavior: 'auto' });
    }, 50);

    // 用户手动交互时暂停
    const pause = () => clearInterval(interval);
    el.addEventListener('touchstart', pause, { once: true });
    el.addEventListener('mouseenter', pause, { once: true });

    return () => clearInterval(interval);
  }, []);

  return (
    <div ref={scrollRef} className="flex items-center gap-4 px-4 py-1.5 border-b bg-muted/30 overflow-x-auto text-xs"
      style={{
        maskImage: 'linear-gradient(90deg, transparent, black 40px, black calc(100% - 40px), transparent)',
        WebkitMaskImage: 'linear-gradient(90deg, transparent, black 40px, black calc(100% - 40px), transparent)',
      }}
    >
      {error && (
        <span className="px-2 py-0.5 bg-red-500/10 text-red-500 text-[10px] rounded shrink-0">
          {error}
        </span>
      )}
      <span className="text-muted-foreground shrink-0">市场</span>
      {indices.map(idx => (
        <div key={idx.code} className="flex items-center gap-1.5 shrink-0">
          <span className="text-muted-foreground">{idx.name}</span>
          {loading ? (
            <span className="text-muted-foreground">--</span>
          ) : (
            <>
              <span className="font-mono font-finance">{idx.price || '--'}</span>
              {idx.change !== 0 && (
                <span className={idx.change > 0 ? 'stock-up' : 'stock-down'}>
                  {idx.change > 0 ? '+' : ''}{idx.change.toFixed(2)}%
                </span>
              )}
            </>
          )}
        </div>
      ))}
    </div>
  );
}
