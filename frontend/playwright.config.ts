// Input: Playwright CLI 读取此配置
// Output: 统一 baseURL / retries / 截图&trace 策略
// Pos: frontend/playwright.config.ts — P1 真浏览器 e2e 根配置
//
// 一旦此配置变化, 请同步更新 tests/e2e/README.md.

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  retries: 1,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'off',
    actionTimeout: 15_000,
    navigationTimeout: 60_000,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // 用完整 chromium (channel:'chromium'), 避开 headless-shell 未下载
        channel: 'chromium',
      },
    },
  ],
});
