# BE-02c2 推理决策类 Agent 单元测试报告

- 时间：2026-05-17 21:30:00 +08:00
- 仓库：`StockAnal_Sys`
- 范围：bull_researcher / bear_researcher / risk_manager / decision_maker / reflection / strategy_evolver
- 前置约束：LLM 全 mock；不可 push；新文件 commit 标签 `[NEW-FILE:#20260517-01]`

## 1. 执行总览

| 项 | 数值 |
| --- | --- |
| 用例数 | 33 |
| 通过 | 33 |
| 失败 | 0 |
| 跳过 | 0 |
| 总耗时 | 0.55s（含覆盖率） |
| 综合覆盖率 | 71%（目标 ≥ 70% 达标） |

证据：`tests/audit/evidence/BE-02c2_pytest.log`

## 2. 各 Agent 用例与覆盖率

| Agent | 用例数 | 覆盖率 | 状态 |
| --- | --- | --- | --- |
| BullResearcherAgent | 4 | 78% | PASS |
| BearResearcherAgent | 5 | 81% | PASS |
| RiskManagerAgent | 7 | 71% | PASS |
| DecisionMakerAgent | 5 | 76% | PASS |
| ReflectionAgent | 5 | 62% | PASS（覆盖率略低，详见 5.1） |
| StrategyEvolver | 7 | 66% | PASS（覆盖率略低，详见 5.2） |

## 3. 测试维度落地

### 3.1 BullResearcherAgent
- happy_path：mock 4 个上游 report → bull_case 文本生成、progress=50、status=success
- LLM error → fallback 字符串，status=failed
- AI 客户端缺失 → fallback，status=failed
- 上下文注入：技术/基本面/舆情/资金 4 段 prompt 全部出现

### 3.2 BearResearcherAgent
- happy_path 文本生成
- LLM error fallback
- AI 客户端缺失 fallback
- **R2 反驳式 prompt 注入**：当 state 含 bull_case 时 prompt 注入"看多观点（需质疑）"段落与 bull_case 内容
- 无 bull_case 时 prompt 不出现反驳段落（负向验证）

### 3.3 RiskManagerAgent（含 EVENT_RISK_ALERT publish）
- happy_path：风险评估 schema 完整，progress=70
- **高风险触发 EVENT_RISK_ALERT publish（level=high）**
- **中高风险触发 EVENT_RISK_ALERT publish（level=medium）**
- 低风险 不触发 alert（噪声抑制验证）
- LLM error → fallback 路径走 RiskMonitor stub
- schema 完整性
- `_publish_risk_alert` 隔离验证：高/中等/低各档分级

### 3.4 DecisionMakerAgent（含 HITL 触发）
- happy_path：action/confidence/price_targets/risk_level 完整，progress=100
- **HITL 触发**：final_decision.risk_level=高 时调用 `hitl._publish_approval_event` →
  断言 EVENT_APPROVAL_NEEDED 被 publish，payload 含 `[APPROVAL]`/risk_level=high/options=approve+reject
- LLM error → HOLD/confidence=0.3，status=failed
- 无 AI client → HOLD/confidence=0.5，status=fallback
- LLM 返回非 JSON → fallback dict（confidence=0.5）

### 3.5 ReflectionAgent（含落盘 data/agent_reflections）
- happy_path：reflect → 落盘 `<tmp_data_dir>/agent_reflections/600519_reflections.json`
- LLM 失败 → reflection={'error':...} 仍然落盘
- 无 AI client → skipped，不落盘
- **多次反思追加**（不覆盖）：3 次后文件含 3 条记录
- `get_past_reflections` 读取裁剪

