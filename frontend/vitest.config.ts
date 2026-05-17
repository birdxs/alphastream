// Input  : Vitest 启动时读取该配置
// Output : 前端单元/组件测试环境（jsdom）、覆盖率（v8）输出目录
// Pos    : frontend/ 根目录；与 next.config.ts / tsconfig.json 同级
//
// 一旦此文件修改，请同步更新 tests/audit/test_framework.md。

import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: [
      "tests/**/*.{test,spec}.{ts,tsx}",
      "../tests/frontend/**/*.{test,spec}.{ts,tsx}",
      "src/**/*.{test,spec}.{ts,tsx}",
    ],
    exclude: [
      "node_modules/**",
      "tests/e2e/**",
      ".next/**",
      "test-results/**",
    ],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json", "lcov"],
      reportsDirectory: "../tests/audit/evidence/frontend_coverage",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.d.ts",
        "src/**/*.stories.tsx",
        "src/**/__mocks__/**",
        "node_modules/**",
      ],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    fs: {
      // 允许访问父级 tests/ 目录（W1a 落盘的 tests/frontend/** 测试位于仓库根下）
      allow: [path.resolve(__dirname, ".."), path.resolve(__dirname, ".")],
    },
  },
});
