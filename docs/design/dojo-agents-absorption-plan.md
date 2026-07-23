# DojoAgents → StockAnal_Sys「吸收·合并·融化」设计方案

```
Input: Comdr 战略意图 — 吸收 Alpha-Dojo/DojoAgents 的机制精华；以 AI 原生产品形态融化进 StockAnal_Sys；严禁脚手架式照搬与功能清单堆砌
Output: 可审批的完整设计（第一性原理 / 未问关键题 / 因果机制 / AI 原生形态 / 能力画像 / 差距 / P0-P2 融化切片 / 超越 / Sprint0-4 / 硬口令 / 证据 / 审批栏）
Pos: docs/design/dojo-agents-absorption-plan.md — 设计层唯一入口；审批通过前禁止编码实施
```

| 字段 | 值 |
|------|-----|
| **文档状态** | **已通过 2026-07-23 Comdr 全权托管**；**Sprint0–3 本地可使用交付冲刺（2026-07-24 01:18 +08:00）** |
| **版本** | `v1.2`（Sprint0–3 收口 + DELIVERY-STATUS） |
| **日期锚点** | `2026-07-23` 设计日；交付锚点 `2026-07-24 01:18:57 +08:00` |
| **工作目录** | `/Users/panda/Downloads/StockAnal_Sys` |
| **对照对象** | [Alpha-Dojo/DojoAgents](https://github.com/Alpha-Dojo/DojoAgents)（Apache-2.0，PyPI `dojoagents`≈0.1.9） |
| **本仓宿主** | Flask:8888 + Next:3000 + LangGraph multi-agent + adapters/Wind + Chat/Artifacts |
| **战略对齐** | `docs/AI_NATIVE_RESEARCH.md`（Chat 为主、Artifacts 为工位、过程透明、用户保持控制） |
| **授权边界** | 全文设计已批；Comdr 已授权无人托管实现至 Sprint3 交付冲刺；仍 **禁 push（默认）** |
| **Sprint0 证据** | `/Users/panda/Downloads/StockAnal_Sys/docs/design/sprint0-inventory.md` |
| **交付清单** | `/Users/panda/Downloads/StockAnal_Sys/docs/design/DELIVERY-STATUS.md` |

---

## 0. 审批栏（强制）

| 项 | 内容 |
|----|------|
| **状态** | **已通过 2026-07-23 Comdr 全权托管** |
| **审批人** | Comdr |
| **审批时间** | **2026-07-23**（全文批准；以本 MD 为准，非早期竞品摘要 PortfolioSnapshot-P0） |
| **通过条件** | ① 同意「AI 原生：Agent 一等公民，UI=证据面+确认面」 ② 同意「融化非照抄 / 不引入 dojoagents 运行时」 ③ 锁定 P0 最小切片 ④ Sprint0 仅只读/契约，不写业务代码 |
| **否决/修改权** | Comdr 可整体否决、改优先级、砍 Sprint、改熔断与 HITL 默认策略 |
| **生效后准入** | Sprint 0 **已执行**；仍禁止 push；**业务编码**须另批「可进 Sprint1」 |
| **本轮绝对禁止** | `pip install dojoagents/strands-agents/dojosdk` 进主依赖；新建第二 HTTP 主入口；Vite 第二前端；替换 `coordinator.py` 主图；复制 Dojo monorepo；用假数 Demo Agent |
| **Sprint0 进度** | **完成**（2026-07-23 15:33:50 +08:00）：事件 payload / terminal 态 / HITL 断点 / 风险分级 → `docs/design/sprint0-inventory.md` |
| **Sprint1–3 进度** | **本地已落地**（详见 §11 状态表 + `DELIVERY-STATUS.md`）；P0-7 降级帽与部分 P1 仍未闭合 |
| **下一步闸门** | 交付冲刺后：P0-7 / 写工具硬拦增强 / P1 Skills·Plan；默认仍 **禁 push** |

> **铁律**：设计全文已批；实现按 Comdr 全权托管 + 分 Sprint 授权推进。伪修复（无铁证三件套）= 任务失败。

---

## 1. 设计立场：彻底摒弃传统开发思维

### 1.1 我们拒绝什么

| 传统思维（禁止） | 为什么在本任务失效 |
|------------------|-------------------|
| **功能清单 / 对标抄作业** | 「Dojo 有 X，我们也加一个 X 页面/模块」只产生平行壳，不改变决策质量与可审计性 |
| **模块堆砌** | 多一个 `skills/` 目录或 dashboard SPA，不等于 Agent 回路更可信；复杂度上升、记忆分裂 |
| **以 UI 为业务中心** | 表单 CRUD、菜单点点点，把 Agent 降级成后台批处理；与 AI 原生金融产品相反 |
| **先堆架构抽象再找问题** | 微服务 / 第二 runtime / 新消息中间件无法回答「用户为何信任这一次 BUY 研究结论」 |
| **Demo 导向假数据** | 金融场景假绿勾 = 产品伦理事故（铁律 #1） |

### 1.2 我们坚持什么（AI 原生产品）

1. **Agent run 是一等公民**；页面是投影。  
2. **UI = 证据面 + 确认面 + 结论面**，不是控制台皮肤。  
3. **控制流**：用户表达意图 → Agent 在工具/角色/护栏中编排 → 仅在高代价节点 HITL。  
4. **扩展方式**：新工具、新事件契约、新 Artifact 类型、新 Skill 剧本 —— **不是**新网站。  
5. **竞争力锚**：过程可信、决策可解释、降级不撒谎、风控可确认 —— **不是**「指标更全的 Dashboard」。

### 1.3 一句话命题

**把 DojoAgents 的 Loop 工程学（护栏、意图-工具路由、组合 harness、Skills、Plan DAG、provenance、可观测轨迹）与「多角色对抗/可回放」机制，融化进 StockAnal 既有 LangGraph 编排与 Chat+Artifacts —— 不新建第二套 Agent 主题乐园。**

「吸收」≠ 依赖上游包。  
「合并」= 职责进现有 `tools` / `coordinator` / EventBus / stores。  
「融化」= 用本仓惯用栈 **重写语义**，类名与路径用 StockAnal 词汇。

---

## 2. 第一性原理

### 2.1 真正要解决的问题（非「对齐竞品功能表」）

个人投资者需要的是一套 **可信的决策外骨骼**：

1. 问题与 **我的仓/关注面** 绑定，而非悬浮标的百科。  
2. 多步工具调用 **可展开审计**（谁调了什么、数据从哪来、是否降级）。  
3. 跨市场与新闻冲击有 **可复现因果链**，而非模型散文。  
4. 离开页面后仍有 **受控的主动伴生**（定时简报），且不烧穿配额。  
5. 会改变状态的写操作必须 **护栏 + HITL**，分析意图不得静默建仓。

### 2.2 本仓不可冲毁的地基

| 原则 | 锚点 |
|------|------|
| 铁律 #1 金融数据零假值 | Skeleton / 「—」以外禁止假行情 |
| 铁律 #2 禁用 Playwright | 真测 CDP / WebBridge |
| 铁律 #3 worker 资源策略 | 禁全量 vitest/砸内存启服 |
| 铁律 #4 schema 演进 | `PRAGMA user_version` |
| Adapter 降级链 + Wind 省积分 | `adapter_registry` / `wind_budget` |
| 每请求独立 LangGraph | 防 #7845 跨会话污染 |
| OpenAPI + schema + `api_error` | 契约稳定性 |

### 2.3 宿主边界（逻辑拓扑，非新仓库）

```
用户意图 (Chat / 微信 MCP)
        │
        ▼
  Flask web_server  ←── 唯一业务 HTTP 主入口
        │
        ▼
  LangGraph coordinator  ←── 编排主脑（保留）
        │
   ┌────┴────────────────────────────┐
   │  融化进回路的能力（非平行产品）    │
   │  Guardrail · Tool Protocol       │
   │  Portfolio harness · Skills      │
   │  Plan DAG · Provenance · Memory  │
   │  辩论/评分卡/HITL/EventBus        │
   └────┬────────────────────────────┘
        │ 证据流 (EventBus + Artifacts)
        ▼
  UI：证据面 · 确认面 · 结论面（Next）
        │
        ▼
  真相源：checkpoint(thread_id) + 合规任务投影
```

---

## 3. 【未问但更关键的问题】

若跳过本节直接列 API，方案必沦为功能堆砌。下列问题才是决策核（默认答案待 Comdr 批注可改）。

### 3.1 产品 / 信任

| # | 未问的问题 | 若不答的后果 | 本方案默认 |
|---|------------|--------------|------------|
| Q1 | 用户买的是「答案」还是「可审计的决策过程」？ | 聊天壳 vs 研究工作站分叉 | **过程 + 结论** 双交付；Artifact 与 reasoning 同级 |
| Q2 | 失败时闭嘴还是展示失败因果？ | 假绿勾 / 静默降级 | **展示失败因果**；禁止假数填洞 |
| Q3 | 谁拥有最终动作权？ | HITL 虚设或处处弹窗 | 低风险自动 / 高风险 **阻塞确认** |
| Q4 | 一次分析的「完成」定义？ | 进度永远 99% | `final_decision` + 关键 Artifact + 审批终态（若需） |
| Q5 | 多 Agent 冲突展示多数决还是显式对抗？ | 鸡汤掩盖分歧 | **显式对抗面** + 分歧结构化 |
| Q6 | 「持仓上下文」从哪来才不算空中造仓？ | Agent 幻觉组合 | **本仓 portfolio/watchlist 真源** + 读工具；截图仅草案+HITL |

### 3.2 系统 / 回路

| # | 未问的问题 | 本方案默认 |
|---|------------|------------|
| Q7 | 外部 Dojo「训练回合」在生产研究中对应什么？ | **单次 research run**；offline arena 仅 P2，不进热路径 |
| Q8 | 状态真相源？ | **SqliteSaver thread_id=conversation_id**；前端为投影 |
| Q9 | 工具失败是 Agent 失败还是数据降级？ | 降级进 `degradation` + **confidence 上界**；UI 标 DEGRADED |
| Q10 | 同签名工具死循环谁负责停？ | **Tool Guardrail** 进回路（融化 Dojo 护栏机制） |
| Q11 | 分析意图能否调用写仓工具？ | **否**——协议 + 服务端二次拒绝（Harness） |
| Q12 | EventBus 是糖还是契约？ | **一等契约**；无事件的「黑盒跑完」= 不合格 |
| Q13 | 旧 TradingAgents 双轨？ | P0 **只强化 LangGraph 路径**；旧路径只读兼容 |

### 3.3 合规 / 金融伦理

| # | 未问的问题 | 本方案默认 |
|---|------------|------------|
| Q14 | 是否可被理解为投资建议？ | 决策 Artifact **强制免责声明**；action=研究结论非下单 |
| Q15 | mock 股价演示 Agent？ | **否**（铁律 #1） |
| Q16 | 反思能否自动改生产评分权重？ | P0 **只记录**；演进变更需人审 merge |
| Q17 | Wind 积分与护栏关系？ | block/halt **不得**再触发 try_consume；配额感知路由 |

---

## 4. 【因果机制：从数据到决策】

融化对象是 **因果**，不是目录树。禁止用空洞分层（「表现层/领域层/基础设施层」堆砌）代替机制。

### 4.1 主因果链（一次可信 run）

```
用户意图
  → Intent 归类（分析 / 筛选 / 读仓 / 拟写仓 / 市场全景 / 新闻冲击）
  → Tool Protocol 裁剪「允许工具面」（防意图漂移）
  → LangGraph 角色编排（analyst fan-out → 对抗 → risk → decision）
  → 每次工具调用：
        Guardrail.before → Adapter/Wind 真源拉取 → 结果 Truth 标记(source/cache/degraded)
        → Guardrail.after（同签名失败计数 / no-progress）
        → EventBus 发 tool 证据 → 可选 provenance 追加
  → 数据残缺 → degradation↑ → confidence_cap↓（禁止用 0 或假行情补洞）
  → 多空对抗暴露单角色偏见 → disagreement 结构化
  → final_decision + scorecard
  → 若高代价：HITL 确认面阻塞 → 人因进入因果（approve/reject/modify）
  → checkpoint 落盘（可回放）
  → UI 三面同时更新（证据 / 确认 / 结论）
```

### 4.2 子因果：真 / 假数据如何改变置信度

| 触发 | 数据状态如何变 | 决策置信度如何变 | 用户必须看见 |
|------|----------------|------------------|--------------|
| adapter 超时 | `degraded` / 空结果合法 | confidence **硬帽**下调 | 横幅 + 时间线错误节点 |
| 缓存命中 | `cache_hit=true` + 时戳 | 略降或中性（视 TTL） | provenance 标注 |
| Wind 配额耗尽 | 自动 fallback 链 | 帽取决于 fallback 质量 | 「省积分路径」提示 |
| 同签名工具连败 | Guardrail block/halt | run 可中止或降级完成 | reasoning「护栏中止」 |
| bull/bear 高分歧 | disagreement.severity 高 | 默认升风险档 / 促 HITL | 辩论 Artifact |
| 用户拒绝审批 | approval=rejected | 不得当作用户同意执行 | 确认面终态 |

### 4.3 Dojo 有效机制 → 本仓锚点（机制表）

| 机制 | 因果（Why it works） | 融化锚点 | 绝不照搬 |
|------|----------------------|----------|----------|
| Role specialization | 窄职责降幻觉混合 | 既有 technical/fundamental/… | 不新建平行品牌 Agent 树 |
| Adversarial debate | 对立目标逼证据竞争 | bull/bear + debate 状态 | 不引外部辩论框架包 |
| Agent Loop 护栏 | 阻断无效工具燃烧 | 新建本仓 `tool_guardrails` 挂 tools/FC | 不 copy `dojoagents.agent.guardrails` |
| Intent-tool protocol | 防分析轮误写 | `STOCKANAL_TOOL_PROTOCOL` + 服务端校验 | 不抄 `dojo.v2` 事件名 |
| Portfolio harness | 读写工具面隔离 | 读工具 P0 / 写+HITL P1 | 不照搬类层次 |
| Skills | 可分发可复用剧本 | `data/skills` + loader 注入回路 | 不建成第二产品站 |
| Plan DAG | 复杂任务可依赖调度 | 轻量 plan store；与 graph 分工 | 不替换 LangGraph |
| Provenance 原语 | 反幻觉审计 | Artifact/结果 `provenance[]` | 不引 dojosdk 类型包 |
| Observable trace | 信任来自中间态 | EventBus + timeline + side-panel | 不黑盒只吐终句 |
| HITL on costly nodes | 人放在期望损失最大处 | `hitl.py` + 确认面一等 UI | 不每步弹窗疲劳 |
| Checkpoint/replay | 可复现、可分叉 | SqliteSaver + conversation_id | 不另起 session 库 |
| Reflection | 方法可进化 | reflection / evolver → 人审 skill | P0 不自改生产权重 |
| Memory prefetch | 上下文自带仓与史 | 扩展 `agent_memory` | 不默认云端记忆黑盒 |
| Cron/Gateway | 主动伴生 | NotificationSink + 微信优先 | 不全量上齐全渠道 |
| Eval gym | 策略可回归 | P2 offline only | 不在线训练烧配额 |

### 4.4 反因果（照抄致死）

| 照抄 | 致死因果 | 对策 |
|------|----------|------|
| 整包 `dojoagents` + strands | 双 runtime、与 LangGraph 冲突 | 语义重写 |
| FastAPI:8765 + Vite SPA | 入口分裂、鉴权双轨 | 只强化 8888/3000 |
| 训练 while-true HTTP | OOM、烧积分（铁律 #3） | 单次 run + 硬超时 |
| mock 行情撑 Demo | 铁律 #1 事故 | Skeleton/DEGRADED |
| 每概念一个微服务 | 运维面爆炸 | 全进 Flask 回路 |
| 开放任意 terminal | 安全不可控 | 默认不吸收 |

---

## 5. 【AI 原生产品形态定义】

### 5.1 四层回路（全部是「Agent 回路零件」，不是「菜单模块」）

| 层 | 定义 | 本仓落点 |
|----|------|----------|
| **A. Agent 编排** | 意图→角色/计划→终态 | `coordinator` +（融化）Plan/Protocol |
| **B. 工具面** | 世界接口；唯一数据入口 | `tools.py` + adapters +（融化）读仓/市场 facade |
| **C. 证据信封** | 工具结果、provenance、辩论、降级、scorecard 的可传输结构 | EventBus payload + Artifacts |
| **D. 人机确认环** | 高代价动作的阻塞、标注、回写 | `hitl` + 确认面 UI + 审批 API |

### 5.2 三面 UI（UI 不是业务中心）

| 面 | 职责 | 非职责 |
|----|------|--------|
| **证据面** | 工具时间线、数据血统、多空分歧、降级原因 | 替用户填表完成业务 |
| **确认面** | 审批/拒绝/修改、超时语义显式 | 藏在设置页的隐蔽开关 |
| **结论面** | decision memo、免责声明、可执行研究结论 | 伪装成券商下单键 |

### 5.3 与 a16z / 本仓 AI-Native 调研对齐

- 从聊天到 **可观察行动**（工具与状态变更可见）。  
- 提示框是入口不是产品全部：行为理解 = Protocol + 持仓上下文 + Skill。  
- 金融标杆路径：对话为主、图表为辅（`docs/AI_NATIVE_RESEARCH.md`）。  
- Generative UI：优先 **声明式 Artifact JSON** 映射既有组件，不开放任意 HTML。

---

## 6. 【传统思维 vs AI 原生】对照表

| 维度 | 旧做法（传统） | 为何失效 | 新做法（AI 原生·本方案） |
|------|----------------|----------|--------------------------|
| 一等公民 | 页面 / CRUD | Agent 变成批处理黑盒 | **Agent run + 证据流** |
| 需求描述 | 「加 portfolio 页字段」 | 与决策质量无关 | 「分析意图如何安全接触真仓」 |
| 对齐竞品 | 抄四看板 SPA | 双前端、维护税 | 融化 Loop 机制进既有 Chat 工位 |
| 控制流 | 用户逐步点菜单 | 认知负担、易漏证 | 意图驱动编排 + 闸门介入 |
| 失败 | toast / 500 | 金融用户被误导 | 结构化 degradation + confidence 帽 |
| 状态 | 前后端各说各话 | 刷新丢、双写 | checkpoint 真相源 + 投影 |
| 扩展 | 新页面/新服务 | 范围爆炸 | 新工具/事件/Artifact/Skill |
| 写操作 | 表单直接落库 | Agent 误写灾难 | Harness + HITL + 提案态 |
| 测试 | 只测状态码 | 伪绿 | 轨迹可复现 + 零假数 + 闸门 |
| 成功指标 | 功能点数 | 不可信繁荣 | 可指出证据路径、高风险零无确认通过 |

---

## 7. DojoAgents 能力画像（具体竞品）

> 证据包：2026-07-23 上游 README/AGENTS/架构 docs + 本地 `/tmp/dojo_*` 摘录。画像用于融化，不用于抄目录。

### 7.1 产品叙事能力

| 能力域 | Dojo 表现 | 观察成熟度 |
|--------|-----------|------------|
| 定位 | 个人全市场 AI；强调 Loop 引擎 | 高 |
| 每日市场全景 | 多工具、步骤可展开 | 中高 |
| 突发新闻影响 | 拆题→交叉工具 | 中高 |
| 持仓截图诊断 | 多模态→行业/风险 | 中 |
| 模拟组合 | 诊断后建仓跟踪 | 中高 |
| 四看板 | Portfolio/Markets/Sectors/Equities | 高 |
| 多渠道/Cron | Gateway + APScheduler | 中 |

### 7.2 Loop 工程能力（高价值融化源）

| 能力域 | 上游要点 | 融化优先级 |
|--------|----------|------------|
| Agent Loop | 模型↔工具↔结果↔终答 | 机制对照；主脑仍用 LangGraph |
| Guardrails | 同签名失败 warn/block、同工具 halt、no-progress、危险命令 block | **P0** |
| Dashboard tool protocol | 按意图固定工具路由/禁止写 | **P0** |
| Portfolio harness | 分析 vs 突变工具隔离 | **P0 读 / P1 写** |
| Skills | MD+frontmatter、required tools | **P1** |
| Planning | PlanStep depends_on、死锁保护 | **P1** |
| Memory | prefetch / sync_turn / providers | **P1** |
| Provenance 原语 | AnalysisResult + DataSourceRef | **P0–P1** |
| Token/上下文压缩 | ledger + policy | **P1–P2** |
| Multi-agent pool | delegate_task 等 | ≈ 本仓已有辩论图，慎叠 |
| Sandbox/terminal | 代码执行 | **默认不吸收** |
| dojosdk 数据面 | 官方网关 | **不替换 adapters** |
| FastAPI+SSE dojo.v2 | 独立 dashboard API | **不照搬** |
| 插件 hooks | Claude plugin 形态 | P2 可选挂 EventBus |

### 7.3 技术栈（异构 → 默认不融化栈）

Python≥3.11 · FastAPI · strands-agents · React+Vite · APScheduler · uv —— 与本仓 Flask/LangGraph/Next **异构**。**融化语义，不融化栈。**

---

## 8. StockAnal_Sys 基线与差距矩阵

### 8.1 宿主优势（已有回路零件）

| 域 | 锚点 |
|----|------|
| LangGraph 多角色+决策 | `app/agents/*` |
| HITL + EventBus | `hitl.py` / `event_bus.py` |
| 工具 + FC | `tools.py` / `ai_client.py` |
| 适配器/Wind | `adapters/*` / `wind_*` |
| 记忆/会话/checkpoint | `agent_memory.py` / SqliteSaver |
| Chat+Artifacts+SSE | `frontend/src/components/**` |
| portfolio/watchlist store | zustand + 后端 API（需工具化） |
| 工程纪律与测试基线 | CLAUDE 铁律 + pytest 规模 |

### 8.2 差距矩阵

图例：**Gap-D**=Dojo 更强待融化 · **≈**=各有千秋 · **S**=本仓更强  

| 维度 | 差距 | 融化策略（进回路，非加模块名） | 优先级 |
|------|------|--------------------------------|--------|
| 工具失败护栏 | Gap-D | Guardrail 挂 FC/tools 前后 | P0 |
| 意图-工具协议 | Gap-D | Protocol 注入 + 服务端拒绝 | P0 |
| 真仓可读 | Gap-D | portfolio 读工具进 Agent 上下文 | P0 |
| 证据/provenance | Gap-D | 证据信封字段统一 | P0 |
| 确认面产品级 | Gap-D/体验 | HITL UI 一等公民 | P0 |
| 辩论结构化 | ≈ 偏文本 | 对抗 Artifact | P0 |
| 完成态契约 | 弱 | terminal 态枚举 | P0 |
| Skills | Gap-D | skill 注入 system/tool | P1 |
| Plan DAG | Gap-D | 业务 DAG 与 graph 分工 | P1 |
| 写仓+Harness | Gap-D | 提案态+HITL | P1 |
| 市场 facade | ≈ | 统一工具语义，源仍 adapters | P1 |
| Memory 会话摘要 | Gap-D | 扩展 agent_memory | P1 |
| 上下文压缩 | Gap-D | 轨迹摘要/指针 | P1–P2 |
| 截图识仓 | Gap-D | 草案+HITL | P2 |
| Cron/通知 | Gap-D | Sink+微信优先 | P2 |
| 四看板 SPA | 不追求 | 增强既有页可选 | P2 |
| 数据真源/合规 | **S** | 贯穿验收 | — |
| API 鉴权文档 | **S** | 新能力必须挂契约 | — |

---

## 9. P0 / P1 / P2 吸收清单（能力融化进 Agent 回路）

> 每项七段：**锚点→缺口→融化→契约→验收→超越→风险**。  
> 表述强制为「回路能力」，禁止理解为「再开一个子系统 repo」。

### 9.1 P0 — 信任与回路最小闭合

#### P0-1 工具调用护栏（进 Loop） ✅ 完成（2026-07-23）

| 段 | 内容 |
|----|------|
| 锚点 | Dojo `ToolCallGuardrailController` |
| 缺口 | 同签名死循环烧 LLM/Wind |
| 融化 | `app/core/tool_guardrails.py`（重写）：before/after 挂 `tools.execute_tool` 与 `chat_with_tools`/`chat_with_tools_stream`（/api/ai/chat） |
| 契约 | allow\|warn\|block\|halt；env：`TOOL_GUARD_EXACT_FAIL_WARN/BLOCK`、`TOOL_GUARD_SAME_TOOL_WARN/HALT`；correlation_id 日志；block 结果 `data=null` 无假数 |
| 验收 | `tests/backend/unit/test_tool_guardrails.py` **11 passed**（mock 连续失败触发 block） |
| 超越 | block 不进底层（不烧 Wind）；artifact 路径对 block/halt 不包装结构化假 Artifact |
| 风险 | 过严误杀 → env 调高阈值；无 ContextVar 时旁路直调保持兼容 |
| 进度 | **DONE** commit 见 `feat(agent): P0-1 tool call guardrail against failure storms` |

#### P0-2 意图-工具协议 + 服务端二次校验 — **Sprint2 部分 DONE（规则意图路由，2026-07-23）**

| 段 | 内容 |
|----|------|
| 锚点 | Dojo `DASHBOARD_TOOL_PROTOCOL` |
| 缺口 | 自由 FC 意图漂移 |
| 融化 | **Sprint2 落地**：`app/core/intent_router.py` 规则分类（`single_stock_deep` / `portfolio` / `cross_market_event` / `market_overview` / `general`）；`/api/ai/chat` SSE `event:meta` + system_hint；analyze 拒绝 mutate 仍属后续加强 |
| 契约 | intent 枚举 + confidence/reasons/stock_codes；`router=rules_v1`；无假行情数 |
| 验收 | `tests/backend/unit/test_sprint2_intent_portfolio.py` 意图规则用例 |
| 超越 | intent 写入 done.payload；前端 chat-panel intent badge |
| 风险 | 规则假阳性 → 后续可 LLM 辅助但不依赖联网 |
| 进度 | **Sprint2 A 已落地**；完整 `STOCKANAL_TOOL_PROTOCOL` 写工具硬拦仍可增强 |

#### P0-3 持仓读入回路（反空中造仓） — **Sprint2 DONE（2026-07-23）**

| 段 | 内容 |
|----|------|
| 锚点 | Dojo portfolio_read_* |
| 缺口 | ~~Agent 难稳定读真仓~~ |
| 融化 | `get_portfolio_snapshot` / `get_portfolio_risk_summary`（`tools.py`）；chat body `portfolio_snapshot` → ContextVar；前端 portfolio-store 发送时注入 |
| 契约 | `{holdings, source, as_of}`；空仓 `holdings=[]`；name===code 置空串（铁律 #1） |
| 验收 | 单测空仓/有仓/scrub name；schema 接受 optional snapshot |
| 超越 | portfolio 意图自动注入 system 摘要 + 工具可复核 |
| 风险 | 隐私/鉴权 → 仍走现有 AUTH；未建新 DB |
| 进度 | **Sprint2 B+C+D 已落地** |

#### P0-4 证据信封：provenance + 工具时间线契约 — **工具时间线 DONE（2026-07-23 Sprint1 / 任务编号 P0-4）**

| 段 | 内容 |
|----|------|
| 锚点 | Dojo AnalysisResult/DataSourceRef；本仓 timeline |
| 缺口 | ~~工具事件字段不统一~~（时间线已规范）；provenance[] 仍待补 |
| 融化 | 规范化 `agent.tool_call` / `agent.tool_result`（映射 `tool.call.*` + wire `tool_call_*`） |
| 契约 | name / args_digest / ok / error / duration_ms / source；兼容 tool_name/arguments/result |
| 验收 | timeline 卡片只消费契约字段；digest 稳定；失败 ok=false |
| 超越 | Artifact「数据血统」折叠（provenance 后续） |
| 风险 | 字段膨胀 → 默认摘要 |
| 交付 | `ai_client` payload helpers + 双主题 publish；前端 tool-call-card/timeline/types |

#### P0-5 确认面一等公民（HITL 产品闭合） — **DONE（2026-07-23）**

| 段 | 内容 |
|----|------|
| 锚点 | Dojo 高代价人机；本仓 `hitl.py`+API |
| 缺口 | ~~主对话确认体验弱~~ 已闭合 |
| 融化 | 审批卡挂 `agent-side-panel`；`request_approval` 阻塞；任务态 `awaiting_approval`；事件 `approval.needed`/`approval.resolved` |
| 契约 | pending/approved/rejected/timeout_reject；高风险禁止静默通过；timeout_auto 仅非高风险防御分支 |
| 验收 | 高风险 → request_approval；GET/POST pending API；侧栏确认卡 3s 轮询；超时 timeout_reject |
| 超越 | 与 scorecard/分歧 severity 联动自动升档（后续） |
| 风险 | 超时策略已锁定高风险 timeout_reject |
| 交付 | hitl/coordinator/web_server/event_bus；approval-card/pending-approvals；test_hitl_gate + test_hitl |

#### P0-6 辩论证据面 + 完成态 — **证据面 DONE（2026-07-23 Sprint1 / 任务编号 P0-3）**

| 段 | 内容 |
|----|------|
| 锚点 | Dojo 可观察对抗；本仓 bull/bear |
| 缺口 | ~~长文本难扫读~~；terminal 完成态仍待统一 |
| 融化 | `agent.debate_turn` 事件 + `debate_card` 双栏 Artifact + side-panel 分歧条 |
| 契约 | side=bull\|bear\|summary；thesis/confidence/divergence_points；state 仍写 debate_summary |
| 验收 | 不读长文可扫到分歧点；bull/bear/summary 三轮可观测 |
| 超越 | 分歧点链接 tool 证据 id |
| 风险 | 信息过载 → 默认双栏折叠摘要 |
| 交付 | coordinator `_summarize_debate`；web_server debate_card；DebateCardArtifact |

#### P0-7 降级可视化与 confidence 帽（零假值回路）

| 段 | 内容 |
|----|------|
| 锚点 | 铁律 #1 + Dojo 反幻觉 |
| 缺口 | 降级时仍可能「像真」|
| 融化 | `agent.degraded` 事件 + UI 横幅 + confidence_cap |
| 契约 | causes[] 结构化；禁止 0 填假指标 |
| 验收 | 断网/超时场景无假行情 |
| 超越 | TruthGuard：mock 路径拦截 |
| 风险 | 过噪 → 聚合展示 |

**P0 非目标**：新 Agent 品牌、offline gym、自动改权重、Vite 看板、旧 TradingAgents 新功能、dojosdk。

---

### 9.2 P1 — 可编排、可复用、可回放

| ID | 能力融化 | 锚点 | 回路落点 | 验收要点 |
|----|----------|------|----------|----------|
| P1-1 | Skills 注入 | SkillManager | `data/skills` + loader；进 system/tool | 3 内置 skill 可跑通步骤 |
| P1-2 | Plan DAG | PlanExecutionEngine | SQLite plans；步进调 tools/agent | 死锁保护单测；两步依赖完成 |
| P1-3 | 写仓提案+Harness | portfolio_write+harness | 提案工具 + apply 需 approval_id | 无审批不落库 |
| P1-4 | 跨市场/板块 facade | market/sector 工具 | 统一工具名，源=adapters | 契约测 + 可选联网抽样 |
| P1-5 | Memory prefetch/摘要 | MemoryManager | 扩 `agent_memory` session 维 | 二轮引用前序结论 |
| P1-6 | 上下文压缩 | ContextCompressor | 工具结果指针化 + 保留数字表 | 超长轨迹可答 |
| P1-7 | 决策备忘 Artifact | 可解释终局 | action/否决/引用 evidence_index | 模板快照 |
| P1-8 | Run scorecard | 质量分解 | data_coverage/role_agreement/tool_success/confidence_cap | 低分默认升风险 |
| P1-9 | Checkpoint 只读回放 | replay | 默认不重跑付费工具 | UI 入口+标识 |
| P1-10 | 反思可读 | reflection | Artifact；不写生产权重 | 人可审 |

### 9.3 P2 — 伴生与选修（可砍）

| ID | 能力融化 | 说明 |
|----|----------|------|
| P2-1 | 截图→持仓草案 | 多模态；低置信强制 HITL；不自动入真仓 |
| P2-2 | NotificationSink | 微信 MCP 优先；统一 publish 接口 |
| P2-3 | Agent 定时任务注册表 | 盘后简报/异动；DISABLE_NETWORK 不启 |
| P2-4 | 前端指挥舱增强 | 仍在 Next，不新建 Vite |
| P2-5 | Offline arena | 历史标的批量对比策略版本 |
| P2-6 | evolver 受控合并 | PR 式 + 人工门；可导出 skill 草稿 |
| P2-7 | hooks 观察点 | EventBus 扩展；超时保护 |
| P2-8 | A2A | 独立契约层，不污染业务 OpenAPI |

---

## 10. 超越设计（≥5，相对 Dojo 默认路径）

| # | 超越点 | 为何我们能做到 | 验收 |
|---|--------|----------------|------|
| T1 | **辩论图 × 持仓 TopN 联合推演** | 已有 bull/bear/risk 子图 | 组合≥3 标的产出共识/冲突矩阵 Artifact |
| T2 | **Wind 配额感知工具调度** | `WindQuota`+熔断成熟 | 配额 0 不发付费 HTTP |
| T3 | **TruthGuard 零假值** | 铁律 #1 已是军规 | 假数夹具被拦截 |
| T4 | **合规夹注自动化** | 研究结论非下单 | 快照含免责+时间窗+来源 |
| T5 | **既有 15+ Artifact 成 Loop 展示标准** | 不造新图表栈 | 协议产物可映射或文本 fallback |
| T6 | **reflection/evolver → Skill 飞轮** | 方法资产化 | ≥1 条人审 skill 草稿 |
| T7 | **本地鉴权/隐私模型** | AUTH/CSRF/correlation | 安全回归不回退 |

---

## 11. 实施路线图 Sprint 0–4

> 全文设计已批（全权托管）；绝对时间锚点文档日 2026-07-23；交付冲刺锚点 2026-07-24 01:18 +08:00。默认禁 push。

### 11.0 Sprint 状态总表（2026-07-24 01:18 +08:00）

| Sprint | 主题 | 状态 | 关键 commit（短哈希） | 备注 |
|--------|------|------|----------------------|------|
| **Sprint 0** | 只读盘点与契约 | **DONE** | `7886bd5` | `sprint0-inventory.md` |
| **Sprint 1** | P0 回路闭合（护栏/HITL/辩论/时间线） | **DONE（主切片）** | `dd0fbc4` `fe1c08e` `0c244f9` `627a969` `7d78236` `fd077ae` | P0-7 未做；provenance 数组未完 |
| **Sprint 2** | 意图路由 + 真仓只读 | **DONE** | `f0d1289` | P0-2 规则路由；完整写工具硬拦可增强 |
| **Sprint 3** | 组合诊断 + 观察 mode | **DONE（本切片）** | `b612718` | Skills/Plan/Memory 仍属 P1 未启动 |
| **Sprint 4** | 写仓 harness + facade + P2 | **未开** | — | 待 Comdr |

### 11.1 P0 项 DONE 汇总

| ID | 能力 | 状态 | 代表 commit | 落点摘要 |
|----|------|------|-------------|----------|
| **P0-1** | 工具调用护栏 | **DONE** | `dd0fbc4` | `tool_guardrails.py` + execute_tool / FC stream |
| **P0-2** | 意图-工具协议 | **部分 DONE** | `f0d1289` | `intent_router.py` 规则路由 + SSE meta；写工具硬拦仍可增强 |
| **P0-3** | 持仓读入回路 | **DONE** | `f0d1289` | `get_portfolio_snapshot` / risk_summary；chat 注入 snapshot |
| **P0-4** | 工具时间线契约 | **DONE（timeline）** | `0c244f9` | tool_call/result 契约字段；provenance[] 仍待 |
| **P0-5** | HITL 确认面 | **DONE** | `fe1c08e` `627a969` | ApprovalCard / pending API / timeout_reject |
| **P0-6** | 辩论证据面 | **DONE（证据面）** | `0c244f9` | debate_card + 分歧条；terminal 完成态仍可统一 |
| **P0-7** | 降级帽 / confidence | **TODO** | — | `agent.degraded` + UI 横幅未闭合 |

配套已交付（非 P0 编号但支撑可使用）：

| 能力 | commit | 说明 |
|------|--------|------|
| Settings 顶栏入口 | `7d19e75` | 桌面/移动导航齿轮 |
| Wind 请求级开关 + 配额 API | `7cae626` | `/api/wind/quota`；设置页 Wind 区块 |
| Sprint3 组合诊断 + 观察 | `b612718` | `/portfolio` 诊断卡 + mode live\|watch |

完整启动/验证/回滚 → **`docs/design/DELIVERY-STATUS.md`**。

### Sprint 0 — 只读盘点与契约（零业务代码） ✅ DONE

- 事件 payload 文字 schema、terminal 态表、HITL 断点清单、风险分级差距 → **已落盘** `docs/design/sprint0-inventory.md`（2026-07-23 15:33:50 +08:00）。  
- 退出条件已满足；后续编码按托管推进。

### Sprint 1 — P0 回路闭合 ✅ 主切片 DONE

- **P0-1 工具护栏：DONE**（`dd0fbc4`）  
- **P0-5 HITL 确认面：DONE**（`fe1c08e`/`627a969`）  
- **P0-4 工具时间线 + P0-6 辩论证据面：DONE**（`0c244f9` 等）  
- **未闭合**：P0-7 降级帽；provenance[]；terminal 态统一。  
- 分批 pytest；CDP 真测；禁 Playwright/全量 vitest。

### Sprint 2 — 意图 + 真仓只读 ✅ DONE

- **P0-2 规则意图路由 + P0-3 持仓 snapshot 工具与 chat 注入**（`f0d1289`）。  
- 辩论 Artifact / decision memo / scorecard 深化仍可后续增强（部分在 Sprint1 已做证据面）。

### Sprint 3 — 组合诊断 + 观察 mode ✅ 本切片 DONE；P1 Skills 未开

- **组合风险诊断 + 观察标记（`b612718`）**：  
  - `risk_monitor.build_portfolio_diagnosis` + `analyze_portfolio_risk` 扩展字段（缺行业=`unknown`，禁止假行业）  
  - OpenAPI `/api/portfolio_risk`；`portfolio-store` `mode: live|watch`；`/portfolio` 诊断摘要  
- **未开**：P1-1 Skills / P1-2 Plan DAG / Memory / 压缩 / 回放。

### Sprint 4 — 写仓 harness + 市场 facade + P2 选修

- 仅当 P0/P1 稳定且 Comdr 明示；offline arena / Sink / 截图等可砍。

### 每 Sprint DoD

- [x] 绝对时间戳验证记录（交付冲刺节）  
- [x] 无假金融数据路径（铁律 #1 守卫保留）  
- [x] 可回滚 commit 粒度  
- [x] 本文件 / DELIVERY-STATUS 同步  
- [x] 能力描述是「回路」而非「新菜单」  
- [x] 未 push（默认）  


---

## 12. 不建议照搬清单

| # | 项 | 理由 | 本仓替代 |
|---|-----|------|----------|
| 1 | 依赖 dojoagents/strands/dojosdk | 双 runtime | 语义重写 |
| 2 | FastAPI dashboard :8765 | 入口分裂 | 8888/3000 |
| 3 | Vite 第二前端 | 重复 Next | 增强 frontend/ |
| 4 | `~/.dojo` 配置中心 | 与 .env 分裂 | 现有 env/settings |
| 5 | 默认 terminal/execute_code | 安全面 | 白名单指标可选 |
| 6 | Gateway 全渠道一次上齐 | 范围爆炸 | Sink+微信 |
| 7 | Dojo 仓规「禁 git」等 | 与本仓纪律冲突 | 遵 CLAUDE |
| 8 | dojosdk 替换数据面 | 破坏 adapters/Wind 铁证 | facade 挂现源 |
| 9 | 全盘 AtomicJsonl 换存 | 已有 SQLite/atomic_write | 新元数据优先 SQLite |
| 10 | 原样 copy harness 类树 | 不契 HITL/EventBus | 重写状态机 |
| 11 | `dojo.v2` 事件名 | 污染 SSE | 映射 EventBus |
| 12 | 新建 `dojo/` 运行时包 | 平行系统 | 能力进 `app/agents|core` |
| 13 | 在线 RL 改生产策略 | 不可审计 | scorecard+人审 |
| 14 | mock 行情 Demo | 铁律 #1 | 真源或 Skeleton |

---

## 13. 融化硬口令（给 worker）— `MELT-DOJO-2026-07-23`

1. 未获「可进 Sprint1」→ **禁止业务代码**（设计全文已批 ≠ 编码授权）。  
2. 禁止主依赖引入 `dojoagents` / `strands-agents` / `dojosdk`。  
3. 禁止整文件 copy Dojo 源码；只允许对照后的 **StockAnal 词汇重写**。  
4. 禁止第二 HTTP 用户主入口 / 第二前端工程。  
5. **Agent 一等公民**：改动必须说明如何改变「意图→工具→证据→确认→结论」因果，禁止只加死页面。  
6. 新工具/路由：schema + OpenAPI + 测试 + `api_error` + `now_cn()`。  
7. 铁律 #1–#4 全开；Wind 高频行情默认不进；block 不计配额。  
8. LangGraph **每请求独立 graph**，禁止进程级单例并发共享。  
9. analyze intent **服务端拒绝** mutate 工具；写操作必须 HITL/显式确认。  
10. 资源：pytest 分批；禁 Playwright；禁擅自 dev/build/run.py。  
11. 新建文件走特例审批标签；优先改现有文件。  
12. 完成必须铁证（命令、passed 数、授权真测路径）；禁止伪修复。  
13. 中文说明 + 绝对时间戳 +08:00；回滚列表写清。  
14. Sprint 结束更新 TODO/CHANGELOG/本文件状态。

---

## 14. 风险、回滚与熔断

| 风险 | 等级 | 缓解 | 回滚 |
|------|------|------|------|
| 事件洪水 | M | 节流聚合 | 退订新事件 |
| HITL 超时被误解为同意 | H | UI 显式 timeout 态；Comdr 定默认 | 旧 hitl 策略 |
| state/checkpoint 不兼容 | H | Optional 字段 | 停读新字段 |
| 假数 Demo | **Blocker** | 铁律 #1 | 立即回滚 |
| OOM | H | 铁律 #2/#3 | 停服清理 |
| 范围变重写 | H | 非目标清单 | 砍 Sprint |
| 引入上游包 | H | 硬口令#2 | 移出依赖 |

**全局熔断**：P0 验收出现假数 / 伪重启 / 无对比证据 → 整 Sprint 不计完成。

---

## 15. 成功度量（可复核）

| 指标 | P0 后目标 |
|------|-----------|
| 高风险决策无确认面通过 | **0** |
| 分析意图误触发写工具 | **0** |
| 同签名工具死循环超阈 | **0**（护栏） |
| 用户可点击到证据路径 | ≥1 跳 |
| 降级 run 无 confidence 帽 | **0** |
| 新平行 Agent 框架 | **0** |
| 假行情展示 | **0** |

---

## 16. 证据链接

### 16.1 外部 DojoAgents

| 证据 | 位置 |
|------|------|
| 主仓 | https://github.com/Alpha-Dojo/DojoAgents |
| README 产品能力 | 上游 README（中/英）：Loop、四看板、截图识仓、多市场 |
| AGENTS.md 工程心智 | 上游 AGENTS.md：目录、ToolExecutor、ConfigStore |
| 架构文档 | Agent Loop / Dashboard / Multi-agent·Plan / Plugins / Gateway |
| 依赖 | 上游 `pyproject.toml`（fastapi/strands/dojosdk/mcp/apscheduler…） |
| 本地摘录（worker 2026-07-23） | `/tmp/dojo_readme.md` `/tmp/dojo_readme_zh.md` `/tmp/dojo_agents_md.md` `/tmp/dojo_guardrails.py` `/tmp/dojo_loop_head.py` `/tmp/dojo_portfolio_harness.py` `/tmp/dojo_planning_engine.py` `/tmp/dojo_skills_mgr.py` `/tmp/dojo_memory_mgr.py` `/tmp/dojo_dashboard_tool_proto.py` `/tmp/dojo_arch_*.md` |

### 16.2 本仓

| 路径 | 角色 |
|------|------|
| `/Users/panda/Downloads/StockAnal_Sys/docs/design/dojo-agents-absorption-plan.md` | **本文** |
| `/Users/panda/Downloads/StockAnal_Sys/docs/AI_NATIVE_RESEARCH.md` | AI 原生战略 |
| `/Users/panda/Downloads/StockAnal_Sys/CLAUDE.md` | 铁律与交付史 |
| `/Users/panda/Downloads/StockAnal_Sys/app/agents/coordinator.py` | 编排主脑 |
| `/Users/panda/Downloads/StockAnal_Sys/app/agents/state.py` | 共享状态 |
| `/Users/panda/Downloads/StockAnal_Sys/app/agents/hitl.py` | HITL |
| `/Users/panda/Downloads/StockAnal_Sys/app/agents/reflection.py` / `strategy_evolver.py` | 反思/演进 |
| `/Users/panda/Downloads/StockAnal_Sys/app/core/tools.py` | 工具主点 |
| `/Users/panda/Downloads/StockAnal_Sys/app/core/agent_memory.py` | 记忆 |
| `/Users/panda/Downloads/StockAnal_Sys/app/core/event_bus.py` | 事件契约总线 |
| `/Users/panda/Downloads/StockAnal_Sys/app/core/wind_budget.py` | 配额 |
| `/Users/panda/Downloads/StockAnal_Sys/app/adapters/adapter_registry.py` | 降级链 |
| `/Users/panda/Downloads/StockAnal_Sys/app/web/web_server.py` | HTTP 宿主 |
| `/Users/panda/Downloads/StockAnal_Sys/frontend/src/lib/stores/portfolio-store.ts` | 持仓投影源 |
| `/Users/panda/Downloads/StockAnal_Sys/frontend/src/components/artifacts/` | 证据展示层 |

---

## 17. Comdr 决策问卷

请审批时明确：

1. P0 七条是否全做？砍哪些？  
2. HITL 超时默认：timeout_auto 通过，还是默认拒绝？  
3. Sprint1 是否授权启 8888/3000 真测？  
4. 旧 TradingAgents：冻结 / 限期删 / 双轨？  
5. scorecard 是否允许自动上调 risk_level？（推荐允许）  
6. 是否允许 Sprint4 之前启动写仓工具？（推荐 P1 且强 HITL）  
7. NotificationSink/微信伴生是否进入本季度范围？

批注方式：章节号 + 修改句；通过后状态改为 `approved-v1.x` 并署绝对时间。

---

## 18. 附录

### A. 建议 env（实施阶段）

`TOOL_GUARD_EXACT_FAIL_WARN/BLOCK` · `TOOL_GUARD_SAME_TOOL_HALT` · `STOCKANAL_TOOL_PROTOCOL_ENABLED` · `SKILLS_DIR` · `PLAN_MAX_STEPS` · `MEMORY_SESSION_TTL_H` · `MAX_TOOL_RESULT_CHARS`

### B. 证据信封草图（非上游源码）

```text
ToolGuardDecision { action, code, message, tool_name, count }
ProvenanceItem { source, adapter?, fetched_at, cache_hit?, note? }
Degradation { level, causes[] }
Disagreement { points[], severity }
Scorecard { data_coverage, role_agreement, tool_success_rate, confidence_cap }
PlanStep { id, title, depends_on[], status, result? }
SkillMeta { name, description, required_tools[], markets[], body_path }
```

### C. 术语

| 术语 | 含义 |
|------|------|
| DojoAgents | 具体上游项目 Alpha-Dojo/DojoAgents |
| Dojo 机制 | 护栏/协议/harness/skill/plan/对抗/回放等可融化因果 |
| 融化 | 机制进现有回路；禁止平行复制 |
| 证据面/确认面/结论面 | AI 原生 UI 三职责 |
| Scorecard | run 质量分解，不是股价预测分 |

### D. 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0-draft-for-approval | 2026-07-23 | 完整稿：AI 原生贯穿 + DojoAgents 具体能力融化 + P0–P2 + Sprint0–4；**待 Comdr 审批**；禁止编码 |
| v1.1 | 2026-07-23 | **已通过 2026-07-23 Comdr 全权托管**；Sprint0 只读盘点完成（`sprint0-inventory.md`）；实现编码仍须「可进 Sprint1」闸 |

### E. Sprint0 证据入口

| 交付 | 路径 |
|------|------|
| 事件 payload / terminal / HITL 断点 / 风险差距 | `/Users/panda/Downloads/StockAnal_Sys/docs/design/sprint0-inventory.md` |

---

## 19. 一页纸结论

1. **不是**加功能模块，**是**强化 Agent 回路：编排 · 工具 · 证据信封 · 人机确认。  
2. **吸收** DojoAgents 的 Loop 工程学与可观测对抗思想；**不吸收** FastAPI/Vite/strands/dojosdk 整栈。  
3. **宿主** = Flask + LangGraph + Next + adapters/Wind。  
4. **P0** = 护栏 + 协议硬拦 + 真仓只读 + 证据信封 + 确认面 + 辩论/完成态 + 降级帽。  
5. **超越** = 辩论×持仓、Wind 感知调度、TruthGuard、合规夹注、Artifacts 标准化、演进→skill。  
6. **现状** = **全权托管 + Sprint0–3 主切片本地可使用；P0-7 与多数 P1 未开；见 DELIVERY-STATUS。**

---

**— 全文完 · 全权托管 · Sprint0–3 主切片 DONE · v1.2 · 交付清单 DELIVERY-STATUS.md —**  
**绝对路径**：`/Users/panda/Downloads/StockAnal_Sys/docs/design/dojo-agents-absorption-plan.md`

### P0-5 HITL 确认面（2026-07-23）

状态：**完成**。闸门在 `coordinator` final_decision 后 `request_approval`；前端 `ApprovalCard`/`PendingApprovalsPanel` 挂 `agent-side-panel`；高风险超时 `timeout_reject`。详见 `sprint0-inventory.md` 末段。

### Sprint2 意图路由 + 持仓只读（2026-07-23）

| 段 | 内容 |
|----|------|
| 范围 | P0-2（规则意图）+ P0-3（真仓只读）chat 路径融化 |
| 后端 | `intent_router.py`；`tools.py` ContextVar + 2 工具；`web_server.ai_chat_stream` meta/system 注入；`schema`/`openapi` `portfolio_snapshot` |
| 前端 | `use-chat-stream` 附带 snapshot；`onMeta`→`chat-store.lastIntentMeta`；`chat-panel` intent badge |
| 测试 | `tests/backend/unit/test_sprint2_intent_portfolio.py` |
| commit | `feat(agent): Sprint2 intent routing + portfolio snapshot tools` |
| 禁 | push；假持仓；新建持仓 DB |

### Sprint3 组合风险诊断 + 观察 mode（2026-07-23）

| 段 | 内容 |
|----|------|
| 范围 | portfolio_risk 诊断字段；观察组合 UI 标记（只读语义） |
| 后端 | `app/analysis/risk_monitor.py`：`build_portfolio_diagnosis`；`sector_concentration`/`name_overlap`/`defensive_weight`/`unknown_industry_share`；缺行业→`unknown` |
| API | `/api/portfolio_risk` 响应扩展；`openapi_spec` 保守追加；`tools._analyze_portfolio_structure` 附带诊断 |
| 前端 | `portfolio-store` `mode: live\|watch` + migrate v2；`/portfolio` 诊断卡片 + 观察标签 |
| 测试 | `tests/backend/unit/test_analysis_risk_monitor.py`（+4）；`tests/frontend/stores/portfolio-store.test.ts`（+2）→ 14 pytest / 8 vitest |
| commit | `feat(portfolio): Sprint3 risk diagnosis + watch mode marker` |
| 禁 | push；假行业；agent 自动写仓 |

### P0-3 辩论证据面 + P0-4 工具时间线（2026-07-23 Sprint1 任务编号）

> 说明：本任务口令编号 **P0-3=辩论证据面**、**P0-4=工具时间线契约**，对应设计文 **§P0-6 / §P0-4（工具侧）**。

状态：**代码完成（本地 commit，未 push）**。

| 编号 | 能力 | 关键路径 |
|------|------|----------|
| P0-3 / 设计 P0-6 | `agent.debate_turn` + debate_card 双栏 + 分歧扫读 | `app/agents/coordinator.py` `_summarize_debate`；`app/web/web_server.py` SSE artifact；`frontend/.../debate-card.tsx`；`agent-side-panel` strip |
| P0-4 / 设计 P0-4 | `agent.tool_call`/`agent.tool_result` 契约字段 | `app/core/ai_client.py` helpers；`app/core/event_bus.py` 常量；`tool-call-card`/`use-chat-stream`/`types` |

验证：`tests/agents/test_debate_summary.py`（含 debate_turn + payload 契约）；相关 import smoke；前端 tsc 改动文件。

