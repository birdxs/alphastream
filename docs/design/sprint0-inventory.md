# Sprint 0 只读盘点清单

```
Input: Comdr 已批准 dojo-agents-absorption-plan.md；本文件仅证据 + 契约草案
Output: 事件 payload 草案 / terminal 态枚举 / HITL 断点 / 风险分级差距 / P0 实现入口建议
Pos: docs/design/sprint0-inventory.md — Sprint0 交付物；零业务代码
```

| 字段 | 值 |
|------|-----|
| 文档版本 | **v1.0** |
| 盘点时间 | **2026-07-23 15:33:50 +08:00**（校时：本机 PDT 08:33:53 -0700 ≡ UTC 15:33:53；Cloudflare Date `Thu, 23 Jul 2026 15:33:54 GMT`；GitHub Date `Thu, 23 Jul 2026 15:33:50 GMT`；最大偏差 ≤4s，通过） |
| 状态 | **Sprint0 盘点完成；Sprint1 多项 P0 DONE；Sprint2（意图+真仓只读）DONE 2026-07-23** |
| 约束 | **零** `app/` / `frontend/src` 业务改动；禁 push；禁启服务 |
| 依据设计 | `docs/design/dojo-agents-absorption-plan.md` **v1.1**（全文为准；非早期 PortfolioSnapshot-P0） |
| 批准 MD 的 P0 编号 | **P0-1** 工具护栏 · **P0-2** 意图协议 · **P0-3** 真仓只读 · **P0-4** 证据信封 · **P0-5 确认面（HITL）** · **P0-6** 辩论+完成态 · **P0-7** 降级帽 |
| Sprint1 建议首攻 | 按设计 MD：**P0-1 护栏 + P0-5 确认面** 可并行，确认面断点已齐（见 §6）；Comdr 可砍子集 |

---

## 1. 事件 payload 草案

约定：

- 传输：进程内 `EventBus.publish(event_type, payload: dict)`；HTTP SSE 侧多包一层 `event: <name>` + `data: JSON`。
- 共用信封字段（所有事件宜带，标 **可选** 的允许旧发布点渐进补齐）：

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `task_id` | string | 条件必选 | Agent 异步任务 ID；progress / approval 链路必选 |
| `conversation_id` | string | 可选 | 对话会话 |
| `stock_code` | string | 可选 | 标的 |
| `ts` | string (ISO8601 +08:00) | 可选 | 事件时刻；缺省由消费方 `now` |
| `schema_version` | int | 可选 | 默认 1 |

### 1.1 `task.progress_advance`

| | |
|--|--|
| 现状 | **已有**。`coordinator._ProgressTracker.advance` → `get_event_bus().publish('task.progress_advance', …)`；`web_server._run_new_agent_system` 订阅并 `update_task_status`。 |
| 设计名 | 与现状同名（已对齐） |

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `progress` | int | 是 | 0–100 |
| `node` | string | 是 | 完成的图节点名 |
| `completed` | int | 否 | 已完成节点数 |
| `total` | int | 否 | 总节点数 |
| `message` | string | 否 | 人类可读步骤 |

**示例：**

```json
{
  "task_id": "agt_20260723_001",
  "progress": 42,
  "node": "fundamental_analyst",
  "completed": 3,
  "total": 7,
  "message": "基本面分析完成"
}
```

### 1.2 `agent.role_started` / `agent.role_finished`

| | |
|--|--|
| 现状 | **语义有、命名分叉**。`EVENT_AGENT_STARTED='agent_progress.started'`、`EVENT_AGENT_COMPLETED='agent_progress.completed'`；payload 常用 `event_type: 'agent_progress'` + `data.phase ∈ {started,completed}`（见 `coordinator` publish）。 |
| Sprint1 策略 | **发布点增加别名**或 **前端映射表**：设计名 `agent.role_*` ↔ 现名 `agent_progress.*`；禁止第二套 bus。 |

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `role` | string | 是 | 角色 ID/中文名（如 `风险管理师` / `decision_maker`） |
| `phase` | string | 是 | `started` \| `finished`（设计侧 finished ≡ 现 completed） |
| `task_id` | string | 否 | 关联任务 |
| `stock_code` | string | 否 | 标的 |
| `duration_ms` | int | 否 | 仅 finished |
| `ok` | bool | 否 | 仅 finished；失败为 false |
| `summary` | string | 否 | 一句话结果 |

