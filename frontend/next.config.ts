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
          destination: 'http://localhost:8888/api/:path*',
        },
        // FIX-E4: /health 探针也要代理到后端，否则前端永远 404 → 错误显示"后端不可达"
        {
          source: '/health',
          destination: 'http://localhost:8888/health',
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
