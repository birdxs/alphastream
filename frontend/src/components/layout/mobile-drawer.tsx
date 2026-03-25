// Input: 无
// Output: 移动端侧边抽屉导航菜单
// Pos: components/layout/mobile-drawer.tsx - 移动端导航抽屉
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Menu, MessageSquare, Briefcase, Star, Settings } from "lucide-react";
import Link from "next/link";

export function MobileDrawer() {
  return (
    <Sheet>
      <SheetTrigger
        render={
          <Button variant="ghost" size="icon" className="sm:hidden" />
        }
      >
        <Menu className="h-5 w-5" />
      </SheetTrigger>
      <SheetContent side="left" className="w-64 p-0">
        <div className="p-4 border-b">
          <h2 className="font-bold text-lg flex items-center gap-2">
            <span className="text-primary">AI</span>金融分析
          </h2>
        </div>
        <nav className="p-2 space-y-1">
          {[
            { href: "/", icon: MessageSquare, label: "AI对话" },
            { href: "/portfolio", icon: Briefcase, label: "投资组合" },
            { href: "/watchlist", icon: Star, label: "自选股" },
            { href: "/settings", icon: Settings, label: "设置" },
          ].map(item => (
            <Link key={item.href} href={item.href}>
              <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-accent transition-colors">
                <item.icon className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">{item.label}</span>
              </div>
            </Link>
          ))}
        </nav>
      </SheetContent>
    </Sheet>
  );
}
