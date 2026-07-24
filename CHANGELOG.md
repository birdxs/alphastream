# Changelog

## 2026-07-24 — [S-UI-docs] 对齐 S-UI-0~3 已落地口径（docs only）

- 修正滞后表述：S-UI-0~3 **代码已落地**（样例 commit：`972f3b8` / `9ec81f2` / `f8d0fe3` / `ddf1d50` / `3a5c6c7` 等）；**S-UI-4 终验待 WebBridge**（非「阻塞于 0~3」）。
- `docs/design/ui-renovation-plan.md` → `v1.2-sui-code-landed`：文末审批栏、§8 验收分层、§12 commit 样例、附录决策摘要同步。
- `TODO.md` UI 节已与「0~3 已落地 / 4 终验待」一致；未改业务代码；未启服务；**未 push**。

## 2026-07-24 — S-UI-4 静态预检 + 改造进度跟踪

- Comdr 已全批 A–D；**（历史条目）** 当时记 S-UI-0 WIP；**现口径以本节上方 [S-UI-docs] 与 plan v1.2 为准：0~3 已落地**。
- S-UI-4 静态预检：`tsc --noEmit` / 关键路由 eslint exit 0；dashboard/settings/portfolio 长页滚动代码审通过；**终验待 WebBridge**（0~3 已不构成阻塞）。
- 文档：`TODO.md` UI 节、`docs/design/ui-renovation-plan.md` §12。**仍禁 push**。

## 2026-07-23 — 方案复审·文档对齐（docs only）

- 对齐 `docs/design/dojo-agents-absorption-plan.md` §11 / §9.2 / 审批栏 / 结论：Plan=状态机、Skills=system_hint、Memory 启动预取、provenance 已强制；删除「Skills/Plan 未开」「provenance 仍待」等过时句。
- `docs/design/DELIVERY-STATUS.md` → **v1.12-doc-align-capability-truth**：新增 §11 能力真相表；更新 §5 限制与「仍暂缓项」。
- `docs/design/README.md` / `CLAUDE.md` / `TODO.md` 同步记录。
- **未改业务代码**；未启服务；未 push。

## 2026-06-15 13:48:26 +08:00 — OpenAPI 文档覆盖收口（第三~六批）+ 依赖维护

- OpenAPI 文档第三批扩充（`73bfc36`）：`/api/openapi.json` 新增 8 个端点 operation，覆盖更多 `/api/*` 业务路由。
- OpenAPI 文档第四批扩充（`2258f04`）：再新增 10 个端点 operation。
- OpenAPI 文档第六批扩充（`c9ced74`）：再新增 7 个端点 operation。
- OpenAPI 文档第五批补做（`0f114f8`）：补齐 9 个端点 operation（本批因质量事件补做，详见 TODO）。
- 依赖维护——移除死依赖 + Next 升级（`7734ed8`）：从前端依赖中移除未被引用的 `jotai` 死依赖；`next` 由 16.2.6 升级至 16.2.9。
- 依赖维护——锁文件漂移同步（`535973b`）：同步 `package-lock.json` 漂移，消除 `next` high 级别安全告警的假阳性。
- 收口结论：OpenAPI `paths` 由 30 增至 64，`/api/*` 业务路由基本收口；剩余有意保留的特例为 SSE `market_stream` 与 A2A 协议端点（待后续专项文档化）。
- 说明：本轮仅扩充静态 OpenAPI 文档与依赖元数据，未改运行时路由行为；未启服务、未 push。

## 2026-06-02 14:53:38 +08:00 — 前后端连调真测：基本面 tab 400 与 agent 工具挂死两处治本修复

- 修复个股基本面 tab 打不开（`2f7828f`）：`/api/stock_profile` 的 `StockProfileSchema` 缺 `market_type` 字段，marshmallow 默认 `unknown=RAISE` 把前端传入的 `market_type=A` 当作"未知字段"直接拒绝，返回 0.002s 即时 400，导致 PE/PB/ROE 基本面 tab 无法加载（路由本身并不读该字段）。补 `market_type = fields.String(load_default='A', validate=mv.OneOf(['A','HK','US','B']))`（对齐同文件 `StockDataSchema`）。属自 Sprint 3-C 引入的既有缺陷，非回归。
- 修复 AI 对话 agent 工具挂死（`a6a3a12`）：agent 工具 `get_stock_data` 的数据拉取链全程无 per-call 超时（`fallback_manager` 裸阻塞 + akshare 无 socket timeout），网络停顿时永久阻塞，唯一兜底为 30min 的 `AGENT_GRAPH_TIMEOUT`（等同无超时），SSE 停在 0% 前端永久"分析中"。为 `FallbackManager` 单次 adapter 调用引入 `ThreadPoolExecutor` 硬超时（env `FALLBACK_PER_CALL_TIMEOUT`，默认 30s，`finally cancel_futures` 防线程泄漏），超时抛 `TimeoutError` 落入现有 except 自动切下一 adapter。未用 `resilient_call`（其自带 3 次重试会与 `max_retries=2` 叠加成 6 次重试风暴）。属设计遗漏，非回归。
- 真测覆盖（Kimi WebBridge 真实浏览器，禁 Playwright）：首页 SSE 真实指数 + 503 降级 "---" 占位无假数据；仪表盘真实名称/行情；个股 600519 名称修复生效（无"未知"）；AI 对话真实 LLM + Function Calling 前半段正常。本机连不上 A 股实时源（eastmoney 不可达），K 线/基本面/agent 多端点降级属真实网络限制非代码缺陷。
- 验证：profile 修复离线 16 passed + 真重启（PID 5040）从 Unknown field 变 OneOf 校验；fallback 修复 71 passed + 3 新超时用例（adapter sleep 30s 测试亚秒完成）0 回归 + 真重启（PID 5835）日志实证超时切 adapter、stock_data 200/17.9s 返真实 K 线。本轮文档同步未启服务、未连付费端点、未跑测试、未 push。

## 2026-05-29 17:39:14 +08:00 — 修复股票名称显示为"未知" + 名称加载稳定性增强

- 修复股票名称显示为"未知"：此前即便上游数据源成功返回，名称仍被错误兜底成"未知"。根因是解析层只认 `name`/`股票名称` 字段，而真实数据源用的是各自的字段名（东财 `股票简称`、baostock `code_name`、雪球 `org_short_name_cn`/`org_name_cn`、yfinance `shortName`/`longName`）。现按多候选键归一化取名，并将全部取不到时的兜底由"未知"改为显示股票代码本身（不展示假名称，遵守金融数据零假值铁律）。
- 名称加载稳定性增强（可重试 + 后台预热）：
  - A 股名称缓存加载失败后不再"一次失败永久放弃"，改为带冷却窗（默认 60s）的可重试，超时阈值由 5s 放宽到 15s，仅加载成功才标记完成；并发场景下用双重检查锁定防止重试风暴。
  - 名称加载移至后台预热线程，用户请求路径不再因等待名称缓存而阻塞（最长可省去 15s 等待）；缓存未命中时即时以股票代码占位返回。后台预热在加载成功后自动退出、失败时按冷却窗节流、离线模式（`DISABLE_NETWORK=1`）不启动。
  - 对雪球数据源响应补充结构守卫，异常响应受控降级（行为与返回契约不变）。
- 验证：相关单元测试 `TestStockNameRoute`（10）、`TestAkshareXueqiuSchemaGuard`（3）、`test_analysis_stock_analyzer.py`（59）全部通过；4 个 commit 各经独立复核。本轮文档同步未启服务、未连网、未 push。

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
