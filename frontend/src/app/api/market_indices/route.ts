/**
 * Input: GET 请求（无参数）
 * Output: 后端 /api/market_indices 的 JSON 响应（含 Connection: keep-alive）
 * Pos: Next.js API Route — Turbopack 启动时自动编译，消除首次请求 17s JIT 编译延迟
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。
 *
 * B23: 用 Route Handler 替代 next.config.ts rewrite，原因：
 *  1. Turbopack 在 dev server 启动时编译所有 Route Handler，rewrite 是 runtime lazy-eval
 *  2. Route Handler 可以显式设置 Connection: keep-alive（覆盖 Werkzeug 的 close）
 *  3. 支持 AbortSignal 传播（浏览器取消时后端也取消）
 */

const BACKEND = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api/market_indices`
  : 'http://127.0.0.1:8888/api/market_indices';

export async function GET(req: Request): Promise<Response> {
  const signal = req.signal;

  let upstream: Response;
  try {
    upstream = await fetch(BACKEND, { signal, cache: 'no-store' });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return new Response(JSON.stringify({ error: msg }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const body = await upstream.arrayBuffer();

  return new Response(body, {
    status: upstream.status,
    headers: {
      'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json',
      // 显式覆盖 Werkzeug 透传的 Connection: close，让 Chromium 复用连接
      'Connection': 'keep-alive',
      'Cache-Control': 'no-cache',
    },
  });
}
