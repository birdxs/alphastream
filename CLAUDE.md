# StockAnal_Sys 项目级 CLAUDE.md

> 本文件为本项目专属纪律与上下文记忆，全局 `~/.pandacc/CLAUDE.md` 优先于本文件，但本文件中的硬性纪律不得被忽略。

---

## 🚨 铁律 #1：金融数据零假值（最高优先级，2026-05-19 19:30 入永久记忆）

**触发背景**：B27 Kimi 真测发现 dashboard 10s 显示假数据 1174.06 / 4384.17（组件 mock / SWR fallback 旧值），用户可能误以为是真实行情。Comdr 严正声明：金融领域追求数据精确度，禁止任何场景下任何理由使用任何假数据。

### 强制约束

1. **严禁任何形式的假数据**，包括但不限于：
   - 组件 `useState(MOCK_DATA)` 初始 state 含具体数值
   - SWR `fallbackData` / `initialData` 含具体数值
   - localStorage / sessionStorage 缓存命中旧 schema 返回旧值
   - mock module / fixtures 在生产代码路径被引用
   - demo / placeholder / stub 数据流入用户可见 UI
   - 测试 fixture 的硬编码股价/指数被 prod 代码 import

2. **数据未到位时唯一允许的呈现**：
   - `<Skeleton />` / `<Spinner />`（loading 态）
   - "—" / "暂无" / "加载中"（明确无数据文案）
   - `null` / `undefined`（不渲染）
   - 禁止任何看起来像真实金融数据的占位（包括 0.00 / N/A 数字、demo 股价、历史快照）

3. **代码审查**：
   - 任何 PR 含数字硬编码（除 timeout/limit/page-size 等基础设施常量）必须明确说明非数据用途
   - 任何 `fallback` / `default` / `mock` / `placeholder` 命名的变量含数值必须代码评审

4. **测试义务**：
   - 用 Kimi WebBridge 真测，多时间窗采样（5s/10s/15s/20s/30s）
   - 任何时间窗显示"看起来像真数"但与 API 返回不一致 = 假数 bug

5. **违反处理**：
   - 发现假数据 = Blocker 级别立即修
   - commit message 必须标注遵守本铁律

---

## 团队管理机制（继承全局）

- 香草少校担任 PM，下达指令、跟踪验收，不插手具体事务
- agent team 24 名成员按分工执行，责任到人
- 验收通过后立即释放 agent 节约资源
- 阶段性工作 auto 推进，不必频繁回报

---

## 工作纪律：杜绝伪修复（最高优先级，2026-05-18 入永久记忆）

**触发背景**：前一 worker 宣称 6 类问题全 PASS，实际后端 PID uptime=2418s（40min），证明旧进程从未真重启、代码改动未生效。属虚假汇报，严重失职。

任何修复任务必须满足**铁证三件套**才算 PASS：

1. **进程指纹**
   - 服务重启后 `uptime_s < 60` 才算真重启
   - 引用旧 PID / 旧 uptime 视为伪重启
   - 必须 `lsof -ti:PORT | xargs kill -9` + `pkill -9` 双保险清进程

2. **真实复现**
   - 每个问题先在真实浏览器（Kimi WebBridge）复现现象
   - 截图保存原现象（REAL_BEFORE_*）
   - 修复后同操作再次截图证明现象消失（REAL_AFTER_*）
   - **前后对比双截图，不允许只截通过态**

3. **真实数据**
   - 所有数值证据必须来自真实接口 / 真实 LLM 调用
   - mock / stub / 单元测试 PASS **不构成**问题解决证据
   - 必须有 DevTools Network 标签真实请求/响应 或 curl 真实返回

**违反任意一条 = 伪修复 = 任务失败。**

不接受：
- "unit test PASS"
- "代码已改"
- "截图显示有数据"（无对比基线）
- "自审钩子返回空数组"

只接受：
- 旧现象的真实截图 + 改动 + 真重启 + 同操作下新现象消失的真实截图
- 浏览器 DevTools Console 与 Network 标签真实证据
- 后端日志 grep 真实存在的关键字（heartbeat / 配置加载等）

---

## 项目关键端口

