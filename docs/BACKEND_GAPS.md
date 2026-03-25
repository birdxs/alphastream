# 后端能力缺口审计与补齐设计

```
Input: 现有后端代码审计结果
Output: AI-native前端所需后端能力缺口清单与补齐方案
Pos: docs/BACKEND_GAPS.md - 后端改造的唯一权威设计文档
```

> 一旦我被修改，请更新所属文件夹的 README.md。

---

**版本**: v1.0.0
**审计范围**: web_server.py / ai_client.py / tools.py / coordinator.py / state.py / event_bus.py
**审计结论**: 当前后端为传统REST+轮询架构，支撑AI-native前端需补齐6项核心能力

---

## 1. 能力缺口清单

| # | 缺口描述 | 严重度 | 影响范围 | 现状 |
|---|---------|--------|---------|------|
| G1 | **无SSE流式输出端点** | P0-致命 | 全部AI交互体验 | `start_agent_analysis`为异步任务+轮询，`api/qa`为同步阻塞，均无流式输出 |
| G2 | **无Generative UI数据协议** | P0-致命 | 前端组件动态渲染 | 工具返回纯字符串(`str`)，无结构化artifact schema，前端无法据此选择React组件 |
| G3 | **无实时Agent状态推送** | P1-严重 | Agent执行过程可视化 | `event_bus.py`存在但仅进程内回调，未桥接到HTTP/SSE通道；轮询`agent_analysis_status`只能获取粗粒度progress |
| G4 | **无对话上下文管理** | P1-严重 | 多轮对话连续性 | `ai_client.chat_with_tools()`接受messages列表但无持久化；`api/qa`每次独立调用无历史 |
| G5 | **无预判性提问生成** | P2-重要 | 交互引导体验 | AI回复后无follow-up建议问题机制 |
| G6 | **AI调用无流式支持** | P0-致命 | Token逐字输出 | `ai_client.chat_completion()`调用`client.chat.completions.create()`未传`stream=True`，无法逐token产出 |

### 现有能力确认（无需改动）

| 能力 | 状态 | 说明 |
|------|------|------|
| 40+ REST API端点 | ✅ 保留 | 自选股/投资组合/行业分析等，前端直接调用，工具函数内部调用，均不需改动 |
| 7个工具函数 | ✅ 保留 | `tools.py`中的LangChain @tool + OpenAI schema双格式，Agent调用链路完整 |
| LangGraph编排 | ✅ 保留 | `coordinator.py`的fan-out/fan-in/条件路由无需修改，需增加SSE事件钩子 |
| EventBus | ⚠️ 需扩展 | 已有进程内发布订阅，需桥接到SSE通道 |
| MCP工具API | ✅ 保留 | `/api/mcp/tools`和`/api/mcp/call`保持不变 |

---

## 2. SSE流式端点设计

### 2.1 核心端点：`POST /api/ai/chat`

**职责**：接收用户消息，SSE流式返回AI分析全过程（Token + 工具调用 + Agent状态 + Artifact数据）。

**请求**：
```json
{
  "message": "分析一下贵州茅台的投资价值",
  "conversation_id": "conv_abc123",
  "stock_code": "600519",
  "market_type": "A",
  "research_depth": 3,
  "stream": true
}
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| message | string | 是 | - | 用户消息 |
| conversation_id | string | 否 | 自动生成 | 对话ID，用于多轮上下文 |
| stock_code | string | 否 | 从message中AI提取 | 股票代码 |
| market_type | string | 否 | "A" | 市场类型 |
| research_depth | int | 否 | 3 | 研究深度1-5 |
| stream | bool | 否 | true | 是否流式输出 |

**响应**：`Content-Type: text/event-stream`

### 2.2 SSE事件类型定义

每个SSE消息格式：
```
event: {event_type}
data: {json_payload}

```

#### 事件类型完整列表

```typescript
// 1. AI文字Token流
event: token
data: {"content": "贵州", "finish_reason": null}

