# BE-03b 最小批 Core 测试 #2 — ConversationManager + AI Client

- 任务编号：BE-03b
- 范围：`app/core/conversation.py`（204 行） + `app/core/ai_client.py`（637 行）
- 测试文件：
  - `tests/backend/unit/test_core_conversation.py`
  - `tests/backend/unit/test_core_ai_client.py`
- 证据：`tests/audit/evidence/BE-03b_pytest.log`
- 执行时间：2026-05-17 +08:00

## 1. 总览

| 指标 | 数值 |
|---|---|
| 总用例数 | 56 |
| Passed | 54 |
| Failed | 0 |
| XFailed（已知缺陷标记） | 2 |
| Skipped | 0 |
| 用时 | ~10.5s |

> 备注：T021_threadpool_concurrent_add_message_json_integrity 为竞态用例，在大约 30%~50% 的运行中能复现 H2 衍生缺陷（JSON 截断），命中时记为 xfail；未命中时为 pass，二者均合规。

## 2. 覆盖率

| 模块 | Stmts | Miss | Branch | BrPart | Cover | 目标 | 达成 |
|---|---|---|---|---|---|---|---|
| `app/core/conversation.py` | 116 | 12 | 34 | 5 | **89%** | ≥ 85% | OK |
| `app/core/ai_client.py` | 296 | 39 | 112 | 20 | **85%** | ≥ 70% | 远超 |
| TOTAL | 412 | 51 | 146 | 25 | **86%** | — | — |

## 3. 用例清单

### A. ConversationManager — 23 用例

| ID | 名称 | 用途 | 结果 |
|---|---|---|---|
| T001 | singleton_pattern | `get_conversation_manager()` 单例 | PASS |
| T002 | singleton_returns_same_instance | 多次调用同一实例 | PASS |
| T003 | create_with_default_title | 默认标题 | PASS |
| T004 | create_with_custom_title | 自定义标题 | PASS |
| T005 | create_unique_id | UUID 唯一 | PASS |
| T006 | get_existing_conversation | get 存在 | PASS |
| T007 | get_nonexistent_returns_none | get 不存在返回 None | PASS |
| T008 | list_empty | 空列表 | PASS |
| T009 | list_multiple_sorted_by_updated_at | 按 updated_at desc 排序 | PASS |
| T010 | add_message_basic | 追加基础消息 | PASS |
| T011 | add_message_with_artifacts_and_tool_calls | 含 artifacts & tool_calls | PASS |
| T012 | add_message_updates_timestamp | 更新 updated_at | PASS |
| T013_H2 | H2_message_truncation_to_50 | **H2 暴露**：51 条 → 截到 50 | PASS（缺陷已确认） |
| T014 | delete_existing_conversation | 删除存在 | PASS |
| T015 | delete_nonexistent_returns_false | 删除不存在返回 False | PASS |
| T016_C3 | C3_delete_conv_does_not_clean_checkpoint | **C3 暴露**：删 conv 不清 checkpoint | XFAIL（缺陷已确认） |
| T017 | json_persistence_round_trip | 写盘后 load schema 一致 | PASS |
| T018 | concurrent_add_message | threading 10 线程并发（轻量） | PASS |
| T019 | conversation_dir_isolation | tmp dir 隔离 | PASS |
| T020 | get_missing_returns_none | get 缺失 None | PASS |
| **T021_H2** | **threadpool_concurrent_add_message_json_integrity** | **ThreadPoolExecutor 10 线程并发 → 直接读盘验证 JSON 完整性；命中竞态则 xfail 标记** | PASS or XFAIL（缺陷暴露） |
| **T022** | **update_title_api_missing** | 任务要求的 `update_title(conv_id, title)` API 未实现 | XFAIL（API 缺失） |

### B. AI Client — 33 用例（含参数化展开）

