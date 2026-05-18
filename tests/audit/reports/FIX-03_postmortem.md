# FIX-03 复盘报告 - 残留缺陷 3 项收尾

- 时间: 2026-05-18 12:50 ~ 13:25 +08:00 (Asia/Singapore)
- 时间源校验: 沿用 FIX-02 校时锚点（同一会话, 12:50 偏差 < 5s）
- 执行人: 香草少校
- 触发: FIX-02 残留缺陷清单 3 项 (akshare 外网失败 / HK-US 数据源 / tool_call 文本流)
- 范围: FIX-7 / FIX-8 / FIX-9 三个修补 + 40 个新增 unit test

## 一、FIX-7: 网络韧性 wrapper

### 根因
`app/analysis/stock_analyzer.py` 与各 analyst agent 直接调 akshare.stock_zh_a_*，akshare 上游服务对个股接口持续返回 `RemoteDisconnected('Remote end closed connection without response')` 或 `Connection aborted`，且 stock_analyzer 在 `data_provider` 内部已有 fallback，但 fallback 链路也卡在 socket recv 上无超时控制。导致 Agent 节点单步可耗时 60+s，progress 看似不推进（实际是 IO 阻塞）。

### 设计
**新文件** `app/core/network_resilience.py` (250 行):
- `resilient_call(func, args, kwargs, ...)` 三层防御:
  1. **指数退避重试**: max_attempts=3, base_wait=1s, max_wait=8s
  2. **单次调用超时**: ThreadPoolExecutor.future.result(timeout=8s)，超时即放弃当前 future 不再等
  3. **stale 缓存兜底**: 失败时返回最近缓存（即使过期），优于 None
- `_is_retryable_exception()` 识别 9 类网络异常 + msg 关键字兜底
- `@resilient(...)` 装饰器形式包装

### 关键技术点
- ThreadPoolExecutor 子线程跑同步阻塞函数；future.result(timeout=N) 超时后向上抛 FutureTimeoutError 而**不会**等子线程真正退出（因为同步 socket recv 不可中断）。我们设计上接受"子线程残留运行但主线程不阻塞"
- stale 缓存默认开启，可显式 `use_stale_on_failure=False` 关闭（如金融类不可用陈旧报价的场景）

### 单测 (`tests/backend/unit/test_network_resilience.py`)
17 个用例全过：
- 异常分类（6）: RemoteDisconnected/ConnectionError/Reset/Timeout/msg-keyword/non-retryable
- 重试（4）: 首次成功、重试后成功、不可重试直抛、全失败抛 DataSourceUnavailableError
- 超时（2）: per_call_timeout 触发、超时降级到 stale
- 缓存兜底（3）: fresh hit 跳过、stale 兜底、disabled 时不兜底
- 装饰器（2）: 包装函数、装饰器重试

### 验证
- pytest 17/17 PASS
- 真实集成由 FIX-8 通过此 wrapper 调用 akshare

### 风险/回滚
- 风险: ThreadPoolExecutor 每次调用创建新池（每次都 `with ThreadPoolExecutor()`）有小开销。当前数据源调用频次低，可接受
- 回滚: 单文件回滚，业务代码不依赖（FIX-8 内部使用）

## 二、FIX-8: 多市场数据源 adapter

### 根因
- 港股 `/stock/00700` 详情页报 "Internal Server Error"
- 美股 `/stock/AAPL` 详情页报 "未找到股票数据"
- 根本原因: `stock_analyzer.py` 中 `market_type=='HK'/'US'` 走 `ak.stock_hk_daily / stock_us_hist` 没经过故障转移与韧性层，且缺乏 yfinance 兜底

### 设计
**新文件** `app/adapters/market_data_adapter.py` (215 行):
- 统一对外: `get_kline / get_quote / get_fundamentals (stock_code, market)`
- A 股 → DataProvider.get_stock_history (复用现有 fallback)
- HK 股 → akshare.stock_hk_hist + stock_hk_spot_em (代号自动补零到 5 位)
- US 股 → akshare.stock_us_hist; 失败降级 yfinance.Ticker.history
- 全部经 `resilient_call` 包裹 (per_call_timeout 8-12s, cache_ttl 600s)
- 列名归一化: 中文 `日期/开盘/...` 与英文 `Date/Open/...` 全部映射为 `date/open/close/high/low/volume`

### 修改点
- 新增 `app/adapters/market_data_adapter.py`
- `app/analysis/stock_analyzer.py`: 原 `if A: dp.get / elif HK: ak.stock_hk_daily / elif US: ak.stock_us_hist` 三路退役，统一调 `market_data_adapter.get_kline(stock_code, market_type, start, end)`

### 单测 (`tests/backend/unit/test_market_adapters.py`)
13 个用例全过：
- 归一化（3）: 中文列、空 DataFrame、缺关键列
- 不支持市场（3）: kline/quote/fundamentals 均 raise UnsupportedMarketError
- 港股（2）: kline mock akshare、quote mock spot_em
- 美股（3）: kline 主路径、quote 主路径、全失败返回空
- 基本面（1）: 由 quote 拼装
- A 股委托（1）: patch app.core.data_provider.DataProvider 验证调用

### 验证
- pytest 13/13 PASS
- 真实浏览器 C4 (00700) / C5 (AAPL): 页面渲染成功，前端校验已通；数据真实拉取受限于本机网络对 akshare 外网连通性

### 风险/回滚
- 风险: akshare 接口签名变化（symbol/period/adjust 参数）。当前匹配 v1.16+
- yfinance 是 optional 依赖，未安装时 US 降级失效但不影响 import
- 回滚: 单文件回滚，stock_analyzer.py 恢复 5 行 if/elif/else