**示例 `role_started`：**

```json
{
  "event_type": "agent.role_started",
  "role": "technical_analyst",
  "phase": "started",
  "task_id": "agt_20260723_001",
  "stock_code": "600519"
}
```

**示例 `role_finished`：**

```json
{
  "event_type": "agent.role_finished",
  "role": "technical_analyst",
  "phase": "finished",
  "task_id": "agt_20260723_001",
  "ok": true,
  "duration_ms": 12840,
  "summary": "趋势偏多，评分 72"
}
```

### 1.3 `agent.tool_call` / `agent.tool_result`

| | |
|--|--|
| 现状 | **已有**。`ai_client` → `EVENT_TOOL_CALL_START='tool_call.start'` / `EVENT_TOOL_CALL_RESULT='tool_call.result'`；payload 内 `event_type: 'tool_call_start' \| 'tool_call_result'`。前端 `use-chat-stream` / `agent-side-panel` 消费 `tool_call_*`。 |
| Sprint1 策略 | 设计名 `agent.tool_*` 作为 **契约别名**；落盘字段下表与现状对齐后可并存 publish（同一 payload 双 type 或映射表）。 |

**tool_call：**

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `tool_call_id` | string | 是 | 一次调用唯一 ID |
| `tool_name` | string | 是 | 工具名 |
| `arguments` | object | 否 | 结构化参数 |
| `arguments_raw` | string | 否 | 截断原文 |
| `agent` | string | 否 | 发起角色 |
| `task_id` | string | 否 | 任务 |

**tool_result：**

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `tool_call_id` | string | 是 | 对齐 call |
| `tool_name` | string | 是 | 工具名 |
| `ok` | bool | 是 | 成功/失败 |
| `result_preview` | string | 否 | 截断结果 |
| `error` | string | 否 | 失败信息 |
| `duration_ms` | int | 否 | 耗时 |
| `degraded` | bool | 否 | 上游降级 |

**示例：**

```json
{
  "event_type": "agent.tool_call",
  "tool_call_id": "call_abc123",
  "tool_name": "get_stock_data",
  "arguments": {"stock_code": "600519", "market_type": "A"},
  "agent": "technical_analyst"
}
```

```json
{
  "event_type": "agent.tool_result",
  "tool_call_id": "call_abc123",
  "tool_name": "get_stock_data",
  "ok": true,
  "result_preview": "rows=120, adjust=qfq",
  "duration_ms": 1820,
  "degraded": false
}
```

### 1.4 `agent.debate_turn`

| | |
|--|--|
| 现状 | **缺失独立事件**。存在 bull/bear 分析节点与报告字段，无 `debate_turn` 发布约定。 |
| Sprint1 | **新增约定 + 发布点**（仅 EventBus 事件名与字段，图结构可不拆）。 |

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 |
| `side` | string | 是 | `bull` \| `bear` \| `moderator` |
| `round` | int | 是 | 从 1 起 |
| `role` | string | 否 | 发言角色 |
| `claim` | string | 是 | 主张摘要（≤500 字） |
| `evidence_refs` | string[] | 否 | 工具/段落引用 ID |
| `confidence` | number | 否 | 0–1 或 0–100（实现时统一） |

**示例：**

