# 验收报告 - BE-01c Agent 异步分析 + HITL 路由测试

| 项 | 值 |
|---|---|
| 报告ID | BE-01c |
| 域 | Backend API · Agent 异步分析 / HITL 审批 |
| 执行时间 | 2026-05-17 21:32:00 +08:00 ~ 2026-05-17 21:47:00 +08:00 |
| 状态 | ✅ 通关（16/16） |

## 1. 测试范围

覆盖 `app/web/web_server.py` 中以下路由（行号锚点据 routes_raw.txt + grep 验证）：

| 序 | 路由 | 方法 | 行号 | 状态 |
|---|---|---|---|---|
| 1 | `/api/start_agent_analysis` | POST | 2483 | 存在，已测 |
| 2 | `/api/agent_analysis_status/<task_id>` | GET | 2665 | 存在，已测 |
| 3 | `/api/agent_analysis_result/<task_id>` | GET | — | 路由不存在（结果由 status 接口的 `result` 字段返回）；以 404 兜底断言 |
| 4 | `/api/agent_submit_approval` | POST | 2762 | 存在，已测（approve/reject 双路径） |
| 5 | `/api/agent_pending_approvals` | GET | 2751 | 存在，已测 |
| 6 | `/api/agent_analysis_history` | GET | 2691 | 存在，已测 |
| 7 | `/api/agent_memory/<stock_code>` | GET | — | 路由不存在；以 404 兜底断言并登记缺口 |
| 8 | `/api/agent_reflections/<stock_code>` | GET | — | 路由不存在；以 404 兜底断言并登记缺口 |

测试文件：`tests/backend/api/test_agent_async_routes.py`

## 2. 测试矩阵

| 用例 ID | 能力 | 类型 | 关键断言 | 结果 |
|---|---|---|---|---|
| BE-01c-T01 | start_agent_analysis happy | unit | 200 + task_id + status∈{pending,running} + coordinator.run_agent_analysis 被异步线程调用 | ✅ |
| BE-01c-T02 | start_agent_analysis 非法股票码 | unit | 400 + error | ✅ |
| BE-01c-T03 | start_agent_analysis 缺失股票码 | unit | 400 + error | ✅ |
| BE-01c-T04 | agent_analysis_status 命中已落盘任务 | unit | 200 + id/progress/params 字段齐 | ✅ |
| BE-01c-T05 | agent_analysis_status 不存在 | unit | 404 + error | ✅ |
| BE-01c-T06 | agent_analysis_result 路由不存在 | unit | 404（路由未注册） | ✅ |
| BE-01c-T07 | agent_submit_approval approve 路径 | unit+event | 200 + approved=True + EventBus 推 EVENT_APPROVAL_NEEDED + content 含 'approved' | ✅ |
| BE-01c-T08 | agent_submit_approval reject 路径 | unit+event | 200 + approved=False + EventBus 推 EVENT_APPROVAL_NEEDED + content 含 'rejected' | ✅ |
| BE-01c-T09 | agent_submit_approval 缺 task_id | unit | 400 + error | ✅ |
| BE-01c-T10 | agent_submit_approval 未知 task | unit | 404 + error | ✅ |
| BE-01c-T11 | agent_pending_approvals 命中 | unit | 200 + approvals 列表含注入 task_id | ✅ |
| BE-01c-T12 | agent_pending_approvals 空列表 | unit | 200 + `{approvals: []}` | ✅ |
| BE-01c-T13 | agent_analysis_history happy | unit | 200 + completed/failed 入列、running 不入列 | ✅ |
| BE-01c-T14 | agent_analysis_history 内部异常 | unit | 500 + error | ✅ |
| BE-01c-T15 | agent_memory 路由不存在 | unit | 404 | ✅ |
| BE-01c-T16 | agent_reflections 路由不存在 | unit | 404 | ✅ |

## 3. 执行记录

```
$ pytest tests/backend/api/test_agent_async_routes.py -v 2>&1 | tee tests/audit/evidence/BE-01c_pytest.log
...
======================= 16 passed, 11 warnings in 5.04s ========================
```

外部依赖与 IO mock：
- `app.agents.coordinator.run_agent_analysis` → MagicMock（避免真实 LangGraph 编译）
- `app.core.event_bus.EventBus().publish` → 本地 monkeypatch spy 包装（侧录事件）
- 任务持久化使用 `agent_session_manager.save_task / delete_task` 临时落盘，测试后清理
- 全程未触达 akshare/openai 等真实外部源

## 4. 结果统计

- 通过：16
- 失败：0
- 跳过：0
- 用时：5.04s

## 5. 缺陷清单

| ID | 等级 | 描述 | 复现 | 建议 |
|---|---|---|---|---|
| BE-01c-D01 | 中 | 缺失 `GET /api/agent_analysis_result/<task_id>` 路由；前端如需独立"结果"接口需在 web_server.py 中注册（当前通过 `agent_analysis_status` 的 `result` 字段返回） | T06 直接 GET 该路径返回 404 | 在 web_server.py 增补只读 result 端点，或在文档中明确以 status.result 为唯一出口 |
| BE-01c-D02 | 中 | 缺失 `GET /api/agent_memory/<stock_code>` 路由；CLAUDE.md 与前端 spec 提及该能力 | T15 GET 返回 404 | 评估 long_term_memory 暴露需求并补全或下线 spec |
| BE-01c-D03 | 中 | 缺失 `GET /api/agent_reflections/<stock_code>` 路由 | T16 GET 返回 404 | 同上 |
| BE-01c-D04 | 低 | 全局 fixture `mock_event_bus`（conftest.py:191）引用了不存在的 `eb_mod.event_bus` 模块级单例，会导致依赖该 fixture 的测试 setup 阶段 AttributeError | 将该 fixture 应用于任意测试用例即触发 | 修复 fixture：改为 `monkeypatch.setattr(EventBus(), 'publish', ...)` 直接拦截单例实例 |
| BE-01c-D05 | 低 | `/api/start_agent_analysis` 返回 status='pending'，但 docstring/前端注释多处提到 'running'，存在字面不一致风险 | T01 实测返回 pending | 统一首次返回值为 'pending'，并在 OpenAPI/前端 spec 同步 |

## 6. 结论

通关。

- 5 条真实存在的路由（启动/状态/历史/pending/submit）功能与错误分支均验证；
- HITL approve / reject 双路径分别覆盖，并通过对 EventBus 单例的 publish spy 断言 `EVENT_APPROVAL_NEEDED` 事件按预期推送；
- 3 条 spec 中提及但代码未实现的路由（result / memory / reflections）作为缺口登记 D01–D03；
- 顺带发现公共 fixture 缺陷 D04 与状态名一致性问题 D05。

阻断项：无。

## 7. 时间锚点

- 开始：2026-05-17 21:32:00 +08:00
- 结束：2026-05-17 21:47:00 +08:00

## 8. 证据

- 测试源：`tests/backend/api/test_agent_async_routes.py`
- 执行日志：`tests/audit/evidence/BE-01c_pytest.log`
- 路由清单：`tests/audit/evidence/routes_raw.txt`
- 行号参照：`app/web/web_server.py` lines 2483 / 2665 / 2691 / 2751 / 2762
- HITL 实现：`app/agents/hitl.py`（`approval_manager` 单例，`submit_approval` 在第 106 行触发 `_publish_approval_event` → `EVENT_APPROVAL_NEEDED`）
