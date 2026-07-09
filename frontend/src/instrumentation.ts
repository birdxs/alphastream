/**
 * Input: Next.js 服务器启动事件
 * Output: 预热 /api/market_indices Turbopack 路由编译
 * Pos: src/instrumentation.ts — Next.js 服务器启动钩子
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 *
 * B23: Turbopack dev server 对 /api/* rewrite 路由的首次请求需要 JIT 编译（约 17s）。
 * 本文件在服务器启动时预热这个路由，确保 Playwright 测试 / 用户首次访问时
 * 路由已编译完成，fetch 延迟 < 50ms 而非 17s。
 */
/**
 * 轮询等待 dev server 就绪（最多 30s），然后同步预热关键 API 路由。
 * `register()` 是 async，Next.js 会等待它完成后才标记服务器 Ready，
 * 这确保 Turbopack 在首次用户请求前已完成 JIT 编译（避免 17s 延迟）。
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs' && (process.env.NODE_ENV ?? 'development') === 'development') {
    const port = process.env.PORT || '3000';
    const baseUrl = `http://127.0.0.1:${port}`;

    // 轮询等待 dev server HTTP 就绪（最多 10s，每 200ms 一次）
    for (let i = 0; i < 50; i++) {
      try {
        const r = await fetch(`${baseUrl}/`, { signal: AbortSignal.timeout(500) });
        if (r.ok || r.status < 500) break;
      } catch {
        // 还没就绪，继续等
        await new Promise(res => setTimeout(res, 200));
      }
    }

    // 阻塞预热：等 Turbopack 编译完成（会耗时 ~17s，但之后用户首次请求就快）
    // 注意：register() 在 Next.js dev 里是 fire-and-forget，不阻塞 HTTP Ready
    // 因此预热完成前可能已经有用户请求进来；但一旦预热完成，后续请求就快了
    try {
      const ctrl = new AbortController();
      const tid = setTimeout(() => ctrl.abort(), 60000); // 60s 超时
      await fetch(`${baseUrl}/api/market_indices`, { signal: ctrl.signal });
      clearTimeout(tid);
      console.log('[B23-warmup] /api/market_indices Turbopack 路由预热完成');
    } catch (e) {
      console.warn('[B23-warmup] /api/market_indices 预热失败:', String(e).slice(0, 80));
    }
  }
}
