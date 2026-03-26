// Input: theme-store状态
// Output: 紧凑导航栏 (h-12)，Bloomberg Terminal风格
// Pos: 页面顶部固定导航
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import Link from "next/link";
import { useThemeStore } from "@/lib/stores/theme-store";
import { Button } from "@/components/ui/button";
import { Sun, Moon, MessageSquare, Search, Settings, TrendingUp, TrendingDown, Activity } from "lucide-react";
import { MobileDrawer } from "./mobile-drawer";

export function Navbar() {
  const theme = useThemeStore(s => s.theme);
  const toggleTheme = useThemeStore(s => s.toggleTheme);
  const stockColorScheme = useThemeStore(s => s.stockColorScheme);
  const toggleColorScheme = useThemeStore(s => s.toggleColorScheme);

  return (
    <nav
      aria-label="主导航"
      className="flex h-12 items-center justify-between border-b border-border/40 bg-background/80 backdrop-blur-xl px-3 shrink-0"
    >
      {/* Left: Logo + Nav */}
      <div className="flex items-center gap-1">
        <Link href="/" className="flex items-center gap-1.5 mr-3 px-1 group">
          <div className="w-6 h-6 rounded-md bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-sm">
            <Activity className="h-3.5 w-3.5 text-white" />
          </div>
          <span className="font-bold text-sm tracking-wide">AI金融</span>
        </Link>

        <div className="hidden sm:flex items-center">
          <Link href="/">
            <Button variant="ghost" size="sm" className="h-8 px-2.5 gap-1.5 text-xs text-foreground">
              <MessageSquare className="h-3.5 w-3.5" />
              对话
            </Button>
          </Link>
        </div>

        <MobileDrawer />
      </div>

      {/* Center: Search */}
      <button
        onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
        className="hidden md:flex items-center gap-2 bg-muted/40 rounded-lg px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted/70 border border-border/30 transition-colors"
      >
        <Search className="h-3.5 w-3.5" />
        <span>搜索股票...</span>
        <kbd className="ml-4 px-1.5 py-0.5 rounded-md bg-background/90 text-[9px] font-medium border border-border/50 shadow-sm">⌘K</kbd>
      </button>

      {/* Right: Controls */}
      <div className="flex items-center gap-0.5">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={toggleColorScheme}
          aria-label="切换涨跌色"
          title={stockColorScheme === 'cn' ? '中国标准（红涨绿跌）' : '国际标准（绿涨红跌）'}
        >
          {stockColorScheme === 'cn' ? (
            <TrendingUp className="h-3.5 w-3.5 text-rose-500" />
          ) : (
            <TrendingDown className="h-3.5 w-3.5 text-emerald-500" />
          )}
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={toggleTheme} aria-label="切换主题">
          {theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </Button>
        <Link href="/settings">
          <Button variant="ghost" size="icon" className="h-8 w-8 hidden sm:flex">
            <Settings className="h-3.5 w-3.5" />
          </Button>
        </Link>
      </div>
    </nav>
  );
}