event: token
data: {"content": "茅台", "finish_reason": null}

event: token
data: {"content": "", "finish_reason": "stop"}

// 2. 工具调用开始
event: tool_call_start
data: {
  "tool_call_id": "call_abc123",
  "tool_name": "get_technical_indicators",
  "arguments": {"stock_code": "600519"},
  "agent": "技术分析师"
}

// 3. 工具调用结果
event: tool_call_result
data: {
  "tool_call_id": "call_abc123",
  "tool_name": "get_technical_indicators",
  "result_summary": "RSI=62, MACD金叉, 趋势向上",
  "artifact": {
    "type": "artifact",
    "artifact_type": "technical_indicators",
    "data": { ... }
  },
  "duration_ms": 1200
}

// 4. Agent进度变化
event: agent_progress
data: {
  "agent_name": "技术分析师",
  "status": "completed",
  "progress": 25,
  "message": "技术分析完成，启动基本面和资金流分析...",
  "agents_completed": ["技术分析师"],
  "agents_pending": ["基本面分析师", "资金流分析师"]
}

// 5. Artifact数据推送（Generative UI专用）
event: artifact
data: {
  "type": "artifact",
  "artifact_type": "candlestick_chart",
  "title": "贵州茅台(600519) K线图",
  "data": {
    "stock_code": "600519",
    "stock_name": "贵州茅台",
    "ohlcv": [...],
    "indicators": {...}
  }
}

// 6. 思考过程（可选，用于显示AI推理链）
event: reasoning
data: {
  "content": "用户询问投资价值，需要综合技术面、基本面和资金流...",
  "agent": "协调器"
}

// 7. 错误事件
event: error
data: {
  "code": "TOOL_EXECUTION_FAILED",
  "message": "获取资金流向数据超时",
  "recoverable": true
}

// 8. 流结束（附带follow-up建议）
event: done
data: {
  "conversation_id": "conv_abc123",
  "message_id": "msg_xyz789",
  "usage": {"prompt_tokens": 2500, "completion_tokens": 800},
  "follow_up_questions": [
    "茅台的PE估值与历史相比处于什么水平？",
    "北向资金近期对茅台的增减持情况如何？",
    "白酒行业整体趋势如何？"
  ]
}
```

### 2.3 后端实现方案

**技术选型：Flask SSE（无需迁移框架）**

Flask 3.1.0 原生支持 `Response(generate(), content_type='text/event-stream')`，通过Python generator实现SSE，**无需迁移到FastAPI**。

```python
# 实现要点（伪代码）
from flask import Response, stream_with_context
import json
import queue

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat_stream():
    data = request.json

    def generate():
        event_queue = queue.Queue()

        # 1. 订阅EventBus事件，转发到queue
        # 2. 启动后台线程执行Agent分析
        # 3. 流式调用OpenAI（stream=True）
        # 4. yield SSE格式事件

        while True:
            event = event_queue.get(timeout=300)
            if event is None:  # 结束信号
                break
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )
```

### 2.4 ai_client.py 需新增的流式方法

```python
def chat_completion_stream(client, messages, temperature=0.7, max_tokens=4096, tools=None):
    """流式聊天完成调用，返回迭代器"""
    kwargs = {
        'model': get_ai_model(),
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
        'stream': True,  # 关键差异
    }
    if tools:
        kwargs['tools'] = tools
        kwargs['tool_choice'] = 'auto'

    return client.chat.completions.create(**kwargs)


def chat_with_tools_stream(client, messages, tools_schema, tool_executor=None,
                            max_tool_rounds=3, event_callback=None):
    """
    带工具调用循环的流式AI对话。
    每产生一个token/工具调用事件，通过event_callback推送。
    """
    # 核心逻辑：
    # for chunk in stream:
    #   if chunk.choices[0].delta.content:
    #       event_callback('token', {'content': chunk.choices[0].delta.content})
    #   if chunk.choices[0].delta.tool_calls:
    #       # 收集完整tool_call后执行
    #       event_callback('tool_call_start', {...})
    #       result = tool_executor(tool_name, args)
    #       event_callback('tool_call_result', {...})
    pass
