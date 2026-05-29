# TODO

## 2026-05-29 11:21:02 +08:00 — Wind(万得) 数据源集成

- [x] P1 离线层底座：`app/core/wind_budget.py`（WindCache + WindQuota S/A/B 硬隔离）、`app/adapters/wind_adapter.py`（WindAdapter MCP HTTP，缓存+配额省积分）、`tests/backend/unit/test_wind_budget.py`（16 mock 单测全绿）、`.env-example` 追加 WIND_* 配置。不接入任何路由/registry/tools。
- [x] P1.5 加固：失败短时熔断（`WIND_FAIL_COOLDOWN` 默认 300s，进程内表 RLock 保护，冷却窗内不消费额度）、sqlite WAL（WindCache/WindQuota 两引擎）、补 4 单测（并发无超扣/超时降级/AUTH_ERROR 降级/熔断冷却）。pytest 20 passed。
- [x] P2a 离线接入降级链：`__init__.py` 导出 WindAdapter；registry 置 `xbrl_financials` 链首（Wind→EDGAR→YFinance→OpenBB），未污染高频行情域；`tools.py get_fundamental_data` 加 Wind 优先源（未配 key 静默回落）。离线零网络，registry 既有测试 104 passed 无回归。
- [x] P2b 真机连通验证（commit `8057f0a`）：修复 Wind MCP 返回 `text/event-stream`(SSE) 解析（`_parse_mcp_response` 收集 `data:` 行取最后有效 JSON-RPC），原 `resp.json()` 必失败降级空结果的根因已解。`tools/list` schema 拉取经核实免费。
- [x] P2c 业务错误信封降级（commit `a8a741e`）：Wind 业务错误信封（QUOTA_ERROR/AUTH_ERROR 等）识别为失败降级 None，不写缓存。
- [x] P2d question 入参补全（commit `acdde93`）：Wind 官方契约 `required=["question"]` 补中文 NL 模板（fundamentals/basicinfo，带 `lang=中文`）；`600036.SH` 真机拿到真实结构化数据；缓存命中 0 积分；配额扣减生效；今日真机共烧 3 积分。pytest 26 passed（含 2 个 question 模板断言）。
- [x] P2 question 模板质量核对（只读）：`get_financial_data`/`get_stock_info` 拼的 question 均为「标的+业务问题」合理中文 NL，符合 Wind 官方契约，无需改模板。
- [~] P3 Agent NL 工具层（可选/暂缓）：Wind 官方「skill 模式」（在 `app/core/tools.py` 暴露 Wind 取数工具供 Agent Function Calling）列为可选 P3，暂缓。架构结论：保留 WindAdapter 作后端结构化数据源即满足当前交付。
- [ ] P3 行情与成分股缺口评估（暂缓）：评估 `get_stock_kline` 是否在低频特殊场景启用（当前降级 None 避免烧积分）；成分股缺工具（当前返回 []）寻找替代。

## 2026-05-25 14:48:49 +08:00

- [x] 完成时间真实性校验、前后端启动、curl 连调与浏览器验收。
- [x] 修复后端启动任务清理 naive/aware datetime 日志错误。
- [x] 修复 `/api/market_indices` 与 `/api/stock_name` 冷启动超时后仍阻塞响应的问题。
- [x] 治理离线测试环境导入期后台线程，消除 pytest 结束期 closed stream logging error。
- [x] 修复前端 hydration mismatch，并将 market indices 离线降级改为安静处理。
- [x] 后续治理：`npm run lint` 中既有 `frontend/tests/e2e/p1_alt_data_real.spec.ts` 4 个 `no-explicit-any`（2026-05-29，见 CHANGELOG，已用判别联合类型 `AltApiResult` + `AltApiBody` 替换，零 `eslint-disable`）。
- [x] 后续治理：开发模式首次 Turbopack 冷启动偶发首页/health 超时（2026-05-29，见 CHANGELOG）。配置层缓解：`/health` 改由 `src/app/health/route.ts` Route Handler 代理（dev 启动即编译，替代 runtime lazy-eval 的 rewrite），并在 `layout.tsx` 补 `/health` prefetch 预热。`/` 根页面在 dev 模式仍按 on-demand 首次编译，属 Next.js dev 固有行为，需后续真机启动复测确认收益。

## 2026-05-25 15:10:37 +08:00

- [x] 完成 Comdr 手动前端测试值守日志收尾记录。
- [x] 停止本地前端 3000 与后端 8888 服务，并释放开发缓存。
- [x] 后续治理：资金流 Eastmoney 上游 `ProxyError/RemoteDisconnected` 属预期降级时，不应输出完整 Traceback；改为受控 WARNING 降级日志与可测试返回（2026-05-29，见 CHANGELOG）。
- [x] 后续治理：Recharts 图表容器 `width(-1)/height(-1)` 警告，已新增 `SafeResponsiveContainer` 统一封装，容器实测尺寸 ≤0 时渲染 Skeleton 占位（2026-05-29，见 CHANGELOG）。
- [ ] 下次手动测试：继续同步观测前后端日志，重点复核 `/api/ai/chat`、`/api/individual_fund_flow`、`/api/market_indices` 与图表页面切换。
