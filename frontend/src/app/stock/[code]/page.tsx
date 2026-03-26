// Input: URL路由参数 code (股票代码)
// Output: 股票详情页面（头部信息 + Tab切换内容区：K线/基本面/资金流/新闻/风险）
// Pos: /stock/[code] 路由页面，对标fiscal.ai的Company详情页
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { use, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { ArrowLeft, Star, StarOff, Bot, Loader2 } from "lucide-react";
import { GlassCard } from "@/components/common/glass-card";
import { useWatchlistStore } from "@/lib/stores/watchlist-store";
import { apiClient } from "@/lib/api/client";

/* ---------- 动态加载 Artifact 组件 ---------- */
const CandlestickChartArtifact = dynamic(
  () =>
    import("@/components/artifacts/candlestick-chart").then((m) => ({
      default: m.CandlestickChartArtifact,
    })),
  { ssr: false, loading: () => <LoadingSkeleton label="K线图" /> }
);

const FundamentalScorecardArtifact = dynamic(
  () =>
    import("@/components/artifacts/fundamental-scorecard").then((m) => ({
      default: m.FundamentalScorecardArtifact,
    })),
  { ssr: false, loading: () => <LoadingSkeleton label="基本面" /> }
);

const CapitalFlowArtifact = dynamic(
  () =>
    import("@/components/artifacts/capital-flow-chart").then((m) => ({
      default: m.CapitalFlowArtifact,
    })),
  { ssr: false, loading: () => <LoadingSkeleton label="资金流" /> }
);

const NewsFeedArtifact = dynamic(
  () =>
    import("@/components/artifacts/news-feed").then((m) => ({
      default: m.NewsFeedArtifact,
    })),
  { ssr: false, loading: () => <LoadingSkeleton label="新闻" /> }
);

const RiskRadarArtifact = dynamic(
  () =>
    import("@/components/artifacts/risk-radar-chart").then((m) => ({
      default: m.RiskRadarArtifact,
    })),
  { ssr: false, loading: () => <LoadingSkeleton label="风险" /> }
);

/* ---------- 类型定义 ---------- */
type TabKey = "kline" | "fundamental" | "capital" | "news" | "risk";

interface TabDef {
  key: TabKey;
  label: string;
}

const TABS: TabDef[] = [
  { key: "kline", label: "K线" },
  { key: "fundamental", label: "基本面" },
  { key: "capital", label: "资金流" },
  { key: "news", label: "新闻" },
  { key: "risk", label: "风险" },
];

/* ---------- 加载骨架 ---------- */
function LoadingSkeleton({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <Loader2 className="h-8 w-8 animate-spin text-[#3737CC]/60" />
      <span className="text-sm text-white/40">加载{label}数据中…</span>
    </div>
  );
}

/* ---------- 主页面 ---------- */
export default function StockDetailPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = use(params);
  const router = useRouter();

  /* 自选股状态 */
  const { hasItem, addItem, removeItem } = useWatchlistStore();
  const isWatched = hasItem(code);

  /* 头部数据 */
  const [stockName, setStockName] = useState<string>("");
  const [latestPrice, setLatestPrice] = useState<number | null>(null);
  const [changePercent, setChangePercent] = useState<number | null>(null);

  /* Tab */
  const [activeTab, setActiveTab] = useState<TabKey>("kline");

  /* 各Tab数据 */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [klineData, setKlineData] = useState<any[] | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [fundamentalData, setFundamentalData] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [capitalData, setCapitalData] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [newsData, setNewsData] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [riskData, setRiskData] = useState<any>(null);

  /* 加载状态 */
  const [loadingTab, setLoadingTab] = useState<Record<TabKey, boolean>>({
    kline: false,
    fundamental: false,
    capital: false,
    news: false,
    risk: false,
  });
  const [errorTab, setErrorTab] = useState<Record<TabKey, string | null>>({
    kline: null,
    fundamental: null,
    capital: null,
    news: null,
    risk: null,
  });

  /* ---------- 数据获取 ---------- */

  // K线（同时提取头部价格）
  const fetchKline = useCallback(async () => {
    if (klineData) return;
    setLoadingTab((p) => ({ ...p, kline: true }));
    setErrorTab((p) => ({ ...p, kline: null }));
    try {
      const res = await apiClient.get<{ data: Record<string, unknown>[] }>(
        "/api/stock_data",
        { stock_code: code, market_type: "A", period: "1y" }
      );
      const rows = res.data || [];
      setKlineData(rows);

      // 从最后一条提取价格信息
      if (rows.length > 0) {
        const last = rows[rows.length - 1];
        const prev = rows.length > 1 ? rows[rows.length - 2] : null;
        const close = Number(last.close) || 0;
        setLatestPrice(close);
        if (prev) {
          const prevClose = Number(prev.close) || 0;
          if (prevClose > 0) {
            setChangePercent(
              Number((((close - prevClose) / prevClose) * 100).toFixed(2))
            );
          }
        }
        // 尝试提取名称（如果后端返回了name字段）
        if (last.name && typeof last.name === "string") {
          setStockName(last.name as string);
        }
      }
    } catch (e) {
      setErrorTab((p) => ({
        ...p,
        kline: e instanceof Error ? e.message : "获取K线数据失败",
      }));
    } finally {
      setLoadingTab((p) => ({ ...p, kline: false }));
    }
  }, [code, klineData]);

  // 基本面
  const fetchFundamental = useCallback(async () => {
    if (fundamentalData) return;
    setLoadingTab((p) => ({ ...p, fundamental: true }));
    setErrorTab((p) => ({ ...p, fundamental: null }));
    try {
      const res = await apiClient.post<Record<string, unknown>>(
        "/api/fundamental_analysis",
        { stock_code: code }
      );
      setFundamentalData(res);
      // 从基本面接口提取股票名称
      if (res.stock_name && typeof res.stock_name === "string") {
        setStockName(res.stock_name);
      }
    } catch (e) {
      setErrorTab((p) => ({
        ...p,
        fundamental: e instanceof Error ? e.message : "获取基本面数据失败",
      }));
    } finally {
      setLoadingTab((p) => ({ ...p, fundamental: false }));
    }
  }, [code, fundamentalData]);

  // 资金流
  const fetchCapital = useCallback(async () => {
    if (capitalData) return;
    setLoadingTab((p) => ({ ...p, capital: true }));
    setErrorTab((p) => ({ ...p, capital: null }));
    try {
      const res = await apiClient.get<Record<string, unknown>>(
        "/api/individual_fund_flow",
        { stock_code: code }
      );
      setCapitalData(res);
    } catch (e) {
      setErrorTab((p) => ({
        ...p,
        capital: e instanceof Error ? e.message : "获取资金流数据失败",
      }));
    } finally {
      setLoadingTab((p) => ({ ...p, capital: false }));
    }
  }, [code, capitalData]);

  // 新闻（通过AI分析接口获取——暂用enhanced_analysis，或可直接调analyze）
  const fetchNews = useCallback(async () => {
    if (newsData) return;
    setLoadingTab((p) => ({ ...p, news: true }));
    setErrorTab((p) => ({ ...p, news: null }));
    try {
      // 使用enhanced_analysis获取新闻，如果后端没有专门的新闻API
      const res = await apiClient.post<Record<string, unknown>>(
        "/api/enhanced_analysis",
        {
          stock_code: code,
          analysis_type: "news",
        }
      );
      setNewsData(res);
    } catch {
      // 新闻API可能不存在，设置空列表作为降级
      setNewsData({ items: [] });
      setErrorTab((p) => ({ ...p, news: "暂无新闻数据" }));
    } finally {
      setLoadingTab((p) => ({ ...p, news: false }));
    }
  }, [code, newsData]);

  // 风险
  const fetchRisk = useCallback(async () => {
    if (riskData) return;
    setLoadingTab((p) => ({ ...p, risk: true }));
    setErrorTab((p) => ({ ...p, risk: null }));
    try {
      const res = await apiClient.post<Record<string, unknown>>(
        "/api/risk_analysis",
        { stock_code: code, market_type: "A" }
      );
      setRiskData(res);
    } catch (e) {
      setErrorTab((p) => ({
        ...p,
        risk: e instanceof Error ? e.message : "获取风险数据失败",
      }));
    } finally {
      setLoadingTab((p) => ({ ...p, risk: false }));
    }
  }, [code, riskData]);

  /* 初始加载K线 */
  useEffect(() => {
    fetchKline();
  }, [fetchKline]);

  /* 切tab时按需加载 */
  useEffect(() => {
    switch (activeTab) {
      case "kline":
        fetchKline();
        break;
      case "fundamental":
        fetchFundamental();
        break;
      case "capital":
        fetchCapital();
        break;
      case "news":
        fetchNews();
        break;
      case "risk":
        fetchRisk();
        break;
    }
  }, [activeTab, fetchKline, fetchFundamental, fetchCapital, fetchNews, fetchRisk]);

  /* ---------- AI分析跳转 ---------- */
  const handleAIAnalysis = () => {
    const msg = encodeURIComponent(`分析股票 ${code} ${stockName}`);
    router.push(`/?prefill=${msg}`);
  };

  /* ---------- 自选切换 ---------- */
  const toggleWatchlist = () => {
    if (isWatched) {
      removeItem(code);
    } else {
      addItem(code, stockName || code);
    }
  };

  /* ---------- 渲染内容区 ---------- */
  const renderTabContent = () => {
    const tab = activeTab;
    const loading = loadingTab[tab];
    const error = errorTab[tab];

    if (loading) return <LoadingSkeleton label={TABS.find((t) => t.key === tab)?.label || ""} />;
    if (error && !getTabData(tab)) {
      return (
        <div className="flex flex-col items-center justify-center py-20 gap-2">
          <span className="text-red-400/80 text-sm">{error}</span>
          <button
            className="text-xs text-[#3737CC] hover:underline"
            onClick={() => {
              // 清除缓存以重新加载
              switch (tab) {
                case "kline": setKlineData(null); break;
                case "fundamental": setFundamentalData(null); break;
                case "capital": setCapitalData(null); break;
                case "news": setNewsData(null); break;
                case "risk": setRiskData(null); break;
              }
            }}
          >
            点击重试
          </button>
        </div>
      );
    }

    switch (tab) {
      case "kline":
        return klineData ? (
          <CandlestickChartArtifact
            data={{
              stock_code: code,
              stock_name: stockName,
              ohlcv: klineData,
            }}
          />
        ) : null;
      case "fundamental":
        return fundamentalData ? (
          <FundamentalScorecardArtifact data={fundamentalData} />
        ) : null;
      case "capital":
        return capitalData ? (
          <CapitalFlowArtifact data={capitalData} />
        ) : null;
      case "news":
        return newsData ? <NewsFeedArtifact data={newsData} /> : null;
      case "risk":
        return riskData ? <RiskRadarArtifact data={riskData} /> : null;
      default:
        return null;
    }
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getTabData = (tab: TabKey): any => {
    switch (tab) {
      case "kline": return klineData;
      case "fundamental": return fundamentalData;
      case "capital": return capitalData;
      case "news": return newsData;
      case "risk": return riskData;
    }
  };

  /* ---------- 涨跌颜色 ---------- */
  const priceColor =
    changePercent === null
      ? "text-white/70"
      : changePercent >= 0
        ? "text-red-400"
        : "text-green-400";

  const changeStr =
    changePercent !== null
      ? `${changePercent >= 0 ? "+" : ""}${changePercent}%`
      : "";

  /* ---------- AI智能提示 ---------- */
  const getAiHint = (): { text: string; color: string; bg: string } | null => {
    if (changePercent === null) return null;
    if (changePercent > 3) return { text: "大幅上涨，注意追高风险", color: "#EF4444", bg: "rgba(239,68,68,0.12)" };
    if (changePercent >= 1) return { text: "温和上涨", color: "#F59E0B", bg: "rgba(245,158,11,0.12)" };
    if (changePercent < -3) return { text: "大幅下跌，关注支撑位", color: "#10B981", bg: "rgba(16,185,129,0.12)" };
    if (changePercent <= -1) return { text: "小幅调整", color: "#6B7280", bg: "rgba(107,114,128,0.12)" };
    return { text: "横盘整理", color: "#8888A0", bg: "rgba(136,136,160,0.12)" };
  };
  const aiHint = getAiHint();

  /* ---------- JSX ---------- */
  return (
    <div className="min-h-screen w-full px-4 py-4 md:px-8 md:py-6 space-y-4 max-w-7xl mx-auto">
      {/* ======= 头部 ======= */}
      <GlassCard padding="md" hover={false} glow="brand">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {/* 左：返回 + 股票信息 */}
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => router.back()}
              className="flex items-center justify-center h-9 w-9 rounded-xl bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.08] transition-colors shrink-0"
              aria-label="返回"
            >
              <ArrowLeft className="h-4 w-4 text-white/60" />
            </button>

            <div className="flex items-baseline gap-2 min-w-0 flex-wrap">
              <span className="text-lg font-bold text-white tracking-wide font-mono">
                {code}
              </span>
              {stockName && (
                <span className="text-base text-white/70 truncate">
                  {stockName}
                </span>
              )}
            </div>

            {/* 价格 */}
            {latestPrice !== null && (
              <div className="flex items-baseline gap-2 ml-2">
                <span className={`text-xl font-bold tabular-nums ${priceColor}`}>
                  ¥{latestPrice.toFixed(2)}
                </span>
                {changeStr && (
                  <span className={`text-sm font-medium ${priceColor}`}>
                    {changeStr}
                  </span>
                )}
                {aiHint && (
                  <span
                    className="text-[10px] font-medium px-2 py-0.5 rounded-full ml-1 whitespace-nowrap"
                    style={{ color: aiHint.color, backgroundColor: aiHint.bg }}
                  >
                    {aiHint.text}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* 右：操作按钮 */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={toggleWatchlist}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-all border ${
                isWatched
                  ? "bg-yellow-500/15 border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/25"
                  : "bg-white/[0.06] border-white/[0.08] text-white/50 hover:bg-white/[0.12] hover:text-yellow-400"
              }`}
            >
              {isWatched ? (
                <Star className="h-4 w-4 fill-current" />
              ) : (
                <StarOff className="h-4 w-4" />
              )}
              <span>{isWatched ? "已自选" : "自选"}</span>
            </button>

            <button
              onClick={handleAIAnalysis}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-[#3737CC]/15 border border-[#3737CC]/30 text-[#3737CC] hover:bg-[#3737CC]/25 transition-all"
            >
              <Bot className="h-4 w-4" />
              <span>AI分析</span>
            </button>
          </div>
        </div>
      </GlassCard>

      {/* ======= Tab 切换栏 ======= */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-hide">
        {TABS.map((tab) => {
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`relative px-4 py-2 text-sm font-medium whitespace-nowrap transition-all duration-200 rounded-lg ${
                active
                  ? "text-[#3737CC] bg-[#3737CC]/10"
                  : "text-white/50 hover:bg-white/[0.06] hover:text-white/70"
              }`}
            >
              {tab.label}
              {/* 底部品牌色指示线 — 带滑动过渡 */}
              <span
                className={`absolute bottom-0 left-1/2 -translate-x-1/2 h-0.5 rounded-full bg-[#3737CC] transition-all duration-300 ${
                  active ? "w-4 opacity-100" : "w-0 opacity-0"
                }`}
              />
            </button>
          );
        })}
      </div>

      {/* ======= 内容区 ======= */}
      <GlassCard padding="lg" hover={false} className="min-h-[400px]">
        {renderTabContent()}
      </GlassCard>
    </div>
  );
}
