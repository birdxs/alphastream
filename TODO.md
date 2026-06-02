# TODO

## 2026-06-02 14:53:38 +08:00 — 前后端连调 + Kimi 真测前端能力（含 2 个治本修复）

- [x] 首页行情真测：SSE `market_stream` 推真实指数（上证 4057.74/深证 15340.36/创业板 3950.94/沪深300 4844.26）；REST 503 降级显 "---" 占位，无假数据、无 Hydration。
- [x] 仪表盘真测：自选股/持仓真实名称（腾景科技 688195 等）、`stock_quote_batch` 真实数据（688195=220.71/-5.64%）与 UI 一致。
- [x] 个股详情（600519）真测：股票名称修复完全生效（贵州茅台，无"未知"）；K 线降级（本机连不上 eastmoney）显"点击重试"占位合规。
- [x] AI 对话真测：真实 LLM（mimo-v2.5-pro）+ SSE + Function Calling 前半段正常；`get_stock_data` 工具卡死根因已治本。
- [x] `2f7828f` 治本：`StockProfileSchema` 补 `market_type` 字段（marshmallow `unknown=RAISE` 把前端 `market_type=A` 当未知字段拒绝→即时 400，基本面 tab 打不开）。离线 16 passed；真重启（PID 5040）铁证从 Unknown field 变 OneOf 校验。
- [x] `a6a3a12` 治本：`FallbackManager` 引入 per-call 硬超时（env `FALLBACK_PER_CALL_TIMEOUT` default 30，ThreadPoolExecutor 单次超时防 agent 工具永久挂死）。71 passed + 3 新超时用例，0 回归；真重启（PID 5835）日志实证超时切 adapter，stock_data 200/17.9s 返真实 K 线。
- [ ] 2 个 commit 均未 push，待 Comdr 决定是否 push。
- [ ] 改天续测：对比（`/compare`）/组合（`/portfolio`）/市场扫描/`api-docs` 的 Kimi 真测（对比页因内存紧+UI 超时中止）。
- [ ] 改天续测：C 方案 AI 对话 agent 路径 UI 层真测验证（后端日志已实证 per-call 超时生效）。
- [ ] 改天续测：`profile`/`stock_data` 真实数据需可联网环境复测（本机连不上 A 股实时源）。

## 2026-05-29 17:39:14 +08:00 — 股票名称显示修复轮（analyzer 真实键名 + 可重试缓存 + 后台预热）

- [x] `5fb8734` analyzer 真实键名归一化：`stock_analyzer.get_stock_info` 解析层按 8 候选键（股票名称/股票简称/code_name/shortName/longName/org_short_name_cn/org_name_cn/name）优先级取名，"未知"视为无效，全 miss 兜底退股票代码（合规铁律 #1）；+7 正向单测，改 2 旧 bug 断言。
- [x] `1f71c10` 可重试 A 股名称缓存 + 雪球结构守卫：超时 5s→15s；失败改记 `_CACHE_LAST_FAIL_TS` + 冷却窗 `STOCK_NAME_CACHE_RETRY_COOLDOWN_S`(60s) 可重试，仅成功才永久标记已加载，双重检查锁定防风暴；雪球路径补 df 非空+首行 dict 守卫（行为不变）；+5 离线单测。
- [x] `94e8c5f` 名称加载移后台预热：前台 4 处请求路径只读缓存不阻塞（去掉最多 15s 同步等待），未命中退股票代码；新增 `_preload_stock_names` 后台线程（`_startup_background_enabled()` 门控，`DISABLE_NETWORK=1` 不启，失败 sleep 节流、成功即退、异常不杀线程）；+4 单测。
- [x] `b1fad03` 修测试瑕疵：name-safe 测试改 patch 全局 `analyzer`（原 patch `get_analyzer` 为死代码），注入真正生效；class 耗时 6.58s→0.62s。
- [x] 复核与回归：4 commit 各经独立 fresh-eyes 复核通过；`TestStockNameRoute` 10 passed、`TestAkshareXueqiuSchemaGuard` 3 passed、`test_analysis_stock_analyzer.py` 59 passed。
- [ ] 4 个 commit 均未 push，待 Comdr 测试后决定是否 push。
- [ ] 联调剩余项待 Comdr 本地或高配环境补完：前端代理、美股链路、openapi、首页。
- [ ] backlog 备注：issue #35 本轮已解可关闭；#33/#30 非代码项；PR #37 暂忽略。

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