```json
{
  "event_type": "agent.debate_turn",
  "task_id": "agt_20260723_001",
  "side": "bull",
  "round": 1,
  "role": "bull_researcher",
  "claim": "量价共振向上，基本面 ROE 稳定",
  "evidence_refs": ["tool:call_abc123", "report:fundamental"],
  "confidence": 0.72
}
```

### 1.5 `approval_needed`

| | |
|--|--|
| 现状 | **已有，命名分叉**。`EVENT_APPROVAL_NEEDED = 'approval.needed'`；`hitl.request_approval` 实际 payload：`event_type: 'reasoning'`，`data.content` 含 `[APPROVAL]` 文本，`data.level`/`task_id`/`risk_level`/`action_type`/`details`。 |
| 期望契约名 | 设计 `approval_needed`（可用为 alias 或统一 event_type 字段）。 |

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 与 `HumanApprovalManager` pending key 一致 |
| `risk_level` | string | 是 | `low` \| `medium` \| `high` |
| `action_type` | string | 是 | 如 `trade_decision` |
| `details` | object | 否 | 决策摘要 / 价位 / 否决点 |
| `timeout_s` | int | 否 | 默认 300 |
| `status` | string | 是 | 发出时固定 `pending` |
| `level` | string | 否 | UI 档（现实现写 `warn`） |

**示例：**

```json
{
  "event_type": "approval_needed",
  "task_id": "agt_20260723_001",
  "risk_level": "high",
  "action_type": "trade_decision",
  "status": "pending",
  "timeout_s": 300,
  "details": {
    "action": "BUY",
    "stock_code": "600519",
    "target_price": null,
    "reason": "综合评分高但波动率偏高"
  }
}
```

**消费侧决议事件（成对，已有 `approval.resolved`）：**

| 字段 | 类型 | 必选 |
|------|------|------|
| `task_id` | string | 是 |
| `approved` | bool | 是 |
| `feedback` | string | 否 |
| `timeout_auto` | bool | 否（true = 超时默认通过，**禁止 UI 渲染为「用户同意」**） |

### 1.6 `agent.degraded`

| | |
|--|--|
| 现状 | **无独立事件**。降级多体现为 tools/adapters 返回空、`errors` 列表、日志 WARNING；铁律 #1 靠 UI 不造假数。 |
| Sprint1 | **新增**；供 P0-2 横幅与 confidence 帽。 |

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `task_id` | string | 否 | 任务 |
| `level` | string | 是 | `info` \| `warn` \| `critical` |
| `cause` | string | 是 | 机器可读：`timeout` / `upstream_empty` / `quota` / `auth` / `parse` |
| `message` | string | 是 | 人类可读（无假价） |
| `source` | string | 否 | adapter/tool 名 |
| `confidence_cap` | number | 否 | 建议置信度上界 |
| `stock_code` | string | 否 | 标的 |

**示例：**

```json
{
  "event_type": "agent.degraded",
  "task_id": "agt_20260723_001",
  "level": "warn",
  "cause": "timeout",
  "source": "akshare_adapter.get_kline",
  "message": "K线上游超时，已跳过该证据源",
  "confidence_cap": 0.5,
  "stock_code": "600519"
}
```

### 1.7 `run.scorecard`

| | |
|--|--|
| 现状 | **缺失**。决策结束有 `final_decision` Artifact 路径，无四维 scorecard 事件。 |
| Sprint1/P1 | 设计预留；P0-5 可先在 terminal 态挂 `scorecard: null`。 |

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 |
| `data_coverage` | number | 是 | 0–1 数据覆盖 |
| `role_agreement` | number | 是 | 0–1 角色一致度 |
| `tool_success_rate` | number | 是 | 0–1 |
| `confidence_cap` | number | 是 | 降级后置信上界 |
| `notes` | string[] | 否 | 说明 |

**示例：**

```json
{
  "event_type": "run.scorecard",
  "task_id": "agt_20260723_001",
  "data_coverage": 0.75,
  "role_agreement": 0.6,
  "tool_success_rate": 0.9,
  "confidence_cap": 0.55,
  "notes": ["fundamental timeout", "bull/bear divergence on valuation"]
}
```