```

---

## 3. Artifact数据协议（Generative UI）

### 3.1 通用Artifact Schema

```json
{
  "$schema": "artifact/v1",
  "type": "artifact",
  "artifact_type": "<type_enum>",
  "title": "组件标题",
  "description": "可选描述",
  "data": { },
  "metadata": {
    "source_tool": "get_technical_indicators",
    "generated_at": "2026-03-25T14:30:00+08:00",
    "stock_code": "600519"
  }
}
```

### 3.2 Artifact类型注册表

| artifact_type | 来源工具 | 前端React组件 | data字段结构 |
|---------------|---------|--------------|-------------|
| `candlestick_chart` | get_stock_data | `<CandlestickChart>` | `{ohlcv: [{date,open,high,low,close,volume}], indicators: {ma5,ma20,ma60}}` |
| `technical_indicators` | get_technical_indicators | `<TechnicalDashboard>` | `{score, trend, rsi, macd: {value,signal,histogram}, bollinger: {upper,middle,lower}, signals: [{type,description}]}` |
| `fundamental_metrics` | get_fundamental_data | `<FundamentalCard>` | `{score, pe_ratio, pb_ratio, roe, debt_ratio, revenue_growth, profit_growth, financial_health}` |
| `capital_flow_chart` | get_capital_flow | `<CapitalFlowChart>` | `{main_force_net, north_flow, institutional_flow, retail_flow, trend_days: [{date,net_flow}]}` |
| `news_feed` | get_stock_news | `<NewsFeed>` | `{items: [{time, title, content, sentiment, source}]}` |
| `risk_gauge` | get_risk_assessment | `<RiskGauge>` | `{risk_score, risk_level, volatility_risk, trend_risk, reversal_risk, volume_risk, factors: [...]}` |
| `search_results` | search_web | `<SearchResults>` | `{results: [{title, url, snippet, source}]}` |
| `decision_card` | DecisionMaker | `<DecisionCard>` | `{action, confidence, reasoning, price_targets: {support,resistance}, risk_score}` |
| `investor_consensus` | InvestorCoordinator | `<InvestorPanel>` | `{consensus: {recommendation,confidence_score,reasoning}, opinions: {buffett:{...},munger:{...},...}}` |
| `agent_pipeline` | Coordinator | `<AgentPipeline>` | `{agents: [{name,status,progress,duration_ms}], current_agent, total_progress}` |

### 3.3 工具返回值改造方案

**当前问题**：`tools.py`中所有工具返回纯字符串（`str`），无法携带结构化artifact数据。

**改造策略**：工具函数内部返回值不变（保持向后兼容），在SSE层包装artifact。

具体方案：**在`execute_tool()`外层增加artifact包装器**，不修改现有工具函数：

```python
# 新增：app/core/artifact_wrapper.py

ARTIFACT_TYPE_MAP = {
    "get_stock_data": "candlestick_chart",
    "get_technical_indicators": "technical_indicators",
    "get_fundamental_data": "fundamental_metrics",
    "get_capital_flow": "capital_flow_chart",
    "get_stock_news": "news_feed",
    "search_web": "search_results",
    "get_risk_assessment": "risk_gauge",
}

def execute_tool_with_artifact(tool_name: str, arguments: dict) -> dict:
    """执行工具并包装为artifact格式"""
    from app.core.tools import execute_tool

    raw_result = execute_tool(tool_name, arguments)
    artifact_type = ARTIFACT_TYPE_MAP.get(tool_name)

    return {
        "raw_result": raw_result,  # 给AI继续推理用
        "artifact": {
            "type": "artifact",
            "artifact_type": artifact_type,
            "title": f"{arguments.get('stock_code', '')} {tool_name}",
            "data": _parse_tool_result(tool_name, raw_result, arguments),
            "metadata": {
                "source_tool": tool_name,
                "stock_code": arguments.get("stock_code", ""),
            }
        }
    }