- 后端：`http://127.0.0.1:8888`（FastAPI / Flask via run.py）
- 前端：`http://127.0.0.1:3000`（Next.js dev）
- 健康端点：`/health`（必须返回 `uptime_s`）

---

## 真重启标准动作

```bash
lsof -ti:8888 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
pkill -9 -f "python.*run.py" 2>/dev/null
pkill -9 -f "next dev" 2>/dev/null
sleep 5
# 启动后立刻 curl /health 校验 uptime_s < 60
```

---

## 市场指数 17s 延迟修复记录（commit 2ef5473，2026-05-19 21:05 +08:00）

### 根因分析

本次修复解决了 `/api/market_indices` 首次请求 17s 延迟导致首屏 `···` loading 卡住的问题，共三层根因：

1. **Turbopack JIT 编译延迟（17s）**：`next.config.ts` 里的 rewrite 规则为运行时延迟编译，首次请求需等 Turbopack 编译约 17s。修复：创建 Next.js Route Handler（`frontend/src/app/api/market_indices/route.ts`），Turbopack 启动时即编译，首次请求 ~30ms。

2. **并发 akshare 竞争（各自独立调 akshare，16s 延迟）**：prefetch + React fetchIndices 并发到达后端时，各自独立调用 akshare API，导致竞争和延迟。修复：加 `_market_indices_lock`（双重检查锁定模式），同时只有一个线程调 akshare。

3. **缓存 30s 到期无刷新**：30s TTL 到期后，下一次请求又是冷缓存。修复：`_preload_market_indices()` 改为循环刷新（每 25s），确保缓存始终有效。

### 额外修复

- `get_market_indices()` 加快速超时（`INDEX_FAST_TIMEOUT_MS=1500ms`），冷启动时 1.5s 内返回 degraded，前端 loading 消失
- `fetchIndices()` 改回走 same-origin proxy（Route Handler），不再直连 8888
- `layout.tsx` 加 `<link rel=prefetch>`，提前触发 Route Handler warmup

### 验证证据

```
has_dots@5s: false (Playwright headless, sequential runs)
has_loading@5s: false
上证指数 4169.54 +0.92% (真实数据)
```

---

## 时间真实性校验记录（2026-05-19 01:46:03 +08:00）

- 校验发起：2026-05-19 01:46:03 +08:00
- 本机系统时间：Tue May 19 01:46:03 CST 2026（Asia/Singapore +08:00）
- 时间源 1：`curl -sI https://timeanddate.com` → `Date: Mon, 18 May 2026 17:46:04 GMT`（UTC+0 = +08:00 即 2026-05-19 01:46:04）
- 时间源 2：`curl -sI https://www.cloudflare.com` → 已获取（与源1偏差 < 5秒）
- 最大偏差：< 5 秒（阈值 100 秒）
- 判定：**通过**
- 基准时间锚点：2026-05-19 01:46:03 +08:00（供后续日志引用）

---

## 证据清单（2026-05-19 T9 timeout 富足化 + LangGraph #7845 审计）

### 议题1：env-driven timeout 最佳实践

- 来源1（官方）：https://docs.python.org/3/library/os.html#os.getenv — Python 3.12 / 检索时间 2026-05-19 01:50 +08:00 — `os.getenv(key, default)` 标准写法，采用
- 来源2（OpenAI SDK）：https://github.com/openai/openai-python — v1.x SDK 中 `httpx.Timeout` 参数文档，采用
- 来源3（Next.js env）：https://nextjs.org/docs/app/building-your-application/configuring/environment-variables — NEXT_PUBLIC_ 前缀规范，采用
- 结论：采用 `os.getenv(KEY, default)` / `Number(process.env.NEXT_PUBLIC_FOO) || default` 模式

### 议题2：LangGraph #7845 streaming tool_call 消息泄漏

- 来源1（Issue）：https://github.com/langchain-ai/langgraph/issues/7845 — 联网核查，issue 描述 streaming 模式下共享 graph instance 可能导致跨会话 tool_call_id 泄漏
- 来源2（LangGraph docs）：https://langchain-ai.github.io/langgraph/concepts/checkpointing/ — thread_id 隔离机制文档
- 来源3（本地代码）：`app/agents/coordinator.py:490` — `graph = build_analysis_graph(...)` 每次调用均新建实例
- 结论：**本项目不受 #7845 影响**，详见下方审计报告

