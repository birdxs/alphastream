# AI-Native 智能金融分析平台（Dark Glassmorphism）

![版本](https://img.shields.io/badge/版本-3.0.0-blue.svg)
![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)
![React](https://img.shields.io/badge/React-19-61DAFB.svg)
![Python](https://img.shields.io/badge/Python-3.9+-green.svg)
![Flask](https://img.shields.io/badge/Flask-3.1-red.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi_Agent-purple.svg)
![AKShare](https://img.shields.io/badge/AKShare-1.16+-orange.svg)

> Claude Code 驱动的 14-Agent 金融分析系统，对标 [fiscal.ai](https://fiscal.ai) 的产品质感与信息密度。

---

## 📝 项目概述

本项目是一个**重构后**的全栈 AI 金融分析平台：

- **前端**：Next.js 16 + React 19 + Tailwind + shadcn/ui + TradingView Lightweight Charts，Dark Glassmorphism 设计语言（毛玻璃、深色、高对比）。
- **后端**：Flask 3.1 + LangGraph 多 Agent 编排 + akshare/baostock 双源冗余数据层。
- **核心能力**：14 个专业 AI Agent 并行协同、SSE 实时流式进度透传、17 种搜索引擎统一入口、Zustand 对话/自选/组合持久化、10 种 Artifact 可视化卡片、MCP 标准化工具服务器。

平台覆盖 A 股 / 美股 / ETF / 指数 / 行业 多市场，提供技术面、基本面、资金流、情绪、多空辩论、风险、投资者人格（巴菲特/芒格/林奇/达摩达兰）、智能决策等全维度分析。

---

## 🏗️ 系统架构

```
StockAnal_Sys/
│
├── frontend/                        # Next.js 16 前端（重构后）
│   ├── src/
│   │   ├── app/                     # App Router 路由
│   │   │   ├── page.tsx             # 首页（三栏门户）
│   │   │   ├── dashboard/           # 智能仪表盘
│   │   │   ├── stock/[code]/        # 股票详情 + Agent 实时流
│   │   │   ├── screener/            # 市场扫描
│   │   │   ├── portfolio/           # 投资组合
│   │   │   ├── watchlist/           # 自选列表
│   │   │   ├── compare/             # 多股对比
│   │   │   ├── news/                # 财经新闻
│   │   │   └── settings/            # 设置
│   │   ├── components/
│   │   │   ├── agent/               # Agent 面板/进度/思维链/工具调用时间线
│   │   │   ├── artifacts/           # 10 种 Artifact（K线/资金流/风险雷达/评分雷达/新闻/决策/人格/搜索…）
│   │   │   ├── charts/              # 图表封装（LWC + Recharts）
│   │   │   ├── chat/                # 对话/输入框/消息流
│   │   │   ├── market/              # 行情组件
│   │   │   ├── layout/ common/ ui/  # 布局与 shadcn 基础组件
│   │   └── lib/
│   │       ├── api/client.ts        # 后端 API 客户端
│   │       ├── stores/              # Zustand 持久化（chat/agent/portfolio/watchlist/theme/settings）
│   │       ├── hooks/ types/ utils/ # 自定义 hook / TS 类型 / 工具
│   │       └── i18n.ts              # 国际化
│
├── app/                             # Flask 后端
│   ├── web/                         # Web 层（路由、SSE、认证、行业端点）
│   │   ├── web_server.py            # 主路由 + SSE /api/agent_stream 透传
│   │   ├── auth_middleware.py
│   │   └── industry_api_endpoints.py
│   ├── agents/                      # 14-Agent 子系统（LangGraph 编排）
│   │   ├── coordinator.py           # 动态编排（并行 fan-out/fan-in + 条件路由）
│   │   ├── technical_analyst.py fundamental_analyst.py capital_flow_analyst.py
│   │   ├── sentiment_analyst.py bull_researcher.py bear_researcher.py
│   │   ├── risk_manager.py decision_maker.py reflection.py strategy_evolver.py
│   │   ├── hitl.py                  # Human-in-the-Loop 审批
│   │   └── investors/               # 巴菲特 / 芒格 / 林奇 / 达摩达兰
│   ├── core/                        # 核心基础设施
│   │   ├── ai_client.py             # 统一 AI 客户端（超时/重试/降级）
│   │   ├── data_provider.py         # 统一数据层
│   │   ├── cache.py                 # Redis / 内存缓存
│   │   ├── search.py search_engines.py  # 17 引擎统一入口 + multi_search + 6 条 fallback
│   │   ├── tools.py                 # 双格式工具注册（LangChain + OpenAI FC）
│   │   ├── agent_memory.py          # TF-IDF 语义记忆
│   │   ├── event_bus.py             # Agent 事件总线（SSE 源头）
│   │   ├── conversation.py          # 对话持久化（按 updated_at 倒序）
│   │   ├── artifact_wrapper.py      # Artifact 契约封装（stock_name/新闻/风险扁平字段）
│   │   ├── fallback_manager.py database.py
│   ├── adapters/                    # 数据源适配（akshare + baostock 双源冗余）
│   ├── analysis/                    # 分析引擎（股票/基本面/资金流/行业/ETF/风险/QA/新闻）
│   └── mcp/stock_data_server.py     # MCP 标准化工具服务器
│
├── docs/                            # 架构与作战文档
│   ├── API.md FRONTEND_ARCHITECTURE.md BACKEND_GAPS.md
│   ├── SEARCH_ENGINES.md            # 17 引擎权威来源交叉验证
│   └── BATTLE_2026-04-14_PM.md      # 最新作战记录
│
├── scripts/start.sh                 # 启动/停止/监控脚本
├── run.py requirements.txt
├── Dockerfile docker-compose.yml docker-compose.frontend.yml
└── nginx/ config/ data/ logs/
```

---

## ✨ 核心能力

### 1. 14-Agent 实时流式分析
- **LangGraph 动态编排**：基本面 + 资金流并行、多空辩论并行、条件路由（技术分析失败即快速失败）。
- **Function Calling**：Agent 通过 OpenAI tools 自主决定查询什么数据，拒绝预填硬编码。
- **AI 首席策略官**：投资者共识由 AI 综合研判论据强度（非简单投票），降级时回退硬编码评分。
- **语义记忆全覆盖**：14 个 Agent 全量接入 TF-IDF 历史分析记忆。
- **反思学习 + 策略演进**：reflection.py / strategy_evolver.py 自适应更新提示词。

### 2. SSE 实时透传
- 后端 `event_bus` 产出 Agent 事件 → `/api/agent_stream` SSE 推送 → 前端 `agent-store` 消费 → `agent-side-panel` + `tool-call-timeline` + `thinking-chain` 渲染进度、思维链、工具调用。

### 3. 17 种搜索引擎统一入口
- **中文域（8）**：百度 / 搜狗 / 360 / 必应中文 / 知乎 / 微博 / 百度百科 / Wikipedia-zh
- **全球域（9）**：Google / Bing / DuckDuckGo / Brave / Startpage / Mojeek / Yandex / Tavily / SERP
- **知识域（2）**：WolframAlpha / Wikipedia
- `multi_search()` 并发去重 + 6 条 fallback 链；LLM 可显式指定 `engine='wolframalpha' | 'wikipedia' | 'concurrent'`。

### 4. Zustand 持久化
- `chat-store` 对话历史（按 updated_at 倒序，删除即时生效）
- `watchlist-store` / `portfolio-store` 自选与组合（客户端持久化）
- `agent-store` 实时 Agent 状态
- `theme-store` / `settings-store` 主题与偏好

### 5. Dark Glassmorphism UI
- 深色毛玻璃，高通透度，CSS 变量驱动主题
- 10 种 Artifact 卡片：K 线、技术面板、资金流、风险雷达、评分雷达、基本面评分卡、决策卡、投资者人格、新闻流、搜索结果
- 对标 fiscal.ai 的信息密度与视觉品质

### 6. MCP 工具服务器
- `app/mcp/stock_data_server.py` 对外暴露标准化工具接口，支持跨系统 Agent 调用。

### 7. 数据层 v2（2026-04-15 扩张）
- **21 Adapter + 16 业务域 Registry**：A股双源冗余 + 美股SEC EDGAR + 港股/日股yfinance + 宏观(NBS/FRED/World Bank/IMF) + 加密(ccxt/CoinGecko) + 新闻RSS六源 + OpenBB桥 + **P3 另类数据 5 支柱**(航运BDI+港口+AIS / 卫星NASA CMR / 产业链OpenCorporates / 招聘Arbeitnow / ESG多源公开)。
- **`AdapterRegistry.call_with_fallback`**：domain→多 adapter 自动降级；14 Agent + 4 投资者人格全量接入。
- **10 P3 REST API 端点** + **5 P3 Artifact 组件**：后端/前端字段契约唯一化 (v2 wrap)，软降级契约 (空数据 200+success:true+空 artifact)。
- **3 OpenCLI JS 爬虫**：雪球讨论 / 东财股吧 / 财联社电报，浏览器态 Cookie 策略。
- **搜索层与数据层分工**：`search_engines`=文本/URL搜索(17引擎HTML抓取), `Registry`=结构化DataFrame(工商/财报/K线)，互补解耦。

---

## 🛠️ 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 16, React 19, Tailwind 4, shadcn/ui, Zustand, Jotai, TradingView LWC, Recharts, react-markdown, AI SDK |
| 后端 | Python 3.9+, Flask 3.1, LangGraph, LangChain, OpenAI-compatible API |
| 数据源 | AKShare + BaoStock 双源冗余 + 21 Adapter/16 Domain Registry (efinance/yfinance/SEC EDGAR/NBS/FRED/WB/IMF/ccxt/CoinGecko/OpenBB/RSS×6/Ashare/easyquotation + P3 另类: Shipping/Satellite/Corporate/Jobs/ESG) |
| 爬取 | **OpenCLI (jackwener/OpenCLI, 15.8k⭐)** 浏览器态 Cookie 策略桥 + 3 JS adapter (雪球/东财股吧/财联社) |
| 搜索 | 17 引擎（8 中文 + 9 全球 + 2 知识），无需 API Key 可跑 |
| 缓存 | Redis（可选）/ 内存降级 |
| 通信 | SSE（Server-Sent Events）实时流 |
| 部署 | Docker, docker-compose, Gunicorn, Nginx |

---

## 🚀 启动

### 前置
- Python 3.9+，Node.js 20+
- `.env` 填入 `OPENAI_API_KEY` 等（参见下表）

### 后端（Flask，端口 8888）
```bash
pip install -r requirements.txt
python3 run.py
# 或
bash scripts/start.sh start
```

### 前端（Next.js，端口 3000）
```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000`，前端通过 `NEXT_PUBLIC_API_BASE` 代理到 `http://localhost:8888`。

### Docker 一键
```bash
docker-compose up -d                       # 后端
docker-compose -f docker-compose.frontend.yml up -d   # 前端
```

### 关键环境变量
| 变量 | 说明 | 默认 |
|------|------|------|
| `OPENAI_API_KEY` | AI 模型密钥（必填） | 无 |
| `OPENAI_API_URL` | API 端点 | `https://api.openai.com/v1` |
| `OPENAI_API_MODEL` | 模型名 | `gpt-4o` |
| `PORT` | 后端端口 | `8888` |
| `USE_AGENT_SYSTEM` | Agent 系统开关 | `true` |
| `USE_REDIS_CACHE` | Redis 缓存开关 | `false` |
| `TAVILY_API_KEY` / `SERP_API_KEY` | 可选搜索增强 | 无 |
| `FRED_API_KEY` | FRED 宏观 80 万序列（免费申请） | 无 (降级为空) |
| `OPENCORPORATES_API_KEY` | 产业链/工商（免费 500/月；匿名亦可） | 无 |
| `SEC_EDGAR_UA` | SEC EDGAR UA 规范（格式：`App Name email`） | 项目默认 |
| `AISHUB_USERNAME` | AIS 船舶位置（免费注册 username） | 无 (降级为空) |
| `JOBS_ADAPTER_UA` | Jobs 招聘 UA 伪装（可选） | 项目默认 |
| `ALLOWED_ORIGINS` | CORS 白名单 | `localhost:8888,localhost:3000` |

---

## 📚 文档

- [docs/OPERATIONS.md](docs/OPERATIONS.md) — **v3.1 运维手册**（启动/Key/代理/故障/Agent链路）
- [docs/API.md](docs/API.md) — 40+ 路由对接标准
- [docs/FRONTEND_ARCHITECTURE.md](docs/FRONTEND_ARCHITECTURE.md) — 前端架构
- [docs/BACKEND_GAPS.md](docs/BACKEND_GAPS.md) — 后端差距追踪
- [docs/SEARCH_ENGINES.md](docs/SEARCH_ENGINES.md) — 17 引擎权威来源交叉验证
- [docs/BATTLE_2026-04-14_PM.md](docs/BATTLE_2026-04-14_PM.md) — 最新作战记录

---

## 📋 版本

### v3.1.0（2026-04-15，数据层 v2）
- 21 Adapter + 16 Domain Registry + `call_with_fallback` 自动降级
- 10 P3 REST API 端点 (shipping/esg/corporate/jobs/satellite/alt_data) + 5 P3 Artifact 组件
- 12 Agent + 4 投资者人格全量接入 Registry；55+ commits 入 main；384 pytest PASS
- 3 OpenCLI JS 爬虫 (雪球/东财股吧/财联社)
- 软降级契约统一（空数据 200+success:true+空 artifact）
- 搜索层与数据层职责分离：search_engines=文本搜索 / Registry=结构化数据

### v3.0.0（重构版）
- 全新 Next.js 16 + React 19 前端替代 Jinja 模板
- 14 Agent + LangGraph 动态编排 + Function Calling
- SSE 实时透传 + Zustand 持久化 + 10 种 Artifact
- 17 搜索引擎统一入口 + 6 条 fallback
- Dark Glassmorphism UI，对标 fiscal.ai
- Artifact 契约对齐（stock_name / 新闻按 code 过滤 / 风险扁平字段）
- 对话持久化/删除即时生效，按 updated_at 倒序

### v2.x
详见 git 历史与 [docs/](docs/)。

---

## ⚠️ 免责声明

本项目为 AI 驱动探索版，输出**不构成投资建议**。AI 可能产生错误内容，由此造成的任何损失本项目不负责。

---

> **此项目的任何功能、架构更新，必须在结束后同步更新相关文档。这是我们契约的一部分。**