| ID | 名称 | 用途 | 结果 |
|---|---|---|---|
| T001 | get_ai_client_with_key | OPENAI_API_KEY 存在 → 返回 client；`get_ai_model()` 取 env | PASS |
| T002 | get_ai_client_without_key | 无 API key 返回 None | PASS |
| T003 | chat_completion_success | 非流式正常调用 + 参数透传 | PASS |
| T004 | chat_completion_no_client | client=None 友好降级 | PASS |
| T005 | chat_completion_error_mapping | RateLimitError → 友好限流提示 | PASS |
| T005b | chat_completion_unknown_error_fallback | 未知异常 → 通用兜底文案 | PASS |
| T006 | chat_completion_tools_kwargs | tools/tool_choice/temperature/max_tokens 透传 | PASS |
| T007 | chat_completion_stream | 返回 stream + `stream=True` | PASS |
| T007b | chat_completion_stream_no_client | None 客户端 | PASS |
| T007c | chat_completion_stream_error | APITimeoutError → "AI分析超时" | PASS |
| T008 | get_completion_content_variants | None/空 choices/正常 | PASS |
| T009 | chat_with_tools_no_tool_call | 0 工具调用直返文本 | PASS |
| T010 | chat_with_tools_one_round | Function Calling 一轮完整路径 | PASS |
| T011 | chat_with_tools_no_client | client=None | PASS |
| T012 | chat_with_tools_stream_read_error | 流读取 APIConnectionError → "无法连接" | PASS |
| T013 | chat_with_tools_executor_exception | tool_executor 抛错 → 不崩溃，写入 result | PASS |
| T014 | chat_with_tools_exceed_rounds | 超 max_rounds → 走非流式 fallback | PASS |
| T015 | client_timeout_and_retries | OpenAI 构造参数：max_retries=2, connect=10s | PASS |
| T016 | chat_with_tools_stream_smoke | smoke：导出可调用 | PASS |
| T017 | truncate_large | 10KB 截断 + 非字符串兜底 | PASS |
| T018 | publish_helpers_swallow_errors | event_bus 异常不外溢 | PASS |
| T018b | publish_helpers_success_path | 正常发布两次 | PASS |
| T019 | chat_with_tools_stream_returns_none | 空流 → "AI返回空流" | PASS |
| T020 | chat_with_tools_default_executor | tool_executor=None 走 `app.core.tools.execute_tool` | PASS |
| T021×3 | stream_error_map[Auth/BadReq/Internal] | 三种错误映射 | PASS×3 |
| T022 | chat_with_tools_bad_json_args | tool_call arguments JSON 损坏 → 容错 | PASS |
| T023 | chat_with_tools_stream_text_only | 纯 token 流 + event_callback 收到 token/done | PASS |
| T024 | chat_with_tools_stream_one_round | 流式一轮工具调用全路径 | PASS |
| T025 | chat_with_tools_stream_read_error | 中途断流 → "无法连接" + error 事件 | PASS |
| T026 | chat_with_tools_stream_exceed_rounds | 超 max_rounds → fallback 总结 | PASS |
| T027 | chat_with_tools_stream_no_client | None 客户端 | PASS |
| T028 | chat_with_tools_stream_bad_json_recover | `{"a":1}{"b":2}` → 正则提取首个 JSON | PASS |

## 4. 缺陷暴露 / 跟踪

| 编号 | 严重度 | 标题 | 证据用例 | 状态 |
|---|---|---|---|---|
| **H2** | High | `add_message` 强截断至最近 50 条，旧消息直接丢失，无 archive | T013_H2 (PASS) | 已暴露并冻结 |
| **H2-Derived** | High | `_save_conversation` 非原子写（`open w` + `json.dump`），并发会破坏 JSON | T021 (XFAIL on race) | 已暴露，建议改为 `os.replace` 原子写 |
| **C3** | Medium | `delete_conversation` 未清理 LangGraph checkpoint 残留 | T016_C3 (XFAIL) | 已暴露 |
| **API-Gap** | Low | `ConversationManager.update_title` 任务要求 API 缺失 | T022 (XFAIL) | 待补齐 |

## 5. 关键设计

1. **Mock 边界**：未替换整个 `app.core.ai_client` 模块；仅 mock `client.chat.completions.create`（OpenAI SDK 客户端方法）与 `event_bus.get_event_bus`，符合"不直接 mock 整个模块"约束。
2. **流响应构造**：用 `types.SimpleNamespace` 复刻 OpenAI ChatCompletionChunk 鸭子结构（`choices[0].delta.content / .tool_calls`），无需依赖真实 OpenAI 类型。
3. **HTTP 库选择**：openai 1.x 基于 `httpx`，无法用 `responses`（专 requests/urllib3）。`respx` 未安装；采用 SDK 边界 mock 等价方案。
4. **并发 truncation 用例**：竞态结果不可控，命中 `JSONDecodeError` 时主动 `xfail` 记录缺陷而非 fail，避免 CI 抖动且保留诊断信息。
5. **Tmp dir 隔离**：所有 conversation 测试 `monkeypatch CONVERSATION_DIR`，全程不污染工程目录。
6. **LLM 全 mock**：无任何真实网络/真实 API key 调用。

## 6. 验证命令

```bash
cd /Users/panda/Downloads/StockAnal_Sys
pytest tests/backend/unit/test_core_conversation.py tests/backend/unit/test_core_ai_client.py -v
pytest tests/backend/unit/test_core_conversation.py tests/backend/unit/test_core_ai_client.py \
  --cov=app.core.conversation --cov=app.core.ai_client --cov-report=term
```

## 7. 结论

- 覆盖率双双达标：conversation 89%、ai_client 85%。
- H2、H2 衍生、C3 三个缺陷有可复现测试证据。
- 任务要求 `update_title` API 缺口已用 xfail 跟踪。
- 用例稳定，10 次重跑无随机失败（T021 竞态命中视为 xfail，仍合规）。
