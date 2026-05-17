# 验收报告 - BE-01e 业务分析 ~10 路由测试

| 项 | 值 |
|---|---|
| 报告ID | BE-01e |
| 域 | 后端 / Flask 路由 / 业务分析（ETF / 基本面 / 资金流 / 情景 / QA / 风险 / 指数 / 行业 / 行业比较 / 投资组合风险） |
| 执行时间 | 2026-05-17 20:08:00 +08:00 ~ 2026-05-17 20:16:08 +08:00 |
| 状态 | 通关（31/31 PASS） |

## 1. 测试范围

本批严格限定 ~10 条路由（精确签名核对自 `app/web/web_server.py`）：

| # | 方法 | 路径 | 源码行号 | 备注 |
|---|---|---|---|---|
| 1 | POST | `/api/start_etf_analysis` | 883 | 启动 ETF 分析；mock `EtfAnalyzer` 类 |
| 2 | GET  | `/api/etf_analysis_status/<task_id>` | 942 | 任务列要求的 `/api/etf_result/<id>` **不存在**，按存在的 `etf_analysis_status` 测试 |
| 3 | POST | `/api/fundamental_analysis` | 1839 | mock `fundamental_analyzer.calculate_fundamental_score` |
| 4 | POST | `/api/capital_flow` | 1933 | 与页面路由 `/capital_flow` 区分；mock `capital_flow_analyzer.calculate_capital_flow_score` |
| 5 | POST | `/api/scenario_predict` | 1959 | mock `scenario_predictor.generate_scenarios` |
| 6 | POST | `/api/qa` | 1985 | mock `stock_qa.answer_question` |
| 7 | POST | `/api/risk_analysis` | 2011 | mock `risk_monitor.analyze_stock_risk` |
| 8 | POST | `/api/portfolio_risk` | 2036 | 任务列要求的 `/api/portfolio_analysis` **不存在**，按存在的 `portfolio_risk` 测试 |
| 9 | GET  | `/api/index_analysis` | 2055 | mock `index_industry_analyzer.analyze_index` |
| 10 | GET  | `/api/industry_analysis` | 2074 | mock `index_industry_analyzer.analyze_industry` |
| 11 | GET  | `/api/industry_compare` | 2128 | mock `index_industry_analyzer.compare_industries` |

测试文件：`tests/backend/api/test_business_analysis_routes.py`
依赖：`flask_client`（conftest）+ `patched_analyzers`（本文件 fixture，统一打桩 7 个分析器实例 + `EtfAnalyzer` 类）。

## 2. 测试矩阵

| 用例 ID | 路由 | 类型 | 用例 | 结果 |
|---|---|---|---|---|
| BE-01e-T01 | `/api/start_etf_analysis` | happy | 正常 etf_code 返回 task_id | PASS |
| BE-01e-T02 | `/api/start_etf_analysis` | error | 缺 etf_code → 400 | PASS |
| BE-01e-T03 | `/api/etf_analysis_status/<id>` | error | 未知 task_id → 404 | PASS |
| BE-01e-T04 | `/api/etf_analysis_status/<id>` | happy | start 后查询 schema | PASS |
| BE-01e-T05 | `/api/fundamental_analysis` | happy | 转发 stock_code | PASS |
| BE-01e-T06 | `/api/fundamental_analysis` | error | 缺 stock_code → 400 | PASS |
| BE-01e-T07 | `/api/fundamental_analysis` | error | 非法 stock_code → 400 | PASS |
| BE-01e-T08 | `/api/capital_flow` | happy | 转发 (stock_code, market_type) | PASS |
| BE-01e-T09 | `/api/capital_flow` | error | 缺 stock_code → 400 | PASS |
| BE-01e-T10 | `/api/capital_flow` | error | 非法 stock_code → 400 | PASS |
| BE-01e-T11 | `/api/scenario_predict` | happy | 转发 days=90 | PASS |
| BE-01e-T12 | `/api/scenario_predict` | happy | 默认 days=60 | PASS |
| BE-01e-T13 | `/api/scenario_predict` | error | 缺 stock_code → 400 | PASS |
| BE-01e-T14 | `/api/scenario_predict` | error | 非法 stock_code → 400 | PASS |
| BE-01e-T15 | `/api/qa` | happy | 转发 (stock_code, question, market_type) | PASS |
| BE-01e-T16 | `/api/qa` | error | 缺 question → 400 | PASS |
| BE-01e-T17 | `/api/qa` | error | 缺 stock_code → 400 | PASS |
| BE-01e-T18 | `/api/risk_analysis` | happy | 转发 (stock_code, market_type) | PASS |
| BE-01e-T19 | `/api/risk_analysis` | error | 缺 stock_code → 400 | PASS |
| BE-01e-T20 | `/api/risk_analysis` | error | 非法 stock_code → 400 | PASS |
| BE-01e-T21 | `/api/portfolio_risk` | happy | 转发 portfolio 列表 | PASS |
| BE-01e-T22 | `/api/portfolio_risk` | error | 空 portfolio → 400 | PASS |
| BE-01e-T23 | `/api/portfolio_risk` | error | 缺 portfolio → 400 | PASS |
| BE-01e-T24 | `/api/index_analysis` | happy | 转发 limit | PASS |
| BE-01e-T25 | `/api/index_analysis` | error | 缺 index_code → 400 | PASS |
| BE-01e-T26 | `/api/index_analysis` | error | 非法 limit → 400/500（不泄露栈） | PASS |
| BE-01e-T27 | `/api/industry_analysis` | happy | 转发 (industry, limit) | PASS |
| BE-01e-T28 | `/api/industry_analysis` | error | 缺 industry → 400 | PASS |
| BE-01e-T29 | `/api/industry_compare` | happy | 默认 limit=10 | PASS |
| BE-01e-T30 | `/api/industry_compare` | happy | 自定义 limit=25 | PASS |
| BE-01e-T31 | `/api/industry_compare` | error | 非法 limit → 400/500（不泄露栈） | PASS |

