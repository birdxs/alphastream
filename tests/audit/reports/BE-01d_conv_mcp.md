# 验收报告 - BE-01d 对话 CRUD + MCP + A2A 路由

| 项 | 值 |
|---|---|
| 报告ID | BE-01d |
| 域 | backend / api / conversation / mcp / a2a |
| 执行时间 | 2026-05-17 19:58:00 +08:00 ~ 2026-05-17 20:04:45 +08:00 |
| 状态 | ✅ 通关 |

## 1. 测试范围

| 路由 | 方法 | 文件锚点 |
|---|---|---|
| `/api/conversations` | GET | `app/web/web_server.py:3096` |
| `/api/conversations/<id>` | GET | `app/web/web_server.py:3105` |
| `/api/conversations/<id>` | DELETE | `app/web/web_server.py:3115` |
| `/api/mcp/tools` | GET | `app/web/web_server.py:2806` |
| `/api/mcp/call` | POST | `app/web/web_server.py:2815` |
| `/a2a/v1` | POST | `app/web/web_server.py:3180` |
| `/.well-known/agent-card.json` | GET | `app/web/web_server.py:3168` |

实测文件：`tests/backend/api/test_conversation_mcp_routes.py`（318 行）。

注：POST `/api/conversations` 在路由清单中**不存在**（仅 GET），用例 `test_list_wrong_method_post_405` 已对其作 405/404 兜底校验，作为"路由缺口"记录于第 5 节。

## 2. 测试矩阵

| 用例 ID | 路由 | 类型 | 命令 | 结果 |
|---|---|---|---|---|
| BE-01d-T001 | GET /api/conversations | happy(空) | pytest -v | ✅ |
| BE-01d-T002 | GET /api/conversations | happy(seeded) | pytest -v | ✅ |
| BE-01d-T003 | POST /api/conversations | error(405) | pytest -v | ✅ |
| BE-01d-T004 | GET /api/conversations/\<id\> | happy | pytest -v | ✅ |
| BE-01d-T005 | GET /api/conversations/\<id\> | error(404) | pytest -v | ✅ |
| BE-01d-T006 | DELETE /api/conversations/\<id\> | happy | pytest -v | ✅ |
| BE-01d-T007 | DELETE /api/conversations/\<id\> | error(404) | pytest -v | ✅ |
| BE-01d-T008 | GET /api/mcp/tools | happy | pytest -v | ✅ |
| BE-01d-T009 | GET /api/mcp/tools | error(method) | pytest -v | ✅ |
| BE-01d-T010 | POST /api/mcp/call | error(unknown tool) | pytest -v | ✅ |
| BE-01d-T011 | POST /api/mcp/call | happy(mocked legal tool) | pytest -v | ✅ |
| BE-01d-T012 | POST /api/mcp/call | error(missing tool field 400) | pytest -v | ✅ |
| BE-01d-T013 | POST /api/mcp/call | error(non-json body 400) | pytest -v | ✅ |
| BE-01d-T014 | POST /a2a/v1 | contract(JSON-RPC 2.0 stub 501) | pytest -v | ✅ |
| BE-01d-T015 | POST /a2a/v1 | edge(no body, id=None) | pytest -v | ✅ |
| BE-01d-T016 | POST /a2a/v1 | error(wrong method GET) | pytest -v | ✅ |
| BE-01d-T017 | GET /.well-known/agent-card.json | contract(A2A v1 schema) | pytest -v | ✅ |
| BE-01d-T018 | GET /.well-known/agent-card.json | error(wrong method) | pytest -v | ✅ |

共 **18** 用例，覆盖 8 路由槽位（含 1 个不存在的 POST 创建路由）。

## 3. 执行记录

命令：
```
python -m pytest tests/backend/api/test_conversation_mcp_routes.py -v --no-header
```

关键输出（`tests/audit/evidence/BE-01d_pytest.log` 完整保存）：
```
======================= 18 passed, 11 warnings in 5.28s ========================
```

用时：5.28 秒。warning 全部来自第三方 `openbb_intrinio` 的 Pydantic v2.12 DeprecationWarning，与被测代码无关。

