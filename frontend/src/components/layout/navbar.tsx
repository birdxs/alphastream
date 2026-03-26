// Input: 无（从theme-store获取状态）
// Output: 顶部导航栏UI，含路由链接、主题/配色切换和移动端抽屉导航
// Pos: 布局层，固定在页面顶部
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import Link from "next/link";
import { useThemeStore } from "@/lib/stores/theme-store";
import { Button } from "@/components/ui/button";
import { Sun, Moon, MessageSquare, Briefcase, Star, Settings, Search } from "lucide-react";
import { MobileDrawer } from "./mobile-drawer";

export function Navbar() {
  const { theme, toggleTheme, stockColorScheme, toggleColorScheme } = useThemeStore();
  
  return (
    <nav aria-label="主导航" className="flex h-14 items-center justify-between border-b bg-background px-4">
      <div className="flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg">
          <span className="text-primary">AI</span>
          <span>金融分析</span>
        </Link>
        <div className="hidden sm:flex items-center gap-1">
          <Link href="/">
            <Button variant="ghost" size="sm" className="gap-2">
              <MessageSquare className="h-4 w-4" />
              <span>AI对话</span>
            </Button>
          </Link>
          <Link href="/portfolio">
            <Button variant="ghost" size="sm" className="gap-2">
              <Briefcase className="h-4 w-4" />
              <span>投资组合</span>
            </Button>
          </Link>
          <Link href="/watchlist">
            <Button variant="ghost" size="sm" className="gap-2">
              <Star className="h-4 w-4" />
              <span>自选股</span>
            </Button>
          </Link>
        </div>
        <button
          onClick={() => {
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }));
          }}
          className="hidden md:flex items-center gap-2 bg-muted/50 rounded-lg px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted transition-colors border border-border/50"
        >
          <Search className="h-3.5 w-3.5" />
          <span>搜索股票...</span>
          <kbd className="ml-4 px-1 py-0.5 rounded bg-background text-[10px] border">⌘K</kbd>
        </button>
        <MobileDrawer />
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={toggleColorScheme} title={stockColorScheme === 'cn' ? '红涨绿跌' : '绿涨红跌'} aria-label="切换涨跌色">
          <span className="text-xs font-mono">{stockColorScheme === 'cn' ? '🔴涨' : '🟢涨'}</span>
        </Button>
        <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="切换主题">
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