### 1.8 事件名对照（现状 → 设计）

| 设计名 | 现状常量/字符串 | 状态 |
|--------|-----------------|------|
| `task.progress_advance` | `'task.progress_advance'` | 已对齐 |
| `agent.role_started` | `EVENT_AGENT_STARTED` = `agent_progress.started` | 需映射 |
| `agent.role_finished` | `EVENT_AGENT_COMPLETED` = `agent_progress.completed` | 需映射 |
| `agent.tool_call` | `EVENT_TOOL_CALL_START` = `tool_call.start` / `event_type=tool_call_start` | 需映射 |
| `agent.tool_result` | `EVENT_TOOL_CALL_RESULT` = `tool_call.result` / `event_type=tool_call_result` | 需映射 |
| `agent.debate_turn` | — | **新增** |
| `approval_needed` | `EVENT_APPROVAL_NEEDED` = `approval.needed`（payload 伪装 `reasoning`） | 需契约净化 |
| `agent.degraded` | — | **新增** |
| `run.scorecard` | — | **新增**（P1 可深化） |

旁路已有、本 Sprint 不改语义：`token`、`reasoning`、`llm_request`、`risk.alert`、`artifact`。

---

## 2. Terminal 态枚举（API / UI / 内部对齐）

### 2.1 任务态（FileSession / agent 异步）

源：`app/web/web_server.py` 常量。

| 内部值 | API 展示建议 | UI 文案（中文） | 是否 terminal |
|--------|--------------|-----------------|---------------|
| `pending` | `pending` | 排队中 | 否 |
| `running` | `running` | 分析中 | 否 |
| `completed` | `completed` | 已完成 | **是** |
| `failed` | `failed` | 失败 | **是** |
| `cancelled` | `cancelled` | 已取消 | **是** |

### 2.2 Approval 态（HITL）

| 内部值 | API | UI | 说明 |
|--------|-----|-----|------|
| `pending` | `pending` | 待确认 | 阻塞高风险（期望） |
| `approved` | `approved` | 已批准 | 用户显式同意 |
| `rejected` | `rejected` | 已拒绝 | 用户否决 |
| `timeout_auto` | `timeout_auto` | **超时自动通过** | **禁止**与 `approved` 混文案 |

合并展示维度（设计 state `approval.status`）：

`none | pending | approved | rejected | timeout_auto`

### 2.3 final_decision 动作与风险（决策 Artifact）

源：`decision_maker` / 结果结构。

| 维度 | 枚举 | UI |
|------|------|-----|
| `action` | `BUY` \| `SELL` \| `HOLD`（及历史兼容小写） | 买入 / 卖出 / 观望 |
| `risk_level`（决策） | 低 / 中 / 高（中文，现状） | 同步徽章 |
| HITL `risk_level` | `low` \| `medium` \| `high` | 须与决策侧建映射表 |

### 2.4 Artifact 完成态（P0-5）

| 键 | 含义 | terminal 判定 |
|----|------|----------------|
| `decision_card` / decision Artifact | 终裁卡片 | 建议 completed 必有或显式 `missing` |
| 其他 charts / reports | 可选 | 缺失不单独失败任务 |
| `approval` | 高风险时 | high → 非 `none` 才算完整闭环 |

### 2.5 建议统一 terminal 复合态（API 只读投影，Sprint1 实现）

| `run_terminal` | 条件 |
|----------------|------|
| `running` | task ∈ {pending,running} |
| `awaiting_approval` | task=running **或** completed_but 且 approval=pending |
| `completed_clean` | task=completed ∧ approval∈{none,approved} ∧ 有 final_decision |
| `completed_timeout_auto` | task=completed ∧ approval=timeout_auto |
| `rejected` | approval=rejected（任务可 failed 或 completed+否决标记） |
| `failed` | task=failed |
| `cancelled` | task=cancelled |