```

**重要**：工具内部的分析器（如`StockAnalyzer.quick_analyze_stock()`）已返回dict，只是在`tools.py`中被`str(result)`序列化了。artifact包装器需要在序列化之前捕获原始dict结构。这意味着需要小幅修改工具函数，让它们返回`(str_summary, raw_data_dict)`元组，或新增一批返回结构化数据的工具变体。

**推荐方案**：给`execute_tool`增加`return_raw=True`参数，返回原始数据而非字符串。

---

## 4. Agent状态推送协议

### 4.1 EventBus到SSE桥接

当前`event_bus.py`是进程内发布订阅，需要桥接到SSE通道：

```python
# 需要扩展event_bus.py，增加SSE桥接能力

# 新增事件类型常量
EVENT_AGENT_STARTED = 'agent.started'
EVENT_AGENT_COMPLETED = 'agent.completed'
EVENT_TOOL_CALL_START = 'tool.call.start'
EVENT_TOOL_CALL_RESULT = 'tool.call.result'
EVENT_TOKEN_GENERATED = 'token.generated'
EVENT_STREAM_DONE = 'stream.done'
```

### 4.2 Agent节点需注入事件发布

当前各Agent（如`TechnicalAnalystAgent.analyze()`）执行完毕后未发布事件。需要在coordinator的图节点wrapper中注入事件发布：

```python
# coordinator.py 改造方案
def _wrap_agent_node(agent_analyze_fn, agent_name):
    """包装Agent节点函数，注入事件发布"""
    def wrapped(state):
        event_bus = get_event_bus()
        event_bus.publish(EVENT_AGENT_STARTED, {
            'agent_name': agent_name,
            'stock_code': state.get('stock_code')
        })
        try:
            result = agent_analyze_fn(state)
            event_bus.publish(EVENT_AGENT_COMPLETED, {
                'agent_name': agent_name,
                'status': 'success',
                'progress': _calc_progress(agent_name, state.get('research_depth', 3))
            })
            return result
        except Exception as e:
            event_bus.publish(EVENT_AGENT_COMPLETED, {
                'agent_name': agent_name,
                'status': 'error',
                'error': str(e)
            })
            raise
    return wrapped
```

### 4.3 事件流完整时序

```
[SSE连接建立]
  → agent_progress: {agent: "协调器", status: "started", progress: 0}
  → agent_progress: {agent: "技术分析师", status: "started", progress: 5}
  → tool_call_start: {tool: "get_stock_data", agent: "技术分析师"}
  → tool_call_result: {tool: "get_stock_data", artifact: {...}}
  → tool_call_start: {tool: "get_technical_indicators", agent: "技术分析师"}
  → tool_call_result: {tool: "get_technical_indicators", artifact: {...}}
  → token: {content: "根据技术面分析..."} (AI对技术分析的commentary)
  → agent_progress: {agent: "技术分析师", status: "completed", progress: 10}
  → agent_progress: {agent: "基本面分析师", status: "started", progress: 10}
  → agent_progress: {agent: "资金流分析师", status: "started", progress: 10}
  → ... (并行执行)
  → agent_progress: {agent: "基本面分析师", status: "completed", progress: 25}
  → agent_progress: {agent: "资金流分析师", status: "completed", progress: 25}
  → ... (继续后续Agent)
  → artifact: {artifact_type: "decision_card", data: {...}}
  → token: {content: "综合分析建议..."} (最终决策commentary)
  → done: {follow_up_questions: [...]}
