// Input: 无
// Output: 404页面UI（提示页面未找到，提供返回首页按钮）
// Pos: Next.js App Router全局404处理页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <div className="text-6xl">&#128269;</div>
      <h2 className="text-xl font-semibold">页面未找到</h2>
      <p className="text-muted-foreground">请检查URL或返回首页</p>
      <Link href="/">
        <Button>返回首页</Button>
      </Link>
    </div>
  );
}