**API/UI 用语一致表（强制）：**

| 概念 | 禁止混用词 | 标准词 |
|------|------------|--------|
| 用户点同意 | 「超时默认」「自动」 | **已批准** |
| 超时默认通过 | 「用户同意」 | **超时自动通过** |
| 任务成功结束 | 「分析中」 | **已完成** |
| 风控拦截待点 | 「失败」 | **待确认** |

---

## 3. HITL API ↔ 前端断点清单（只读）

### 3.1 后端能力（已有）

| 层 | 路径 | 行为 |
|----|------|------|
| 核心 | `app/agents/hitl.py` | `HumanApprovalManager`：`request_approval` / `submit_approval` / `get_pending_approvals`；风险表 low→auto、medium→log、high→block+Event；超时默认 **approved + timeout_auto** |
| 路由 | `GET /api/agent_pending_approvals` | 列表 pending（OpenAPI + `AgentPendingApprovalsSchema`） |
| 路由 | `POST /api/agent_submit_approval` | body: `task_id` 必填，`approved` default false，`feedback` max 2000（`AgentSubmitApprovalSchema`） |
| 事件 | `approval.needed` / `approval.resolved` | 见 §1.5；UI 通道夹带 `reasoning`+`[APPROVAL]` |
| 测试 | `tests/backend/integration/test_hitl.py`、`test_agent_async_routes`、e2e journey J3 | 多直接注入 manager，**不依赖图内调用** |

### 3.2 图 / 协调器断点（关键缺口）

| 检查项 | 结论 |
|--------|------|
| `coordinator.py` 是否调用 `request_approval` | **否**（全仓生产路径仅 tests / audit 文档引用） |
| `risk_manager` 是否进 HITL | **否**；仅 `EVENT_RISK_ALERT`（reasoning 通道） |
| `decision_maker` 是否进 HITL | **否**；直接写 `final_decision` |
| 结果 | **高风险阻塞形同虚设**：API 与 manager 可测，主 run 不触发 pending |

### 3.3 前端挂载点

| 位置 | 现状 | 与 HITL 关系 |
|------|------|----------------|
| `frontend/src/lib/hooks/use-chat-stream.ts` | SSE：`/api/ai/agent-analyze` 或 `/api/ai/chat`；token / tool_call_* / artifact / done；`useAgentStore` 时间线 | **无** pending 轮询；**无** submit |
| `frontend/src/components/agent/agent-side-panel.tsx` | 解析 `[APPROVAL]` → timeline `warn` + 🚨 | **只读展示**；无按钮 |
| `frontend/src/lib/stores/agent-store.ts` | events / roles / progress 聚合 | 无 approval slice |
| `frontend/src/components/artifacts/decision-card.tsx` | 渲染 `decision_card` Artifact | 不挂审批动作 |
| chat-panel / message-list | 消息与 artifact 宿主 | **无确认卡组件** |
| 全局检索 `agent_pending` / `agent_submit` / `submitApproval` | **frontend 0 命中业务调用** | API 未挂载 |

### 3.4 断点总表（缺口）

| ID | 断点 | 严重度 | Sprint1 归属 |
|----|------|--------|--------------|
| BP-1 | 主图不调用 `request_approval` | **Critical** | P0-1 后端闸门 |
| BP-2 | 前端无确认卡 / 无 approve·reject 控件 | **Critical** | P0-1 前端 |
| BP-3 | 前端不调 `GET/POST` 审批 API | **Critical** | P0-1 |
| BP-4 | 事件伪装 `reasoning`+`[APPROVAL]` 脆弱 | High | P0-1 契约净化 |
| BP-5 | `timeout_auto` 无独立 UI 标记 | High | P0-1 / 风险文档 |
| BP-6 | 任务态与 approval 态未联合 terminal | Medium | P0-5 |
| BP-7 | debate / degraded / scorecard 无事件 | Medium | P0-2/3/5 / P1-2 |

