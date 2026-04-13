// Input: 后端 /api/market_stream SSE 实时推送 或 /api/market_indices 轮询(降级)
// Output: 紧凑市场ticker条 (h-7)，显示上证/深证/创业板/沪深300实时行情
// Pos: 首页顶部，显示主要市场指数数据
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { useEffect, useState, useCallback, useRef } from "react";
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
  // 记录每个指数的价格变化方向: 'up' | 'down' | null
  const [flashMap, setFlashMap] = useState<Record<string, 'up' | 'down' | null>>({});
  const prevQuotesRef = useRef<IndexQuote[]>([]);

  const fetchIndices = useCallback(async () => {
    try {
      const res = await apiClient.get<MarketIndicesResponse>("/api/market_indices");
      if (res?.indices && res.indices.length > 0) {
        // 比较新旧价格，触发flash动画
        const prev = prevQuotesRef.current;
        if (prev.length > 0) {
          const newFlash: Record<string, 'up' | 'down' | null> = {};
          res.indices.forEach(q => {
            const old = prev.find(p => p.name === q.name);
            if (old && q.price !== old.price) {
              newFlash[q.name] = q.price > old.price ? 'up' : 'down';
            }
          });
          if (Object.keys(newFlash).length > 0) {
            setFlashMap(newFlash);
            // 动画结束后清除flash状态
            setTimeout(() => setFlashMap({}), 800);
          }
        }
        prevQuotesRef.current = res.indices;
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

  // SSE实时推送，失败时降级为30秒轮询
  useEffect(() => {
    let eventSource: EventSource | null = null;
    let fallbackInterval: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;

    const apiBase = process.env.NEXT_PUBLIC_API_URL || '';

    const handleSSEData = (rawData: string) => {
      try {
        const res: MarketIndicesResponse = JSON.parse(rawData);
        if (res?.indices && res.indices.length > 0) {
          const prev = prevQuotesRef.current;
          if (prev.length > 0) {
            const newFlash: Record<string, 'up' | 'down' | null> = {};
            res.indices.forEach(q => {
              const old = prev.find(p => p.name === q.name);
              if (old && q.price !== old.price) {
                newFlash[q.name] = q.price > old.price ? 'up' : 'down';
              }
            });
            if (Object.keys(newFlash).length > 0) {
              setFlashMap(newFlash);
              setTimeout(() => setFlashMap({}), 800);
            }
          }
          prevQuotesRef.current = res.indices;
          setQuotes(res.indices);
          setError(false);
          setLoading(false);
        }
      } catch {
        // 解析失败忽略，等待下一次推送
      }
    };

    const connectSSE = () => {
      if (disposed) return;
      eventSource = new EventSource(`${apiBase}/api/market_stream`);

      eventSource.onmessage = (event) => {
        handleSSEData(event.data);
      };

      eventSource.onerror = () => {
        // SSE连接失败，关闭并降级为轮询
        eventSource?.close();
        eventSource = null;
        if (!disposed) {
          // 3秒后尝试重连，同时启用轮询作为降级
          if (!fallbackInterval) {
            fetchIndices(); // 立即获取一次
            fallbackInterval = setInterval(fetchIndices, 30000);
          }
          reconnectTimer = setTimeout(() => {
            if (fallbackInterval) {
              clearInterval(fallbackInterval);
              fallbackInterval = null;
            }
            connectSSE();
          }, 3000);
        }
      };
    };

    // 先用fetch获取一次数据（快速首屏），然后连接SSE
    fetchIndices().then(() => {
      if (!disposed) connectSSE();
    });

    return () => {
      disposed = true;
      eventSource?.close();
      if (fallbackInterval) clearInterval(fallbackInterval);
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [fetchIndices]);

  // 加载中或错误时显示占位
  if (loading) {
    return (
      <div className="flex items-center gap-3 px-3 h-7 bg-background/80 dark:bg-[#06060F]/80 backdrop-blur-sm border-b border-foreground/[0.06] dark:border-white/[0.06] text-[11px] shrink-0">
        {FALLBACK_NAMES.map((name) => (
          <div key={name} className="flex items-center gap-1 shrink-0">
            <span className="text-muted-foreground dark:text-[#8888A0]">{name}</span>
            <span className="text-foreground dark:text-[#F0F0F5]/40 font-mono animate-pulse">···</span>
          </div>
        ))}
      </div>
    );
  }

  const displayItems = error || quotes.length === 0
    ? FALLBACK_NAMES.map((name) => ({ name, code: "", price: 0, change_pct: 0, isError: true }))
    : quotes.map((q) => ({ ...q, isError: false }));

  return (
    <div className="flex items-center gap-3 px-3 h-7 bg-background/80 dark:bg-[#06060F]/80 backdrop-blur-sm border-b border-foreground/[0.06] dark:border-white/[0.06] text-[11px] shrink-0 overflow-x-auto">
      {displayItems.map((q, i) => (
        <div key={q.name} className={`flex items-center gap-1 shrink-0 ${!q.isError && flashMap[q.name] === 'up' ? 'flash-up' : ''} ${!q.isError && flashMap[q.name] === 'down' ? 'flash-down' : ''}`}>
          <span className="text-muted-foreground dark:text-[#8888A0]">{q.name}</span>
          {q.isError ? (
            <span className="text-foreground dark:text-[#F0F0F5]/60 font-mono">---</span>
          ) : (
            <>
              <span className="font-mono text-foreground dark:text-[#F0F0F5]">
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
