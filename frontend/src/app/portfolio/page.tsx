// Input: portfolio-store 持久化持仓 + /api/portfolio_risk 诊断 + 用户操作
// Output: 投资组合页：添加/删除/观察标签 + 风险诊断摘要（Skeleton/— 无数据时）
// Pos: /portfolio 路由页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useMemo, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Plus,
  Trash2,
  TrendingUp,
  TrendingDown,
  BarChart3,
  MessageSquare,
  Briefcase,
  Sparkles,
  Eye,
  Shield,
  AlertTriangle,
} from "lucide-react";
import { GlassCard } from "@/components/common/glass-card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePortfolioStore, type HoldingMode } from "@/lib/stores/portfolio-store";
import { useStockNames } from "@/lib/hooks/use-stock-names";
import { useStockPrices } from "@/lib/hooks/use-stock-prices";
import { formatPrice, formatPercent, getPriceColorClass } from "@/lib/utils/format";
import { apiClient, extractData } from "@/lib/api/client";
import Link from "next/link";

/** 诊断摘要（仅用真实 API；字段缺失显示 —，禁止假数） */
interface PortfolioDiagnosisView {
  riskLevel: string | null;
  riskScore: number | null;
  maxSector: string | null;
  maxSectorWeight: number | null;
  defensiveWeight: number | null;
  unknownShare: number | null;
  homogenized: boolean | null;
  hints: string[];
}

