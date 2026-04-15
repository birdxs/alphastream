# E2E 测试

- `m1_alt_data.spec.ts` — M1 Stock页另类数据Tab端到端 scenario (role=tab 兼容存疑, 参考 p1)
- `p1_alt_data_real.spec.ts` — P1 真浏览器 e2e: 页面渲染 + 直连后端 /api/alt_data 链路 + 截图留证
- `screenshots/` — 运行产物（fullPage 截图, 已加 .gitignore）

运行: `npx playwright test tests/e2e/ --reporter=list`
前置: 后端 `:8888` + 前端 `:3000` 已启动。依赖 `@playwright/test` + `npx playwright install chromium`。
Dev 模式下 Next 16 hydration 使 Playwright click 偶尔不触发 state, 故 P1 spec 采用 `page.evaluate(fetch)` 直连后端验证 API 链路，保证稳定。

一旦结构变化, 请更新此 README.
