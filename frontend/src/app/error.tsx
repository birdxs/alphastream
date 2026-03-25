// Input: Error对象 + reset回调函数
// Output: 全局错误边界UI（展示错误信息和重试按钮）
// Pos: Next.js App Router全局错误处理页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <div className="text-6xl">&#9888;&#65039;</div>
      <h2 className="text-xl font-semibold">出了点问题</h2>
      <p className="text-muted-foreground text-sm max-w-md text-center">
        {error.message}
      </p>
      <Button onClick={reset}>重试</Button>
    </div>
  );
}
