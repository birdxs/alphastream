// Input: portfolio-store持久化持仓数据 + 用户操作
// Output: 投资组合管理页面，含添加/删除持仓、盈亏概况、跳转AI分析
// Pos: /portfolio路由页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, TrendingUp, TrendingDown, BarChart3, MessageSquare, Briefcase } from "lucide-react";
import { usePortfolioStore } from "@/lib/stores/portfolio-store";
import { formatPrice, formatPercent, getPriceColorClass } from "@/lib/utils/format";
import Link from "next/link";

// TODO: 接入后端 POST /analyze 获取持仓股票的实时价格
// 当前使用本地localStorage持久化，未来可同步到服务端
export default function PortfolioPage() {
  const { holdings, addHolding, removeHolding } = usePortfolioStore();
  const [showAdd, setShowAdd] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [newShares, setNewShares] = useState("");
  const [newCost, setNewCost] = useState("");
  const [formError, setFormError] = useState("");

  const totalValue = holdings.reduce((sum, h) => sum + (h.currentPrice || h.costPrice) * h.shares, 0);
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
        <Button size="sm" onClick={() => setShowAdd(!showAdd)}>
          <Plus className="h-4 w-4 mr-1" />添加持仓
        </Button>
      </div>

      {/* 组合概况 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">总市值</p>
            <p className="text-2xl font-bold font-finance">&yen;{formatPrice(totalValue)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">总盈亏</p>
            <p className={`text-2xl font-bold font-finance ${getPriceColorClass(totalPnl)}`}>
              {totalPnl >= 0 ? '+' : ''}{formatPrice(totalPnl)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">收益率</p>
            <p className={`text-2xl font-bold font-finance flex items-center gap-1 ${getPriceColorClass(totalReturn)}`}>
              {totalReturn >= 0 ? <TrendingUp className="h-5 w-5"/> : <TrendingDown className="h-5 w-5"/>}
              {formatPercent(totalReturn)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* 添加表单 */}
      {showAdd && (
        <Card>
          <CardContent className="pt-4">
            <div className="flex gap-2 items-end">
              <div className="flex-1">
                <label className="text-xs text-muted-foreground">股票代码</label>
                <Input value={newCode} onChange={e => setNewCode(e.target.value)} placeholder="600519" className={formError.includes('代码') ? 'border-red-500' : ''} />
              </div>
              <div className="flex-1">
                <label className="text-xs text-muted-foreground">股票名称</label>
                <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="贵州茅台" />
              </div>
              <div className="flex-1">
                <label className="text-xs text-muted-foreground">持股数量</label>
                <Input value={newShares} onChange={e => setNewShares(e.target.value)} placeholder="100" type="number" className={formError.includes('数量') ? 'border-red-500' : ''} />
              </div>
              <div className="flex-1">
                <label className="text-xs text-muted-foreground">成本价</label>
                <Input value={newCost} onChange={e => setNewCost(e.target.value)} placeholder="1800" type="number" className={formError.includes('成本') ? 'border-red-500' : ''} />
              </div>
              <Button onClick={handleAdd}>添加</Button>
            </div>
            {formError && <p className="text-xs text-red-500 mt-1">{formError}</p>}
          </CardContent>
        </Card>
      )}

      {/* 持仓列表 */}
      <Card>
        <CardHeader><CardTitle className="text-sm flex items-center gap-2"><BarChart3 className="h-4 w-4"/>持仓明细</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-2">
            {holdings.length === 0 ? (
              <div className="text-center py-12 space-y-4">
                <Briefcase className="h-12 w-12 text-muted-foreground/30 mx-auto" />
                <p className="text-muted-foreground">暂无持仓</p>
                <p className="text-sm text-muted-foreground/60">点击上方"添加持仓"开始管理您的投资组合</p>
              </div>
            ) : (
              holdings.map(h => {
                const pnl = ((h.currentPrice || h.costPrice) - h.costPrice) * h.shares;
                const pnlPct = ((h.currentPrice || h.costPrice) - h.costPrice) / h.costPrice * 100;
                return (
                  <div key={h.code} className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors">
                    <div className="flex items-center gap-3">
                      <div>
                        <span className="font-medium">{h.name}</span>
                        <Link href={`/?stock=${h.code}`} className="text-xs text-primary hover:underline ml-2" title="跳转AI分析">
                          {h.code}
                        </Link>
                      </div>
                    </div>
                    <div className="flex items-center gap-6 text-sm">
                      <div className="text-right">
                        <p className="font-mono">{h.shares}股</p>
                        <p className="text-xs text-muted-foreground">成本 {formatPrice(h.costPrice)}</p>
                      </div>
                      <div className="text-right w-24">
                        <p className={`font-finance ${getPriceColorClass(pnl)}`}>
                          {formatPrice(pnl)}
                        </p>
                        <p className={`text-xs ${getPriceColorClass(pnlPct)}`}>
                          {formatPercent(pnlPct)}
                        </p>
                      </div>
                      <Link href={`/?stock=${h.code}`}>
                        <Button variant="ghost" size="icon" title="AI分析">
                          <MessageSquare className="h-4 w-4" />
                        </Button>
                      </Link>
                      <Button variant="ghost" size="icon" onClick={() => removeHolding(h.code)}>
                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