[SSE连接关闭]
```

---

## 5. 对话管理API设计

### 5.1 对话存储模型

```python
# 新增到 state.py 或独立 conversation.py
class Conversation:
    conversation_id: str       # UUID
    created_at: datetime
    updated_at: datetime
    title: str                 # 自动生成或用户命名
    messages: List[Message]    # 完整消息历史
    stock_codes: List[str]     # 涉及的股票代码
    analysis_refs: List[str]   # 关联的Agent分析task_id

class Message:
    message_id: str
    role: str                  # user / assistant / system
    content: str
    artifacts: List[dict]      # 该消息产生的artifact列表
    tool_calls: List[dict]     # 该消息触发的工具调用
    created_at: datetime
```

### 5.2 对话管理REST端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/conversations` | 获取对话列表（分页） |
| GET | `/api/conversations/<id>` | 获取单个对话详情（含历史消息） |
| DELETE | `/api/conversations/<id>` | 删除对话 |
| PATCH | `/api/conversations/<id>` | 更新对话标题 |

注意：**创建对话和添加消息通过SSE端点`/api/ai/chat`隐式完成**，不需要单独的创建端点。

### 5.3 对话上下文传递

SSE端点`/api/ai/chat`接收`conversation_id`参数：
- **首次对话**：不传`conversation_id`，后端自动创建并在`done`事件中返回
- **后续对话**：传入已有的`conversation_id`，后端从存储中加载历史messages，拼接到AI调用的messages列表中
- **上下文窗口**：保留最近20条消息（约4000 tokens），超出部分自动摘要压缩

### 5.4 存储方案

当前系统已有SQLite（`database.py`中`USE_DATABASE`标志）：
- 对话数据存入SQLite新表`conversations`和`messages`
- 与现有`AnalysisResult`表关联
- 内存中保留活跃对话的LRU缓存（最近50个对话）

---

## 6. 预判性提问生成

### 6.1 实现方案

在最终AI回复完成后，用单独一次轻量AI调用生成follow-up问题：

```python
FOLLOW_UP_PROMPT = """基于刚才的分析对话，生成3-5个用户可能想继续追问的问题。
要求：
1. 问题要具体且有价值，与当前分析的股票相关
2. 覆盖不同角度（技术面/基本面/行业/风险/操作建议）
3. 每个问题不超过30字
4. 返回JSON数组格式

当前股票: {stock_code}
最近对话摘要: {conversation_summary}
"""
```

### 6.2 返回位置

follow-up问题在SSE流的`done`事件中返回（见2.2节`done`事件定义）。

---

## 7. 后端技术栈评估

### 7.1 Flask vs FastAPI 评估

| 维度 | Flask 3.1.0（当前） | FastAPI | 结论 |
|------|---------------------|---------|------|
| SSE支持 | ✅ `Response(generator, content_type='text/event-stream')` | ✅ `StreamingResponse` | 两者均原生支持 |
| 异步IO | ⚠️ 通过`threading`实现（当前已用） | ✅ 原生async/await | Flask够用，但FastAPI更优雅 |
| WebSocket | ⚠️ 需flask-socketio | ✅ 原生支持 | SSE场景不需要WebSocket |
| 现有代码量 | 2400+行路由，40+端点 | 需要全部重写 | **迁移成本巨大** |
| LangGraph兼容 | ✅ 线程中同步调用 | ✅ 可异步调用 | 两者均可 |
| OpenAI SDK流式 | ✅ 同步迭代器`for chunk in stream` | ✅ 异步迭代器 | 两者均可 |

**结论：不迁移，继续使用Flask 3.1.0**

理由：
1. Flask SSE完全满足需求，无技术障碍
2. 迁移40+端点到FastAPI的工程量远大于收益
3. 当前`threading`模式与LangGraph的同步`graph.invoke()`天然兼容
4. Flask生态（flask-cors, flask-caching, flask-swagger）已深度集成

### 7.2 Flask SSE实现注意事项

