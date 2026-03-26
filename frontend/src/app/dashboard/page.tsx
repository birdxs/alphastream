// Input: 后端 /api/market_indices、/api/latest_news、watchlist-store、portfolio-store
// Output: 投资看板页面 — Bento Grid布局，Dark Glassmorphism风格
// Pos: app/dashboard/page.tsx - Dashboard看板主页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api/client";
import { StatsCard } from "@/components/common/stats-card";
import { GlassCard } from "@/components/common/glass-card";
import { useWatchlistStore, type WatchItem } from "@/lib/stores/watchlist-store";
import { usePortfolioStore, type Holding } from "@/lib/stores/portfolio-store";
import {
  TrendingUp,
  TrendingDown,
  Newspaper,
  Bot,
  Send,
  Star,
  PieChart,
  ArrowRight,
  RefreshCw,
  Plus,
  ExternalLink,
} from "lucide-react";

/* ---------- 类型定义 ---------- */

interface IndexQuote {
  name: string;
  code: string;
  price: number;
  change_pct: number;
}

interface MarketIndicesResponse {
  indices: IndexQuote[];
}

interface NewsItem {
  title: string;
  content?: string;
  publish_time?: string;
  source?: string;
}

interface NewsResponse {
  success: boolean;
  news: NewsItem[];
}

interface WatchQuote extends WatchItem {
  price?: number;
  change_pct?: number;
  loading?: boolean;
}

/* ---------- 工具函数 ---------- */