### 3.5 时序（现状 vs 期望）

**现状（简化）：**

```
User → agent-analyze/chat SSE
     → LangGraph roles → final_decision → task completed
     → RISK_ALERT 可能出现在 timeline
     → request_approval 从不发生 → pending API 常空
```

**期望（P0-1）：**

```
… → decision/risk 得 risk_level
  → high: publish approval_needed + request_approval 阻塞
  → UI 确认卡 + poll pending / SSE
  → POST submit_approval → resolved → 继续或否决 → terminal 一致
  → medium: 可观察日志/横幅，不阻塞（与 hitl 表一致）
  → low: 自动
```

---

## 4. 风险分级：现状 vs 期望

### 4.1 HITL 表（权威，`hitl.py`）

| level | require_approval | 行为 |
|-------|------------------|------|
| low | False | 自动通过 |
| medium | False | 日志；不阻塞 |
| high | True | Event + 阻塞直至 submit 或 timeout |

超时：`APPROVAL_TIMEOUT` default **300s** → **`approved=True`, `timeout_auto=True`**。

### 4.2 风险管理师（`risk_manager.py`）

| 维度 | 现状 |
|------|------|
| 评分 | `risk_score` 0–100 |
| 文案档 | 低/中低/中等/中高/高 |
| 事件 | score≥40 或中高+ → `EVENT_RISK_ALERT`；level 映射 `high`/`medium`/`low`（中等刷 `low` 档事件） |
| 与 HITL | **无** `request_approval` |

### 4.3 决策（`decision_maker.py`）

| 维度 | 现状 |
|------|------|
| 输出 | `final_decision` 含 action、中文 `risk_level` 等 |
| 闸门 | **无** HITL |

### 4.4 差距与期望（对齐设计 Q3）

| 项 | 现状 | 期望（设计） | 差距 |
|----|------|--------------|------|
| 低风险自动 | HITL 表支持；主路径恒自动 | 保持 | 表 OK，链路未接 |
| 中风险可回溯 | 仅日志/RiskAlert | 可回溯标记 + 不强制阻塞 | 缺结构化记录 |
| 高风险阻塞确认 | **主 run 不阻塞** | 阻塞 + 确认面 | **最大缺口** |
| 超时语义 | 默认通过 | UI 显式 timeout_auto；可选改默认拒绝（待 Comdr） | 文档已记风险 |
| 分数→HITL 档 | 无统一映射函数 | 建议：score≥80 或「高风险」→ high；60–80 或「中高」→ medium/high 策略表；其余 low | 需 Sprint1 单一函数 |
| scorecard 调档 | 无 | P1-2 低分抬升风险档 | 后置 |

**推荐映射草案（实现期，非本 Sprint 改代码）：**

```
if risk_score >= 80 or risk_level_cn in {高风险}:
    hitl = high
elif risk_score >= 60 or risk_level_cn in {中高风险}:
    hitl = high   # 可配置为 medium；默认偏严以符合「确认面一等公民」
elif risk_score >= 40 or risk_level_cn in {中等风险}:
    hitl = medium
else:
    hitl = low
```

---

## 5. Sprint0 交付勾选（对照设计 §8 Sprint0）

| # | 交付 | 落点 | 状态 |
|---|------|------|------|
| 1 | 事件 payload 草案 | 本文 §1 | **完成** |
| 2 | terminal 态枚举 | 本文 §2 | **完成** |
| 3 | HITL API ↔ 前端断点 | 本文 §3 | **完成** |
| 4 | 风险分级现状 vs 期望 | 本文 §4 | **完成** |
| 5 | 设计 MD 审批栏锁定 + Sprint0 进度 | `dojo-agents-absorption-plan.md` | **同步本批** |

**退出条件**：仍待 Comdr 批「**可进 Sprint1**」。Sprint0 **不**等于授权编码。