---

## LangGraph #7845 审计报告（2026-05-19 01:50 +08:00）

### 审计结论：不受影响

### 证据链（三项缺一不可）

**1. 无 astream/stream 调用**

```
grep -n "astream\|\.stream(" app/agents/coordinator.py
# 零输出 — 项目仅使用同步 graph.invoke()
```

**2. 每 request 独立 graph instance（非 singleton）**

```python
# coordinator.py:490
graph = build_analysis_graph(research_depth, selected_analysts)  # 每次调用新建
```

`build_analysis_graph()` 在函数内部构建 `StateGraph`，没有模块级缓存、`@lru_cache` 或全局变量复用。

**3. thread_id 隔离 + 独立初始 messages**

```python
# coordinator.py: invoke_config
invoke_config = {'configurable': {'thread_id': thread_id}}
# initial_state['messages'] = []  # 每次从空列表开始
```

每个分析请求使用独立 `thread_id`（= conversation_id），SqliteSaver 按 thread_id 分区存储，不存在跨会话 messages 污染。

### 为何不受影响

LangGraph #7845 的根因是：共享同一个 graph **实例** 并用 `astream` 做并发请求，导致内部 tool_call_id 队列在多会话间交叉。本项目：
- 使用 `invoke`（同步，单 future 串行）
- 每次请求独立新建 graph instance
- initial state messages 从空列表初始化

上述三点共同保证不受 #7845 影响，**无需修复**。

---

## Timeout 富足化变更记录（commit df1764d，2026-05-19 01:52 +08:00）

| env key | 接入文件 | 行为变化 |
|---|---|---|
| AI_HTTP_TIMEOUT | app/core/ai_client.py:41 | httpx.Timeout 第一参数改 env，default 600 |
| AI_HTTP_CONNECT_TIMEOUT | app/core/ai_client.py:41 | httpx.Timeout connect 改 env，default 15 |
| AI_CHAT_TIMEOUT | app/web/web_server.py:2971 | default 900→1800 |
| AGENT_GRAPH_TIMEOUT | app/agents/coordinator.py:552 | graph.invoke() 包 ThreadPoolExecutor，default 1800 |
| NETWORK_RESILIENCE_DEFAULT_TIMEOUT | app/core/network_resilience.py:137 | per_call_timeout 默认值改 env，default 30 |
| NETWORK_RESILIENCE_CACHE_TTL | app/core/network_resilience.py:138 | cache_ttl 默认值改 env，default 600 |
| STOCK_DATA_THREAD_TIMEOUT | app/web/web_server.py:1192 | fut.result(timeout=env)，default 50 |
| ADAPTERS_STATUS_OVERALL_TIMEOUT | app/web/web_server.py:4015 | as_completed(timeout=env)，default 10 |
| ADAPTERS_STATUS_PER_CALL_TIMEOUT | app/web/web_server.py:4010 | _hc_one 第3参数改 env，default 5 |
| ALT_DATA_SUBTASK_TIMEOUT | app/web/web_server.py:3762 | _p3_call_with_timeout timeout 改 env，default 45 |
| NEXT_PUBLIC_API_DEFAULT_TIMEOUT_MS | frontend/src/lib/api/client.ts | get/post 加 AbortController，default 60000 |
| NEXT_PUBLIC_SSE_HEARTBEAT_TIMEOUT_MS | frontend/src/lib/api/client.ts | idleMs 优先读该 key，default 120000 |
| PROFILE_BAOSTOCK_TIMEOUT_S | app/web/web_server.py:1477 | baostock 主路径 hard deadline，22s→8s（可由 env 覆盖） |

---

## P1 baostock 超时削减变更记录（commit ab0658c，2026-05-19 18:58 +08:00）

- 改动文件：`app/web/web_server.py` 3 处（行 1392 注释、行 1477 timeout 值、行 1479 warning 文案）
- env key：`PROFILE_BAOSTOCK_TIMEOUT_S`，default=8
- 铁证：真重启 PID=35618 uptime_s=6.88，4 股票实测 Total<14s（原 26-28s），HTTP=200，pe_ttm/pb/roe/market_cap 全非空
- Playwright 截图：/tmp/b21-stock-5s.png（K线已加载）、/tmp/b21-stock-15s.png（at15s_has_loading=false）

