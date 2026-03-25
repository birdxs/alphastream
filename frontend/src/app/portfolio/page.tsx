// Input: 用户持仓数据（本地状态）
// Output: 投资组合管理页面，含添加/删除持仓、盈亏概况
// Pos: /portfolio路由页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, TrendingUp, TrendingDown, BarChart3 } from "lucide-react";

interface Holding {
  code: string;
  name: string;
  shares: number;
  costPrice: number;
  currentPrice?: number;
}

export default function PortfolioPage() {
  const [holdings, setHoldings] = useState<Holding[]>([
    { code: "600519", name: "贵州茅台", shares: 100, costPrice: 1800, currentPrice: 1650 },
    { code: "000001", name: "平安银行", shares: 500, costPrice: 12.5, currentPrice: 11.8 },
  ]);
  const [showAdd, setShowAdd] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newShares, setNewShares] = useState("");
  const [newCost, setNewCost] = useState("");

  const totalValue = holdings.reduce((sum, h) => sum + (h.currentPrice || h.costPrice) * h.shares, 0);
  const totalCost = holdings.reduce((sum, h) => sum + h.costPrice * h.shares, 0);
  const totalPnl = totalValue - totalCost;
  const totalReturn = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;

  const addHolding = () => {
    if (newCode && newShares && newCost) {
      setHoldings([...holdings, {
        code: newCode, name: newCode, shares: Number(newShares),
        costPrice: Number(newCost), currentPrice: Number(newCost)
      }]);
      setNewCode(""); setNewShares(""); setNewCost("");
      setShowAdd(false);
    }
  };

  const removeHolding = (code: string) => {
    setHoldings(holdings.filter(h => h.code !== code));
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
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">总市值</p>
            <p className="text-2xl font-bold font-mono">&yen;{totalValue.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">总盈亏</p>
            <p className={`text-2xl font-bold font-mono ${totalPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {totalPnl >= 0 ? '+' : ''}{totalPnl.toLocaleString()}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">收益率</p>
            <p className={`text-2xl font-bold font-mono flex items-center gap-1 ${totalReturn >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {totalReturn >= 0 ? <TrendingUp className="h-5 w-5"/> : <TrendingDown className="h-5 w-5"/>}
              {totalReturn.toFixed(2)}%
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
                <Input value={newCode} onChange={e => setNewCode(e.target.value)} placeholder="600519" />
              </div>
              <div className="flex-1">
                <label className="text-xs text-muted-foreground">持股数量</label>
                <Input value={newShares} onChange={e => setNewShares(e.target.value)} placeholder="100" type="number" />
              </div>
              <div className="flex-1">
                <label className="text-xs text-muted-foreground">成本价</label>
                <Input value={newCost} onChange={e => setNewCost(e.target.value)} placeholder="1800" type="number" />
              </div>
              <Button onClick={addHolding}>添加</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 持仓列表 */}
      <Card>
        <CardHeader><CardTitle className="text-sm flex items-center gap-2"><BarChart3 className="h-4 w-4"/>持仓明细</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-2">
            {holdings.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">暂无持仓，点击上方&ldquo;添加持仓&rdquo;</p>
            ) : (
              holdings.map(h => {
                const pnl = ((h.currentPrice || h.costPrice) - h.costPrice) * h.shares;
                const pnlPct = ((h.currentPrice || h.costPrice) - h.costPrice) / h.costPrice * 100;
                return (
                  <div key={h.code} className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors">
                    <div className="flex items-center gap-3">
                      <div>
                        <span className="font-medium">{h.name}</span>
                        <span className="text-xs text-muted-foreground ml-2">{h.code}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-6 text-sm">
                      <div className="text-right">
                        <p className="font-mono">{h.shares}股</p>
                        <p className="text-xs text-muted-foreground">成本 {h.costPrice}</p>
                      </div>
                      <div className="text-right w-24">
                        <p className={`font-mono ${pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                          {pnl >= 0 ? '+' : ''}{pnl.toFixed(0)}
                        </p>
                        <p className={`text-xs ${pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                          {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                        </p>
                      </div>
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