1. **Nginx反向代理**：需设置`proxy_buffering off`和`X-Accel-Buffering: no`
2. **连接超时**：Agent分析可能需要60-180秒，需设置足够的`proxy_read_timeout`
3. **并发连接**：Flask开发服务器单线程，生产环境需`gunicorn -w 4 -k gevent`或`--threads 8`
4. **CORS**：SSE端点需要在CORS配置中允许`text/event-stream`响应类型

### 7.3 依赖项变更

无需新增Python依赖。Flask 3.1.0 + OpenAI SDK（已安装）已包含所有必需功能。

---

## 8. 实施优先级排序

### P0 — 必须首先完成（阻塞前端开发）

| 任务 | 涉及文件 | 工作量估算 | 说明 |
|------|---------|-----------|------|
| **SSE流式端点** `/api/ai/chat` | `web_server.py` | 3天 | 前端所有AI交互的唯一入口 |
| **ai_client流式方法** | `ai_client.py` | 1天 | 新增`chat_completion_stream`和`chat_with_tools_stream` |
| **Artifact包装器** | 新增`artifact_wrapper.py` | 2天 | 工具结果结构化，含7个工具的数据解析 |
| **SSE事件协议实现** | `web_server.py` | 1天 | token/tool_call/agent_progress/done事件格式 |

### P1 — 核心体验（可与前端并行开发）

| 任务 | 涉及文件 | 工作量估算 | 说明 |
|------|---------|-----------|------|
| **EventBus SSE桥接** | `event_bus.py` | 1天 | 进程内事件转SSE通道 |
| **Agent节点事件注入** | `coordinator.py` | 1天 | 各Agent执行包装器，发布start/complete事件 |
| **对话上下文管理** | 新增`conversation.py`或扩展`database.py` | 2天 | 对话存储/加载/上下文窗口管理 |
| **对话REST端点** | `web_server.py` | 0.5天 | 列表/详情/删除/重命名 |

### P2 — 增强体验（可后续迭代）

| 任务 | 涉及文件 | 工作量估算 | 说明 |
|------|---------|-----------|------|
| **预判性提问生成** | `ai_client.py` / `web_server.py` | 0.5天 | done事件中附带follow-up |
| **工具函数结构化返回** | `tools.py` + 各analyzer | 3天 | 让工具返回原始dict而非纯字符串 |
| **对话历史摘要压缩** | `conversation.py` | 1天 | 超出上下文窗口时自动摘要 |

### 总工作量估算

- **P0**: 约7人天
- **P1**: 约4.5人天
- **P2**: 约4.5人天
- **总计**: 约16人天

### 实施顺序建议

```
Week 1: P0（SSE端点 + 流式AI + Artifact协议）→ 前端可开始对接
Week 2: P1（事件桥接 + Agent状态 + 对话管理）→ 完整交互体验
Week 3: P2（follow-up + 工具结构化 + 摘要压缩）→ 体验优化
```

---

## 9. 需修改的文件清单汇总

| 文件 | 修改类型 | 优先级 |
|------|---------|--------|
| `app/web/web_server.py` | 新增SSE端点 + 对话REST端点 | P0+P1 |
| `app/core/ai_client.py` | 新增流式方法 `chat_completion_stream` / `chat_with_tools_stream` | P0 |
| `app/core/event_bus.py` | 新增事件类型常量 + SSE桥接方法 | P1 |
| `app/agents/coordinator.py` | Agent节点包装器注入事件发布 | P1 |
| `app/core/tools.py` | 可选：增加`return_raw`参数 | P2 |
| `app/core/artifact_wrapper.py` | **新建**：artifact包装器（见3.3节） | P0 |
| `app/core/conversation.py` | **新建**：对话管理模块（见5节） | P1 |
| `docs/API.md` | 更新：新增SSE端点和对话管理端点文档 | P0完成后 |

---

此项目的任何功能、架构更新，必须在结束后同步更新相关文档。这是我们契约的一部分。
