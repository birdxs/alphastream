// Input: theme-store状态
// Output: 紧凑导航栏 (h-12)
// Pos: 页面顶部固定导航

"use client";
import Link from "next/link";
import { useThemeStore } from "@/lib/stores/theme-store";
import { Button } from "@/components/ui/button";
import { Sun, Moon, MessageSquare, Search, Settings } from "lucide-react";
import { MobileDrawer } from "./mobile-drawer";

export function Navbar() {
  const theme = useThemeStore(s => s.theme);
  const toggleTheme = useThemeStore(s => s.toggleTheme);
  const stockColorScheme = useThemeStore(s => s.stockColorScheme);
  const toggleColorScheme = useThemeStore(s => s.toggleColorScheme);

  return (
    <nav
      aria-label="主导航"
      className="flex h-12 items-center justify-between border-b border-border/60 bg-background/95 backdrop-blur-sm px-3 shrink-0"
    >
      {/* Left: Logo + Nav */}
      <div className="flex items-center gap-1">
        <Link href="/" className="flex items-center gap-1.5 font-bold text-sm mr-3 px-1">
          <span className="text-primary">◆</span>
          <span>AI金融</span>
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
        className="hidden md:flex items-center gap-2 bg-muted/60 rounded-md px-3 py-1 text-xs text-muted-foreground hover:bg-muted border border-border/40 transition-colors"
      >
        <Search className="h-3 w-3" />
        <span>搜索股票</span>
        <kbd className="ml-3 px-1 py-px rounded bg-background/80 text-[9px] border border-border/60">⌘K</kbd>
      </button>

      {/* Right: Controls */}
      <div className="flex items-center gap-0.5">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={toggleColorScheme} aria-label="切换涨跌色">
          <span className="text-[10px]">{stockColorScheme === 'cn' ? '🔴' : '🟢'}</span>
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