---

## M1/M2 实时指数兜底链变更记录（commit 88e0a3c，2026-05-19 19:22 +08:00）

### 根因
`push2.eastmoney.com` 代理失败，`stock_zh_index_spot_em()` 挂死无响应，首页/Dashboard 指数永久显示 `···`/加载中。

### 方案（三级兜底 + 启动预热）
1. 主路径：东财 `stock_zh_index_spot_em`（5s 超时）
2. 兜底1：新浪 `stock_zh_index_spot_sina`（15s 超时，实测 ~9s，4 指数齐全）
3. 兜底2：历史日线 `stock_zh_index_daily` 4 路并发（12s 超时）
4. 兜底3：返回过期缓存（source=stale_cache）
5. 30s 内存缓存（`INDEX_CACHE_TTL_S`），缓存命中 <50ms
6. 启动预热线程：服务启动 2s 后自动拉取，消除首次请求 17s 等待
7. 响应头 `X-Data-Source` / `X-Cache` 标记来源

### 新增 env
| key | default | 说明 |
|---|---|---|
| INDEX_PRIMARY_TIMEOUT_S | 5 | 东财超时 |
| INDEX_FALLBACK_TIMEOUT_S | 15 | 新浪超时 |
| INDEX_CACHE_TTL_S | 30 | 内存缓存 TTL |

### 铁证
- 真重启：uptime_s=4.057（PID 37570）
- API 首次响应：17.8s（东财5s超时 + 新浪~9s），X-Data-Source: sina
- 缓存命中响应：0.035s，X-Cache: HIT
- Playwright 截图（2026-05-19 19:20 +08:00）：
  - `home_has_dots: false`（上证4169.54/深证15569.91/创业板3908.44/沪深3004852.88）
  - `home_has_realnum: true`
  - `dash_has_loading: false`（市场概览全部渲染完成）
- 截图路径：`/tmp/b20-home-after.png`、`/tmp/b20-dashboard-after.png`

---

## Batch 16 变更记录（commit 2c5caf9，2026-05-19 12:40 +08:00）

### 改动 1：AkshareAdapter health_check 探针优化

- 文件：`app/adapters/akshare_adapter.py`
- 变更：
  - 新增模块级缓存常量 `_AKSHARE_HC_CACHE` / `_AKSHARE_HC_TTL` / `_AKSHARE_HC_PROBE_SYMBOL`
  - 将 `health_check` 从 `ak.stock_zh_a_spot_em()`（全市场拉取，~9s）改为 `ak.stock_individual_spot_xq()`（单股快照 + 60s 缓存）
- 实测：冷启动 3740ms（< 5000ms），缓存命中 0ms
- 新增 env 键：`AKSHARE_HC_CACHE_TTL`（default 60）、`AKSHARE_HC_PROBE_SYMBOL`（default SH600519）

### 改动 2：B12 stock_profile akshare 兜底链（方案 D 分层混合）

- 文件：`app/web/web_server.py`
- 变更：
  - 新增 `_PROFILE_STALE_MAX_S`（env `PROFILE_STALE_MAX_S`，default 86400）
  - 新增内嵌函数 `_akshare_fill(prof, fields, budget_s)`：使用 `stock_individual_spot_xq`（PE/PB/市值）+ `stock_financial_abstract`（ROE）并行补齐缺失字段
  - `_do_all_baostock` 末尾：baostock 返回缺失字段时自动调 `_akshare_fill`
  - 外层 `except (_TPETimeout, TimeoutError)`：baostock 超时 → akshare-only 兜底 → stale cache → 503 三级降级
- 实测：600519/000001/000651 全部 HTTP=200 + X-Data-Source=akshare-fallback
  - 600519: market_cap=16553.89亿、pe_ttm=20.013、pb=6.111、roe=10.57
  - 000001: market_cap=2105.51亿、pe_ttm=4.89、pb=0.454、roe=2.83
  - 000651: market_cap=2181.19亿、pe_ttm=7.582、pb=1.455、roe=4.07
- industry 字段：当前 akshare 可用端点均无行业字段（em/xq 均受限），保持 null

### 时间校验记录（Batch 16）

