// Input: portfolio-store持久化持仓数据 + 用户操作
// Output: 投资组合管理页面，含添加/删除持仓、盈亏概况、AI分析全部持仓品牌色渐变大按钮，Dark Glassmorphism风格
// Pos: /portfolio路由页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, TrendingUp, TrendingDown, BarChart3, MessageSquare, Briefcase, Sparkles } from "lucide-react";
import { GlassCard } from "@/components/common/glass-card";
import { usePortfolioStore } from "@/lib/stores/portfolio-store";
import { useStockNames } from "@/lib/hooks/use-stock-names";
import { useStockPrices } from "@/lib/hooks/use-stock-prices";
import { formatPrice, formatPercent, getPriceColorClass } from "@/lib/utils/format";
import Link from "next/link";

export default function PortfolioPage() {
  const { holdings, addHolding, removeHolding } = usePortfolioStore();
  const codes = useMemo(() => holdings.map(h => h.code), [holdings]);
  const existing = useMemo(() => Object.fromEntries(holdings.map(h => [h.code, h.name])), [holdings]);
  const resolvedNames = useStockNames(codes, existing);
  const livePrices = useStockPrices(codes);
  const displayName = (code: string, name: string) => (name && name !== code ? name : resolvedNames[code] || code);
  const priceOf = (h: { code: string; costPrice: number; currentPrice?: number }) =>
    livePrices[h.code]?.price ?? h.currentPrice ?? h.costPrice;
  const [showAdd, setShowAdd] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [newShares, setNewShares] = useState("");
  const [newCost, setNewCost] = useState("");
  const [formError, setFormError] = useState("");

  const totalValue = holdings.reduce((sum, h) => sum + priceOf(h) * h.shares, 0);
  const totalCost = holdings.reduce((sum, h) => sum + h.costPrice * h.shares, 0);
  const totalPnl = totalValue - totalCost;
  const totalReturn = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;

  const handleAdd = () => {
    setFormError("");
    if (!newCode || !/^\d{6}$/.test(newCode)) {
      setFormError("请输入6位股票代码"); return;
    }
    if (!newShares || Number(newShares) <= 0) {
      setFormError("持股数量必须大于0"); return;
    }
    if (!newCost || Number(newCost) <= 0) {
      setFormError("成本价必须大于0"); return;
    }
    addHolding({
      code: newCode,
      name: newName || newCode,
      shares: Number(newShares),
      costPrice: Number(newCost),
      currentPrice: Number(newCost),
    });
    setNewCode(""); setNewName(""); setNewShares(""); setNewCost("");
    setShowAdd(false);
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">投资组合</h1>
        <Button size="sm" onClick={() => setShowAdd(!showAdd)} className="bg-foreground/[0.08] dark:bg-white/[0.08] border border-foreground/[0.12] dark:border-white/[0.12] hover:bg-foreground/[0.15] dark:hover:bg-white/[0.15] text-foreground">
          <Plus className="h-4 w-4 mr-1" />添加持仓
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
            {totalPnl >= 0 ? '+' : ''}{formatPrice(totalPnl)}
          </p>
        </GlassCard>
        <GlassCard padding="md">
          <p className="text-sm text-muted-foreground dark:text-white/50">收益率</p>
          <p className={`text-2xl font-bold font-mono flex items-center gap-1 ${getPriceColorClass(totalReturn)}`}>
            {totalReturn >= 0 ? <TrendingUp className="h-5 w-5"/> : <TrendingDown className="h-5 w-5"/>}
            {formatPercent(totalReturn)}
          </p>
        </GlassCard>
      </div>

      {/* 添加表单 */}
      {showAdd && (
        <GlassCard padding="md">
          <div className="flex gap-2 items-end flex-wrap">
            <div className="flex-1 min-w-[120px]">
              <label htmlFor="stock-code" className="text-xs text-muted-foreground dark:text-white/50">股票代码</label>
              <Input id="stock-code" value={newCode} onChange={e => setNewCode(e.target.value)} placeholder="600519" className={`bg-foreground/[0.04] dark:bg-white/[0.04] border-foreground/[0.1] dark:border-white/[0.1] ${formError.includes('代码') ? 'border-[#FF8767]' : ''}`} />
            </div>
            <div className="flex-1 min-w-[120px]">
              <label htmlFor="stock-name" className="text-xs text-muted-foreground dark:text-white/50">股票名称</label>
              <Input id="stock-name" value={newName} onChange={e => setNewName(e.target.value)} placeholder="贵州茅台" className="bg-foreground/[0.04] dark:bg-white/[0.04] border-foreground/[0.1] dark:border-white/[0.1]" />
            </div>
            <div className="flex-1 min-w-[100px]">
              <label htmlFor="stock-shares" className="text-xs text-muted-foreground dark:text-white/50">持股数量</label>
              <Input id="stock-shares" value={newShares} onChange={e => setNewShares(e.target.value)} placeholder="100" type="number" className={`bg-foreground/[0.04] dark:bg-white/[0.04] border-foreground/[0.1] dark:border-white/[0.1] ${formError.includes('数量') ? 'border-[#FF8767]' : ''}`} />
            </div>
            <div className="flex-1 min-w-[100px]">
              <label htmlFor="stock-cost" className="text-xs text-muted-foreground dark:text-white/50">成本价</label>
              <Input id="stock-cost" value={newCost} onChange={e => setNewCost(e.target.value)} placeholder="1800" type="number" className={`bg-foreground/[0.04] dark:bg-white/[0.04] border-foreground/[0.1] dark:border-white/[0.1] ${formError.includes('成本') ? 'border-[#FF8767]' : ''}`} />
            </div>
            <Button onClick={handleAdd} className="bg-[#3737CC] hover:bg-[#4545DD] text-white">添加</Button>
          </div>
          {formError && <p className="text-xs text-[#FF8767] mt-1">{formError}</p>}
        </GlassCard>
      )}

      {/* AI分析全部持仓 - 品牌色渐变大按钮（始终展示，空持仓时禁用） */}
      {holdings.length > 0 ? (
        <Link
          href={`/?q=${encodeURIComponent('分析我当前持仓的整体风险和优化建议，持仓列表：' + holdings.map(h => h.code).join(','))}`}
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
              <p className="text-sm text-muted-foreground dark:text-white/25">点击上方"添加持仓"开始管理您的投资组合</p>
            </div>
          ) : (
            holdings.map(h => {
              const cp = priceOf(h);
              const pnl = (cp - h.costPrice) * h.shares;
              const pnlPct = h.costPrice > 0 ? ((cp - h.costPrice) / h.costPrice) * 100 : 0;
              return (
                <div key={h.code} className="flex items-center justify-between p-3 rounded-xl bg-foreground/[0.03] dark:bg-white/[0.03] border border-foreground/[0.06] dark:border-white/[0.06] hover:bg-foreground/[0.07] dark:hover:bg-white/[0.07] transition-all duration-200">
                  <div className="flex items-center gap-3">
                    <div>
                      <span className="font-medium">{displayName(h.code, h.name)}</span>
                      <Link href={`/stock/${h.code}`} className="text-xs text-[#6B5EE4] hover:underline ml-2 font-mono" title="查看详情">
                        {h.code}
                      </Link>
                    </div>
                  </div>
                  <div className="flex items-center gap-6 text-sm">
                    <div className="text-right">
                      <p className="font-mono">{h.shares}股</p>
                      <p className="text-xs text-muted-foreground dark:text-white/40">成本 {formatPrice(h.costPrice)}</p>
                    </div>
                    <div className="text-right w-24">
                      <p className={`font-mono ${getPriceColorClass(pnl)}`}>
                        {formatPrice(pnl)}
                      </p>
                      <p className={`text-xs font-mono ${getPriceColorClass(pnlPct)}`}>
                        {formatPercent(pnlPct)}
                      </p>
                    </div>
                    <Link href={`/?stock=${h.code}`}>
                      <Button variant="ghost" size="icon" title="AI分析" className="hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08]">
                        <MessageSquare className="h-4 w-4" />
                      </Button>
                    </Link>
                    <Button variant="ghost" size="icon" onClick={() => removeHolding(h.code)} className="hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08]">
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
