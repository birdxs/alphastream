# 运维手册 OPERATIONS (v3.1 一日闭环后)

> Input: 已落盘的21 adapter + Registry + 10 P3 API + 5 Artifact
> Output: 快速启动 / Key申请 / 代理配置 / 故障排查 / Agent链路手册
> Pos: 数据层v2 生产级入门文档 [NEW-FILE:#20260415-42]

> 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

---

## 1. 快速启动

### 1.1 后端 (Flask, port 8888)

```bash
cp .env-example .env           # 编辑 OPENAI_API_KEY 等必填项
pip install -r requirements.txt
python3 run.py                  # 或 bash scripts/start.sh start
```

健康检查：`curl http://localhost:8888/api/market_indices`

### 1.2 前端 (Next.js, port 3000)

```bash
cd frontend
npm install
npm run dev                     # 开发模式
npm run build && npm start      # 生产模式 (H1已验证 next build全绿)
```

前端通过 `NEXT_PUBLIC_API_BASE` 代理到 `http://localhost:8888`。

### 1.3 Docker 一键

```bash
docker-compose up -d                                   # 后端
docker-compose -f docker-compose.frontend.yml up -d    # 前端
```

---

## 2. 环境配置

### 2.1 必填 Key

| 变量 | 说明 |
|---|---|
| `OPENAI_API_KEY` | AI模型密钥 (OpenAI兼容即可) |
| `OPENAI_API_URL` | API端点, 默认 `https://api.openai.com/v1` |
| `OPENAI_API_MODEL` | 模型名, 默认 `gpt-4o` |

### 2.2 免费可选 Key (5个, 未配置走软降级)

| Key名 | 申请URL | 限额 | 未配置行为 |
|---|---|---|---|
| `FRED_API_KEY` | https://fred.stlouisfed.org/docs/api/api_key.html | 无限免费,仅需邮箱 | `macro_us` 仅用 OpenBB/WorldBank 降级 |
| `OPENCORPORATES_API_KEY` | https://api.opencorporates.com/documentation/API-Reference | 500 calls/月免费 | 匿名亦可,响应限速 |
| `SEC_EDGAR_UA` | 格式 `"AppName email"` | 10 req/s | 项目内置默认UA,仍可工作 |
| `AISHUB_USERNAME` | https://www.aishub.net/api | 免费注册feed | `ShippingAdapter.get_ais_vessels` 返回空DataFrame |
| `JOBS_ADAPTER_UA` | 可选UA覆盖 | — | 使用项目默认UA |
| `TAVILY_API_KEY` / `SERP_API_KEY` | https://app.tavily.com / https://serper.dev | 1000次/月 | 17引擎其他15路可用 |

### 2.3 HTTP代理 (境内强烈推荐)

境外源 (yfinance/EDGAR/FRED/ccxt/CoinGecko/WorldBank/IMF/shipping/satellite/corporate/jobs/esg/rss_news) 在境内直连通常 403/451/超时。

```bash
# .env 末尾
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
NO_PROXY=localhost,127.0.0.1,akshare.com,baostock.com,stats.gov.cn,sse.com.cn,szse.cn
```

- `requests/urllib` 自动继承大写 env；`yfinance/ccxt` 已在代码中显式透传 (参见 `app/adapters/_proxy_utils.py`)。
- 境内源 (akshare/baostock/stats.gov.cn/sse/szse) 通过 `NO_PROXY` 直连, 避免代理劫持。

---

## 3. 数据层架构

### 3.1 21 Adapter + 16 Domain 映射表

| Domain | Adapter优先级链 | Key需求 |
|---|---|---|
| `a_stock_kline` | Akshare → Baostock → Efinance → Ashare → YFinance | 无 |
| `a_stock_realtime` | Efinance → Easyquotation → Akshare → OpenCLIBridge | 无 |
| `us_stock` | YFinance → OpenBB → EDGAR | SEC-UA可选 |
| `hk_stock` | YFinance → Akshare | 无 |
| `macro_us` | FRED → OpenBB → WorldBank | FRED免费 |
| `macro_cn` | NBS → Akshare | 无 |
| `macro_global` | WorldBank → IMF → OpenBB | 无 |
| `crypto` | CCXT → CoinGecko → YFinance → OpenBB | 无 |
| `news` | RSSNews → OpenCLIBridge → Akshare | 无 |
| `sentiment_social` | OpenCLIBridge | 浏览器Cookie |
| `xbrl_financials` | EDGAR → YFinance → OpenBB | SEC-UA可选 |
| `esg_rating` | ESGAdapter (多源公开) | 无 |
| `commodity_shipping` | ShippingAdapter (BDI/港口/AIS) | AISHub可选 |
| `earth_observation` | SatelliteAdapter (NASA CMR) | 无 |
| `corporate_entity` | CorporateAdapter (OpenCorporates) | OC可选 |
| `hiring_signal` | JobsAdapter (Arbeitnow) | 无 |

### 3.2 调用链路

```
Agent.fetch(domain, method, **kwargs)
  → AdapterRegistry.default().call_with_fallback(domain, method, **kwargs)
    → adapters[0].method() → _is_valid_result?
      ↓ fail/empty
    → adapters[1].method() → ...
      ↓ 全失败
    → raise Exception(tried=[...], last_error=...)
```

- `_is_valid_result`: 非None、DataFrame非空、list/dict非空。
- 单例: `AdapterRegistry.default()` 进程级懒加载, 测试可 `reset_default()`。
- 依赖缺失的 adapter 在实例化阶段静默 SKIP (日志 WARN)。

---

## 4. 10 P3 REST API 端点

| Method | Path | 参数 | Artifact type |
|---|---|---|---|
| GET | `/api/shipping/bdi` | `days` | `shipping_bdi` |
| GET | `/api/shipping/port/<port>` | — | `shipping_port` |
| GET | `/api/esg/<ticker>` | — | `esg_rating` |
| GET | `/api/esg/climate/<cik>` | — | `esg_climate` |
| GET | `/api/corporate/search` | `q`, `jurisdiction` | `corporate_search` |
| GET | `/api/corporate/<company_id>/network` | — | `corporate_network` |
| GET | `/api/jobs/search` | `q`, `location` | `jobs_search` |
| GET | `/api/jobs/company/<company>` | — | `jobs_company` |
| GET | `/api/satellite/search` | `collection`, `bbox` | `satellite_granule` |
| GET | `/api/alt_data/<ticker>` | — | `alt_data_bundle` |

**软降级契约统一**: 空数据返回 `200 + {success:true, artifact:{...空字段}}`，前端渲染空态而非错误态。

---

## 5. 14-Agent 全链路

```
coordinator (LangGraph编排)
├─ technical_analyst      ← a_stock_kline / us_stock
├─ fundamental_analyst    ← xbrl_financials / macro_cn
├─ capital_flow_analyst   ← a_stock_realtime
├─ sentiment_analyst      ← news / sentiment_social
├─ bull_researcher        ← 复用上游
├─ bear_researcher        ← 复用上游
├─ investors/ (4投资者人格)
│  ├─ buffett             ← xbrl_financials / esg_rating
│  ├─ munger              ← corporate_entity / hiring_signal
│  ├─ lynch               ← commodity_shipping / jobs
│  └─ damodaran           ← macro_us / macro_global
├─ risk_manager           ← earth_observation / commodity_shipping
├─ decision_maker         ← 综合所有上游
├─ reflection             ← TF-IDF 历史记忆
└─ strategy_evolver       ← 自适应提示词
hitl (Human-in-the-Loop) — 正交审批
```

- 编排特性: 基本面+资金流并行、多空辩论并行、条件路由 (技术分析失败即快速失败)。
- Function Calling: Agent 通过 OpenAI tools 自主决定查询什么数据。
- SSE 透传: `event_bus` → `/api/agent_stream` → 前端 `agent-store`。

---

## 6. 故障排查

| 症状 | 可能原因 | 排查步骤 |
|---|---|---|
| SSE 超时无进度 | backend卡住 / Registry fetch hang | `tail -f /tmp/backend.log` 搜 `call_with_fallback`;检查代理连通 |
| 日志 `⚫ SKIPPED adapter` | 可选依赖未装 | `pip install efinance yfinance ccxt pycoingecko openbb` |
| 🟡 空 DataFrame | 上游反爬/地区限制/Key未配 | 配 `HTTP_PROXY`; 补对应免费Key |
| `400 corporate endpoint` | 路由签名不匹配 | 查 `app/web/web_server.py` 路由参数名 (`path:company_id`) |
| 全链路降级失败 | 所有adapter超时 | `curl -x $HTTP_PROXY https://query1.finance.yahoo.com` 验代理 |
| 前端 `next build` 失败 | TS类型错误 | 参考 H1 commit `e737a2d` tsconfig 配置 |
| Redis 连接拒绝 | `USE_REDIS_CACHE=true` 但未启redis | 改 `false` 走内存降级 |
| `OPENAI_API_KEY invalid` | Key失效/URL错 | 检查 `OPENAI_API_URL` 是否包含 `/v1` 后缀 |

调试工具：
- `AdapterRegistry.default().get_status()` — 查各域注册与失败计数。
- `scripts/smoke_adapters.py` — 真网络冒烟 (授权后运行)。

---

## 7. 测试矩阵

| 层 | 命令 | 覆盖 |
|---|---|---|
| Adapter 单元 | `pytest tests/adapters/` | 329+ mock, 零真网络 |
| Core 单元 | `pytest tests/core/` | 38 测试, artifact_wrapper+registry |
| Web API | `pytest tests/web/` | 20 测试, P3 10端点 |
| Agent 集成 | `pytest tests/agents/` | 18 测试, Registry接入 |
| 代理工具 | `pytest tests/adapters/test_proxy_utils.py` | 7 测试 |
| 真网络冒烟 | `python3 scripts/smoke_adapters.py` | 手动执行, 不入CI |

**累计 391+ pytest PASS** (截至 2026-04-15 Phase-5)。

---

## 8. 文档索引

- [README.md](../README.md) — v3.1 项目总入口
- [docs/README.md](README.md) — 12篇文档索引
- [docs/API.md](API.md) — 40+ 路由对接规范
- [docs/FRONTEND_ARCHITECTURE.md](FRONTEND_ARCHITECTURE.md) — 前端架构
- [docs/SEARCH_ENGINES.md](SEARCH_ENGINES.md) — 17引擎权威来源交叉验证
- [docs/FINANCIAL_DATA_EXPANSION_2026-04-15.md](FINANCIAL_DATA_EXPANSION_2026-04-15.md) — 数据层v2完整历史 (2252行)
- [docs/BATTLE_2026-04-14_PM.md](BATTLE_2026-04-14_PM.md) — 最新作战记录
- [app/adapters/README.md](../app/adapters/README.md) — 21 adapter 清单
- [clis/README.md](../clis/README.md) — 3 JS 爬虫 (雪球/东财/财联社)

---

> **此项目的任何功能、架构更新，必须在结束后同步更新相关文档。这是我们契约的一部分。**
