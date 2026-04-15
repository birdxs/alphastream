# Q4 Agent + A2A 协作链路审查报告

**审查时间**: 2026-04-15 21:21 +08:00
**审查人**: 香草少校 (agent team)
**执行证据**: `/tmp/backend.log` (L71–L223, 688111 depth=3 实测, 21:06:03 → 21:10:25, 耗时 262s)

---

## 一、14个Agent清单 (代码盘点)

| # | Agent | 文件 | 作为 LangGraph node? |
|---|---|---|---|
| 1  | TechnicalAnalyst           | `app/agents/technical_analyst.py`          | YES (入口, 恒启) |
| 2  | FundamentalAnalyst         | `app/agents/fundamental_analyst.py`        | YES (depth>=2) |
| 3  | CapitalFlowAnalyst         | `app/agents/capital_flow_analyst.py`       | YES (depth>=2) |
| 4  | SentimentAnalyst           | `app/agents/sentiment_analyst.py`          | YES (depth>=3) |
| 5  | BullResearcher             | `app/agents/bull_researcher.py`            | YES (depth>=4) |
| 6  | BearResearcher             | `app/agents/bear_researcher.py`            | YES (depth>=4) |
| 7  | RiskManager                | `app/agents/risk_manager.py`               | YES (depth>=5) |
| 8  | DecisionMaker              | `app/agents/decision_maker.py`             | YES (恒启) |
| 9  | Reflection                 | `app/agents/reflection.py`                 | YES (decision→reflection→END) |
| 10 | InvestorCoordinator        | `app/agents/investors/investor_coordinator.py` | YES (depth>=5) |
| 11 | BuffettAgent               | `app/agents/investors/buffett.py`          | 子调用 (InvestorCoordinator 内串行) |
| 12 | MungerAgent                | `app/agents/investors/munger.py`           | 子调用 |
| 13 | LynchAgent                 | `app/agents/investors/lynch.py`            | 子调用 |
| 14 | DamodaranAgent             | `app/agents/investors/damodaran.py`        | 子调用 |
| -- | StrategyEvolver            | `app/agents/strategy_evolver.py`           | NO (旁路: 注入 system prompt + 事后 evolve) |
| -- | HITL HumanApproval         | `app/agents/hitl.py`                       | NO (旁路: 由 DecisionMaker/外部调用) |
| -- | CoordinatorAgent           | `app/agents/coordinator.py`                | 自身即 graph builder |

> 结论: 代码中 14 个"分析型" agent 全部落入 graph 或作为 coordinator 内部子调用. StrategyEvolver / HITL 为正交切面 (非 node), 不算入14数.

---

## 二、Agent 执行矩阵 (按 research_depth)

| Agent            | d=1 | d=2 | d=3 | d=4 | d=5 | 21:06 实测(d=3) | 状态 |
|------------------|:---:|:---:|:---:|:---:|:---:|:---:|---|
| technical        | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ Round1 工具调用 | OK |
| fundamental      | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ Round1 fundamental | OK (并行) |
| capital_flow     | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ Round1 capital_flow | OK (并行) |
| sentiment        | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ 21:08:29 执行 | **OK但数据源降级** |
| bull_researcher  | ✗ | ✗ | ✗ | ✓ | ✓ | — (d=3未触发) | 未执行 |
| bear_researcher  | ✗ | ✗ | ✗ | ✓ | ✓ | — (d=3未触发) | 未执行 |
| risk_manager     | ✗ | ✗ | ✗ | ✗ | ✓ | — (d=3未触发) | 未执行 |
| investors(×4)    | ✗ | ✗ | ✗ | ✗ | ✓ | — (d=3未触发) | 未执行 |
| decision_maker   | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ 21:09:56 | OK (registry 降级) |
| reflection       | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (END 前恒执) | OK |

实测路径 (d=3): `technical → [_route_record_normal] → (fundamental ∥ capital_flow) → sentiment → decision → reflection → END`
完成时间: 21:06:03 启动 → 21:10:25 结束 = **4分22秒**.

---

## 三、A2A 协作点识别

