# E2E 测试

- `m1_alt_data.spec.ts` — M1 Stock页另类数据Tab端到端 scenario
- `screenshots/` — 运行产物（fullPage 截图）

运行: `npx playwright test tests/e2e/ --reporter=list`
前置: 后端8888 + 前端3000已启动。依赖 `@playwright/test` (需 `npm i -D @playwright/test` 后 `npx playwright install chromium`)。

一旦结构变化, 请更新此 README.
