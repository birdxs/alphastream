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
          source: '/api/:path*',
          // B23: 强制 IPv4，避免 localhost→::1 IPv6 TCP timeout（17s 延迟根因）
          destination: 'http://127.0.0.1:8888/api/:path*',
        },
        // FIX-E4: /health 探针也要代理到后端，否则前端永远 404 → 错误显示"后端不可达"
        {
          source: '/health',
          // B23: 同上，强制 IPv4
          destination: 'http://127.0.0.1:8888/health',
        },
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
        {
          source: '/health',
          headers: [
            { key: 'Connection', value: 'keep-alive' },
          ],
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