- 本机：2026-05-19 12:40:00 CST（Asia/Singapore +08:00）
- 源1：timeanddate.com HTTPS Date 头
- 源2：cloudflare.com HTTPS Date 头
- 最大偏差：< 5s，判定通过
- 真重启铁证：PID=67520，uptime_s=4.463（< 60）

### pytest 回归（Batch 16，2026-05-19 12:50 +08:00）

- 620 passed，1 failed（test_T018_concurrent_add_message，预存在 bug，Batch 16 改动前已失败，与本次无关）

---

## B25 首页顶栏指数修复记录（commit 3ab9302，2026-05-19 21:33 +08:00）

### 根因
`MarketOverview` 组件首次调用 `/api/market_indices` Route Handler 时，后端偶发 degraded 返回 `indices=[]`（空响应或 source=degraded），原始 `fetchIndices` 里 `else { setError(true) } finally { setLoading(false) }` 会立即结束 loading 进入 error 态，而后续 SSE 如未及时推数据则 5s 内仍显示 `···`（React 重新 mount 后 loading 重置）。

### 修复方案
- `fetchIndices` 改为返回 `Promise<boolean>`，有数据时 return true + `setLoading(false)`，降级/空响应/JSON解析失败时 return false（不设 error，不 setLoading）
- `useEffect` 初始加载改为 `initFetch(attempt)` 带重试：最多3次（间隔800ms），3次全部失败才兜底 `setLoading(false)+setError(true)`
- 新增 `loadingTimer` ref，cleanup 时正确清理重试定时器

### 铁证（2026-05-19 21:33 +08:00）
- Playwright 5s：`has_dots=false` / `has_realnum=true`
- `body_top` 含：上证指数4169.54 +0.92%、深证成指15569.91 +0.26%、创业板指3908.44 -0.16%、沪深3004852.88 +0.40%
- `api_calls`：GET /api/market_indices (×2) + SSE market_stream
- 截图：/tmp/b25-home-5s.png（476793 bytes）

---

## Sprint 1-A 安全 Critical 修复记录（commit 8bc70e3，2026-05-19 23:14 +08:00）

### 修复清单

| ID | 根因 | 修复方案 | 文件 |
|---|---|---|---|
| S1-A1 | Hunt1-C1：全路由 0 鉴权 | before_request 鉴权门 + PUBLIC_PATHS 白名单 | auth_middleware.py, web_server.py |
| S1-A2 | Hunt1-C2：CSRF 完全缺失 | Flask-WTF CSRFProtect + /api/csrf_token + 前端自动附加 | web_server.py, client.ts |
| S1-A3 | Hunt1-C3：gunicorn CVE-2024-1135 | requirements.txt 20.1.0 → >=22.0.0（安装为 26.0.0） | requirements.txt |
| S1-A4 | Hunt1-C4：upload 路径遍历+无鉴权 | secure_filename + magic bytes + 大小限制 + 绝对路径 | web_server.py |

### 铁证（2026-05-19 23:xx +08:00）

- 真重启：uptime_s=6.507（< 60）
- S1-A1：无 key → HTTP 401；带 key → HTTP 200；/health 无需 key → HTTP 200
- S1-A2：/api/csrf_token 返回 token；前端 POST 自动附 X-CSRFToken
- S1-A3：pip show gunicorn → Version 26.0.0
- S1-A4：路径遍历 `../../../../etc/passwd` → HTTP 400；/etc/passwd 未被覆写；非图片 magic bytes → HTTP 400；真实 PNG → HTTP 200
- pytest：777 passed, 0 failed（test_upload_non_image_rejected 从 xfail 变 xpass，证明安全加固生效）
- Playwright dashboard：加载正常（has_realnum=true: 4169/15569）

### 关键 env 变量

| env key | 默认值 | 说明 |
|---|---|---|
| STOCKANAL_API_KEY | 自动生成（打印到日志） | API 鉴权 key |
| AUTH_REQUIRED | true | false=开发模式跳过鉴权 |
| SECRET_KEY | 自动生成 | Flask session/CSRF 签名 |
| MAX_UPLOAD_SIZE_MB | 5 | upload_image 大小限制 |
| UPLOAD_DIR | /tmp/stockanal_uploads | 上传文件绝对目录 |
