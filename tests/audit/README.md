# 测试体系总说明（P3 / W1 落地版）

> 一旦本目录结构或测试约定发生变化，请务必同步更新本文件。

## 1. 目录导航

```
tests/
├── audit/                  本测试体系的"作战指挥部"
│   ├── README.md           本文件
│   ├── capability_matrix.md  能力清单（路由/Agent/适配器/前端组件）
│   ├── test_framework.md   方法论 + 工具链 + Fixture 规范
│   ├── reports/            W2-W7 worker 落盘的验收报告
│   │   └── REPORT_TEMPLATE.md
│   └── evidence/           证据（pytest 日志、覆盖率 HTML、截图）
├── backend/
│   ├── unit/               单测（pure function、无 IO）
│   ├── integration/        组件协作（多模块、含 DB/缓存 mock）
│   ├── api/                Flask HTTP/REST 路由测试
│   └── sse/                Server-Sent Events 流式测试
├── frontend/
│   ├── unit/               纯函数 / utils
│   ├── components/         React 组件渲染交互
│   ├── stores/             Zustand store
│   └── hooks/              自定义 hook
├── e2e/
│   ├── journeys/           用户旅程（多页面 + 数据流）
│   ├── contracts/          前后端契约（OpenAPI / SSE schema）
│   └── perf/               性能 / 长跑
├── fixtures/               跨域共享数据 fixture
└── （legacy 目录：core/ agents/ adapters/ mcp/ web/）
    保留 W1 之前已有的 531 用例，不强制迁移
```

## 2. 如何运行测试

### 2.1 后端 pytest

```bash
# 全部测试（含历史 531 用例）
pytest

# 仅 W1 之后新增的后端测试
pytest tests/backend tests/audit

# 按 marker
pytest -m "unit and not slow"
pytest -m "api or sse"

# 收集（不执行）
pytest --collect-only -q

# 带覆盖率
pytest --cov --cov-config=.coveragerc --cov-report=html
# 覆盖率 HTML 输出到 tests/audit/evidence/coverage_html/
```

### 2.2 前端 vitest

```bash
cd frontend

# 首次运行前需安装测试依赖
npm install   # 会读取 package.json 中的 devDependencies

# 运行测试
npm run test            # 单次
npm run test:watch      # 监听模式
npm run test:coverage   # 含覆盖率（HTML 输出到 tests/audit/evidence/frontend_coverage/）

# Playwright E2E
npm run test:e2e
```

### 2.3 端到端

```bash
# 后端 Flask + 前端 Next 同时启动后
cd frontend && npm run test:e2e
```

## 3. Worker 工作流

1. 从 `capability_matrix.md` 领取报告 ID（如 `BE-01`、`FE-03`、`E2E-02`）。
2. 在对应 `tests/{backend|frontend|e2e}/{子域}/` 下创建 `test_<报告ID>_<主题>.py(.tsx)`。
3. 复用 `conftest.py` 提供的 fixture：`mock_ai_client`、`flask_client`、`sse_client`、`mock_event_bus`、`mock_adapters`、`tmp_data_dir`。
4. 跑通后填写 `tests/audit/reports/<报告ID>.md`（基于 `REPORT_TEMPLATE.md`）。
5. 证据落盘：命令日志、pytest 输出、覆盖率 HTML 截图放入 `tests/audit/evidence/<报告ID>/`。
6. 本地 commit，**严禁 push**。

## 4. 通关红线

- LLM 全 mock，不允许真实调用 OpenAI（即使本地有 API_KEY）。
- 网络 IO（akshare/yfinance/HTTP）必须走 `mock_adapters` 或 `requests_mock`。
- 测试执行时间：单个用例 < 5s，标 `@pytest.mark.slow` 的除外。
- 任何破坏现有 531 用例的改动直接拒绝合入。

## 5. 时间锚点

本体系 W1 框架落盘时间：**2026-05-17 19:10:09 +08:00**（已经过 Google + Apple HTTPS Date 头双源校时，最大偏差 4 秒）。
