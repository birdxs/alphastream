// Input: Next.js App Router子页面（children）
// Output: 全局HTML骨架，含主题Provider、导航栏、字体配置
// Pos: 应用最顶层布局入口
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/layout/navbar";
import { ThemeProvider } from "@/components/layout/theme-provider";
import { GlobalSearch } from "@/components/common/global-search";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "智能金融分析 — AI-Native",
  description: "AI驱动的智能金融分析平台",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className={`${inter.className} antialiased`}>
        <ThemeProvider>
          <div className="flex h-screen flex-col">
            <Navbar />
            <main className="flex-1 overflow-hidden">
              {children}
            </main>
          </div>
          <GlobalSearch />
        </ThemeProvider>
      </body>
    </html>
  );
}
