// Input: 无
// Output: 全局加载动画UI
// Pos: Next.js App Router全局loading状态页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

export default function Loading() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center space-y-4 animate-fade-in">
        <div className="relative w-12 h-12 mx-auto">
          <div className="absolute inset-0 rounded-full border-2 border-muted" />
          <div className="absolute inset-0 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        </div>
        <p className="text-sm text-muted-foreground">加载中...</p>
      </div>
    </div>
  );
}
