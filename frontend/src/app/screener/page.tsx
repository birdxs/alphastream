// Input: 用户筛选条件（市场/板块/PE/市值/ROE/涨跌幅）
// Output: 选股器页面 — 筛选条件 + 结果表格，Dark Glassmorphism风格
// Pos: app/screener/page.tsx - 选股器主页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api/client";
import { useStockNames } from "@/lib/hooks/use-stock-names";
import { useStockPrices } from "@/lib/hooks/use-stock-prices";
import { GlassCard } from "@/components/common/glass-card";
import {
  Filter,
  RotateCcw,
  Search,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  Loader2,
  AlertCircle,
} from "lucide-react";

/* ---------- 类型定义 ---------- */

interface StockItem {
  code: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  pe: number | null;
  market_cap: number | null;
  roe: number | null;
}

interface BoardStocksResponse {
  stock_list: string[];
  count: number;
  index_name: string;
}

interface FilterState {
  market: string;
  board: string;
  peMin: string;
  peMax: string;
  marketCap: string;
  roeMin: string;
  changeMin: string;
  changeMax: string;
}

const DEFAULT_FILTERS: FilterState = {
  market: "a",
  board: "hs300",
  peMin: "",
  peMax: "",
  marketCap: "all",
  roeMin: "",
  changeMin: "",
  changeMax: "",
};

/* ---------- 常量 ---------- */

const MARKET_OPTIONS = [
  { value: "a", label: "A股" },
  { value: "hk", label: "港股" },
  { value: "us", label: "美股" },
];

const BOARD_OPTIONS = [
  { value: "hs300", label: "沪深300" },
  { value: "zz500", label: "中证500" },
  { value: "zz1000", label: "中证1000" },
  { value: "kc50", label: "科创50" },
  { value: "kc100", label: "科创100" },
  { value: "bj50", label: "北证50" },
];

const MARKET_CAP_OPTIONS = [
  { value: "all", label: "全部" },
  { value: "small", label: "小盘 (<50亿)" },
  { value: "mid", label: "中盘 (50-200亿)" },
  { value: "large", label: "大盘 (>200亿)" },
];

/* ---------- 工具函数 ---------- */

function formatMarketCap(cap: number | null): string {
  if (cap === null || cap === undefined) return "--";
  if (cap >= 1e8) return `${(cap / 1e8).toFixed(0)}亿`;
  if (cap >= 1e4) return `${(cap / 1e4).toFixed(1)}万`;
  return cap.toFixed(0);
}

function formatNumber(val: number | null, digits = 2): string {
  if (val === null || val === undefined || isNaN(val)) return "--";
  return val.toFixed(digits);
}

function changeColor(val: number | null): string {
  if (val === null || val === undefined) return "text-muted-foreground";
  if (val > 0) return "text-rose-400";
  if (val < 0) return "text-emerald-400";
  return "text-muted-foreground";
}

/* ---------- 子组件: 玻璃输入框 ---------- */

function GlassInput({
  value,
  onChange,
  placeholder,
  type = "text",
  className = "",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  className?: string;
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`bg-foreground/[0.04] dark:bg-white/[0.04] border border-foreground/[0.1] dark:border-white/[0.1] rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-[#3737CC]/60 focus:ring-1 focus:ring-[#3737CC]/30 transition-colors ${className}`}
    />
  );
}

function GlassSelect({
  value,
  onChange,
  options,
  className = "",
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  className?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`bg-foreground/[0.04] dark:bg-white/[0.04] border border-foreground/[0.1] dark:border-white/[0.1] rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-[#3737CC]/60 focus:ring-1 focus:ring-[#3737CC]/30 transition-colors appearance-none cursor-pointer ${className}`}
      style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.4)' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`,
        backgroundRepeat: "no-repeat",
        backgroundPosition: "right 10px center",
        paddingRight: "32px",
      }}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value} className="bg-[#0a0a1a] text-white">
          {opt.label}
        </option>
      ))}
    </select>
  );
}

/* ---------- 主组件 ---------- */

