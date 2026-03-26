// Input: watchlist-store持久化自选股数据 + 用户操作
// Output: 自选股管理页面，含添加/删除/跳转AI分析
// Pos: /watchlist路由页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, X, MessageSquare, Star } from "lucide-react";
import Link from "next/link";
import { useWatchlistStore } from "@/lib/stores/watchlist-store";
import { useState, useRef } from "react";

export default function WatchlistPage() {
  const { items, addItem, removeItem } = useWatchlistStore();
  const [newCode, setNewCode] = useState("");
  const [longPressItem, setLongPressItem] = useState<string | null>(null);
  const longPressTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const handleTouchStart = (code: string) => {
    longPressTimer.current = setTimeout(() => setLongPressItem(code), 500);
  };
  const handleTouchEnd = () => {
    clearTimeout(longPressTimer.current);
  };

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
            <div className="text-center py-12 space-y-4">
              <Star className="h-12 w-12 text-muted-foreground/30 mx-auto" />
              <p className="text-muted-foreground">暂无自选股</p>
              <p className="text-sm text-muted-foreground/60">按 <kbd className="px-1 py-0.5 rounded bg-muted text-xs">{"\u2318"}K</kbd> 搜索并添加第一只自选股</p>
            </div>
          ) : (
            <div className="space-y-1">
              {items.map(item => (
                <div
                  key={item.code}
                  className="relative flex items-center justify-between p-3 rounded-lg hover:bg-muted/50 transition-colors group"
                  onTouchStart={() => handleTouchStart(item.code)}
                  onTouchEnd={handleTouchEnd}
                  onTouchCancel={handleTouchEnd}
                >
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
                  {longPressItem === item.code && (
                    <div className="absolute right-0 top-full mt-1 bg-popover border rounded-lg shadow-lg z-10 py-1 animate-fade-in">
                      <Link href={`/?stock=${item.code}`} className="block w-full px-4 py-2 text-sm hover:bg-accent text-left">
                        🤖 AI分析
                      </Link>
                      <button className="w-full px-4 py-2 text-sm hover:bg-accent text-left text-red-500" onClick={() => { removeItem(item.code); setLongPressItem(null); }}>
                        🗑️ 删除
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