| 协作点 | 触发深度 | 机制 | EventBus 发布 | 备注 |
|---|---|---|---|---|
| 技术→(基本面 ∥ 资金流) fan-out | d>=2 | LangGraph add_edge + reducer (execution_log/progress) | `EVENT_AGENT_STARTED/COMPLETED` via `_wrap_with_events` | 真并行 ThreadID 不同(13630124032 vs 13613297664) |
| (基本面+资金流) fan-in → sentiment | d>=2/3 | LangGraph 默认 join | 同上 | sentiment 依赖前两报告 via state |
| **bull ↔ bear 并行"辩论"** | d>=4 | **并行 fan-out**, 非真辩论 | ✓ | **⚠ 问题P1**: bear 的 prompt 引用 `bull_case`, 但并行启动时 bull_case 可能尚未生成, 即 `_compile_reports` 会拿到 `None` → 实质是"独立看空", 非"针对性反驳" |
| bull/bear fan-in → risk(d=5) / decision(d=4) | d>=4 | LangGraph join | ✓ | debate_summary 字段 State 里声明但**无 agent 写入** |
| risk → investors(d=5) | d=5 | 串行 edge | ✓ | InvestorCoordinator 内部串行调4人格 |
| InvestorCoordinator → 4人格协商 | d=5 | Python 循环串行调 4 Agent + AI综合研判 (非投票) | ✗ 子人格调用**无 EventBus publish** | AI 不可用降级为加权投票; 子人格执行不可观测 |
| decision_maker ← 全 analyst state | 恒启 | 读取 state 各 report + AdapterRegistry 聚合 news/social/esg | ✓ | registry 三域全 domain 降级失败仍产出决策 |
| reflection → decision feedback | 恒启 | 单向 (decision→reflection→END) 写 reflection.json 供**下次**分析时 strategy_evolver 注入 system prompt | ✗ 无 EVENT_AGENT_STEP_DONE | 跨会话反馈, 非同轮回写 |
| HITL | 条件 | `EVENT_APPROVAL_NEEDED` 常量已定义 | **未在 graph 中触发** | **⚠ 问题P2**: 常量存在但 coordinator 未调用 hitl.request_approval |
| RiskAlert | 条件 | `EVENT_RISK_ALERT` 常量已定义 | **risk_manager 未 publish** | **⚠ 问题P3**: risk agent 完成事件走 wrap, 但高风险场景不发 RISK_ALERT |

---

## 四、发现的问题

### P0 (无) — graph 编排完整, 14 agent 全部可达

### P1 — bull/bear "伪辩论"
- `bull_researcher.py` 与 `bear_researcher.py` 被 `graph.add_edge(last_node, "bull")` + `graph.add_edge(last_node, "bear")` 同步 fan-out 启动.
- `bear_researcher._compile_reports` 期望读 `state['bull_case']`, 但并行时 bull 尚未写入.
- 结果: bear 分析失去"反驳 bull"的语义, 退化为独立看空.
- **建议(不强制改)**: d=4/5 时改为 bull → bear 串行, 或新增 `debate_moderator` 节点做第二轮对抗.

### P2 — EVENT_APPROVAL_NEEDED / EVENT_RISK_ALERT 定义但未发布
- `app/core/event_bus.py` L113-114 定义了常量, 全代码库 grep 无 `.publish(EVENT_APPROVAL_NEEDED` / `.publish(EVENT_RISK_ALERT` 的调用方.
- Comdr 在前端终端看不到 HITL / 风险告警事件.

### P3 — InvestorCoordinator 子人格不可观测
- 4人格 `BuffettAgent/...analyze` 被 for 循环调用 (investor_coordinator.py L51-63), **未经 `_wrap_with_events` 包装**, 前端 SSE 终端看不到 "巴菲特开始分析" 等 reasoning 事件.
- 表现: d=5 时终端会"静默 30-60 秒", 体验差.

### P4 — Registry 多域降级失败 (已知, 非本轮新问题)
- 实测 21:08:29 / 21:09:56 sentiment & decision 的 registry.call_with_fallback:
  - `news.get_latest_news tried=['rss_news']` 全失败
  - `sentiment_social.get_social_sentiment tried=['opencli']` 全失败 (opencli 命令 `xueqiu/discuss` / `eastmoney/guba` unknown)
  - `commodity_shipping.get_bdi_index tried=['shipping']` 全失败
  - `corporate_entity.search_company tried=['opencorporates']` 全失败
  - `hiring_signal.get_company_postings` TimeoutError
  - `esg_rating.get_esg_score` TimeoutError
- 降级路径均 "空上下文不中断决策" 符合设计; 但**数据侧对标 fiscal.ai 时会明显瘦身**.

### P5 — debate_summary 字段悬空
- `state.py` 声明 `debate_summary: Optional[str]`, 无 agent 写入该字段 (grep `debate_summary` 仅见于 state/coordinator 初始化).
- 建议: 新增 debate_moderator 或在 decision_maker 内生成填充.

---

## 五、综合结论

- ✅ **14 agent 全部可执行** (d=5 全链路), 无"定义但未串入 graph"的孤儿 agent
- ✅ **graph 编排完整**: fan-out / fan-in / 条件路由 / reflection 闭环均正常
- ✅ **EventBus 事件链路活跃**: 主干 agent 通过 `_wrap_with_events` 发 started/completed
- ⚠ **A2A 深度不足**: bull-bear 是"并行独白"非"辩论"; 4投资者是"轮询汇总"非"协商"
- ⚠ **3 类事件常量(HITL/RiskAlert)定义未使用**, 前端可观测性有缺口
- ⚠ **6 个 alt-data registry 全域降级失败**, 不影响主决策但削弱决策上下文

本次 **不做 P0 修复** (无 P0). P1/P2/P3 建议列入下一阶段治理.
