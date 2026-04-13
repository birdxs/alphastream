// Input: children React节点
// Output: 根据theme状态切换dark class + 根据stockColorScheme设置data-color-scheme的Provider包装
// Pos: 布局层，包裹整个应用，控制暗色模式与涨跌色方案
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useEffect } from "react";
import { useThemeStore } from "@/lib/stores/theme-store";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { theme, stockColorScheme } = useThemeStore();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  useEffect(() => {
    document.documentElement.setAttribute("data-color-scheme", stockColorScheme);
  }, [stockColorScheme]);

  return <>{children}</>;
}
