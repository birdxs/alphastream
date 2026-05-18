# FIX-01 复盘报告

- 时间: 2026-05-18 10:45-11:20 +08:00 (Asia/Singapore)
- 时间源校验: 本机 date + Google Date 头，偏差 < 10s
- 执行人: 香草少校
- 触发: MANUAL-01 浏览器冒烟测试发现 4 个缺陷
- 范围: 4 个修补 (FIX-1 至 FIX-4) + 配套 9 个 unit test

## FIX-1: load_dotenv override

### 根因
`python-dotenv` 默认 `load_dotenv()` **不覆盖**已存在的环境变量。当 shell 环境（来自 panda-code CLI 父进程）注入了 `OPENAI_API_URL=https://api.moonshot.cn/v1` 和 `OPENAI_API_KEY=sk-sp1KT...` 时，`.env` 内的 `https://oneapi.xiongmaodaxia.online/v1` 失效，模型请求被发往 moonshot.cn，而该网关无 `mimo-v2.5-pro` 模型 → 404 Permission denied。

### 修复 diff 摘要
- `app/web/web_server.py:51` — `load_dotenv()` → `load_dotenv(override=True)`
- `app/analysis/stock_analyzer.py:40` — `load_dotenv()` → `load_dotenv(override=True)`

### 验证
- 修复后启动：`URL=https://oneapi.xiongmaodaxia.online/v1`、`MODEL=mimo-v2.5-pro`
- 浏览器端 chat → LLM 200 OK
- `grep "Not found the model" /tmp/stockanal_backend.log` => 0

### 风险/回滚
- 风险: 若运维通过 shell env 临时切模型/网关，将被 .env 覆盖
- 缓解: 文档中明确"`.env` 是单一真相源"，运维如需切换需改 .env
- 回滚: `git revert <hash>` 单文件回滚 2 行修改

## FIX-2: msgpack numpy.float64 序列化

### 根因
LangGraph `checkpoint/serde/jsonplus.py` 使用 `ormsgpack.packb()` 序列化 state，遇到 `numpy.float64 / numpy.int64 / numpy.ndarray` 抛 `TypeError: Type is not msgpack serializable: numpy.float64`，导致编排在 agent return 后 checkpoint 写入失败，UI 显示"分析过程出错"。

### 修复 diff 摘要
- `app/agents/coordinator.py:10-67` — 新增模块级 `_to_native()` 递归归一化函数（支持 np.floating/integer/bool_/ndarray, pd.Timestamp/Series, dict/list/tuple/set 递归）
- `app/agents/coordinator.py:91-93` (`_wrap_with_events` 内) — `agent_fn(state)` 返回后 `if isinstance(result, dict): result = _to_native(result)`
- `app/agents/investors/investor_coordinator.py:36-42` — `_fallback_wrap_with_events` 内同样调用 `_to_native`

### 关键技术点
`np.float64` **是 Python `float` 的子类**，`np.int64` 是 `int` 的子类。`isinstance(obj, (int, float, bool))` 的快速路径会误判 numpy 标量为原生类型直接返回，**必须先识别 numpy 再走快速路径**。原 v1 实现踩了此坑，v2 已修。

### 配套 unit test (新增文件)
`tests/backend/unit/test_to_native_msgpack.py` — 9 个测试全过：
- `test_to_native_numpy_float64` / `_integer` / `_bool` / `_ndarray`
- `test_to_native_nested_state` 嵌套递归
- `test_to_native_pandas_timestamp`
- `test_to_native_state_is_msgpack_serializable` — 验证 msgpack.packb 闭环
- `test_to_native_ormsgpack_serializable` — 验证 langgraph 实际用的 ormsgpack
- `test_to_native_preserves_primitives` — 原生类型不被破坏

### 验证
- pytest 9/9 PASS
- 后端日志 `grep -cE "msgpack|numpy.float64"` => 0

### 风险/回滚
- 风险: `_to_native` 递归性能开销（state 很大时 O(n)）。当前 state 量级 <100 字段，影响可忽略
- 边缘: 若 agent 返回包含自定义对象（如 dataclass）且未实现 `__float__`，归一化后保持原样，仍可能踩 msgpack 坑——目前 codebase 无此情况
- 回滚: 单点回滚 `coordinator.py` 与 `investor_coordinator.py` 即可，测试文件可单独删

## FIX-3: 港股/美股代号前端正则