export default function ScreenerPage() {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);

  useEffect(() => {
    document.title = "选股器 - AI金融分析";
  }, []);
  // FIX-E2: 挂载时自动加载默认板块（HS300）首屏数据，避免空白
  const [results, setResults] = useState<StockItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(true);

  // 批量补全名称 + 价格/涨跌幅（后端 /api/board_stocks 仅返回代码）
  const resultCodes = useMemo(() => results.slice(0, 20).map(s => s.code), [results]);
  const resolvedNames = useStockNames(resultCodes);
  const resolvedPrices = useStockPrices(resultCodes);
  const [profiles, setProfiles] = useState<Record<string, { pe?: number | null; market_cap?: number | null; roe?: number | null }>>({});

  // 批量拉取 PE/市值/ROE：遍历 resultCodes 调 /api/stock_profile（限流5并发）
  useEffect(() => {
    if (resultCodes.length === 0) return;
    let cancelled = false;
    (async () => {
      const missing = resultCodes.filter(c => !profiles[c]);
      const CONCURRENCY = 5;
      for (let i = 0; i < missing.length; i += CONCURRENCY) {
        const batch = missing.slice(i, i + CONCURRENCY);
        const rs = await Promise.all(batch.map(async (code) => {
          try {
            const p = await apiClient.get<{ pe_ttm?: number | null; market_cap?: number | null; roe?: number | null }>(
              "/api/stock_profile", { stock_code: code }
            );
            return [code, { pe: p.pe_ttm ?? null, market_cap: p.market_cap ?? null, roe: p.roe ?? null }] as const;
          } catch { return [code, { pe: null, market_cap: null, roe: null }] as const; }
        }));
        if (cancelled) return;
        setProfiles(prev => {
          const next = { ...prev };
          rs.forEach(([k, v]) => { next[k] = v; });
          return next;
        });
      }
    })();
    return () => { cancelled = true; };
  }, [resultCodes.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateFilter = useCallback((key: keyof FilterState, val: string) => {
    setFilters((prev) => ({ ...prev, [key]: val }));
  }, []);

  const handleReset = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
    setResults([]);
    setSearched(false);
    setError(null);
  }, []);

  const handleSearch = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSearched(true);

    try {
      // 从后端获取板块成分股列表
      const data = await apiClient.get<BoardStocksResponse>("/api/board_stocks", {
        board: filters.board,
      });

      // 将成分股列表转为StockItem（后端只返回代码列表，其余字段暂不可用）
      const stocks: StockItem[] = (data.stock_list || []).map((code: string) => ({
        code,
        name: code, // 仅有代码，名称显示代码
        price: null,
        change_pct: null,
        pe: null,
        market_cap: null,
        roe: null,
      }));

      // 前端本地过滤（基于可用字段）
      const filtered = stocks.filter((s) => {
        if (filters.peMin && s.pe !== null && s.pe < parseFloat(filters.peMin)) return false;
        if (filters.peMax && s.pe !== null && s.pe > parseFloat(filters.peMax)) return false;
        if (filters.roeMin && s.roe !== null && s.roe < parseFloat(filters.roeMin)) return false;
        if (filters.changeMin && s.change_pct !== null && s.change_pct < parseFloat(filters.changeMin))
          return false;
        if (filters.changeMax && s.change_pct !== null && s.change_pct > parseFloat(filters.changeMax))
          return false;
        if (filters.marketCap !== "all" && s.market_cap !== null) {
          const cap = s.market_cap;
          if (filters.marketCap === "small" && cap >= 5e9) return false;
          if (filters.marketCap === "mid" && (cap < 5e9 || cap >= 2e10)) return false;
          if (filters.marketCap === "large" && cap < 2e10) return false;
        }
        return true;
      });

      setResults(filtered);
    } catch (err) {
      setError(err instanceof Error ? err.message : "筛选请求失败");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // FIX-E2: 挂载后用默认板块首屏加载一次
  useEffect(() => {
    handleSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-full p-4 md:p-6 pb-16 space-y-4 max-w-7xl mx-auto">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-[#3737CC] rounded-xl p-2.5 flex items-center justify-center">
            <Filter className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold">选股器</h1>
            <p className="text-xs text-muted-foreground mt-0.5">按条件筛选股票</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-foreground/[0.1] dark:border-white/[0.1] text-muted-foreground hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] hover:text-foreground transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            重置
          </button>
          <button
            onClick={handleSearch}
            disabled={loading}
            className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-[#3737CC] hover:bg-[#2929aa] text-white font-medium transition-colors disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            搜索
          </button>
        </div>
      </div>

      {/* 筛选条件 */}
      <GlassCard hover={false} padding="md">
        <button
          onClick={() => setFiltersOpen(!filtersOpen)}
          className="flex items-center justify-between w-full text-left md:hidden"
        >
          <span className="text-sm font-medium text-muted-foreground">筛选条件</span>
          {filtersOpen ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        <div className={`${filtersOpen ? "block" : "hidden"} md:block`}>
          <p className="text-sm font-medium text-muted-foreground mb-3 hidden md:block">筛选条件</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mt-3 md:mt-0">
            {/* 市场 */}
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">市场</label>
              <GlassSelect
                value={filters.market}
                onChange={(v) => updateFilter("market", v)}
                options={MARKET_OPTIONS}
                className="w-full"
              />
            </div>

            {/* 板块 */}
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">板块</label>
              <GlassSelect
                value={filters.board}
                onChange={(v) => updateFilter("board", v)}
                options={BOARD_OPTIONS}
                className="w-full"
              />
            </div>

            {/* PE范围 */}
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">PE范围</label>
              <div className="flex items-center gap-2">
                <GlassInput
                  type="number"
                  value={filters.peMin}
                  onChange={(v) => updateFilter("peMin", v)}
                  placeholder="最低"
                  className="w-full"
                />
                <span className="text-muted-foreground text-xs shrink-0">~</span>
                <GlassInput
                  type="number"
                  value={filters.peMax}
                  onChange={(v) => updateFilter("peMax", v)}
                  placeholder="最高"
                  className="w-full"
                />
              </div>
            </div>

            {/* 市值范围 */}
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">市值范围</label>
              <GlassSelect
                value={filters.marketCap}
                onChange={(v) => updateFilter("marketCap", v)}
                options={MARKET_CAP_OPTIONS}
                className="w-full"
              />
            </div>

            {/* ROE最低 */}
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">ROE最低 (%)</label>
              <GlassInput
                type="number"
                value={filters.roeMin}
                onChange={(v) => updateFilter("roeMin", v)}
                placeholder="例: 10"
                className="w-full"
              />
            </div>

            {/* 涨跌幅范围 */}
            <div className="space-y-1.5 sm:col-span-2 lg:col-span-1">
              <label className="text-xs text-muted-foreground">涨跌幅范围 (%)</label>
              <div className="flex items-center gap-2">
                <GlassInput
                  type="number"
                  value={filters.changeMin}
                  onChange={(v) => updateFilter("changeMin", v)}
                  placeholder="-10"
                  className="w-full"
                />
                <span className="text-muted-foreground text-xs shrink-0">~</span>
                <GlassInput
                  type="number"
                  value={filters.changeMax}
                  onChange={(v) => updateFilter("changeMax", v)}
                  placeholder="+10"
                  className="w-full"
                />
              </div>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* 筛选结果 */}
      <GlassCard hover={false} padding="md">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-medium text-muted-foreground">
            筛选结果
            {searched && !loading && (
              <span className="ml-2 text-foreground">
                找到 <span className="font-mono text-[#6b5ee4]">{results.length}</span> 只股票
              </span>
            )}
          </p>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm mb-3">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {/* 加载中 */}
        {loading && (
          <div className="flex items-center justify-center py-16 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin mr-2" />
            正在筛选...
          </div>
        )}

        {/* 未搜索 */}
        {!searched && !loading && (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <Filter className="h-10 w-10 mb-3 opacity-30" />
            <p className="text-sm">设置筛选条件后点击搜索</p>
          </div>
        )}

        {/* 无结果 */}
        {searched && !loading && results.length === 0 && !error && (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <Search className="h-10 w-10 mb-3 opacity-30" />
            <p className="text-sm">未找到符合条件的股票</p>
            <p className="text-xs mt-1 opacity-60">尝试调整筛选条件</p>
          </div>
        )}

        {/* 结果表格 */}
        {searched && !loading && results.length > 0 && (
          <div className="overflow-x-auto -mx-4 px-4">
            <table className="w-full text-sm min-w-[640px]">
              <thead>
                <tr className="bg-foreground/[0.04] dark:bg-white/[0.04]">
                  <th className="text-left font-medium text-muted-foreground px-3 py-2.5 rounded-l-lg">代码</th>
                  <th className="text-left font-medium text-muted-foreground px-3 py-2.5">名称</th>
                  <th className="text-right font-medium text-muted-foreground px-3 py-2.5 font-mono">最新价</th>
                  <th className="text-right font-medium text-muted-foreground px-3 py-2.5 font-mono">涨跌幅</th>
                  <th className="text-right font-medium text-muted-foreground px-3 py-2.5 font-mono">PE</th>
                  <th className="text-right font-medium text-muted-foreground px-3 py-2.5 font-mono">市值</th>
                  <th className="text-center font-medium text-muted-foreground px-3 py-2.5 rounded-r-lg">操作</th>
                </tr>
              </thead>
              <tbody>
                {results.map((stock) => {
                  const price = resolvedPrices[stock.code]?.price ?? stock.price;
                  const changePct = resolvedPrices[stock.code]?.change_pct ?? stock.change_pct;
                  const pe = profiles[stock.code]?.pe ?? stock.pe;
                  const marketCap = profiles[stock.code]?.market_cap ?? stock.market_cap;
                  return (
                  <tr
                    key={stock.code}
                    className="border-b border-foreground/[0.06] dark:border-white/[0.06] hover:bg-foreground/[0.04] dark:hover:bg-white/[0.04] transition-colors"
                  >
                    <td className="px-3 py-2.5 font-mono text-xs">{stock.code}</td>
                    <td className="px-3 py-2.5">{resolvedNames[stock.code] && resolvedNames[stock.code] !== stock.code ? resolvedNames[stock.code] : (stock.name !== stock.code ? stock.name : "--")}</td>
                    <td className="px-3 py-2.5 text-right font-mono">{formatNumber(price)}</td>
                    <td className={`px-3 py-2.5 text-right font-mono ${changeColor(changePct)}`}>
                      {changePct !== null && changePct !== undefined
                        ? `${changePct > 0 ? "+" : ""}${changePct.toFixed(2)}%`
                        : "--"}
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono">{formatNumber(pe)}</td>
                    <td className="px-3 py-2.5 text-right font-mono">{formatMarketCap(marketCap)}</td>
                    <td className="px-3 py-2.5 text-center">
                      <Link
                        href={`/stock/${stock.code}`}
                        className="inline-flex items-center gap-1 text-xs text-[#6b5ee4] hover:text-[#8578f0] transition-colors"
                      >
                        详情
                        <ArrowRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