function formatTime(timeStr?: string): string {
  if (!timeStr) return "";
  try {
    const d = new Date(timeStr);
    if (isNaN(d.getTime())) return timeStr.slice(0, 16);
    return `${(d.getMonth() + 1).toString().padStart(2, "0")}-${d.getDate().toString().padStart(2, "0")} ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
  } catch {
    return timeStr.slice(0, 16);
  }
}

/* ---------- 主组件 ---------- */

export default function DashboardPage() {
  const router = useRouter();

  // 市场指数
  const [indices, setIndices] = useState<IndexQuote[]>([]);
  const [indicesLoading, setIndicesLoading] = useState(true);

  // 新闻
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(true);

  // 自选股行情
  const watchItems = useWatchlistStore((s) => s.items);
  const [watchQuotes, setWatchQuotes] = useState<WatchQuote[]>([]);
  const [watchLoading, setWatchLoading] = useState(false);

  // 持仓
  const holdings = usePortfolioStore((s) => s.holdings);

  // AI分析输入
  const [aiInput, setAiInput] = useState("");

  // 自动刷新计时器
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  /* ---- 数据加载函数 ---- */

  const fetchIndices = useCallback(async () => {
    try {
      const res = await apiClient.get<MarketIndicesResponse>("/api/market_indices");
      if (res?.indices?.length) {
        setIndices(res.indices);
      }
    } catch {
      // 静默失败，保留上次数据
    } finally {
      setIndicesLoading(false);
      setLastRefresh(new Date());
    }
  }, []);

  const fetchNews = useCallback(async () => {
    try {
      const res = await apiClient.get<NewsResponse>("/api/latest_news", {
        limit: "5",
        days: "1",
      });
      if (res?.success && res.news?.length) {
        setNews(res.news.slice(0, 5));
      }
    } catch {
      // 静默
    } finally {
      setNewsLoading(false);
    }
  }, []);

  const fetchWatchQuotes = useCallback(async () => {
    if (!watchItems.length) {
      setWatchQuotes([]);
      return;
    }
    setWatchLoading(true);

    const results: WatchQuote[] = await Promise.all(
      watchItems.map(async (item) => {
        try {
          const res = await apiClient.get<{
            data?: { dates?: string[]; close?: number[]; change_pct?: number[] };
          }>("/api/stock_data", {
            stock_code: item.code,
            period: "1m",
          });
          const data = res?.data;
          if (data?.close?.length) {
            const lastIdx = data.close.length - 1;
            return {
              ...item,
              price: data.close[lastIdx],
              change_pct: data.change_pct?.[lastIdx] ?? 0,
            };
          }
          return { ...item };
        } catch {
          return { ...item };
        }
      })
    );

    setWatchQuotes(results);
    setWatchLoading(false);
  }, [watchItems]);

  /* ---- 初始化 + 自动刷新 ---- */

  useEffect(() => {
    fetchIndices();
    fetchNews();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchWatchQuotes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [watchItems]);

  useEffect(() => {
    // 30秒自动刷新指数
    refreshTimerRef.current = setInterval(fetchIndices, 30000);
    return () => {
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
  }, [fetchIndices]);

  /* ---- 操作 ---- */

  const handleAiSubmit = () => {
    const q = aiInput.trim();
    if (!q) return;
    // 跳转到首页并带上查询参数
    router.push(`/?q=${encodeURIComponent(q)}`);
  };

  const handleAnalyze = (code: string) => {
    router.push(`/?q=${encodeURIComponent(`分析 ${code}`)}`);
  };

  const handleRefresh = () => {
    setIndicesLoading(true);
    fetchIndices();
    fetchWatchQuotes();
    fetchNews();
  };

  /* ---- 指数图标 ---- */
  const getIndexIcon = (changePct: number) =>
    changePct >= 0 ? (
      <TrendingUp className="h-4 w-4 text-[#EF4444]" />
    ) : (
      <TrendingDown className="h-4 w-4 text-[#10B981]" />
    );

  /* ---- 持仓统计 ---- */
  const totalCost = holdings.reduce((sum, h) => sum + h.costPrice * h.shares, 0);
  const totalMarket = holdings.reduce(
    (sum, h) => sum + (h.currentPrice ?? h.costPrice) * h.shares,
    0
  );
  const totalPnL = totalMarket - totalCost;
  const totalPnLPct = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0;

  /* ========== 渲染 ========== */

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* ---- 页头 ---- */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#F0F0F5]">
              Dashboard · 投资看板
            </h1>
            <p className="text-xs text-[#8888A0] mt-0.5">
              {lastRefresh
                ? `最后刷新 ${lastRefresh.toLocaleTimeString("zh-CN")}`
                : "加载中..."}
            </p>
          </div>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.08] rounded-lg text-[#8888A0] hover:text-[#F0F0F5] transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${indicesLoading ? "animate-spin" : ""}`} />
            刷新
          </button>
        </div>

        {/* ---- Bento Grid ---- */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* ========== 1. 市场概览 (占2列) ========== */}
          <div className="md:col-span-2 lg:col-span-2">
            <GlassCard padding="lg" hover={false}>
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="h-4 w-4 text-[#6B5EE4]" />
                <h2 className="text-sm font-semibold text-[#F0F0F5]">市场概览</h2>
              </div>

              {indicesLoading && indices.length === 0 ? (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className="h-24 rounded-xl bg-white/[0.03] animate-pulse"
                    />
                  ))}
                </div>
              ) : indices.length > 0 ? (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {indices.map((idx) => (
                    <StatsCard
                      key={idx.code}
                      label={idx.name}
                      value={idx.price}
                      change={idx.change_pct}
                      format="number"
                      icon={getIndexIcon(idx.change_pct)}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-[#8888A0] text-center py-6">
                  暂无指数数据
                </p>
              )}
            </GlassCard>
          </div>

          {/* ========== 2. AI快速分析入口 ========== */}
          <div className="lg:col-span-1">
            <GlassCard padding="lg" hover={false} glow="ai" className="h-full">
              <div className="flex items-center gap-2 mb-4">
                <Bot className="h-4 w-4 text-[#6B5EE4]" />
                <h2 className="text-sm font-semibold text-[#F0F0F5]">
                  AI 快速分析
                </h2>
              </div>
              <p className="text-xs text-[#8888A0] mb-4">
                输入股票代码或问题，一键启动AI分析
              </p>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={aiInput}
                  onChange={(e) => setAiInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAiSubmit()}
                  placeholder="如：600519、分析比亚迪..."
                  className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#F0F0F5] placeholder:text-[#8888A0]/60 focus:outline-none focus:border-[#6B5EE4]/50 focus:ring-1 focus:ring-[#6B5EE4]/20 transition-colors"
                />
                <button
                  onClick={handleAiSubmit}
                  disabled={!aiInput.trim()}
                  className="px-3 py-2 bg-[#6B5EE4] hover:bg-[#5A4ED3] disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-white text-sm transition-colors"
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>

              <div className="flex flex-wrap gap-1.5 mt-3">
                {["600519", "300750", "000858", "688981"].map((code) => (
                  <button
                    key={code}
                    onClick={() => {
                      setAiInput(`分析 ${code}`);
                      router.push(`/?q=${encodeURIComponent(`分析 ${code}`)}`);
                    }}
                    className="px-2 py-1 text-[10px] bg-white/[0.04] border border-white/[0.06] rounded-md text-[#8888A0] hover:text-[#F0F0F5] hover:bg-white/[0.08] transition-colors"
                  >
                    {code}
                  </button>
                ))}
              </div>
            </GlassCard>
          </div>

          {/* ========== 3. 自选股行情 ========== */}
          <div className="md:col-span-1 lg:col-span-2">
            <GlassCard padding="lg" hover={false} className="h-full">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Star className="h-4 w-4 text-amber-400" />
                  <h2 className="text-sm font-semibold text-[#F0F0F5]">
                    自选股行情
                  </h2>
                </div>
                <button
                  onClick={() => router.push("/watchlist")}
                  className="flex items-center gap-1 text-[10px] text-[#8888A0] hover:text-[#6B5EE4] transition-colors"
                >
                  管理 <ExternalLink className="h-3 w-3" />
                </button>
              </div>

              {watchItems.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <Star className="h-8 w-8 text-[#8888A0]/30 mb-2" />
                  <p className="text-sm text-[#8888A0]">添加自选股开始追踪</p>
                  <button
                    onClick={() => router.push("/watchlist")}
                    className="mt-2 flex items-center gap-1 text-xs text-[#6B5EE4] hover:underline"
                  >
                    <Plus className="h-3 w-3" /> 添加自选
                  </button>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-white/[0.06] text-[#8888A0]">
                        <th className="text-left py-2 font-medium">代码</th>
                        <th className="text-left py-2 font-medium">名称</th>
                        <th className="text-right py-2 font-medium">最新价</th>
                        <th className="text-right py-2 font-medium">涨跌幅</th>
                        <th className="text-right py-2 font-medium">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(watchQuotes.length ? watchQuotes : watchItems).map(
                        (item) => {
                          const q = item as WatchQuote;
                          const pct = q.change_pct;
                          const pctColor =
                            pct !== undefined
                              ? pct >= 0
                                ? "text-[#EF4444]"
                                : "text-[#10B981]"
                              : "text-[#8888A0]";
                          return (
                            <tr
                              key={item.code}
                              className="border-b border-white/[0.04] hover:bg-white/[0.04] transition-colors"
                            >
                              <td className="py-2.5 font-mono text-[#F0F0F5]">
                                {item.code}
                              </td>
                              <td className="py-2.5 text-[#F0F0F5]">
                                {item.name}
                              </td>
                              <td className="py-2.5 text-right font-mono text-[#F0F0F5]">
                                {q.price !== undefined
                                  ? q.price.toFixed(2)
                                  : watchLoading
                                    ? "..."
                                    : "--"}
                              </td>
                              <td
                                className={`py-2.5 text-right font-mono ${pctColor}`}
                              >
                                {pct !== undefined
                                  ? `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`
                                  : watchLoading
                                    ? "..."
                                    : "--"}
                              </td>
                              <td className="py-2.5 text-right">
                                <button
                                  onClick={() => handleAnalyze(item.code)}
                                  className="text-[#6B5EE4] hover:text-[#8B7EFF] transition-colors"
                                  title="AI分析"
                                >
                                  <ArrowRight className="h-3.5 w-3.5 inline" />
                                </button>
                              </td>
                            </tr>
                          );
                        }
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </GlassCard>
          </div>

          {/* ========== 4. 最新新闻 ========== */}
          <div className="md:col-span-1 lg:col-span-1">
            <GlassCard padding="lg" hover={false} className="h-full">
              <div className="flex items-center gap-2 mb-4">
                <Newspaper className="h-4 w-4 text-sky-400" />
                <h2 className="text-sm font-semibold text-[#F0F0F5]">
                  最新新闻
                </h2>
              </div>

              {newsLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div key={i} className="space-y-1.5">
                      <div className="h-3 w-full bg-white/[0.04] rounded animate-pulse" />
                      <div className="h-2.5 w-1/3 bg-white/[0.03] rounded animate-pulse" />
                    </div>
                  ))}
                </div>
              ) : news.length > 0 ? (
                <ul className="space-y-1">
                  {news.map((item, i) => (
                    <li
                      key={i}
                      className="group py-2 border-b border-white/[0.04] last:border-0 hover:bg-white/[0.04] rounded px-1.5 -mx-1.5 transition-colors cursor-default"
                    >
                      <p className="text-xs text-[#F0F0F5] leading-relaxed line-clamp-2 group-hover:text-white transition-colors">
                        {item.title}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        {item.source && (
                          <span className="text-[10px] text-[#8888A0]">
                            {item.source}
                          </span>
                        )}
                        <span className="text-[10px] text-[#8888A0]/60">
                          {formatTime(item.publish_time)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-[#8888A0] text-center py-6">
                  暂无新闻
                </p>
              )}
            </GlassCard>
          </div>

          {/* ========== 5. 持仓概览 (整行) ========== */}
          {holdings.length > 0 && (
            <div className="md:col-span-2 lg:col-span-3">
              <GlassCard padding="lg" hover={false}>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <PieChart className="h-4 w-4 text-emerald-400" />
                    <h2 className="text-sm font-semibold text-[#F0F0F5]">
                      持仓概览
                    </h2>
                  </div>
                  <button
                    onClick={() => router.push("/portfolio")}
                    className="flex items-center gap-1 text-[10px] text-[#8888A0] hover:text-[#6B5EE4] transition-colors"
                  >
                    详情 <ExternalLink className="h-3 w-3" />
                  </button>
                </div>

                {/* 持仓汇总卡片 */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  <StatsCard
                    label="持仓数量"
                    value={holdings.length}
                    format="number"
                    decimals={0}
                  />
                  <StatsCard
                    label="总市值"
                    value={totalMarket}
                    format="large"
                    decimals={2}
                  />
                  <StatsCard
                    label="总盈亏"
                    value={totalPnL}
                    format="large"
                    decimals={2}
                    change={totalPnLPct}
                  />
                  <StatsCard
                    label="收益率"
                    value={totalPnLPct}
                    format="percent"
                    decimals={2}
                  />
                </div>

                {/* 持仓列表 */}
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-white/[0.06] text-[#8888A0]">
                        <th className="text-left py-2 font-medium">代码</th>
                        <th className="text-left py-2 font-medium">名称</th>
                        <th className="text-right py-2 font-medium">持仓量</th>
                        <th className="text-right py-2 font-medium">成本价</th>
                        <th className="text-right py-2 font-medium">现价</th>
                        <th className="text-right py-2 font-medium">盈亏</th>
                      </tr>
                    </thead>
                    <tbody>
                      {holdings.map((h) => {
                        const curPrice = h.currentPrice ?? h.costPrice;
                        const pnl = (curPrice - h.costPrice) * h.shares;
                        const pnlPct =
                          h.costPrice > 0
                            ? ((curPrice - h.costPrice) / h.costPrice) * 100
                            : 0;
                        const pnlColor =
                          pnl >= 0 ? "text-[#EF4444]" : "text-[#10B981]";
                        return (
                          <tr
                            key={h.code}
                            className="border-b border-white/[0.04] hover:bg-white/[0.04] transition-colors"
                          >
                            <td className="py-2.5 font-mono text-[#F0F0F5]">
                              {h.code}
                            </td>
                            <td className="py-2.5 text-[#F0F0F5]">{h.name}</td>
                            <td className="py-2.5 text-right font-mono text-[#F0F0F5]">
                              {h.shares.toLocaleString()}
                            </td>
                            <td className="py-2.5 text-right font-mono text-[#F0F0F5]">
                              {h.costPrice.toFixed(2)}
                            </td>
                            <td className="py-2.5 text-right font-mono text-[#F0F0F5]">
                              {curPrice.toFixed(2)}
                            </td>
                            <td
                              className={`py-2.5 text-right font-mono ${pnlColor}`}
                            >
                              {pnl >= 0 ? "+" : ""}
                              {pnl.toFixed(2)} ({pnlPct >= 0 ? "+" : ""}
                              {pnlPct.toFixed(2)}%)
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