---

## 6. P0 实现入口建议（仅建议，零代码）

**以批准 MD §9 为准。** HITL 确认面在当前编号为 **P0-5**（非早期草稿「P0-1=确认面」）。Sprint1 可并行 **P0-1 工具护栏** 与 **P0-5 确认面**。

### 6.1 P0-5 确认面（HITL 产品闭合）— 断点已齐，建议最小回滚序

1. **后端闸门（单点）**  
   - 文件：`app/agents/decision_maker.py` 末尾 **或** `coordinator` 决策后节点包装。  
   - 行为：将 `final_decision`/`risk_score` 映射 HITL level；`high` 时 `approval_manager.request_approval(task_id, …)`。  
   - 确保 `task_id` 从 run 上下文注入（progress 同源）。

2. **事件契约净化**  
   - `hitl.py`：`approval_needed` 专用 `event_type`（可保留 `[APPROVAL]` 兼容一行）。  
   - 解析 `timeout_auto` 在 `approval.resolved`。

3. **前端确认卡**  
   - **优先挂**：`agent-side-panel`（已识别 🚨）+ 主对话流（`chat-panel` / message 旁）。  
   - 数据：SSE 事件 **或** `GET /api/agent_pending_approvals` 短轮询（task 维）。  
   - 动作：`POST /api/agent_submit_approval`。  
   - 文案：§2.5 一致表。

4. **terminal（与 P0-6 衔接）**  
   - status API 投影 `run_terminal` + approval 字段；决策卡展示 approval 徽章。

### 6.2 同 Sprint 建议并行：P0-1 工具护栏

- 新模块建议：`app/core/tool_guardrails.py`（批准 MD；需 [NEW-FILE] 审批）。  
- 挂点：`app/core/tools.py` 与 `/api/ai/chat` FC 前后。  
- 契约：allow|warn|block|halt；同签名失败计数；block **不计** Wind 配额。

### 6.3 其余 P0 落点速查（证据见本文 §1–4）

| ID | 入口建议 |
|----|----------|
| P0-2 协议硬拦 | system 注入 + analyze 路径服务端拒绝 mutate 工具名 |
| P0-3 真仓只读 | `portfolio-store` 真源 → Agent 工具 `portfolio_list/detail` |
| P0-4 证据信封 | **工具时间线 DONE（Sprint1 任务 P0-4，2026-07-23）** `agent.tool_*` 契约；provenance[] 仍待 |
| P0-6 辩论+完成态 | **辩论证据面 DONE（Sprint1 任务 P0-3，2026-07-23）** `agent.debate_turn` + debate_card；terminal 枚举仍待 |
| P0-7 降级帽 | 新增 `agent.degraded` + UI 横幅 + confidence_cap |

### 6.4 明确不做（P0）

- 新 `dojo/` 目录、第二 EventBus、替换整个 coordinator、依赖 `dojoagents`/`strands`/`dojosdk`、Vite 第二前端、PortfolioSnapshot 类「空中造仓」、改超时默认除非 Comdr 另批。

### 6.5 回滚

- 闸门：去掉 `request_approval` 调用即恢复「直出决策」。  
- 前端：卸确认卡组件不影响只读 timeline。  
- 护栏：env 关闭或退订 before/after hook。  
- 事件 alias：退订新 type 即可。

### 6.6 验收铁证（Sprint1 预告，非本批执行）

- **P0-5**：人为 high → pending API 非空 + UI 确认卡 + approve/reject 改状态；`timeout_auto` 徽标 ≠「已批准」。  
- **P0-1**：同签名工具 ≥N 次 → block/halt，日志 correlation_id。  
- 禁假数 / 伪重启（铁律 #1/#2/#3）。

---

## 7. 关键只读路径索引