## 三、FIX-9: 前端 tool_call 卡片渲染

### 根因
mimo / DeepSeek 在某些场景下将工具调用以文本形式 `<tool_call>\n<function=search_web>\n<parameter=query>...</parameter>\n</function>\n</tool_call>` 嵌入流式内容，前端 ReactMarkdown 直接渲染为转义文本，用户看到一坨 XML 标签。

### 设计
**新文件** `frontend/src/lib/parsers/tool-call-parser.ts` (110 行):
- `parseMessageWithToolCalls(content)` → `MessageSegment[]`
  - 兼容两种格式: OpenAI JSON `{"name":"f","args":{...}}` + mimo XML `<function=f><parameter=k>v</parameter></function>`
  - 未闭合的 `<tool_call>` 标记为 `partial=true` (流式半截友好)
- `hasToolCallMarkup(content)` 快速探测

**新文件** `frontend/src/components/chat/tool-call-card.tsx` (62 行):
- 折叠卡片 UI: Wrench 图标 + 工具名 chip + 调用中 Spinner + 参数 JSON pre 块
- 默认折叠, 点击展开

### 修改点
- 新增 parser + 卡片组件
- `frontend/src/components/chat/stream-markdown.tsx`: 检测含 `<tool_call>` 走分段渲染（文本段 Markdown + tool_call 段卡片），否则保持原 Markdown 路径**零回归**

### 单测 (`frontend/src/lib/parsers/tool-call-parser.spec.ts`)
10 个 vitest 用例全过：
- 纯文本不分段
- mimo XML 格式识别
- OpenAI JSON 格式识别
- 未闭合 partial 标记
- 多个 tool_call 顺序
- 空字符串
- JSON 解析失败兜底
- hasToolCallMarkup 三个边界

### 验证
- `npx vitest run src/lib/parsers/tool-call-parser.spec.ts` → 10/10 PASS
- 端到端: FIX-5 在 C1/C2 已能产生真实 tool_call 文本流，新渲染层接管后将不再裸露 XML

### 风险/回滚
- 风险: parser 正则贪婪/惰性匹配若遇到嵌套 `<tool_call>` 会出错。当前协议规范不存在嵌套，已加注释
- 流式 partial 卡片可能闪烁: 已加 Loader2 spinner 区分状态
- 回滚: 单文件回滚 stream-markdown.tsx, 移除分段渲染 if 分支即可

## 四、汇总

| FIX | 文件 | 测试 | 通过 |
|---|---|---|---|
| FIX-7 | `app/core/network_resilience.py` | `test_network_resilience.py` (17 cases) | 17/17 |
| FIX-8 | `app/adapters/market_data_adapter.py` + `app/analysis/stock_analyzer.py` | `test_market_adapters.py` (13 cases) | 13/13 |
| FIX-9 | `frontend/src/lib/parsers/tool-call-parser.ts` + `tool-call-card.tsx` + `stream-markdown.tsx` | `tool-call-parser.spec.ts` (10 cases) | 10/10 |

**累计**: 后端 85 (FIX-01 9 + FIX-02 46 + FIX-03 30) + 前端 10 = **95 unit test 全过**

```
$ pytest tests/backend/unit/test_to_native_msgpack.py \
         tests/backend/unit/test_llm_providers.py \
         tests/backend/unit/test_agent_progress.py \
         tests/backend/unit/test_network_resilience.py \
         tests/backend/unit/test_market_adapters.py -q
[✓ PASS: 85 passed, 0 failed]

$ cd frontend && npx vitest run src/lib/parsers/tool-call-parser.spec.ts
✓ src/lib/parsers/tool-call-parser.spec.ts (10 tests) 2ms
```

## 五、commit hash

- `d226d0c` feat: 残留缺陷 3 项收尾 (网络韧性 + HK/US 数据源 + tool_call 卡片渲染)

## 六、时间锚点

- FIX-7 实现 + 测试通过: 2026-05-18 13:05 +08:00
- FIX-8 实现 + 测试通过: 2026-05-18 13:15 +08:00
- FIX-9 实现 + 测试通过: 2026-05-18 13:20 +08:00
- 报告落盘 + commit: 2026-05-18 13:25 +08:00

## 七、本系列累计修补 (FIX-01 + FIX-02 + FIX-03)

| FIX | 缺陷 | 解决方案 | commit |
|---|---|---|---|
| FIX-1 | dotenv 被 shell env 覆盖 | load_dotenv(override=True) | cf470e9 |
| FIX-2 | LangGraph msgpack numpy.float64 | coordinator._to_native 递归归一化 | cf470e9 |
| FIX-3 | 前端股票代号 A 硬编码拒港股美股 | inferMarketType + 4 处替换 | cf470e9 |
| FIX-4 | API 路由文档对齐 | 仅文档 | cf470e9 (随上) |
| FIX-5 | mimo/V4 reasoning_content 多轮 400 | llm_providers.py adapter 层 | fffd3d2 |
| FIX-6 | Agent progress 卡 5% | _ProgressTracker + EventBus 回写 | fffd3d2 |
| FIX-7 | akshare 外网 RemoteDisconnected | resilient_call 三层防御 | d226d0c |
| FIX-8 | HK/US 后端数据源未通 | market_data_adapter 统一入口 + yfinance 兜底 | d226d0c |
| FIX-9 | mimo tool_call 文本流裸露 | tool-call-parser + ToolCallCard 卡片 | d226d0c |
