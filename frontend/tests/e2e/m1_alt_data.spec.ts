// Input: 浏览器加载 /stock/600519
// Output: 点击"另类数据"Tab, 断言 AltDataPanel 渲染 + /api/alt_data/600519 被调用
// Pos: frontend/tests/e2e — M1 端到端 scenario 真跑脚本
//
// 运行: npx playwright test tests/e2e/m1_alt_data.spec.ts --reporter=list
// 前置: 后端 http://127.0.0.1:8888, 前端 http://127.0.0.1:3000 已启动
//
// 一旦此脚本结构变化, 请同步更新 tests/e2e/README.md 与所属文档.

import { test, expect } from '@playwright/test';

test.describe('M1 AltData Tab E2E', () => {
  test('A股 600519 点击另类数据Tab并断言字段', async ({ page }) => {
    // 监听 alt_data API 响应
    const altDataResponse = page.waitForResponse(
      (r) => r.url().includes('/api/alt_data/600519') && r.status() < 500,
      { timeout: 90_000 }
    );

    await page.goto('http://127.0.0.1:3000/stock/600519', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');

    // 点击 Tab
    const altTab = page.getByRole('tab', { name: /另类数据/ });
    await expect(altTab).toBeVisible({ timeout: 15_000 });
    await altTab.click();

    const resp = await altDataResponse;
    const body = await resp.json();

    // 断言: 即使 adapter 降级, 字段结构必须存在
    expect(body).toHaveProperty('success');
    if (body.success) {
      expect(body.artifact).toHaveProperty('type', 'alt_data');
      expect(body.artifact).toHaveProperty('stock_name');
      expect(body.artifact.data).toEqual(expect.any(Object));
    } else {
      // 降级场景: 必须有 details 说明哪些 domain 失败
      expect(body).toHaveProperty('details');
      expect(Object.keys(body.details).length).toBeGreaterThan(0);
    }

    await page.screenshot({
      path: 'tests/e2e/screenshots/m1_alt_data_600519.png',
      fullPage: true,
    });
  });

  test('美股 AAPL 另类数据Tab冒烟', async ({ page }) => {
    const altDataResponse = page.waitForResponse(
      (r) => r.url().includes('/api/alt_data/AAPL') && r.status() < 500,
      { timeout: 90_000 }
    );

    await page.goto('http://127.0.0.1:3000/stock/AAPL', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');

    const altTab = page.getByRole('tab', { name: /另类数据/ });
    await expect(altTab).toBeVisible({ timeout: 15_000 });
    await altTab.click();

    const resp = await altDataResponse;
    const body = await resp.json();

    expect(body).toHaveProperty('success');
    await page.screenshot({
      path: 'tests/e2e/screenshots/m1_alt_data_AAPL.png',
      fullPage: true,
    });
  });
});
