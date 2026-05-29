# Changelog

## 2026-05-29 14:09:34 +08:00 — Wind P2b→P2d 真机连通修复与交付收尾

- 修复 Wind 数据源在真实网络下的三处连通问题，使其作为后端结构化财务/基本面数据源可用：
  - SSE 响应解析（commit `8057f0a`）：Wind MCP over HTTP 返回 `text/event-stream`，新增 `_parse_mcp_response` 解析 `data:` 行的 JSON-RPC，修复此前每次真实调用必失败降级空结果的问题。
  - 业务错误信封降级（commit `a8a741e`）：QUOTA_ERROR/AUTH_ERROR 等业务错误信封识别为失败并降级，不写缓存。
  - question 入参补全（commit `acdde93`）：按 Wind 官方契约补中文自然语言问句模板（财务/基本档案），修复缺 `question` 必填参导致服务端拒绝；附 2 个离线 mock 单测。
- 真机验证（今日 Wind 真机共消费 3 积分）：`600036.SH` 拿到真实结构化数据；`tools/list` schema 拉取免费；缓存命中 0 积分；配额扣减生效。
- 架构结论：保留 WindAdapter 作后端结构化数据源（`xbrl_financials` 链首），Wind 官方 skill 模式（Agent NL 工具层）列为可选 P3 暂缓。
- 收尾：还原 `.env-example` 中误入的 `WIND_API_KEY=ak_****` 占位值为空（合规，不含敏感样例）。验证（离线）：`test_wind_budget.py` 26 passed、registry 域测试 104 passed 无回归、import smoke ok。未连付费端点、未启服务、未跑 Playwright、未 push。

## 2026-05-29 12:00:00 +08:00 — Wind P2a 离线接入降级链

- `app/adapters/__init__.py`：导出 `WindAdapter`。
- `app/adapters/adapter_registry.py`：将 `WindAdapter` 置 `xbrl_financials` 域链首（Wind→EDGAR→YFinance→OpenBB），并加入 module_index 导入；严禁进入高频行情域（a_stock_kline/a_stock_realtime/market_indices）。未配 WIND_API_KEY 时返回空，由 fallback `_is_valid_result` 自动跳过，离线零网络调用。
- `app/core/tools.py` `get_fundamental_data`：加 Wind 优先源（仅 health_check 为真且返回非空才用，否则静默回落 FundamentalAnalyzer），工具签名/返回契约不变；不动 K线/实时行情工具。
- 验证（DISABLE_NETWORK=1）：import smoke `ok`；registry 链断言通过（Wind 链首、高频域无 Wind）；`test_wind_budget.py` 20 passed；registry domain 既有测试 104 passed 无回归。WIND_API_KEY 当前未配置。未启服务、未连网、未 push。

## 2026-05-29 11:40:00 +08:00 — Wind P1.5 加固

- 失败短时熔断（`app/adapters/wind_adapter.py`）：`_call_wind` 新增进程内 `(windcode,tool)→last_fail_ts` 熔断表（RLock 保护，env `WIND_FAIL_COOLDOWN` 默认 300s）。顺序：缓存命中优先返回 → 未命中且在冷却窗内直接降级（不消费额度、不发 HTTP）→ 配额闸门 → HTTP；失败写熔断标记，成功清除。避免对故障标的反复烧额度。
- sqlite WAL（`app/core/wind_budget.py` `_build_engine`）：sqlite 引擎开 `journal_mode=WAL`/`synchronous=NORMAL`/`busy_timeout=5000`（对照业务库 S1-C6），非 sqlite 跳过；WindCache/WindQuota 两引擎均生效。
- 补 4 个单测（`tests/backend/unit/test_wind_budget.py`）：并发 try_consume 无超扣、httpx 超时降级不写缓存、AUTH_ERROR 信封降级不写缓存、熔断冷却窗内二次降级且额度未再消费。
- 验证：import smoke `ok`；`pytest tests/backend/unit/test_wind_budget.py` → 20 passed（16→20）；未启服务、未连网、未 push。

