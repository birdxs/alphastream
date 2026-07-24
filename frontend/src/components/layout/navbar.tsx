// Input: theme-store状态 + usePathname路由
// Output: 紧凑导航栏 (h-12)，Dark Glassmorphism风格，品牌色底部边线，当前路径高亮；桌面7项导航+设置齿轮；移动端汉堡抽屉(含设置)
// Pos: 页面顶部固定导航
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useThemeStore } from "@/lib/stores/theme-store";
import { Button } from "@/components/ui/button";
import { MobileDrawer } from "@/components/layout/mobile-drawer";
import { Sun, Moon, MessageSquare, LayoutDashboard, Search, TrendingUp, TrendingDown, Activity, Filter, Briefcase, Star, BarChart3, Newspaper, Settings } from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "对话", icon: MessageSquare },
  { href: "/dashboard", label: "看板", icon: LayoutDashboard },
  { href: "/news", label: "新闻", icon: Newspaper },
  { href: "/screener", label: "选股", icon: Filter },
  { href: "/portfolio", label: "持仓", icon: Briefcase },
  { href: "/watchlist", label: "自选", icon: Star },
  { href: "/compare", label: "对比", icon: BarChart3 },
];

export function Navbar() {
  const theme = useThemeStore(s => s.theme);
  const toggleTheme = useThemeStore(s => s.toggleTheme);
  const stockColorScheme = useThemeStore(s => s.stockColorScheme);
  const toggleColorScheme = useThemeStore(s => s.toggleColorScheme);
  const pathname = usePathname();
  const settingsActive = pathname.startsWith("/settings");

  return (
    <nav
      aria-label="主导航"
      className="flex h-12 items-center justify-between bg-card/85 dark:bg-[rgba(10,10,26,0.8)] backdrop-blur-xl border-b border-[#3737CC]/20 px-3 shrink-0"
    >
      {/* Left: Mobile drawer + Logo + Nav */}
      <div className="flex items-center gap-1">
        <MobileDrawer />
        <Link href="/" className="flex items-center gap-1.5 mr-3 px-1 group">
          <div className="bg-[#3737CC] rounded-lg p-1.5 flex items-center justify-center">
            <Activity className="h-3.5 w-3.5 text-white" />
          </div>
          <span className="font-bold text-sm tracking-wide">AI金融</span>
        </Link>

        <div className="hidden sm:flex items-center">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link key={href} href={href}>
                <Button
                  variant="ghost"
                  size="sm"
                  className={`h-8 px-2.5 gap-1.5 text-xs hover:bg-foreground/[0.06] dark:hover:bg-white/[0.08] relative ${
                    isActive
                      ? "text-[#3737CC] font-semibold"
                      : "text-foreground"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                  {isActive && (
                    <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4/5 h-[2px] rounded-full bg-[#3737CC] shadow-[0_0_6px_rgba(55,55,204,0.6)]" />
                  )}
                </Button>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Center: Search — 移动端隐藏 */}
      <button
        onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
        className="hidden md:flex items-center gap-2 bg-foreground/[0.03] dark:bg-white/[0.03] border border-border/60 dark:border-white/[0.08] rounded-lg px-3 py-1.5 text-xs text-muted-foreground hover:bg-foreground/[0.06] dark:hover:bg-white/[0.08] transition-colors"
      >
        <Search className="h-3.5 w-3.5" />
        <span>搜索股票...</span>
        <kbd className="ml-4 px-1.5 py-0.5 rounded-md bg-foreground/[0.05] dark:bg-white/[0.06] text-[9px] font-medium border border-border/60 dark:border-white/[0.08] shadow-sm">⌘K</kbd>
      </button>

      {/* Right: Controls */}
      <div className="flex items-center gap-0.5">
        <Button
          variant="ghost"
          size="icon"
          className="hidden sm:inline-flex h-8 w-8 hover:bg-foreground/[0.06] dark:hover:bg-white/[0.08]"
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
        <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-foreground/[0.06] dark:hover:bg-white/[0.08]" onClick={toggleTheme} aria-label="切换主题">
          {theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </Button>
        <Link
          href="/settings"
          aria-label="设置"
          title="设置"
          aria-current={settingsActive ? "page" : undefined}
          className={`inline-flex h-8 w-8 items-center justify-center rounded-lg hover:bg-foreground/[0.06] dark:hover:bg-white/[0.08] transition-colors ${
            settingsActive ? "text-[#3737CC]" : "text-foreground"
          }`}
          data-testid="navbar-settings-link"
        >
          <Settings className="h-3.5 w-3.5" />
        </Link>
      </div>
    </nav>
  );
}
