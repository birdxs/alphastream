// Input: Error对象（含可选digest字段）+ reset回调函数
// Output: 顶层全局错误边界UI，包裹完整 HTML 文档（Next.js App Router 要求）
// Pos: Next.js App Router 全局最顶层错误兜底，覆盖 RootLayout 崩溃场景
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
// [NEW-FILE:#20260520-S3A] S3-A2 添加，属 CLAUDE.md 白名单 e 项

'use client';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="zh">
      <body>
        <div className="min-h-screen flex items-center justify-center p-6">
          <div className="max-w-md w-full text-center">
            <div className="text-6xl mb-4">&#9888;&#65039;</div>
            <h2 className="text-2xl font-bold mb-4">应用发生严重错误</h2>
            <p className="text-gray-600 mb-6 text-sm">
              {error.digest ? `错误摘要：${error.digest}` : '请尝试刷新页面或联系管理员'}
            </p>
            <button
              onClick={reset}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              重试
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
