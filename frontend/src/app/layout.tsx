// Input: Next.js App Router子页面（children）
// Output: 全局HTML骨架，含主题Provider、导航栏、字体配置、移动端TabBar
// Pos: 应用最顶层布局入口
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/layout/navbar";
import { ThemeProvider } from "@/components/layout/theme-provider";
import { GlobalSearch } from "@/components/common/global-search";
import { KeyboardShortcuts } from "@/components/common/keyboard-shortcuts";
import { MobileTabBar } from "@/components/layout/mobile-tab-bar";
import { NetworkStatus } from "@/components/common/network-status";

// 使用系统字体栈，避免Google Fonts CDN依赖
const fontClassName = "font-sans";

export const metadata: Metadata = {
  title: "智能金融分析 — AI-Native",
  description: "AI驱动的智能金融分析平台",
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className={`${fontClassName} antialiased`}>
        <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-0 focus:left-0 focus:z-[100] focus:bg-primary focus:text-primary-foreground focus:px-4 focus:py-2">
          跳到主内容
        </a>
        <ThemeProvider>
          <div className="flex h-screen flex-col">
            <Navbar />
            <NetworkStatus />
            <main id="main-content" className="flex-1 overflow-hidden">
              {children}
            </main>
            <MobileTabBar />
          </div>
          <GlobalSearch />
          <KeyboardShortcuts />
        </ThemeProvider>
      </body>
    </html>
  );
}