| 主题 | 绝对路径 |
|------|----------|
| 设计主文 | `/Users/panda/Downloads/StockAnal_Sys/docs/design/dojo-agents-absorption-plan.md` |
| 本盘点 | `/Users/panda/Downloads/StockAnal_Sys/docs/design/sprint0-inventory.md` |
| HITL | `/Users/panda/Downloads/StockAnal_Sys/app/agents/hitl.py` |
| EventBus | `/Users/panda/Downloads/StockAnal_Sys/app/core/event_bus.py` |
| Coordinator / progress | `/Users/panda/Downloads/StockAnal_Sys/app/agents/coordinator.py` |
| Risk | `/Users/panda/Downloads/StockAnal_Sys/app/agents/risk_manager.py` |
| Decision | `/Users/panda/Downloads/StockAnal_Sys/app/agents/decision_maker.py` |
| State | `/Users/panda/Downloads/StockAnal_Sys/app/agents/state.py` |
| 审批路由 | `/Users/panda/Downloads/StockAnal_Sys/app/web/web_server.py`（`/api/agent_pending_approvals`、`/api/agent_submit_approval`、progress 订阅） |
| Schema | `/Users/panda/Downloads/StockAnal_Sys/app/web/schema.py` |
| 工具事件 | `/Users/panda/Downloads/StockAnal_Sys/app/core/ai_client.py` |
| 侧栏 | `/Users/panda/Downloads/StockAnal_Sys/frontend/src/components/agent/agent-side-panel.tsx` |
| SSE hook | `/Users/panda/Downloads/StockAnal_Sys/frontend/src/lib/hooks/use-chat-stream.ts` |
| Agent store | `/Users/panda/Downloads/StockAnal_Sys/frontend/src/lib/stores/agent-store.ts` |

---

## 8. 变更记录

| 时间 | 说明 |
|------|------|
| 2026-07-23 15:33:50 +08:00 | Sprint0 初版落盘；只读证据；无业务代码 |

## P0-5 HITL 确认面进度（2026-07-23 23:00 +08:00）

**状态：完成**

| 项 | 落点 | 说明 |
|---|---|---|
| 后端闸门 | `app/agents/coordinator.py` + `app/agents/hitl.py` | `should_request_hitl` 后 `request_approval`；高风险超时 `timeout_reject` |
| 事件 | `event_bus` `approval.needed` / alias `approval_needed` | payload.event_type=`approval_needed`；SSE info 转发可读 |
| pending/submit API | `web_server.py` | GET 返回 approvals+count；POST 改状态；钩子写 `awaiting_approval` |
| 前端确认卡 | `approval-card.tsx` + `pending-approvals.tsx` | `agent-side-panel` 挂载；3s 轮询 |
| 契约 | 禁止静默通过高风险 | approve/reject/timeout_reject 均显式；timeout_auto 仅非高风险防御分支 |

验收：单测 `tests/backend/unit/test_hitl_gate.py`；前端 tsc 聚焦改动文件。

---

## 8. Sprint1 实现进度补记（2026-07-23）

### Sprint1 任务编号 P0-3 辩论证据面 + P0-4 工具时间线（= 设计 P0-6 / P0-4 工具侧）

| 项 | 状态 | 证据 |
|----|------|------|
| bull/bear/debate_summary 进 state | 既有 + 强化 | `coordinator._summarize_debate` 写 `debate_summary` |
| `agent.debate_turn` 事件 | DONE | EVENT_AGENT_DEBATE_TURN；bull/bear/summary 三轮 |
| 前端双栏/分歧扫读 | DONE | `debate-card.tsx` + `agent-side-panel` strip + artifact SSE |
| `agent.tool_call`/`agent.tool_result` 字段 | DONE | name/args_digest/ok/error/duration_ms/source |
| 前端 timeline 契约消费 | DONE | tool-call-card / use-chat-stream / types |

回滚：还原 `ai_client` publish helpers、`_summarize_debate` 事件、`web_server` debate_card 发射与前端 debate 相关组件/类型。

