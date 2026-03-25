// Input: 无（从theme-store获取状态）
// Output: 顶部导航栏UI，含路由链接和主题/配色切换
// Pos: 布局层，固定在页面顶部
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import Link from "next/link";
import { useThemeStore } from "@/lib/stores/theme-store";
import { Button } from "@/components/ui/button";
import { Sun, Moon, MessageSquare, Briefcase, Star, Settings } from "lucide-react";

export function Navbar() {
  const { theme, toggleTheme, stockColorScheme, toggleColorScheme } = useThemeStore();
  
  return (
    <nav className="flex h-14 items-center justify-between border-b bg-background px-4">
      <div className="flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg">
          <span className="text-primary">AI</span>
          <span>金融分析</span>
        </Link>
        <div className="flex items-center gap-1">
          <Link href="/">
            <Button variant="ghost" size="sm" className="gap-2">
              <MessageSquare className="h-4 w-4" />
              <span className="hidden sm:inline">AI对话</span>
            </Button>
          </Link>
          <Link href="/portfolio">
            <Button variant="ghost" size="sm" className="gap-2">
              <Briefcase className="h-4 w-4" />
              <span className="hidden sm:inline">投资组合</span>
            </Button>
          </Link>
          <Link href="/watchlist">
            <Button variant="ghost" size="sm" className="gap-2">
              <Star className="h-4 w-4" />
              <span className="hidden sm:inline">自选股</span>
            </Button>
          </Link>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={toggleColorScheme} title={stockColorScheme === 'cn' ? '红涨绿跌' : '绿涨红跌'}>
          <span className="text-xs font-mono">{stockColorScheme === 'cn' ? '🔴涨' : '🟢涨'}</span>
        </Button>
        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
        <Link href="/settings">
          <Button variant="ghost" size="icon">
            <Settings className="h-4 w-4" />
          </Button>
        </Link>
      </div>
    </nav>
  );
}
