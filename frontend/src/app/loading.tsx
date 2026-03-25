// Input: 无
// Output: 全局加载骨架屏UI
// Pos: Next.js App Router全局loading状态页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="flex h-full">
      <div className="w-[35%] border-r p-4 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
      <div className="flex-1 p-4 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[400px] w-full" />
      </div>
    </div>
  );
}
