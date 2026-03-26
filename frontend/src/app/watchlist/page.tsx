// Input: watchlist-store持久化自选股数据 + 用户操作
// Output: 自选股管理页面，含添加/删除/跳转个股详情，Dark Glassmorphism毛玻璃风格
// Pos: /watchlist路由页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, X, MessageSquare, Star, ArrowRight } from "lucide-react";
import Link from "next/link";
import { GlassCard } from "@/components/common/glass-card";
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
            className="w-40 bg-white/[0.04] border-white/[0.1]"
            onKeyDown={e => e.key === 'Enter' && handleAdd()}
          />
          <Button size="sm" onClick={handleAdd} className="bg-white/[0.08] border border-white/[0.12] hover:bg-white/[0.15] text-foreground"><Plus className="h-4 w-4" /></Button>
        </div>
      </div>

      <GlassCard padding="lg">
        <div className="mb-4">
          <h2 className="text-sm font-semibold">我的自选 ({items.length})</h2>
        </div>
        {items.length === 0 ? (
          <div className="text-center py-12 space-y-4">
            <Star className="h-12 w-12 text-white/15 mx-auto" />
            <p className="text-white/40">暂无自选股</p>
            <p className="text-sm text-white/25">按 <kbd className="px-1.5 py-0.5 rounded-md bg-white/[0.06] text-[10px] font-medium border border-white/[0.08]">{"\u2318"}K</kbd> 搜索并添加第一只自选股</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.08]">
                  <th className="text-left py-2.5 px-3 text-white/40 text-xs font-medium">名称</th>
                  <th className="text-left py-2.5 px-3 text-white/40 text-xs font-medium font-mono">代码</th>
                  <th className="text-right py-2.5 px-3 text-white/40 text-xs font-medium">添加日期</th>
                  <th className="text-right py-2.5 px-3 text-white/40 text-xs font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr
                    key={item.code}
                    className="relative border-b border-white/[0.04] hover:bg-white/[0.04] transition-colors group cursor-pointer"
                    onTouchStart={() => handleTouchStart(item.code)}
                    onTouchEnd={handleTouchEnd}
                    onTouchCancel={handleTouchEnd}
                  >
                    <td className="py-3 px-3">
                      <Link href={`/stock/${item.code}`} className="font-medium hover:text-[#6B5EE4] transition-colors flex items-center gap-1">
                        {item.name}
                        <ArrowRight className="h-3 w-3 opacity-0 group-hover:opacity-60 transition-opacity" />
                      </Link>
                    </td>
                    <td className="py-3 px-3">
                      <Link href={`/stock/${item.code}`} className="font-mono text-[#6B5EE4] hover:underline text-xs">
                        {item.code}
                      </Link>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <span className="text-xs text-white/30 font-mono">
                        {new Date(item.addedAt).toLocaleDateString()}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Link href={`/?stock=${item.code}`}>
                          <Button variant="ghost" size="icon" title="AI分析" className="h-7 w-7 hover:bg-white/[0.08]">
                            <MessageSquare className="h-3.5 w-3.5" />
                          </Button>
                        </Link>
                        <Button variant="ghost" size="icon" onClick={() => removeItem(item.code)} className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white/[0.08]">
                          <X className="h-3.5 w-3.5 text-white/40 hover:text-red-400" />
                        </Button>
                      </div>
                    </td>
                    {longPressItem === item.code && (
                      <td colSpan={4} className="absolute right-0 top-full mt-1 z-10">
                        <div className="bg-[rgba(15,15,35,0.95)] backdrop-blur-xl border border-white/[0.12] rounded-xl shadow-[0_8px_32px_rgba(0,0,0,0.5)] py-1">
                          <Link href={`/?stock=${item.code}`} className="block w-full px-4 py-2 text-sm hover:bg-white/[0.06] text-left">
                            AI分析
                          </Link>
                          <Link href={`/stock/${item.code}`} className="block w-full px-4 py-2 text-sm hover:bg-white/[0.06] text-left">
                            查看详情
                          </Link>
                          <button className="w-full px-4 py-2 text-sm hover:bg-white/[0.06] text-left text-red-400" onClick={() => { removeItem(item.code); setLongPressItem(null); }}>
                            删除
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
