// Input: 用户自选股列表（本地状态）
// Output: 自选股管理页面，含添加/删除/跳转AI分析
// Pos: /watchlist路由页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Plus, X, MessageSquare } from "lucide-react";
import Link from "next/link";

interface WatchItem {
  code: string;
  name: string;
  price?: number;
  change?: number;
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchItem[]>([
    { code: "600519", name: "贵州茅台", price: 1650, change: 2.3 },
    { code: "000858", name: "五粮液", price: 152, change: -1.2 },
    { code: "601318", name: "中国平安", price: 48.5, change: 0.8 },
    { code: "000001", name: "平安银行", price: 11.8, change: -0.5 },
  ]);
  const [newCode, setNewCode] = useState("");

  const addItem = () => {
    if (newCode && !items.find(i => i.code === newCode)) {
      setItems([...items, { code: newCode, name: newCode }]);
      setNewCode("");
    }
  };

  const removeItem = (code: string) => {
    setItems(items.filter(i => i.code !== code));
  };

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">自选股</h1>
        <div className="flex gap-2">
          <Input
            value={newCode}
            onChange={e => setNewCode(e.target.value)}
            placeholder="输入股票代码"
            className="w-40"
            onKeyDown={e => e.key === 'Enter' && addItem()}
          />
          <Button size="sm" onClick={addItem}><Plus className="h-4 w-4" /></Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">我的自选 ({items.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">暂无自选股</p>
          ) : (
            <div className="space-y-1">
              {items.map(item => (
                <div key={item.code} className="flex items-center justify-between p-3 rounded-lg hover:bg-muted/50 transition-colors group">
                  <div>
                    <span className="font-medium">{item.name}</span>
                    <span className="text-xs text-muted-foreground ml-2">{item.code}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    {item.price && (
                      <div className="text-right">
                        <span className="font-mono">{item.price}</span>
                        {item.change != null && (
                          <Badge variant="outline" className={`ml-2 ${item.change >= 0 ? 'text-green-500 border-green-500/30' : 'text-red-500 border-red-500/30'}`}>
                            {item.change >= 0 ? '+' : ''}{item.change}%
                          </Badge>
                        )}
                      </div>
                    )}
                    <Link href={`/?stock=${item.code}`}>
                      <Button variant="ghost" size="icon" title="AI分析">
                        <MessageSquare className="h-4 w-4" />
                      </Button>
                    </Link>
                    <Button variant="ghost" size="icon" onClick={() => removeItem(item.code)} className="opacity-0 group-hover:opacity-100 transition-opacity">
                      <X className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