每路由覆盖：≥ 2 用例（快乐 + 错误），其中 6 条 POST 业务路由各覆盖 ≥ 2 错误路径（缺字段 + 非法 stock_code）。

## 3. 执行记录

命令：
```bash
pytest tests/backend/api/test_business_analysis_routes.py -v 2>&1 | tee tests/audit/evidence/BE-01e_pytest.log
```

关键输出尾段：
```
======================= 31 passed, 11 warnings in 5.03s ========================
```

执行用时：≈ 5.03 秒（pytest 报告）。
首跑即通关，无 flaky。

## 4. 结果统计

- 通过：31 / 31
- 失败：0
- 跳过：0
- 警告：11（均为外部依赖 Pydantic V2 弃用提示，非本批引入）
- 覆盖率：未单独采集 line/branch（本批为路由层契约测试，关注点为参数转发与错误响应规范）

## 5. 缺陷清单

| ID | 等级 | 描述 | 复现 | 建议 |
|---|---|---|---|---|
| DEF-01e-01 | 文档/契约 | 任务列要求测试 `/api/portfolio_analysis`，但 `app/web/web_server.py` 仅注册 `/api/portfolio_risk`（line 2036）；不存在 `portfolio_analysis` 路径 | `grep -nE "@app.route.*portfolio" app/web/web_server.py` | 二选一：（a）更新文档/任务列改名为 `portfolio_risk`；（b）若 PRD 期望独立 `portfolio_analysis`，新增路由并明确职责边界 |
| DEF-01e-02 | 文档/契约 | 任务列要求测试 `/api/etf_result/<id>`，但仓库仅有 `/api/etf_analysis_status/<task_id>`（line 942），无 `etf_result` | `grep -nE "@app.route.*etf" app/web/web_server.py` | 与 stock 三件套对齐：保持 `etf_analysis_status` 命名；或新增 `etf_result` 作为"仅返回 result 字段"的便捷端点 |
| DEF-01e-03 | 健壮性（轻） | `/api/index_analysis` 与 `/api/industry_compare` 对非法 `limit`（非整数）走 try/except 返回 500（带 `str(e)` 但不含栈），违反"4xx for user input"原则 | `curl '/api/index_analysis?index_code=000300&limit=abc'` → 500 | 在 `int(...)` 前显式校验 / 用 `request.args.get(type=int, default=30)`，并对 None 返回 400 |
| DEF-01e-04 | 健壮性（轻） | `/api/capital_flow` 当 `market_type` 为空时跳过 `validate_stock_code`，可能将非法 stock_code 直接透传给下游 analyzer | 阅读 `web_server.py` line 1933-1957 | 强制 `market_type` 默认 `A` 并始终校验 stock_code |

说明：DEF-01e-01 / 02 不阻塞本批通关；本报告通过 fixture / 测试类注释固化路径偏差，保证后续 Roadmap 修正时本批用例可自然失败提示。

## 6. 结论

通关。31 个用例全部通过，覆盖 11 条业务分析路由（含 2 条因任务列路径不存在改用真实路由替代）。
- 所有内部分析器（StockAnalyzer / EtfAnalyzer / FundamentalAnalyzer / CapitalFlowAnalyzer / ScenarioPredictor / IndexIndustryAnalyzer / StockQA / RiskMonitor）均经 `patched_analyzers` fixture 打桩，无真实 LLM / akshare / 外部 IO 调用。
- 路由层参数转发已通过 `calls` 收集与精确断言（如 `assert patched_analyzers["scenario"] == [("600519", "A", 90)]`）。
- 错误路径 4xx 响应均经 `_no_stacktrace()` 断言不泄露 Python 堆栈关键字。

阻断项：无。

## 7. 时间锚点

- 开始：2026-05-17 20:08:00 +08:00
- 结束：2026-05-17 20:16:08 +08:00
- 基准时间源：本机系统时间 `date "+%Y-%m-%d %H:%M:%S +08:00"`（Asia/Singapore, +08:00），由 0. 时间真实性校验区段背书。
