import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  allowedDevOrigins: ['127.0.0.1', 'localhost', '192.168.43.125'],
  turbopack: {
    root: process.cwd(),
  },
  experimental: {
    optimizePackageImports: ['recharts', 'lucide-react'],
  },
  async rewrites() {
    // 仅开发环境使用rewrites代理
    // 生产环境由Nginx反代处理
    if (process.env.NODE_ENV === 'development') {
      return [
        {
          source: '/api-docs',
          destination: 'http://127.0.0.1:8888/api/docs/',
        },
        {
          source: '/api-docs/:path*',
          destination: 'http://127.0.0.1:8888/api/docs/',
        },
        {
          source: '/api/:path*',
          // B23: 强制 IPv4，避免 localhost→::1 IPv6 TCP timeout（17s 延迟根因）
          destination: 'http://127.0.0.1:8888/api/:path*',
        },
        // S-UI-4: Swagger UI 配置 API_URL=/static/swagger.json（Flask 静态）。
        // 经 :3000 打开 /api-docs 时浏览器会同源请求 /static/*；此前未代理 → 404，定义加载失败。
        // Next 自身静态在 /_next/static，/static/* 仅后端 Flask 使用，开发期整前缀代理安全。
        {
          source: '/static/:path*',
          destination: 'http://127.0.0.1:8888/static/:path*',
        },
        // P2: /health 探针改由 src/app/health/route.ts Route Handler 代理。
        // 原 rewrite 是 runtime lazy-eval，首次请求触发 Turbopack JIT 编译偶发超时；
        // Route Handler 在 dev server 启动时即编译，消除冷启动首请求延迟（同 market_indices）。
      ];
    }
    return [];
  },

  async headers() {
    // B23: 覆盖 Werkzeug 透传的 Connection:close，让浏览器能复用 TCP 连接
    // 避免 Playwright/Chromium 每次 fetch /api/* 都重新建立连接（16s 冷启动）
    if (process.env.NODE_ENV === 'development') {
      return [
        {
          source: '/api/:path*',
          headers: [
            { key: 'Connection', value: 'keep-alive' },
          ],
        },
        // P2: /health 的 keep-alive 头由 src/app/health/route.ts Route Handler 自行设置。
      ];
    }
    return [];
  },
};

export default nextConfig;