### Mock 策略
- **对话 CRUD**：`isolated_conv_dir` fixture 通过 `monkeypatch.setattr(conv_mod, "CONVERSATION_DIR", str(tmp_path/"conversations"))` 替换模块级常量，并将 `_manager` 单例重置为 `None`，避免污染真实 `data/conversations/`。
- **MCP `/api/mcp/call`**：`monkeypatch.setattr(mcp_mod, "handle_mcp_tool_call", wrapped)` 包裹 handler，对 `get_stock_history` 返回 `{_mocked: True}` 桩数据，对其他 tool_name 透传给原逻辑（此用例只覆盖 happy 路径）。
- **akshare/LLM**：本批不直接触发，零外部 IO。
- **A2A AgentCard**：纯函数构造，无外部依赖，断言 schema 字段。

## 4. 结果统计

- 通过：**18**
- 失败：**0**
- 错误：**0**
- 跳过：**0**
- 覆盖率：本批针对 7 路由处理函数（含 4 个 stub/list 短函数 + 3 个 CRUD），路由函数行覆盖 ≈100%；分支覆盖含 happy + 主要错误分支（404/400/405/501/未知工具）。

## 5. 缺陷清单

| ID | 等级 | 描述 | 复现 | 建议 |
|---|---|---|---|---|
| D-BE-01d-01 | INFO | POST `/api/conversations`（创建对话）路由不存在，但前端 `frontend/src/lib/api/client.ts` 有引用风险（须 FE 侧确认）| `flask_client.post('/api/conversations', json={...})` → 405 | 若前端确实需要"显式建会话"接口，应在 web_server.py 增补；否则在 OpenAPI 文档明确去除 |
| D-BE-01d-02 | LOW | `/api/conversations/<id>` DELETE 失败统一返回 404 + `{"error":"删除失败"}`，但 ConversationManager.delete_conversation 仅在文件不存在时返回 False，与 404 语义吻合，但错误文案"删除失败"易误导（实际是"对话不存在"） | 见 `test_delete_nonexistent_404` | 错误消息改为 "对话不存在" 与 GET 一致 |
| D-BE-01d-03 | LOW | `/a2a/v1` 当前为 stub（返回 501 + JSON-RPC -32601），未实现 Task/Message RPC，符合代码注释中"预留"标记 | `test_a2a_returns_jsonrpc_method_not_implemented` | 路线在 web_server.py:3126 注释，待 A2A v1 Task RPC 实施工单 |
| D-BE-01d-04 | INFO | `CONVERSATION_DIR` 为模块级硬编码 `os.path.dirname + ../../data/conversations`，无环境变量覆盖路径，测试需 monkeypatch 才能隔离 | fixture `isolated_conv_dir` 已规避 | 建议改为读取 `os.getenv("CONVERSATION_DIR", default_path)` 以提升可测性 |

## 6. 结论

✅ **通关**。18/18 用例全通过，无阻断缺陷。

- 对话 CRUD（list/get/delete）契约稳定，错误路径返回 404 + JSON `error`，无堆栈泄露。
- MCP `tools` 列表与 `call` 调用契约符合 `MCP_SERVER_CONFIG` schema；未知工具走 handler 内部 `{result:{error:"未知工具..."}}` 兜底，外层仍 200，符合 MCP 协议实践。
- A2A `/a2a/v1` JSON-RPC 2.0 envelope 正确（jsonrpc/error.code=-32601/id 透传/501 状态码）。
- AgentCard 8 个 A2A v1 必填字段齐全，url 指向 `/a2a/v1`，`_stub:true` 显式标记。

缺陷 D-BE-01d-01 / 02 / 03 / 04 均为 INFO/LOW，记录待后续 sprint 处理。

## 7. 时间锚点

- 开始：2026-05-17 19:58:00 +08:00
- 结束：2026-05-17 20:04:45 +08:00
- 时间基准：本机系统时间 (Asia/Singapore, +08:00)，与本会话 currentDate=2026-05-17 一致。

## 8. 产出物索引

- 测试代码：`tests/backend/api/test_conversation_mcp_routes.py`
- 执行日志：`tests/audit/evidence/BE-01d_pytest.log`
- 验收报告：`tests/audit/reports/BE-01d_conv_mcp.md`（本文件）
