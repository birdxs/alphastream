# BE-02c1 数据收集类 Agent 单元测试报告

- 任务编号：BE-02c1
- 执行时间：2026-05-17 21:00 ~ 21:10 +08:00
- 目标 Agent：4 个数据收集分析 Agent
- 报告日期：2026-05-17（当前日期，依据指挥官 currentDate 上下文）

## 1. 范围

| Agent | 源文件 | 测试文件 |
|---|---|---|
| TechnicalAnalystAgent | `app/agents/technical_analyst.py` | `tests/backend/unit/test_agent_technical.py` |
| FundamentalAnalystAgent | `app/agents/fundamental_analyst.py` | `tests/backend/unit/test_agent_fundamental.py` |
| CapitalFlowAnalystAgent | `app/agents/capital_flow_analyst.py` | `tests/backend/unit/test_agent_capital_flow.py` |
| SentimentAnalystAgent | `app/agents/sentiment_analyst.py` | `tests/backend/unit/test_agent_sentiment.py` |

边界：本批不含 bull/bear/risk/decision/reflection/evolver，留给 BE-02c2。

## 2. 测试维度覆盖

每个 Agent 6 用例（合计 24 用例），覆盖任务约定的 4 维度：

1. **快乐路径**：mock `chat_with_tools` / `chat_completion` 返回固定 JSON，断言对应 `*_report` 键存在且含必要字段（score / trend / financial_health / main_force_trend / total_news 等）。
2. **数据源失败降级**：mock `_registry_fetch` 抛错或返回 None，验证 `_fallback_analyze` 路径被触发并返回 `mode: fallback`；sentiment 因无 `_fallback_analyze` 函数，验证 try/except 兜底返回 `{'error': ...}`。
3. **LLM 失败降级**：mock `chat_with_tools` `side_effect=RuntimeError` 或 `return (None, [], "error")`，验证 fallback 兜底；额外加 1 用例覆盖「LLM 返回 error 字段」分支。
4. **事件发布**：使用 `mock_event_bus` fixture（commit 2f4d9ad 修复）断言 fallback 路径下未触发 `EVENT_TOKEN_GENERATED` 等 LLM 流事件。

## 3. 执行命令

```bash
cd /Users/panda/Downloads/StockAnal_Sys
pytest tests/backend/unit/test_agent_technical.py \
       tests/backend/unit/test_agent_fundamental.py \
       tests/backend/unit/test_agent_capital_flow.py \
       tests/backend/unit/test_agent_sentiment.py -v
pytest <同上> --cov=app.agents.technical_analyst --cov=app.agents.fundamental_analyst \
              --cov=app.agents.capital_flow_analyst --cov=app.agents.sentiment_analyst \
              --cov-report=term
```

## 4. 结果

### 4.1 通过率

| 文件 | 用例数 | 通过 | 失败 |
|---|---|---|---|
| test_agent_technical.py | 6 | 6 | 0 |
| test_agent_fundamental.py | 6 | 6 | 0 |
| test_agent_capital_flow.py | 6 | 6 | 0 |
| test_agent_sentiment.py | 6 | 6 | 0 |
| **合计** | **24** | **24** | **0** |

### 4.2 覆盖率（term 输出）

| 文件 | Stmts | Miss | Branch | BrPart | Cover |
|---|---|---|---|---|---|
| app/agents/capital_flow_analyst.py | 116 | 31 | 40 | 13 | **68%** |
| app/agents/fundamental_analyst.py | 103 | 27 | 32 | 10 | **70%** |
| app/agents/sentiment_analyst.py | 95 | 19 | 38 | 9 | **76%** |
| app/agents/technical_analyst.py | 115 | 33 | 28 | 9 | **68%** |
| **TOTAL** | **429** | **110** | **138** | **41** | **70%** |

合计 **70% ≥ 70% 目标**，达成。

## 5. 缺陷 / 已知限制

1. **`app.core.tools` 在 coverage 模式下 import 失败**
   - 现象：启用 `--cov` 时 `app.core.tools` 模块被重新 import，langchain `@tool` 装饰器与 pydantic 2.12 的 deprecated decorator 模块冲突，抛出 `TypeError: Expected a Pydantic model. Got <class 'pydantic.deprecated.decorator.GetStockData'>`。
   - 影响范围：任何首次在 coverage 模式下 import `app.core.tools` 的测试。
   - 当前规避：测试文件顶部预注入 `sys.modules["app.core.tools"]` stub（仅含 4 个 Schema 列表常量，均为 `[]`），从而绕开真实模块的 `@tool` 装饰器执行；不影响 Agent 内 `chat_with_tools` 通过 mock 的行为校验。
   - 建议（留给 BE-02c2 / 平台修复）：升级 langchain-core 至兼容 pydantic 2.12 的版本，或在 `app/core/tools.py` 加 lazy import 防护。

2. **sentiment_analyst 无 `_fallback_analyze` 函数**
   - 现象：与任务描述「每 Agent 都有同名兜底」不符。
   - 实际行为：sentiment 通过外层 `try/except` 兜底，异常时返回 `{'sentiment_report': {'error': str(e)}, 'execution_log': [...status: failed]}`。
   - 已在测试 `test_sentiment_fallback_news_fetcher_fails` 中以 `error 字段存在 + status=failed` 验证。

3. **4 个 Agent 本身不发布 `EVENT_AGENT_STARTED / COMPLETED`**
   - 现象：事件由 `coordinator.py`（协调者节点）或 `chat_with_tools` 内部发布；4 个数据 Agent 仅返回 state dict，不直接调用 EventBus。
   - 调整：将事件维度断言改为「fallback 路径下无 `*token*` 事件被发布」，确保 mock_event_bus 接入有效且 fallback 不会误触发 LLM 流事件。

4. **降级数据源链路过深时双重降级**
   - 在 `test_technical_fallback_when_data_source_fails` 与 `test_fundamental_fallback_when_adapter_fails` / `test_capital_flow_fallback_when_adapter_fails` 中，`_registry_fetch` 被 mock 为 side_effect 抛错，覆盖了「fallback 内部也异常」的二级兜底分支：返回 `{'error': ...}` + `status: failed`。断言以 `or` 形式兼容两种合法结果。

## 6. 证据与产物

- 测试文件（4）：`tests/backend/unit/test_agent_{technical,fundamental,capital_flow,sentiment}.py`
- 报告：`tests/audit/reports/BE-02c1_data_agents.md`
- 日志：`tests/audit/evidence/BE-02c1_pytest.log`（含 -v 输出 + --cov term 摘要）

## 7. 结论

24/24 用例通过，覆盖率 70% 达成目标。4 个数据收集 Agent 的快乐路径、双层降级、事件隔离均得到验证。可继续推进 BE-02c2（bull/bear/risk/decision/reflection/evolver 决策类 Agent 测试）。
