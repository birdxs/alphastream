// Input: Next.js App Router子页面（children）
// Output: 全局HTML骨架：Navbar + main content area
// Pos: 应用最顶层布局入口

import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/layout/navbar";
import { ThemeProvider } from "@/components/layout/theme-provider";
import { GlobalSearch } from "@/components/common/global-search";
import { KeyboardShortcuts } from "@/components/common/keyboard-shortcuts";
import { NetworkStatus } from "@/components/common/network-status";

export const metadata: Metadata = {
  title: "AI金融分析",
  description: "AI-Native 智能金融分析平台",
  manifest: "/manifest.json",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-0 focus:left-0 focus:z-[100] focus:bg-primary focus:text-primary-foreground focus:px-4 focus:py-2"
        >
          跳到主内容
        </a>
        <ThemeProvider>
          {/*
            Fixed height shell: navbar (48px) + content (rest).
            Uses 100dvh for mobile keyboard awareness.
          */}
          <div className="flex flex-col" style={{ height: '100dvh' }}>
            <Navbar />
            <NetworkStatus />
            <main id="main-content" className="flex-1 min-h-0">
              {children}
            </main>
          </div>
          <GlobalSearch />
          <KeyboardShortcuts />
        </ThemeProvider>
      </body>
    </html>
  );
}
