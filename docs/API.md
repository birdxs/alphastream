# 后端API对接标准文档

```
Input: 前端HTTP请求
Output: JSON响应数据
Pos: docs/API.md - 前端开发人员后端对接标准，所有路由/参数/返回格式的唯一权威来源
```

> 一旦我被修改，请更新所属文件夹的 README.md。

---

**版本**: v2.3.0
**基础URL**: `http://localhost:8888`
**数据格式**: 请求/响应均为 JSON (`Content-Type: application/json`)
**认证方式**: CORS跨域，允许源由 `ALLOWED_ORIGINS` 环境变量配置
**时间格式**: `YYYY-MM-DD HH:mm:ss`

---

## 目录

- [异步任务通用模式](#异步任务通用模式)
- [Agent智能分析API（核心）](#agent智能分析api核心)
- [股票分析API](#股票分析api)
- [市场扫描API](#市场扫描api)
- [基本面分析API](#基本面分析api)
- [资金流向API](#资金流向api)
- [风险分析API](#风险分析api)
- [行业分析API](#行业分析api)
- [指数/板块API](#指数板块api)
- [情景预测API](#情景预测api)
- [ETF分析API](#etf分析api)
- [智能问答API](#智能问答api)
- [股票数据API](#股票数据api)
- [新闻与历史API](#新闻与历史api)
- [MCP工具API](#mcp工具api)
- [页面路由](#页面路由)
- [错误处理](#错误处理)

---

## 异步任务通用模式

系统中耗时操作（股票分析、市场扫描、Agent分析、ETF分析）均采用异步模式：

```
1. POST /api/start_{type}        → 返回 { task_id, status: "pending" }
2. GET  /api/{type}_status/<id>  → 轮询 { status, progress, result }
3. POST /api/cancel_{type}/<id>  → 取消任务（可选）
```

**状态枚举**: `pending` → `running` → `completed` / `failed` / `cancelled`
**轮询间隔**: 建议 1-3 秒
**progress**: 0-100 整数，各Agent完成时增量更新

---

## Agent智能分析API（核心）

### POST /api/start_agent_analysis

启动多Agent智能分析任务。

**v2.3.0 架构特性**:
- Function Calling: 各Agent通过OpenAI tools自主调用数据工具
- 并行执行: fundamental + capital_flow 并行, bull + bear 并行 (LangGraph fan-out/fan-in)
- 条件路由: 技术分析失败 → 快速失败直达决策节点
- AI首席策略官: 投资者共识由LLM综合研判（非简单投票）
- 语义记忆: 全部Agent接入TF-IDF历史分析记忆
- confidence统一: 全链路浮点数 0.0-1.0

**请求**:
```json
{
  "stock_code": "600519",
  "market_type": "A",
  "research_depth": 5,
  "selected_analysts": ["market", "social", "news", "fundamentals"],
  "analysis_date": "2026-03-25",
  "enable_memory": true,
  "max_output_length": 2048
}
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| stock_code | string | 是 | - | 股票代码 |
| market_type | string | 否 | "A" | A/HK/US |
| research_depth | int | 否 | 3 | 研究深度 1-5，控制调用Agent数量 |
| selected_analysts | array | 否 | 全部 | 选定的分析师类型 |
| analysis_date | string | 否 | 当天 | 分析日期 YYYY-MM-DD |
| enable_memory | bool | 否 | true | 启用语义记忆 |
| max_output_length | int | 否 | 2048 | 最大输出长度 |

**research_depth 对应的Agent调用链**:

| 深度 | 调用Agent | 编排方式 |
|------|----------|----------|
| 1 | 技术分析 → 决策 | 串行 |
| 2 | 技术 → (基本面 + 资金流)**并行** → 决策 | fan-out/fan-in |
| 3 | 技术 → (基本面 + 资金流)**并行** → 情绪 → 决策 | fan-out/fan-in |
| 4 | ... → 情绪 → (看多 + 看空)**并行** → 决策 | 双层fan-out |
| 5 | ... → (看多 + 看空)**并行** → 风险 → 投资者人格(4大师) → 决策 | 完整链路 |

**响应**:
```json
{
  "task_id": "agent_20260325_001",
  "status": "pending",
  "message": "已启动对 600519 的智能体分析"
}
```

---

### GET /api/agent_analysis_status/\<task_id\>

获取Agent分析任务状态。

**进度节点** (各Agent完成时上报):

| progress | 对应Agent |
|----------|----------|
| 5 | 系统初始化 |
| 10 | 技术分析师完成 |
| 25 | 基本面分析师/资金流分析师完成（并行） |
| 40 | 情绪分析师完成 |
| 50 | 看多/看空研究员完成（并行） |
| 70 | 风险管理官完成 |
| 80 | 投资者人格(巴菲特/芒格/林奇/达摩达兰)完成 |
| 100 | 投资决策者+反思Agent完成 |

**响应 (运行中)**:
```json
{
  "id": "agent_20260325_001",
  "status": "running",
  "progress": 40,
  "result": {
    "current_step": "情绪分析师完成，启动多空辩论..."
  }
}
```

**响应 (完成)**:
```json
{
  "id": "agent_20260325_001",
  "status": "completed",
  "progress": 100,
  "result": {
    "decision": {
      "action": "BUY",
      "reasoning": "综合决策理由...",
      "confidence": 0.76,
      "risk_score": 0.24
    },
    "final_state": {
      "stock_code": "600519",
      "company_name": "贵州茅台",
      "technical_report": { "score": 82, "trend": "上涨", "ai_commentary": "...", "tool_calls": [...] },
      "fundamental_report": { "score": 88, "financial_health": "健康", "ai_commentary": "..." },
      "capital_flow_report": { "score": 71, "main_force_trend": "净流入", "ai_commentary": "..." },
      "sentiment_report": { "ai_commentary": "...", "relevant_news_count": 15 },
      "bull_case": "看多论据全文...",
      "bear_case": "看空论据全文...",
      "risk_assessment": { "risk_score": 28, "risk_level": "中低风险", "ai_commentary": "..." },
      "investor_opinions": {
        "buffett": { "recommendation": "BUY", "confidence": 0.85, "reasoning": "..." },
        "munger": { "recommendation": "HOLD", "confidence": 0.6, "reasoning": "..." },
        "lynch": { "recommendation": "BUY", "confidence": 0.8, "reasoning": "..." },
        "damodaran": { "recommendation": "BUY", "confidence": 0.75, "reasoning": "..." }
      },
      "investor_consensus": {
        "final_recommendation": "BUY",
        "consensus_confidence": "高",
        "consensus_confidence_score": 0.85,
        "agreement_level": "强共识",
        "consensus_reasoning": "AI首席策略官综合分析...",
        "key_agreements": ["..."],
        "key_disagreements": ["..."],
        "weight_analysis": "巴菲特和林奇观点更有说服力...",
        "ai_driven": true
      },
      "router_decision": "normal",
      "execution_log": [
        { "agent": "技术分析师", "status": "success", "mode": "ai_agent", "tools_used": 2 },
        { "agent": "基本面分析师", "status": "success", "mode": "ai_agent", "tools_used": 1 }
      ],
      "errors": []
    },
    "current_step": "多Agent分析完成",
    "execution_log": [...],
    "errors": []
  }
}
```

**关键字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| decision.action | string | BUY / SELL / HOLD |
| decision.confidence | float | 0.0-1.0 决策置信度 |
| decision.risk_score | float | 0.0-1.0 风险评分 (= 1 - confidence) |
| investor_consensus.ai_driven | bool | true=AI研判, false=降级投票 |
| investor_consensus.consensus_confidence_score | float | 0.0-1.0 共识置信度 |
| execution_log[].mode | string | ai_agent=Function Calling模式, fallback=降级模式 |
| execution_log[].tools_used | int | AI调用工具次数 |
| router_decision | string | normal=正常路径, fast_fail=快速失败 |

---

### GET /api/agent_analysis_history

获取已完成的Agent分析历史列表。按更新时间降序。

**响应**:
```json
{
  "history": [
    {
      "id": "agent_20260325_001",
      "status": "completed",
      "created_at": "2026-03-25 14:30:00",
      "params": { "stock_code": "600519" },
      "result": { ... }
    }
  ]
}
```

---

### POST /api/delete_agent_analysis

删除或取消Agent分析任务。

**请求**:
```json
{
  "task_ids": ["agent_20260325_001", "agent_20260325_002"]
}
```

**响应**:
```json
{
  "deleted_count": 1,
  "cancelled_count": 1,
  "message": "成功删除1个任务，取消1个任务"
}
```

---

### GET /api/agent_pending_approvals

获取待人工审批的高风险Agent决策（Human-in-the-Loop）。

**响应**:
```json
{
  "approvals": [
    {
      "task_id": "approval_001",
      "decision": { "action": "SELL", "confidence": 0.72 },
      "risk_level": "high"
    }
  ]
}
```

---

### POST /api/agent_submit_approval

提交人工审批结果。

**请求**:
```json
{
  "task_id": "approval_001",
  "approved": true,
  "feedback": "同意卖出"
}
```

---

### GET /api/active_tasks

获取所有正在运行的任务。

**响应**:
```json
{
  "active_tasks": [
    { "task_id": "agent_001", "stock_code": "600519", "progress": 40 }
  ]
}
```

---

## 股票分析API

### POST /analyze

快速分析多只股票（同步，会阻塞，建议改用异步API）。

**请求**:
```json
{
  "stock_codes": ["600519", "000001"],
  "market_type": "A"
}
```

**响应**:
```json
{
  "results": [
    { "stock_code": "600519", "stock_name": "贵州茅台", "score": 85.5, "rating": "强烈推荐" }
  ]
}
```

---

### POST /api/start_stock_analysis

启动个股分析任务（异步）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码 |
| market_type | string | 否 | 默认 "A" |

**响应**: `{ "task_id": "...", "status": "pending" }`
**轮询**: `GET /api/analysis_status/<task_id>`
**取消**: `POST /api/cancel_analysis/<task_id>`

---

### POST /api/enhanced_analysis

增强分析（同步，向后兼容）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码 |
| market_type | string | 否 | 默认 "A" |

---

### GET /api/stock_data

获取股票历史行情及技术指标。支持 300 秒缓存。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码 |
| market_type | string | 否 | 默认 "A" |
| period | string | 否 | 1m/3m/6m/1y，默认 "1y" |

**响应包含**: date, open, high, low, close, volume, sma20, sma50, ema12, ema26, macd, signal, histogram, rsi14, atr14, bb_upper/middle/lower

---

## 市场扫描API

### POST /api/start_market_scan

启动市场扫描（异步，支持最多100只股票，分批处理）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_list | array | 是 | 股票代码列表 |
| min_score | int | 否 | 最低评分阈值，默认 60 |
| market_type | string | 否 | 默认 "A" |

**轮询**: `GET /api/scan_status/<task_id>`
**取消**: `POST /api/cancel_scan/<task_id>`

---

## 基本面分析API

### POST /api/fundamental_analysis

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码 |

**响应包含**: fundamental_score, pe_ratio, pb_ratio, roe, debt_ratio, revenue_growth, profit_growth

---

## 资金流向API

### POST /api/capital_flow

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码 |
| market_type | string | 否 | 默认自动检测 |

### POST /api/north_flow_history

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码 |
| days | int | 否 | 天数，默认 10 |

### GET /api/concept_fund_flow

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| period | string | 否 | 默认 "10日排行" |

### GET /api/individual_fund_flow_rank

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| period | string | 否 | 默认 "10日" |

### GET /api/individual_fund_flow

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码 |

---

## 风险分析API

### POST /api/risk_analysis

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码 |
| market_type | string | 否 | 默认 "A" |

### POST /api/portfolio_risk

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| portfolio | array | 是 | `[{"stock_code": "600519", "weight": 0.5}, ...]` |

---

## 行业分析API

### GET /api/industry_analysis

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| industry | string | 是 | 行业名称 |
| limit | int | 否 | 默认 30，最大 500 |

### GET /api/industry_fund_flow

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbol | string | 否 | 默认 "即时" |

### GET /api/industry_detail

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| industry | string | 是 | 行业名称 |

### GET /api/industry_compare

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| limit | int | 否 | 默认 10 |

### GET /api/sector_stocks

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sector | string | 是 | 行业名称 |

---

## 指数/板块API

### GET /api/index_stocks

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| index_code | string | 否 | 默认 "000300"（沪深300） |

支持: 000300(沪深300), 000905(中证500), 000852(中证1000), 000001(上证指数)

### GET /api/board_stocks

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| board | string | 否 | 默认 "hs300" |

支持: hs300, zz500, zz1000, kc50, kc100, bj50

### GET /api/index_analysis

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| index_code | string | 是 | 指数代码 |
| limit | int | 否 | 默认 30 |

---

## 情景预测API

### POST /api/scenario_predict

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码 |
| market_type | string | 否 | 默认 "A" |
| days | int | 否 | 预测天数，默认 60 |

**响应包含**: 乐观/基准/悲观三种情景，含概率、目标价、关键假设

---

## ETF分析API

### POST /api/start_etf_analysis

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| etf_code | string | 是 | ETF代码 |

**轮询**: `GET /api/etf_analysis_status/<task_id>`

---

## 智能问答API

### POST /api/qa

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码 |
| question | string | 是 | 自然语言问题 |
| market_type | string | 否 | 默认 "A" |

---

## 新闻与历史API

### GET /api/latest_news

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 否 | 不指定则返回市场新闻 |
| limit | int | 否 | 默认 10 |

### GET /api/history_analysis

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码 |
| days | int | 否 | 默认 30 |

### GET /search_us_stocks

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |

---

## MCP工具API

### GET /api/mcp/tools

列出所有MCP可用工具（7个工具：get_stock_data, get_technical_indicators, get_fundamental_data, get_capital_flow, get_stock_news, search_web, get_risk_assessment）。

### POST /api/mcp/call

调用指定MCP工具。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| tool | string | 是 | 工具名称 |
| arguments | object | 是 | 工具参数 |

---

## 页面路由

| 路径 | 说明 |
|------|------|
| `/` | 首页（财经门户风格） |
| `/dashboard` | 智能仪表盘 |
| `/stock_detail/<stock_code>` | 股票详情 |
| `/portfolio` | 投资组合 |
| `/market_scan` | 市场扫描 |
| `/fundamental` | 基本面分析 |
| `/capital_flow` | 资金流向 |
| `/scenario_predict` | 情景预测 |
| `/risk_monitor` | 风险监控 |
| `/qa` | 智能问答 |
| `/industry_analysis` | 行业分析 |
| `/agent_analysis` | Agent智能分析 |
| `/etf_analysis` | ETF分析 |

---

## 错误处理

### HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 端点不存在 |
| 500 | 服务器内部错误 |

### 错误响应格式

```json
{
  "error": "错误描述"
}
```

### 404 响应
```json
{
  "error": "找不到请求的API端点",
  "path": "/api/unknown",
  "method": "GET"
}
```

---

此项目的任何功能、架构更新，必须在结束后同步更新相关文档。这是我们契约的一部分。
