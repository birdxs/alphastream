// Input: watchlist-store持久化自选股数据 + 用户操作
// Output: 自选股管理页面，含添加/删除/跳转AI分析
// Pos: /watchlist路由页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, X, MessageSquare } from "lucide-react";
import Link from "next/link";
import { useWatchlistStore } from "@/lib/stores/watchlist-store";
import { useState } from "react";

export default function WatchlistPage() {
  const { items, addItem, removeItem } = useWatchlistStore();
  const [newCode, setNewCode] = useState("");

  const handleAdd = () => {
    if (newCode) {
      addItem(newCode);
      setNewCode("");
    }
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
            onKeyDown={e => e.key === 'Enter' && handleAdd()}
          />
          <Button size="sm" onClick={handleAdd}><Plus className="h-4 w-4" /></Button>
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
                    <span className="text-xs text-muted-foreground">
                      {new Date(item.addedAt).toLocaleDateString()}
                    </span>
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