### 根因
前端 `page.tsx` / `chat-input.tsx` / `use-stock-prices.ts` / `use-stock-names.ts` 调用后端 API 时**硬编码** `market_type: "A"`。后端 `validate_stock_code()` 用 A 股正则 `^[0-9]{6}$` 校验 5 位港股 `00700` 和字母 `AAPL`，拒绝 → 前端报"股票代码格式无效"。

### 修复 diff 摘要
- `frontend/src/lib/utils/stock-code.ts` — 新增 `inferMarketType(code)` 函数：
  - `^[A-Za-z]{1,5}$` → `'US'`
  - `^[0-9]{4,5}$` → `'HK'`
  - `^[0-9]{6}$` → `'A'`
  - 其他 → `'A'` (兜底)
- `frontend/src/app/stock/[code]/page.tsx:17, 163, 279` — import + 替换 2 处硬编码 `"A"` → `inferMarketType(code)`
- `frontend/src/lib/hooks/use-stock-prices.ts:8, 23` — import + 替换 1 处
- `frontend/src/lib/hooks/use-stock-names.ts:8, 34` — import + 替换 1 处
- `frontend/src/components/chat/chat-input.tsx:12, 243` — import + 替换 1 处（当 `code` 存在时推断，否则保留 `"A"` 兜底）

### 验证
- 浏览器 R1: `/stock/00700` → 无"格式无效"
- 浏览器 R2: `/stock/AAPL` → 无"格式无效"

### 风险/回滚
- 风险: 4 位数字代号有歧义（A 股不存在 4 位，但万一有非标场景）
- 缓解: 后端 `validate_stock_code()` 仍有最终校验，前端推断错也不会绕过后端
- 回滚: 单文件回滚每个 import + 替换

## FIX-4: API 路由文档对齐

### 根因
冒烟测试任务清单使用了不存在的路由名（`/api/news`, `/api/screener`, `/api/agent_progress`），而真实路由为 `/api/latest_news`, `/api/start_market_scan`, `/api/agent_analysis_status/<task_id>`。

### 调查结论
**前端实际代码引用的是正确路由**（如 `frontend/src/app/news/page.tsx:144` 用 `/api/news_sentiment`）。无前端代码需修改。

### 修复
- `tests/audit/reports/MANUAL-01_browser_smoke.md` 已记录真实路由表（详见 P2 章节）
- 后续工作: 若 OpenAPI 文档存在，需对齐 (本次未扩大范围)

### 风险/回滚
无代码改动，无需回滚。

## 修补汇总表

| FIX | 文件:行 | 测试 | 验证证据 |
|-----|--------|------|---------|
| FIX-1 | `app/web/web_server.py:51`, `app/analysis/stock_analyzer.py:40` | 由 R3/R4 端到端覆盖 | URL=oneapi.xiongmaodaxia.online; 0 个 404 |
| FIX-2 | `app/agents/coordinator.py:10-67,91-93`, `app/agents/investors/investor_coordinator.py:36-42` | `tests/backend/unit/test_to_native_msgpack.py` (9 cases) | pytest 9/9; 0 个 msgpack/numpy 错 |
| FIX-3 | `frontend/src/lib/utils/stock-code.ts` (+inferMarketType), `frontend/src/app/stock/[code]/page.tsx`, `frontend/src/lib/hooks/use-stock-prices.ts`, `frontend/src/lib/hooks/use-stock-names.ts`, `frontend/src/components/chat/chat-input.tsx` | 由 R1/R2 浏览器回归覆盖 | 港股/美股代号不再报"格式无效" |
| FIX-4 | 仅文档 (`MANUAL-01_browser_smoke.md` 中真实路由表) | - | - |

## 残留缺陷 (待 Comdr 决定下一步)

1. **mimo-v2.5-pro reasoning_content 协议**: chat completion 偶发 400 BadRequest，要求 `reasoning_content` 字段透传。需 `app/core/ai_client.py` 在多轮对话中保留 thinking 阶段的 reasoning_content 并在下一轮请求中带回。
2. **Agent 任务状态机进度不刷新**: progress 一直 5%，但底层 Agent 实际在跑。状态机与 LangGraph 编排引擎之间事件回写存在断点。

## 时间锚点

- 校时通过: 2026-05-18 10:44:54 +0800 (本机) vs 2026-05-18 02:44:57 GMT (Google Date 头), 偏差 < 10s
- FIX 起始: 2026-05-18 10:45:00 +08:00
- 单元测试通过: 2026-05-18 10:55:00 +08:00
- 浏览器回归完成: 2026-05-18 11:20:00 +08:00