function fmtPctOrDash(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtNumOrDash(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export default function PortfolioPage() {
  const { holdings, addHolding, removeHolding, setHoldingMode } = usePortfolioStore();
  const codes = useMemo(() => holdings.map((h) => h.code), [holdings]);
  const existing = useMemo(
    () => Object.fromEntries(holdings.map((h) => [h.code, h.name])),
    [holdings]
  );
  const resolvedNames = useStockNames(codes, existing);
  const livePrices = useStockPrices(codes);
  const displayName = (code: string, name: string) =>
    name && name !== code ? name : resolvedNames[code] || code;
  const priceOf = (h: { code: string; costPrice: number; currentPrice?: number }) =>
    livePrices[h.code]?.price ?? h.currentPrice ?? h.costPrice;

  const [showAdd, setShowAdd] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [newShares, setNewShares] = useState("");
  const [newCost, setNewCost] = useState("");
  const [newMode, setNewMode] = useState<HoldingMode>("live");
  const [formError, setFormError] = useState("");

  const [diagLoading, setDiagLoading] = useState(false);
  const [diagError, setDiagError] = useState(false);
  const [diagnosis, setDiagnosis] = useState<PortfolioDiagnosisView | null>(null);

  const totalValue = holdings.reduce((sum, h) => sum + priceOf(h) * h.shares, 0);
  const totalCost = holdings.reduce((sum, h) => sum + h.costPrice * h.shares, 0);
  const totalPnl = totalValue - totalCost;
  const totalReturn = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;

  const liveCount = holdings.filter((h) => (h.mode ?? "live") !== "watch").length;
  const watchCount = holdings.filter((h) => h.mode === "watch").length;

  const fetchDiagnosis = useCallback(async () => {
    // 诊断仅对 live 持仓做权重（观察仓不参与风险加权，避免误解）
    const live = holdings.filter((h) => (h.mode ?? "live") !== "watch");
    if (live.length === 0) {
      setDiagnosis(null);
      setDiagError(false);
      setDiagLoading(false);
      return;
    }
    const tv = live.reduce((s, h) => s + priceOf(h) * h.shares, 0);
    const portfolio = live.map((h) => {
      const mv = priceOf(h) * h.shares;
      return {
        stock_code: h.code,
        stock_name: displayName(h.code, h.name),
        weight: tv > 0 ? mv / tv : 1 / live.length,
        market_type: "A",
      };
    });
    setDiagLoading(true);
    setDiagError(false);
    try {
      const res = await apiClient.post<Record<string, unknown>>("/api/portfolio_risk", {
        portfolio,
      });
      const body = extractData(res) as Record<string, unknown>;
      if (!body || typeof body !== "object" || body.error) {
        setDiagnosis(null);
        setDiagError(true);
        return;
      }
      const sector = (body.sector_concentration || {}) as Record<string, unknown>;
      const nameOv = (body.name_overlap || {}) as Record<string, unknown>;
      const hints = Array.isArray(nameOv.hints)
        ? (nameOv.hints as unknown[]).filter((x): x is string => typeof x === "string")
        : [];
      setDiagnosis({
        riskLevel: typeof body.risk_level === "string" ? body.risk_level : null,
        riskScore:
          typeof body.portfolio_risk_score === "number" ? body.portfolio_risk_score : null,
        maxSector: typeof sector.max_sector === "string" ? sector.max_sector : null,
        maxSectorWeight:
          typeof sector.max_sector_weight === "number" ? sector.max_sector_weight : null,
        defensiveWeight:
          typeof body.defensive_weight === "number" ? body.defensive_weight : null,
        unknownShare:
          typeof body.unknown_industry_share === "number"
            ? body.unknown_industry_share
            : typeof sector.unknown_share === "number"
              ? sector.unknown_share
              : null,
        homogenized: typeof nameOv.homogenized === "boolean" ? nameOv.homogenized : null,
        hints,
      });
    } catch {
      setDiagnosis(null);
      setDiagError(true);
    } finally {
      setDiagLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- price/name helpers stable enough via holdings
  }, [holdings, livePrices, resolvedNames]);

  useEffect(() => {
    // 防抖：持仓变更后稍后再拉诊断
    const t = setTimeout(() => {
      void fetchDiagnosis();
    }, 400);
    return () => clearTimeout(t);
  }, [fetchDiagnosis]);

  const handleAdd = () => {
    setFormError("");
    if (!newCode || !/^\d{6}$/.test(newCode)) {
      setFormError("请输入6位股票代码");
      return;
    }
    if (!newShares || Number(newShares) <= 0) {
      setFormError("持股数量必须大于0");
      return;
    }
    if (!newCost || Number(newCost) <= 0) {
      setFormError("成本价必须大于0");
      return;
    }
    addHolding({
      code: newCode,
      name: newName && newName !== newCode ? newName : "",
      shares: Number(newShares),
      costPrice: Number(newCost),
      currentPrice: Number(newCost),
      mode: newMode,
    });
    setNewCode("");
    setNewName("");
    setNewShares("");
    setNewCost("");
    setNewMode("live");
    setShowAdd(false);
  };

  const toggleMode = (code: string, current?: HoldingMode) => {
    setHoldingMode(code, current === "watch" ? "live" : "watch");
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">投资组合</h1>
          <p className="text-xs text-muted-foreground dark:text-white/40 mt-1">
            实盘 {liveCount} · 观察 {watchCount}
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setShowAdd(!showAdd)}
          className="bg-foreground/[0.08] dark:bg-white/[0.08] border border-foreground/[0.12] dark:border-white/[0.12] hover:bg-foreground/[0.15] dark:hover:bg-white/[0.15] text-foreground"
        >
          <Plus className="h-4 w-4 mr-1" />
          添加持仓
        </Button>
      </div>

      {/* 组合概况 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <GlassCard padding="md">
          <p className="text-sm text-muted-foreground dark:text-white/50">总市值</p>
          <p className="text-2xl font-bold font-mono">&yen;{formatPrice(totalValue)}</p>
        </GlassCard>
        <GlassCard padding="md">
          <p className="text-sm text-muted-foreground dark:text-white/50">总盈亏</p>
          <p className={`text-2xl font-bold font-mono ${getPriceColorClass(totalPnl)}`}>
            {totalPnl >= 0 ? "+" : ""}
            {formatPrice(totalPnl)}
          </p>
        </GlassCard>
        <GlassCard padding="md">
          <p className="text-sm text-muted-foreground dark:text-white/50">收益率</p>
          <p
            className={`text-2xl font-bold font-mono flex items-center gap-1 ${getPriceColorClass(totalReturn)}`}
          >
            {totalReturn >= 0 ? (
              <TrendingUp className="h-5 w-5" />
            ) : (
              <TrendingDown className="h-5 w-5" />
            )}
            {formatPercent(totalReturn)}
          </p>
        </GlassCard>
      </div>

      {/* Sprint3 风险诊断摘要 */}
      <GlassCard padding="md">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-muted-foreground dark:text-white/60" />
            <h2 className="text-sm font-semibold">风险诊断</h2>
            <span className="text-[10px] text-muted-foreground dark:text-white/35">
              仅统计实盘持仓
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-xs h-7"
            onClick={() => void fetchDiagnosis()}
            disabled={liveCount === 0 || diagLoading}
          >
            刷新
          </Button>
        </div>

        {liveCount === 0 ? (
          <p className="text-sm text-muted-foreground dark:text-white/40">
            暂无实盘持仓，无法计算诊断（观察仓不参与加权）
          </p>
        ) : diagLoading && !diagnosis ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
          </div>
        ) : diagError && !diagnosis ? (
          <p className="text-sm text-muted-foreground dark:text-white/40 flex items-center gap-1">
            <AlertTriangle className="h-3.5 w-3.5" />
            诊断暂时不可用
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-lg bg-foreground/[0.03] dark:bg-white/[0.03] p-3">
                <p className="text-[11px] text-muted-foreground dark:text-white/45">风险等级</p>
                <p className="text-base font-semibold mt-0.5">
                  {diagnosis?.riskLevel ?? "—"}
                  {diagnosis?.riskScore != null ? (
                    <span className="text-xs font-mono text-muted-foreground ml-1">
                      ({fmtNumOrDash(diagnosis.riskScore)})
                    </span>
                  ) : null}
                </p>
              </div>
              <div className="rounded-lg bg-foreground/[0.03] dark:bg-white/[0.03] p-3">
                <p className="text-[11px] text-muted-foreground dark:text-white/45">
                  最大行业敞口
                </p>
                <p className="text-base font-semibold mt-0.5 truncate">
                  {diagnosis?.maxSector ?? "—"}
                </p>
                <p className="text-[11px] font-mono text-muted-foreground">
                  {fmtPctOrDash(diagnosis?.maxSectorWeight)}
                </p>
              </div>
              <div className="rounded-lg bg-foreground/[0.03] dark:bg-white/[0.03] p-3">
                <p className="text-[11px] text-muted-foreground dark:text-white/45">防御型占比</p>
                <p className="text-base font-semibold font-mono mt-0.5">
                  {fmtPctOrDash(diagnosis?.defensiveWeight)}
                </p>
              </div>
              <div className="rounded-lg bg-foreground/[0.03] dark:bg-white/[0.03] p-3">
                <p className="text-[11px] text-muted-foreground dark:text-white/45">
                  未知行业占比
                </p>
                <p className="text-base font-semibold font-mono mt-0.5">
                  {fmtPctOrDash(diagnosis?.unknownShare)}
                </p>
              </div>
            </div>
            {diagnosis?.homogenized ? (
              <div className="mt-3 text-xs text-amber-600 dark:text-amber-400/90 space-y-1">
                <p className="font-medium flex items-center gap-1">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  同质化提示
                </p>
                {(diagnosis.hints.length ? diagnosis.hints : ["存在同行业或多票主题重叠"]).map(
                  (h) => (
                    <p key={h} className="text-muted-foreground dark:text-white/50 pl-4">
                      · {h}
                    </p>
                  )
                )}
              </div>
            ) : diagnosis ? (
              <p className="mt-3 text-xs text-muted-foreground dark:text-white/40">
                未检测到明显同质化集中
              </p>
            ) : null}
          </>
        )}
      </GlassCard>

      {/* 添加表单 */}
      {showAdd && (
        <GlassCard padding="md">
          <div className="flex gap-2 items-end flex-wrap">
            <div className="flex-1 min-w-[120px]">
              <label htmlFor="stock-code" className="text-xs text-muted-foreground dark:text-white/50">
                股票代码
              </label>
              <Input
                id="stock-code"
                value={newCode}
                onChange={(e) => setNewCode(e.target.value)}
                placeholder="600519"
                className={`bg-foreground/[0.04] dark:bg-white/[0.04] border-foreground/[0.1] dark:border-white/[0.1] ${formError.includes("代码") ? "border-[#FF8767]" : ""}`}
              />
            </div>
            <div className="flex-1 min-w-[120px]">
              <label htmlFor="stock-name" className="text-xs text-muted-foreground dark:text-white/50">
                股票名称
              </label>
              <Input
                id="stock-name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="贵州茅台"
                className="bg-foreground/[0.04] dark:bg-white/[0.04] border-foreground/[0.1] dark:border-white/[0.1]"
              />
            </div>
            <div className="flex-1 min-w-[100px]">
              <label
                htmlFor="stock-shares"
                className="text-xs text-muted-foreground dark:text-white/50"
              >
                持股数量
              </label>
              <Input
                id="stock-shares"
                value={newShares}
                onChange={(e) => setNewShares(e.target.value)}
                placeholder="100"
                type="number"
                className={`bg-foreground/[0.04] dark:bg-white/[0.04] border-foreground/[0.1] dark:border-white/[0.1] ${formError.includes("数量") ? "border-[#FF8767]" : ""}`}
              />
            </div>
            <div className="flex-1 min-w-[100px]">
              <label htmlFor="stock-cost" className="text-xs text-muted-foreground dark:text-white/50">
                成本价
              </label>
              <Input
                id="stock-cost"
                value={newCost}
                onChange={(e) => setNewCost(e.target.value)}
                placeholder="1800"
                type="number"
                className={`bg-foreground/[0.04] dark:bg-white/[0.04] border-foreground/[0.1] dark:border-white/[0.1] ${formError.includes("成本") ? "border-[#FF8767]" : ""}`}
              />
            </div>
            <div className="min-w-[100px]">
              <label htmlFor="stock-mode" className="text-xs text-muted-foreground dark:text-white/50">
                类型
              </label>
              <select
                id="stock-mode"
                value={newMode}
                onChange={(e) => setNewMode(e.target.value === "watch" ? "watch" : "live")}
                className="w-full h-9 rounded-md bg-foreground/[0.04] dark:bg-white/[0.04] border border-foreground/[0.1] dark:border-white/[0.1] text-sm px-2"
              >
                <option value="live">实盘</option>
                <option value="watch">观察</option>
              </select>
            </div>
            <Button onClick={handleAdd} className="bg-[#3737CC] hover:bg-[#4545DD] text-white">
              添加
            </Button>
          </div>
          {formError && <p className="text-xs text-[#FF8767] mt-1">{formError}</p>}
        </GlassCard>
      )}

      {/* AI分析全部持仓 */}
      {holdings.length > 0 ? (
        <Link
          href={`/?q=${encodeURIComponent("分析我当前持仓的整体风险和优化建议，持仓列表：" + holdings.map((h) => h.code).join(","))}`}
          className="block"
        >
          <button className="w-full group relative overflow-hidden rounded-2xl px-6 py-4 bg-gradient-to-r from-[#3737CC] via-[#5A4ED3] to-[#6B5EE4] hover:from-[#4545DD] hover:via-[#6B5EE4] hover:to-[#8B7EFF] shadow-lg shadow-[#6B5EE4]/20 hover:shadow-xl hover:shadow-[#6B5EE4]/30 transition-all duration-300 flex items-center justify-center gap-3">
            <Sparkles className="h-5 w-5 text-white group-hover:rotate-12 transition-transform duration-300" />
            <span className="text-base font-semibold text-white">AI分析全部持仓</span>
            <span className="text-xs text-white/70">（{holdings.length}只）</span>
          </button>
        </Link>
      ) : (
        <button
          disabled
          className="w-full rounded-2xl px-6 py-4 bg-gradient-to-r from-[#3737CC]/40 via-[#5A4ED3]/40 to-[#6B5EE4]/40 flex items-center justify-center gap-3 cursor-not-allowed opacity-60"
          title="请先添加持仓"
        >
          <Sparkles className="h-5 w-5 text-white/70" />
          <span className="text-base font-semibold text-white/80">AI分析全部持仓</span>
          <span className="text-xs text-white/60">（请先添加持仓）</span>
        </button>
      )}

      {/* 持仓列表 */}
      <GlassCard padding="lg">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="h-4 w-4 text-muted-foreground dark:text-white/60" />
          <h2 className="text-sm font-semibold">持仓明细</h2>
        </div>
        <div className="space-y-2">
          {holdings.length === 0 ? (
            <div className="text-center py-12 space-y-4">
              <Briefcase className="h-12 w-12 text-muted-foreground dark:text-white/15 mx-auto" />
              <p className="text-muted-foreground dark:text-white/40">暂无持仓</p>
              <p className="text-sm text-muted-foreground dark:text-white/25">
                点击上方&ldquo;添加持仓&rdquo;开始管理您的投资组合
              </p>
            </div>
          ) : (
            holdings.map((h) => {
              const cp = priceOf(h);
              const pnl = (cp - h.costPrice) * h.shares;
              const pnlPct =
                h.costPrice > 0 ? ((cp - h.costPrice) / h.costPrice) * 100 : 0;
              const isWatch = h.mode === "watch";
              return (
                <div
                  key={h.code}
                  className="flex items-center justify-between p-3 rounded-xl bg-foreground/[0.03] dark:bg-white/[0.03] border border-foreground/[0.06] dark:border-white/[0.06] hover:bg-foreground/[0.07] dark:hover:bg-white/[0.07] transition-all duration-200"
                >
                  <div className="flex items-center gap-3">
                    <div>
                      <span className="font-medium">{displayName(h.code, h.name)}</span>
                      <Link
                        href={`/stock/${h.code}`}
                        className="text-xs text-[#6B5EE4] hover:underline ml-2 font-mono"
                        title="查看详情"
                      >
                        {h.code}
                      </Link>
                      {isWatch ? (
                        <span className="ml-2 inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                          <Eye className="h-3 w-3" />
                          观察
                        </span>
                      ) : (
                        <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-foreground/[0.06] dark:bg-white/[0.06] text-muted-foreground">
                          实盘
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 sm:gap-6 text-sm">
                    <div className="text-right">
                      <p className="font-mono">{h.shares}股</p>
                      <p className="text-xs text-muted-foreground dark:text-white/40">
                        成本 {formatPrice(h.costPrice)}
                      </p>
                    </div>
                    <div className="text-right w-24">
                      <p className={`font-mono ${getPriceColorClass(pnl)}`}>
                        {formatPrice(pnl)}
                      </p>
                      <p className={`text-xs font-mono ${getPriceColorClass(pnlPct)}`}>
                        {formatPercent(pnlPct)}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      title={isWatch ? "设为实盘" : "标为观察"}
                      onClick={() => toggleMode(h.code, h.mode)}
                      className="hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08]"
                    >
                      <Eye
                        className={`h-4 w-4 ${isWatch ? "text-amber-500" : "text-muted-foreground dark:text-white/40"}`}
                      />
                    </Button>
                    <Link href={`/?stock=${h.code}`}>
                      <Button
                        variant="ghost"
                        size="icon"
                        title="AI分析"
                        className="hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08]"
                      >
                        <MessageSquare className="h-4 w-4" />
                      </Button>
                    </Link>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeHolding(h.code)}
                      className="hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08]"
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground dark:text-white/40 hover:text-[#FF8767]" />
                    </Button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </GlassCard>
    </div>
  );
}
