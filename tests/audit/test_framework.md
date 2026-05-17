# 测试方法论与工具链

> Input: 项目测试策略与规范
> Output: 各 Worker 执行测试的统一依据
> Pos: tests/audit/；W1 落盘，W2-W7 持续更新

---

## 1. 测试金字塔

```
        ┌─────────────────┐
        │   E2E (顶层)     │  ← Playwright 端到端用户旅程
        │  契约 / 性能     │    数量少、覆盖关键路径
        └────────┬────────┘
                 │
        ┌────────┴────────┐
        │ 集成 (中层)      │  ← pytest + Flask test_client + SSE
        │ API / SSE 路由  │    验证多模块协作与边界
        └────────┬────────┘
                 │
        ┌────────┴────────┐
        │ 单元 (底层)      │  ← pytest / vitest + RTL
        │ 纯函数 / 组件   │    数量多、执行快、完全 mock IO
        └─────────────────┘
```

---

## 2. 工具链

| 层级 | 工具 | 用途 |
|------|------|------|
| 后端单元/集成/API/SSE | pytest + pytest-cov | 测试执行与覆盖率 |
| 后端 HTTP Mock | responses / requests_mock | 屏蔽外部 HTTP 调用 |
| 前端单元/组件/store/hook | vitest + @testing-library/react | jsdom 环境渲染与交互 |
| 前端断言 | @testing-library/jest-dom | DOM matcher 扩展 |
| 前端用户事件 | @testing-library/user-event | 高保真用户行为模拟 |
| E2E | Playwright | 真实浏览器端到端测试 |
| 覆盖率（后端） | pytest-cov + coverage.py | HTML 报告 → tests/audit/evidence/coverage_html/ |
| 覆盖率（前端） | @vitest/coverage-v8 | HTML 报告 → tests/audit/evidence/frontend_coverage/ |

---

## 3. Mock 策略

### 3.1 LLM 全 mock（强制）

- **禁止**在任何测试中真实调用 OpenAI / Anthropic 等 LLM 接口。
- 使用 `mock_ai_client` fixture（conftest.py），patch `app.core.ai_client` 下的 `chat_completion` / `chat_with_tools` / `chat_completion_stream`。
- Mock 返回值须符合实际响应结构：`{"choices": [{"message": {"content": "..."}}], "usage": {...}}`。

### 3.2 外部数据源 mock（强制）

- akshare / yfinance / 任何 HTTP 数据源必须通过 `mock_adapters` 或 `mock_akshare` fixture 屏蔽。
- 可以使用 `responses` 库拦截 `requests` 调用，或使用 `monkeypatch` 替换适配器函数。

### 3.3 Event Bus mock

- 使用 `mock_event_bus` fixture 截获 `EventBus.publish` 调用，断言事件类型与数据。

### 3.4 文件系统 mock

- 使用 `tmp_data_dir` fixture 提供临时目录，避免污染 `data/` 真实目录。

---

## 4. Fixture 使用规范

`conftest.py`（根目录）提供 8 个全局 fixture，所有测试自动加载，无需手动 import：

| Fixture | 类型 | 用途 |
|---------|------|------|
| `tmp_data_dir` | function scope | 临时 data/ 目录，含 6 个子目录 |
| `mock_ai_client` | function scope | patch LLM 三函数，返回预设 JSON |
| `mock_event_bus` | function scope | 截获 EventBus.publish，收集事件列表 |
| `flask_app` | function scope | TESTING 模式 Flask 实例 |
| `flask_client` | function scope | Flask test_client（依赖 flask_app） |
| `sse_consumer` | function scope | SSE 流消费器，返回 dict 列表 |
| `mock_akshare` | function scope | patch akshare 常用函数，返回 mock DataFrame |
| `mock_adapters` | function scope | patch 适配器层（详见 conftest.py） |

使用示例：

```python
@pytest.mark.api
def test_health(flask_client):
    resp = flask_client.get("/api/health")
    assert resp.status_code == 200

@pytest.mark.unit
def test_agent_analysis(mock_ai_client, tmp_data_dir):
    # mock_ai_client["chat_completion"].return_value 已预设
    ...
```

---

## 5. 验收报告规范

- 每个报告域对应一个 `tests/audit/reports/<报告ID>.md`。
- 模板见 `tests/audit/reports/REPORT_TEMPLATE.md`。
- 证据（pytest 日志 / 覆盖率截图）落盘至 `tests/audit/evidence/<报告ID>/`。

---

## 6. 通关红线

| 维度 | 指标 |
|------|------|
| 后端整体覆盖率 | ≥ 70% (line) |
| 后端关键模块（core/ agents/ web/）| ≥ 85% |
| 前端组件/store/hook | ≥ 60% |
| E2E P0 旅程 | 100% 通过 |
| SSE 30 分钟长跑 RSS 增长 | ≤ 50 MB |
| 历史 531 用例回归 | 0 新增失败 |
| 单个用例执行时间 | < 5s（`slow` marker 除外） |
| LLM 真实调用 | 0 次（全测试周期） |

---

## 7. W1-W7 波次说明

| 波次 | 主题 | 关键产出 |
|------|------|----------|
| W1a | 基础设施骨架 | 目录结构 / pytest.ini / conftest.py / vitest 配置 |
| W1b | 能力清单矩阵 | capability_matrix.md 完整填充（78 路由等） |
| W2 | 后端单元测试 | tests/backend/unit/ 覆盖核心纯函数 |
| W3 | 后端集成/API/SSE 测试 | tests/backend/{integration,api,sse}/ |
| W4 | 前端单元/组件/store 测试 | tests/frontend/{unit,components,stores,hooks}/ |
| W5 | E2E 用户旅程 | tests/e2e/journeys/ P0 旅程全通过 |
| W6 | 契约测试 + 性能 | tests/e2e/{contracts,perf}/ |
| W7 | 总验收 + 报告汇总 | tests/audit/FINAL_ACCEPTANCE_REPORT.md |

---

## 8. 时间锚点

- 方法论文档落盘时间：**2026-05-17 19:21:42 +08:00**（W1a 阶段）
