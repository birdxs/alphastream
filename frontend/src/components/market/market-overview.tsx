// Input: 后端 /api/market_stream SSE(直连8888) 或 /api/market_indices REST轮询(proxy)
// Output: 紧凑市场ticker条 (h-7)，显示上证/深证/创业板/沪深300实时行情
// Pos: 首页顶部，显示主要市场指数数据
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { useEffect, useState, useCallback, useRef } from "react";

interface IndexQuote {
  name: string;
  code: string;
  price: number;
  change_pct: number;
}

interface MarketIndicesResponse {
  indices: IndexQuote[];
  degraded?: boolean;
  status?: string;
}

const FALLBACK_NAMES = ["上证指数", "深证成指", "创业板指", "沪深300"];

export function MarketOverview() {
  const [quotes, setQuotes] = useState<IndexQuote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  // 记录每个指数的价格变化方向: 'up' | 'down' | null
  const [flashMap, setFlashMap] = useState<Record<string, 'up' | 'down' | null>>({});
  const prevQuotesRef = useRef<IndexQuote[]>([]);

  // B25: fetchIndices 返回 true=有数据拿到, false=降级/空响应
  const fetchIndices = useCallback(async (): Promise<boolean> => {
    try {
      // B23: 走 Next.js proxy (同 origin)，避免 Playwright/Chromium 冷启动时直连 8888 的 16s IPv6 超时
      // SSE 单独直连 8888（见下方 connectSSE），两者分离互不阻塞连接池
      const rawRes = await fetch('/api/market_indices');
      if (rawRes.status === 503) {
        if (process.env.NODE_ENV !== 'production') {
          console.debug('[market-overview] market_indices 降级，保留旧数据或占位');
        }
        setLoading(false);
        return false;
      }
      if (!rawRes.ok) {
        console.warn('[market-overview] market_indices HTTP异常:', rawRes.status);
        return false;
      }
      const res: MarketIndicesResponse = await rawRes.json();
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
        setLoading(false);
        return true;
      }
      // B25: degraded(indices=[]) — 不立即报错，等重试或 SSE
      if (res?.degraded || res?.status === 'DEGRADED' || res?.indices?.length === 0) {
        if (process.env.NODE_ENV !== 'production') {
          console.debug('[market-overview] market_indices 空响应/降级，保留旧数据或占位');
        }
        setLoading(false);
      }
      return false;
    } catch (e) {
      // B25: 网络/JSON 错误也不立即报错，由调用方决定是否兜底
      // S3-B4: 补 debug log 便于排查（Hunt3 前端 Major）
      if (process.env.NODE_ENV !== 'production') console.debug('[market-overview] fetchIndices 异常:', e);
      return false;
    }
  }, []);

  // SSE实时推送，失败时降级为30秒轮询
  useEffect(() => {
    let eventSource: EventSource | null = null;
    let fallbackInterval: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let loadingTimer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;

    // B23: SSE 直连后端，避免与 REST fetch 共享 Next.js proxy HTTP/1.1 连接池
    // 若显式设置 NEXT_PUBLIC_API_URL 则用之；否则用 window.location.hostname:8888 直连后端
    const apiBase = process.env.NEXT_PUBLIC_API_URL ||
      (typeof window !== 'undefined'
        ? `${window.location.protocol}//${window.location.hostname}:8888`
        : '');

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
      } catch (e) {
        // S3-B4: 补 debug log（Hunt3 前端 Major）— SSE 解析失败等待下一次推送
        if (process.env.NODE_ENV !== 'production') console.debug('[market-overview] SSE 解析失败:', e);
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

    // B25: 带重试的初始加载 — 最多3次(间隔800ms)解决 Turbopack 首次 degraded 问题
    // 若3次均无数据，兜底结束 loading(显示 error 态 ---)
    const initFetch = async (attempt: number) => {
      if (disposed) return;
      const ok = await fetchIndices();
      if (ok) {
        if (!disposed) connectSSE();
        return;
      }
      if (attempt < 3) {
        loadingTimer = setTimeout(() => initFetch(attempt + 1), 800);
      } else {
        // 3次全部 degraded/失败 → 兜底结束 loading
        setLoading(false);
        setError(true);
        if (!disposed) connectSSE();
      }
    };

    initFetch(0);

    return () => {
      disposed = true;
      eventSource?.close();
      if (fallbackInterval) clearInterval(fallbackInterval);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (loadingTimer) clearTimeout(loadingTimer);
    };
  }, [fetchIndices]);

  // 加载中或错误时显示占位
  if (loading) {
    return (
      <div className="sticky top-0 z-20 flex items-center gap-3 px-3 h-7 bg-background/80 dark:bg-[#06060F]/80 backdrop-blur-sm border-b border-foreground/[0.06] dark:border-white/[0.06] text-[11px] shrink-0">
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
    <div className="sticky top-0 z-20 flex items-center gap-3 px-3 h-7 bg-background/80 dark:bg-[#06060F]/80 backdrop-blur-sm border-b border-foreground/[0.06] dark:border-white/[0.06] text-[11px] shrink-0 overflow-x-auto">
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
                  q.change_pct >= 0 ? "stock-up" : "stock-down"
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
