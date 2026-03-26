// Input: theme-store状态
// Output: 紧凑导航栏 (h-12)，Dark Glassmorphism风格，移动端精简（隐藏搜索+导航链接）
// Pos: 页面顶部固定导航
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import Link from "next/link";
import { useThemeStore } from "@/lib/stores/theme-store";
import { Button } from "@/components/ui/button";
import { Sun, Moon, MessageSquare, LayoutDashboard, Search, TrendingUp, TrendingDown, Activity } from "lucide-react";

export function Navbar() {
  const theme = useThemeStore(s => s.theme);
  const toggleTheme = useThemeStore(s => s.toggleTheme);
  const stockColorScheme = useThemeStore(s => s.stockColorScheme);
  const toggleColorScheme = useThemeStore(s => s.toggleColorScheme);

  return (
    <nav
      aria-label="主导航"
      className="flex h-12 items-center justify-between bg-[rgba(10,10,26,0.8)] backdrop-blur-xl border-b border-white/[0.08] px-3 shrink-0"
    >
      {/* Left: Logo + Nav */}
      <div className="flex items-center gap-1">
        <Link href="/" className="flex items-center gap-1.5 mr-3 px-1 group">
          <div className="bg-[#3737CC] rounded-lg p-1.5 flex items-center justify-center">
            <Activity className="h-3.5 w-3.5 text-white" />
          </div>
          <span className="font-bold text-sm tracking-wide">AI金融</span>
        </Link>

        <div className="hidden sm:flex items-center">
          <Link href="/">
            <Button variant="ghost" size="sm" className="h-8 px-2.5 gap-1.5 text-xs text-foreground hover:bg-white/[0.08]">
              <MessageSquare className="h-3.5 w-3.5" />
              对话
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button variant="ghost" size="sm" className="h-8 px-2.5 gap-1.5 text-xs text-foreground hover:bg-white/[0.08]">
              <LayoutDashboard className="h-3.5 w-3.5" />
              看板
            </Button>
          </Link>
        </div>
      </div>

      {/* Center: Search — 移动端隐藏 */}
      <button
        onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
        className="hidden md:flex items-center gap-2 bg-white/[0.03] border border-white/[0.08] rounded-lg px-3 py-1.5 text-xs text-muted-foreground hover:bg-white/[0.08] transition-colors"
      >
        <Search className="h-3.5 w-3.5" />
        <span>搜索股票...</span>
        <kbd className="ml-4 px-1.5 py-0.5 rounded-md bg-white/[0.06] text-[9px] font-medium border border-white/[0.08] shadow-sm">⌘K</kbd>
      </button>

      {/* Right: Controls */}
      <div className="flex items-center gap-0.5">
        <Button
          variant="ghost"
          size="icon"
          className="hidden sm:inline-flex h-8 w-8 hover:bg-white/[0.08]"
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
        <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-white/[0.08]" onClick={toggleTheme} aria-label="切换主题">
          {theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </Button>
      </div>
    </nav>
  );
}