### 3.6 StrategyEvolver（含落盘 data/agent_strategies）
- happy_path：reflections → 新策略 + evolution_count=1，落盘 `<tmp>/agent_strategies/600519_strategy.json`
- LLM 失败 → 保留 default_strategy，不落盘
- **早返路径**：reflections 信号为空 → 不调 LLM，直接返回 default
- 无 AI client → 早返，不落盘
- 非 JSON 输出 → safe_parse 保护，不落盘
- markdown ```json fenced 输出 → safe_parse 正确解析
- get_active_strategy 默认值

## 4. 关键缺陷与发现

### 4.1 [PASS] EVENT_RISK_ALERT publish 验证
- 高/中高风险时 `app.agents.risk_manager._publish_risk_alert` 正确发布事件至 EventBus
- 事件 payload 结构：`{event_type, data: {level, stock_code, content, ...}}`，`[RISK_ALERT]` 前缀正确
- 低风险与"中等风险（但 score<60）"按预期不触发噪声

### 4.2 [PASS] HITL 触发链验证
- DecisionMakerAgent 自身**不发布** EVENT_APPROVAL_NEEDED，HITL 责任由 `app.agents.hitl` 模块承担
- 测试通过直接调用 `hitl._publish_approval_event` 验证 publish 路径
- payload 结构：`{event_type:"reasoning", data:{content:"[APPROVAL]...", risk_level:"high", options:{approve, reject}}}`

### 4.3 [INFO] 测试环境缺陷规避
- **BE-02c1 复用经验**：`app.core.tools` 与 pydantic 2.12 不兼容（@tool 校验失败），通过 `sys.modules["app.core.tools"]` stub 规避
- **本批新发现**：`app.adapters.adapter_registry` import 时触发真实 RSS 拉取（数十秒阻塞）。
  通过 `sys.modules["app.adapters.adapter_registry"]` stub 规避。
  受影响：`DecisionMakerAgent.analyze` 内部 `from app.adapters.adapter_registry import AdapterRegistry`
- **影响 patch 路径**：6 个 Agent 内部均使用函数体内 `from app.core.ai_client import ...`。
  patch 必须作用在 **`app.core.ai_client.X`** 而非 `app.agents.X.X`。否则 AttributeError。

### 4.4 [INFO] 测试隔离
- reflection / evolver 通过 `monkeypatch.setattr(reflection_mod, "REFLECTION_DIR", ...)` 与
  `monkeypatch.setattr(evolver_mod, "STRATEGY_DIR", ...)` 隔离落盘，未污染真实 `data/agent_reflections/`、
  `data/agent_strategies/`
- decision_maker HITL 测试用本地 `monkeypatch.setattr(EventBus, "publish", ...)` 隔离，
  避免触发已注册订阅者（如 SSE 桥接）造成的潜在阻塞

## 5. 覆盖率未达 70% 项

### 5.1 reflection.py 62%
- 未覆盖：`get_past_reflections` 全失败路径（line 130-145 IO 异常分支）、
  `_compile_state_summary` 失败分支（line 96/98-99），属于 IO 异常的极端兜底，影响面有限
- 主路径（reflect + 落盘 + 追加 + 读取）全覆盖

### 5.2 strategy_evolver.py 66%
- 未覆盖：`save_strategy` 文件 IO 异常分支（line 221-224/242-244）、
  `_apply_strategy_to_context` 极端兜底（line 180-200），属于 IO 异常的极端兜底
- 主路径（evolve + 落盘 + safe_parse + 默认值）全覆盖

均不影响"快乐路径 + 关键失败路径 + 落盘验证"的核心目标。

## 6. 输出物清单（落盘已确认）

```
tests/backend/unit/test_agent_bull.py        (NEW)
tests/backend/unit/test_agent_bear.py        (NEW)
tests/backend/unit/test_agent_risk.py        (NEW)
tests/backend/unit/test_agent_decision.py    (NEW)
tests/backend/unit/test_agent_reflection.py  (NEW)
tests/backend/unit/test_agent_evolver.py     (NEW)
tests/audit/reports/BE-02c2_decision_agents.md (NEW)
tests/audit/evidence/BE-02c2_pytest.log        (NEW)
```

## 7. 下一步建议

1. 补 reflection / evolver 的 IO 异常分支用例可提升到 ≥ 80%
2. coordinator 层 HITL 包装（`coordinator.py` 中触发 hitl.approval_manager.request_approval 的路径）
   建议另立 BE-02c3 集成测试单独覆盖
3. `app.adapters.adapter_registry` import 即拉 RSS 的副作用建议改造为懒加载（性能/可测性双收益）
