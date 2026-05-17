# 验收报告 - BE-01a 健康 + 分析核心 8 路由测试

| 项 | 值 |
|---|---|
| 报告ID | BE-01a |
| 域 | 后端 / Flask 路由 / 健康探针 + 分析三件套 |
| 执行时间 | 2026-05-17 19:45:32 +08:00 ~ 2026-05-17 19:59:23 +08:00 |
| 状态 | 通关 (18/18 PASS) |

## 1. 测试范围

本批严格限定 8 条路由（精确签名核对自 `app/web/web_server.py`）：

| # | 方法 | 路径 | 源码行号 | 备注 |
|---|---|---|---|---|
| 1 | GET | `/` | 569 | `index` HTML 页面 |
| 2 | GET | `/health` | 3770 | JSON 健康探针 |
| 3 | GET | `/api/health` | （不存在） | 仓库未注册，固化"404 占位" |
| 4 | GET | `/api/adapters/status` | 3781 | 22 适配器 health_check |
| 5 | GET | `/api/registry/stats` | 3802 | 注册中心 16 域统计 |
| 6 | POST | `/api/start_stock_analysis` | 753 | 启动分析；返回 task_id |
| 7 | GET | `/api/analysis_status/<task_id>` | 827 | 查询任务状态 |
| 8 | POST | `/api/cancel_analysis/<task_id>` | 857 | 取消任务 |

测试文件：`tests/backend/api/test_health_and_analysis_routes.py`（260 行，18 用例）

Mock 策略（LLM/akshare/真实 HTTP 全屏蔽）：
- `app.web.web_server.analyzer.perform_enhanced_analysis` → 同步返回假结果，不触发 akshare/LLM
- `app.web.web_server._hc_one` → 不对 22 个 adapter 做真实 health_check（每个 5s 超时，最坏 110s 阻塞）；测试中替换为 1ms 返回
- `flask_client` fixture（来自 root `conftest.py`）已注入 `TESTING=True`、关闭重定向、可控 session

## 2. 测试矩阵

| 用例 ID | 路由 | 类型 | 用例 | 结果 |
|---|---|---|---|---|
| BE-01a-T01 | GET / | happy | `test_index_returns_html_ok` 返回 200 + text/html | PASS |
| BE-01a-T02 | GET / | error | `test_index_wrong_method` POST 应被拒 | PASS |
| BE-01a-T03 | GET /health | happy | `test_health_ok_schema` schema 校验（status/uptime_s/version/ts） | PASS |
| BE-01a-T04 | GET /health | error | `test_health_wrong_method` POST 405/404 | PASS |
| BE-01a-T05 | GET /api/health | absent | `test_api_health_returns_404` 路由不存在 | PASS |
| BE-01a-T06 | GET /api/health | absent | `test_api_health_post_also_404` POST 同样 404/405 | PASS |
| BE-01a-T07 | GET /api/adapters/status | happy | `test_adapters_status_ok` schema + 内部计数一致性 (`healthy+unhealthy==total`) | PASS |
| BE-01a-T08 | GET /api/adapters/status | error | `test_adapters_status_wrong_method` POST 拒绝 | PASS |
| BE-01a-T09 | GET /api/registry/stats | happy/受控 | `test_registry_stats_ok` 200 或受控 500（不可 leak stacktrace） | PASS |
| BE-01a-T10 | GET /api/registry/stats | error | `test_registry_stats_wrong_method` POST 拒绝 | PASS |
| BE-01a-T11 | POST /api/start_stock_analysis | happy | `test_start_happy_path_returns_task_id` 返回 task_id 字符串 | PASS |
| BE-01a-T12 | POST /api/start_stock_analysis | error | `test_start_missing_body_returns_400` 空 body 400 | PASS |
| BE-01a-T13 | POST /api/start_stock_analysis | error | `test_start_missing_stock_code_returns_400` 缺字段 400 | PASS |
| BE-01a-T14 | POST /api/start_stock_analysis | error | `test_start_invalid_stock_code_returns_400` 非法代码 400 | PASS |
| BE-01a-T15 | GET /api/analysis_status/<id> | error | `test_status_unknown_task_returns_404` 未知任务 404 | PASS |
| BE-01a-T16 | GET /api/analysis_status/<id> | happy | `test_status_after_start_returns_schema` 字段 id/status/progress/created_at/updated_at | PASS |
| BE-01a-T17 | POST /api/cancel_analysis/<id> | error | `test_cancel_unknown_task_returns_404` 未知任务 404 | PASS |
| BE-01a-T18 | POST /api/cancel_analysis/<id> | happy | `test_cancel_after_start_returns_message` 返回 message | PASS |

