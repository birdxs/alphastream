// Input: theme-store状态 + usePathname路由 + S-UI-0 token
// Output: 紧凑导航栏 (h-12)，字号/间距/强调色对齐 design token；当前路径高亮；桌面7项+设置
// Pos: 页面顶部固定导航（z-sticky）
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
      className="flex h-12 items-center justify-between bg-[var(--bg-surface)]/85 dark:bg-[var(--bg-surface)]/80 backdrop-blur-xl border-b shrink-0"
      style={{
        zIndex: 'var(--z-sticky)',
        borderColor: 'color-mix(in srgb, var(--accent) 22%, var(--border-subtle))',
        paddingLeft: 'var(--space-3)',
        paddingRight: 'var(--space-3)',
        gap: 'var(--space-2)',
      }}
    >
      {/* Left: Mobile drawer + Logo + Nav */}
      <div className="flex items-center" style={{ gap: 'var(--space-1)' }}>
        <MobileDrawer />
        <Link
          href="/"
          className="flex items-center mr-3 px-1 group"
          style={{ gap: 'var(--space-2)' }}
        >
          <div
            className="flex items-center justify-center text-white"
            style={{
              background: 'var(--accent)',
              borderRadius: 'var(--radius-token-sm)',
              padding: '6px',
            }}
          >
            <Activity className="h-3.5 w-3.5" />
          </div>
          <span
            className="font-bold tracking-wide"
            style={{ color: 'var(--text-primary)', fontSize: 'var(--fs-sm)' }}
          >
            AI金融
          </span>
        </Link>

        <div className="hidden sm:flex items-center" style={{ gap: 'var(--space-1)' }}>
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link key={href} href={href}>
                <Button
                  variant="ghost"
                  size="sm"
                  className={`h-8 relative hover:bg-[var(--accent-muted)] ${
                    isActive
                      ? "font-semibold text-[var(--accent)]"
                      : "text-[var(--text-primary)]"
                  }`}
                  style={{
                    gap: 'var(--space-1)',
                    paddingLeft: 'var(--space-2)',
                    paddingRight: 'var(--space-2)',
                    fontSize: 'var(--fs-xs)',
                  }}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                  {isActive && (
                    <span
                      className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4/5 h-[2px] rounded-full"
                      style={{
                        background: 'var(--accent)',
                        boxShadow: '0 0 6px color-mix(in srgb, var(--accent) 60%, transparent)',
                      }}
                    />
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
        className="hidden md:flex items-center border hover:bg-[var(--accent-muted)] transition-colors"
        style={{
          gap: 'var(--space-2)',
          background: 'color-mix(in srgb, var(--text-primary) 3%, transparent)',
          borderColor: 'var(--border-subtle)',
          borderRadius: 'var(--radius-token-sm)',
          padding: '6px var(--space-3)',
          fontSize: 'var(--fs-xs)',
          color: 'var(--text-secondary)',
        }}
      >
        <Search className="h-3.5 w-3.5" />
        <span>搜索股票...</span>
        <kbd
          className="ml-4 font-medium border shadow-sm"
          style={{
            padding: '2px 6px',
            borderRadius: 'var(--radius-token-sm)',
            background: 'color-mix(in srgb, var(--text-primary) 5%, transparent)',
            borderColor: 'var(--border-subtle)',
            fontSize: '9px',
          }}
        >⌘K</kbd>
      </button>

      {/* Right: Controls */}
      <div className="flex items-center" style={{ gap: '2px' }}>
        <Button
          variant="ghost"
          size="icon"
          className="hidden sm:inline-flex h-8 w-8 hover:bg-[var(--accent-muted)]"
          onClick={toggleColorScheme}
          aria-label="切换涨跌色"
          title={stockColorScheme === 'cn' ? '中国标准（红涨绿跌）' : '国际标准（绿涨红跌）'}
        >
          {stockColorScheme === 'cn' ? (
            <TrendingUp className="h-3.5 w-3.5 text-up" />
          ) : (
            <TrendingDown className="h-3.5 w-3.5 text-down" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 hover:bg-[var(--accent-muted)]"
          onClick={toggleTheme}
          aria-label="切换主题"
        >
          {theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </Button>
        <Link
          href="/settings"
          aria-label="设置"
          title="设置"
          aria-current={settingsActive ? "page" : undefined}
          className={`inline-flex h-8 w-8 items-center justify-center hover:bg-[var(--accent-muted)] transition-colors ${
            settingsActive ? "text-[var(--accent)]" : "text-[var(--text-primary)]"
          }`}
          style={{ borderRadius: 'var(--radius-token-sm)' }}
          data-testid="navbar-settings-link"
        >
          <Settings className="h-3.5 w-3.5" />
        </Link>
      </div>
    </nav>
  );
}
