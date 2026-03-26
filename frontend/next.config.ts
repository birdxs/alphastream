import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
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
      ];
    }
    return [];
  },
};

export default nextConfig;