## 2026-05-29 11:21:02 +08:00

- 新增 Wind(万得/aifinmarket) 金融数据源 P1 离线层（仅底座，不接入路由/registry/tools）：
  - `app/core/wind_budget.py` [NEW-FILE:#20260529-WIND-01]：`WindCache`（持久化缓存，sha256 cache_key，TTL 过期判定）+ `WindQuota`（日配额闸门 S/A/B 三档硬隔离，按 +08:00 自然日重置，落 sqlite 跨重启不丢）。独立引擎 `WIND_DATABASE_URL`（默认 `sqlite:///data/wind_cache.db`），与业务库 `USE_DATABASE` 完全隔离。
  - `app/adapters/wind_adapter.py` [NEW-FILE:#20260529-WIND-02]：`WindAdapter(BaseAdapter)`，MCP over HTTP/JSON-RPC 2.0 两步握手（initialize→tools/call）。统一入口 `_call_wind`：缓存优先(0积分)→配额闸门→HTTP→写缓存。`health_check` 仅查 `WIND_API_KEY`（不连网不烧积分）；基本信息(B,7d)/财务(S,30d)；行情不走 Wind 降级 None；成分股无工具返回 []；QUOTA/AUTH 错误静默降级 None。
  - `tests/backend/unit/test_wind_budget.py` [NEW-FILE:#20260529-WIND-03]：16 个全 mock 单测（缓存命中/过期/参数 key、配额内/超额/硬隔离/跨日、adapter 缓存命中不复消费额度、QUOTA_ERROR 降级、未配密钥禁用、`_to_windcode` 分支）。
  - `.env-example`：追加 `WIND_API_KEY`/`WIND_DATABASE_URL`/`WIND_QUOTA_S|A|B`/`WIND_CALL_TIMEOUT`（无真实密钥值）。
  - 验证：import smoke `ok`；`pytest tests/backend/unit/test_wind_budget.py` → 16 passed；全程未启服务、未连网、未 push。

## 2026-05-29 09:55:00 +08:00

- 配置层缓解开发模式 Turbopack 冷启动首次 `/health` 请求偶发超时：新增 `frontend/src/app/health/route.ts` Route Handler，等价代理后端 `127.0.0.1:8888/health`（强制 IPv4，设 `Connection: keep-alive`/`Cache-Control: no-cache`），镜像既有 `api/market_indices/route.ts` 方案。
- 根因：Next.js 16 dev 模式下 `next.config.ts` 的 `rewrites()` 为 runtime lazy-eval，首次请求触发 Turbopack JIT 编译（偶发超时）；而 Route Handler 在 dev server 启动时即编译，消除该路径冷启动首请求延迟。
- `frontend/next.config.ts`：移除现已由 Route Handler 接管的 `/health` rewrite 与对应 `headers()` 条目（`/api/:path*` 代理与 keep-alive 头不变）。
- `frontend/src/app/layout.tsx`：新增 `<link rel="prefetch" href="/health" as="fetch" />`，在 NetworkStatus 探针发起前预热该路由。
- 说明：`/` 根页面在 dev 模式仍按 on-demand 首次编译，属 Next.js dev 固有行为，无法在不启服务前提下安全验证收益；本轮仅做零运行时风险的配置层改动，`tsc --noEmit` 退出 0、`eslint` 目标文件退出 0（0 error 0 warning），未启动任何服务。

## 2026-05-29 09:50:00 +08:00

- 治理 `frontend/tests/e2e/p1_alt_data_real.spec.ts` 中既有的 4 个 `@typescript-eslint/no-explicit-any` 告警（行 47/59/78/91），零 `eslint-disable`、不改断言逻辑与覆盖范围。
- 新增局部类型 `AltApiBody`（`/api/alt_data` 响应体最小契约 + 可索引签名）与判别联合 `AltApiResult`（`{ ok: true; status; body }` | `{ ok: false; error }`）。
- `catch (e: any)` → `catch (e: unknown)`；`page.evaluate` 回调标注返回 `Promise<AltApiResult>`；`(apiResult as any).error` → 判别联合收窄后的 `apiResult.ok ? '' : apiResult.error`。
- 两个 test 块的 `const r: any` → 由返回值推断 `AltApiResult`，新增 `if (!r.ok) return;` 守卫使 TS 自动收窄到成功态后访问 `r.body`，类型安全且失败时仍中止测试。
- 验证：`tsc --noEmit` 退出 0 零错误；`eslint` 目标文件退出 0、0 error 0 warning。

## 2026-05-29 09:43:00 +08:00

- 治理前端 Recharts `The width(-1) and height(-1) of chart should be greater than 0` 警告：新增统一封装 `frontend/src/components/charts/safe-responsive-container.tsx`，用 `ResizeObserver` 实测容器渲染宽高，仅在宽高均 >0 时挂载 Recharts `ResponsiveContainer`，容器被隐藏（`display:none`）、切换或布局未完成（实测尺寸 ≤0）时渲染 `Skeleton` 占位，待尺寸有效后再渲染图表。
- 将 9 处直接使用 `ResponsiveContainer` 的图表替换为 `SafeResponsiveContainer`：`charts/base-line-chart.tsx`、`charts/base-bar-chart.tsx`、`charts/base-pie-chart.tsx`、`artifacts/capital-flow-chart.tsx`、`artifacts/score-radar.tsx`、`artifacts/esg-scorecard.tsx`、`artifacts/shipping-chart.tsx`、`artifacts/hiring-signal.tsx`（折线+饼图两处）。
- 遵守铁律 #1：占位仅为 `Skeleton` 骨架，不渲染任何看起来像真实金融数据的假值。

## 2026-05-29 09:32:08 +08:00

- 治理资金流上游网络降级日志：Eastmoney 个股/板块资金流遇到 `ProxyError`、`RemoteDisconnected`、`ConnectionError`、`Timeout` 等网络层异常时，改为 WARNING 级精简日志（"资金流上游降级: ..."），不再输出完整 Traceback；非网络类异常仍保留 ERROR 级完整堆栈，便于排查真实 bug。
- 返回契约保持不变（`get_individual_fund_flow`/`get_individual_fund_flow_rank`/`get_concept_fund_flow` 的 `data`/`error`/`count`/`source`/`amount_unit` 字段不变），新增单元测试覆盖网络降级与非网络异常分流。

## 2026-05-25 14:48:49 +08:00

- 修复后端任务清理中 aware `now_cn()` 与无时区 `updated_at` 字符串相减导致的启动日志错误。
- 修复 `/api/market_indices` 和 A 股名称缓存加载的 `ThreadPoolExecutor` 超时后等待问题，超时后快速返回降级结果。
- 在 `DISABLE_NETWORK=1` 离线测试环境禁用导入期新闻调度、任务清理与预热线程，避免测试退出后写 closed stream。
- 修复前端首屏 hydration mismatch：语音按钮、本地面板宽度、Dashboard 问候、Agent 折叠状态与对话日期分组改为挂载后读取动态状态。
- 将市场指数离线 503 降级改为前端安静占位/保留旧数据，减少开发联调 console 误报。

## 2026-05-25 15:10:37 +08:00

- 记录 Comdr 手动前端测试值守发现：OneAPI 429 自动重试后成功、资金流 Eastmoney ProxyError 当前会输出完整 Traceback、Recharts 零尺寸容器警告需后续治理。
- 确认手测收尾前后端仍可用：后端 `/health` 200，前端 `/dashboard` HEAD 200。
- 停止本地后端 8888 与前端 3000 服务，清理开发缓存并释放端口；未删除 `node_modules`，未 push。
