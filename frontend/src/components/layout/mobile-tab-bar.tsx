// Input: 当前路由路径
// Output: 移动端底部TabBar导航（对话/自选/组合/设置）
// Pos: layout.tsx底部，仅sm以下屏幕显示
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, BarChart3, Briefcase, Settings, Star } from "lucide-react";

const TABS = [
  { href: "/", icon: MessageSquare, label: "对话" },
  { href: "/watchlist", icon: Star, label: "自选" },
  { href: "/compare", icon: BarChart3, label: "对比" },
  { href: "/portfolio", icon: Briefcase, label: "组合" },
  { href: "/settings", icon: Settings, label: "设置" },
];

export function MobileTabBar() {
  const pathname = usePathname();

  return (
    <nav className="sm:hidden fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-sm border-t z-50">
      <div className="flex items-center justify-around h-14">
        {TABS.map(tab => {
          const active = tab.href === '/' ? pathname === '/' : pathname.startsWith(tab.href);
          return (
            <Link key={tab.href} href={tab.href} className="flex flex-col items-center gap-0.5 py-1">
              <tab.icon className={`h-5 w-5 ${active ? 'text-primary' : 'text-muted-foreground'}`} />
              <span className={`text-[10px] ${active ? 'text-primary font-medium' : 'text-muted-foreground'}`}>
                {tab.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
