# TODO

## 2026-05-25 14:48:49 +08:00

- [x] 完成时间真实性校验、前后端启动、curl 连调与浏览器验收。
- [x] 修复后端启动任务清理 naive/aware datetime 日志错误。
- [x] 修复 `/api/market_indices` 与 `/api/stock_name` 冷启动超时后仍阻塞响应的问题。
- [x] 治理离线测试环境导入期后台线程，消除 pytest 结束期 closed stream logging error。
- [x] 修复前端 hydration mismatch，并将 market indices 离线降级改为安静处理。
- [ ] 后续治理：`npm run lint` 中既有 `frontend/tests/e2e/p1_alt_data_real.spec.ts` 4 个 `no-explicit-any`。
- [ ] 后续治理：开发模式首次 Turbopack 冷启动偶发首页/health 超时，热身后已复测通过。