## 3. 执行记录

命令：
```bash
cd /Users/panda/Downloads/StockAnal_Sys
timeout 180 pytest tests/backend/api/test_health_and_analysis_routes.py -v 2>&1 | tee tests/audit/evidence/BE-01a_pytest.log
```

最末关键行：
```
======================= 18 passed, 11 warnings in 5.29s ========================
```

完整日志：`tests/audit/evidence/BE-01a_pytest.log`（76 行）

用时：pytest 内核 5.29s；包含首次定位、修 fix（增加 `patched_hc_one` mock）、复跑全过程在 14 分钟内（19:45~19:59 +08:00）。

### 过程中遇到的阻塞与修复

首跑卡死在 `TestAdaptersStatusRoute::test_adapters_status_ok`。诊断：
- `app/web/web_server.py:3781 adapters_status()` 顺序遍历 `_ADAPTER_SPECS`（22 个 adapter），逐个 `_hc_one(..., timeout_s=5.0)`。
- 在 CI/测试环境下，部分 adapter 涉及真实网络/凭据，最坏阻塞 ≈ 22 × 5s = 110s，超过 pytest 默认无超时容忍。

修复（不改业务代码，只改测试 mock）：在 `TestAdaptersStatusRoute` 上注入 `patched_hc_one` fixture，monkeypatch `ws._hc_one` 为 1ms 假实现，保留 schema/计数一致性断言。

## 4. 结果统计

- 总用例：18
- 通过：18
- 失败：0
- 错误：0
- 跳过：0
- 覆盖路由：8/8（其中 `/api/health` 固化为"不存在"占位）
- 覆盖率：未单独跑 coverage（本批为路由连通性验证，coverage 由 BE-01 全量批次统一统计）

## 5. 缺陷清单

| ID | 等级 | 描述 | 复现 | 建议 |
|---|---|---|---|---|
| BE-01a-D01 | 中 | `GET /api/adapters/status` 在生产/测试环境下可能阻塞最长 ≈ 110s（22 adapter × 5s 顺序）；无并发、无总体超时。 | `curl http://host/api/adapters/status`，当某 adapter 网络/凭据异常时观察响应时长。 | 改造为线程池并发 health_check + 整体超时（如 6s 硬上限），或返回缓存的最近一次结果 + `ttl`。 |
| BE-01a-D02 | 低 | `/api/health` 路由未注册，但 coordinator/索引/文档中曾出现该路径，造成歧义。 | `curl http://host/api/health` → 404 | 二选一：在文档中明确"健康端点仅 `/health`"；或在 `web_server.py` 增加 `@app.route('/api/health')` 作为 `/health` 的别名。 |

无 P0/P1 阻断项。无 500 stacktrace 泄露。错误路径全部返回结构化 JSON。

## 6. 结论

通关。BE-01a 小批量验证通过，测试链路（root `conftest.py` 的 `flask_client` + monkeypatch fixture）在 Flask 路由测试场景下工作正常。本批不引入业务代码变更，仅在测试层 mock 慢调用。

阻断项：无。

建议后续批次（BE-01b 等）：
- 沿用 `patched_hc_one` / `patched_analyzer` 这类"内部慢调用 mock"模式
- 对所有可能触发真实网络的路由统一加 mock fixture，避免 CI 间歇性挂起

## 7. 时间锚点

- 开始：2026-05-17 19:45:32 +08:00
- 结束：2026-05-17 19:59:23 +08:00
- 基准时间来源：本机 `date` + Cloudflare HTTPS `Date` 响应头双源校验，偏差 ≈ 3s（阈值 100s 内，通过）
- 时区：Asia/Singapore (+08:00)
