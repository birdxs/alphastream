// Input: Next.js App Router子页面（children）
// Output: 全局HTML骨架：Navbar + main content area；S-UI-3 主题 FOUC 预置
// Pos: 应用最顶层布局入口
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/layout/navbar";
import { ThemeProvider } from "@/components/layout/theme-provider";
import { GlobalSearch } from "@/components/common/global-search";
import { KeyboardShortcuts } from "@/components/common/keyboard-shortcuts";
import { NetworkStatus } from "@/components/common/network-status";
import { ToastProvider } from "@/components/common/toast-provider";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI金融分析",
  description: "AI-Native 智能金融分析平台 — 基于多Agent协作的专业投资决策支持系统",
  manifest: "/manifest.json",
  icons: {
    icon: "/favicon.svg",
    apple: "/icon-192.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#0A0A1A",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      {/* B23: 预连接后端，让浏览器 Network Service 在 React hydration 前完成冷启动
          避免 Playwright headless 首次 fetch 的 17s 延迟 */}
      <head>
        <link rel="prefetch" href="/api/market_indices" as="fetch" crossOrigin="anonymous" />
        {/* P2: 预热 /health Route Handler，让浏览器在 NetworkStatus 探针发起前完成后端冷启动连接 */}
        <link rel="prefetch" href="/health" as="fetch" crossOrigin="anonymous" />
        {/* S-UI-3: 同步读取 theme-storage，避免亮暗切换首屏闪白 */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var r=localStorage.getItem('theme-storage');if(!r)return;var j=JSON.parse(r);var t=(j&&j.state&&j.state.theme)||'dark';var s=(j&&j.state&&j.state.stockColorScheme)||'cn';var el=document.documentElement;if(t==='dark')el.classList.add('dark');else el.classList.remove('dark');el.setAttribute('data-color-scheme',s);}catch(e){}})();`,
          }}
        />
      </head>
      <body className={`${inter.className} antialiased`}>
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-0 focus:left-0 focus:z-[100] focus:bg-primary focus:text-primary-foreground focus:px-4 focus:py-2"
        >
          跳到主内容
        </a>
        <ThemeProvider>
          <ToastProvider>
            {/*
              Fixed height shell: navbar (48px) + content (rest).
              Uses 100dvh for mobile keyboard awareness.
            */}
            <div className="flex flex-col" style={{ height: '100dvh' }}>
              <Navbar />
              <NetworkStatus />
              {/* main 作为全站统一滚动容器：flex-1 min-h-0 取得确定高度，overflow-y-auto 让
                  内容超出时在此处滚动（而非冒泡到 body 产生页面级滚动把顶部指数栏推出视口）。
                  首页 page.tsx 自带 h-full+overflow-hidden 的内部布局在此恰好占满不滚动；
                  其它依赖页面级滚动的路由（settings/portfolio/compare/watchlist/stock/screener）
                  改为在 main 内部滚动，行为等价且不被 body overflow:hidden 裁剪。 */}
              <main id="main-content" className="flex-1 min-h-0 overflow-y-auto overscroll-contain">
                {children}
              </main>
            </div>
            <GlobalSearch />
            <KeyboardShortcuts />
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
