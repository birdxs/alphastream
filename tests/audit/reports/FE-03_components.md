# FE-03 前端关键组件测试报告

- 时间：2026-05-17 +08:00
- 工程目录：`/Users/panda/Downloads/StockAnal_Sys/`
- 执行器：vitest@vitest-config(frontend/vitest.config.ts) · jsdom · @testing-library/react · userEvent
- 命令：`cd frontend && npx vitest run ../tests/frontend/components/ --reporter=verbose`
- 日志：`tests/audit/evidence/FE-03_vitest.log`

## 总览

| 指标 | 数值 |
|---|---|
| 测试文件 | 8 |
| 用例总数 | 32 |
| 通过 | 32 |
| 失败 | 0 |
| 跳过 | 0 |

## 覆盖矩阵

| # | 组件 | 路径 | 用例数 | 关键场景 |
|---|---|---|---:|---|
| 1 | ChatInput | `frontend/src/components/chat/chat-input.tsx` | 4 | 点击发送→onSend；Ctrl+Enter；附件 createObjectURL；unmount→revokeObjectURL |
| 2 | ConversationSidebar | `frontend/src/components/chat/conversation-sidebar.tsx` | 2 | 加载列表；二次点击确认删除→DELETE /api/conversations/:id；回归无 `window.location.reload` |
| 3 | MessageBubble | `frontend/src/components/chat/message-bubble.tsx` | 3 | user/assistant 渲染；artifacts Badge 标签 + 占位提示 |
| 4 | ArtifactRenderer | `frontend/src/components/chat/artifact-renderer.tsx` | 6 | decision_card / news_feed / risk_gauge / candlestick_chart / search_results 5 类命中 + unknown 兜底不白屏 |
| 5 | AgentProgressPanel | `frontend/src/components/agent/agent-progress-panel.tsx` | 4 | 空 store→null；isAnalyzing 主标题+百分比；agentProgresses 完成计数；events 计数 |
| 6 | ToolCallCard | `frontend/src/components/agent/tool-call-card.tsx` | 5 | 已知工具名→中文映射；未知名兜底；执行中/完成/失败状态 |
| 7 | ErrorBoundary | `frontend/src/components/common/error-boundary.tsx` | 4 | 正常 children；默认 fallbackTitle；自定义 fallbackTitle；不传染外层 |
| 8 | NetworkStatus | `frontend/src/components/common/network-status.tsx` | 4 | online 默认；offline 事件切换；fetch 探测；online 恢复 |

## 关键回归点

- **ConversationSidebar 删除不触发 reload**（工作区改动 `web/conversation-sidebar.tsx` 移除 `window.location.reload` 后的回归保护）：用例显式断言 `reloadSpy not called`。
- **ChatInput Blob URL 生命周期**（工作区改动 `chat-input.tsx` 增加 unmount revoke 清理）：测试同时验证 `URL.createObjectURL`（附件上传时）与 `URL.revokeObjectURL`（unmount 时）均被调用。
- **ArtifactRenderer unknown 类型兜底**：投递 `artifact_type='this_type_does_not_exist'` 时容器非空（不白屏）。

## 模拟与依赖隔离

- `apiClient` 通过 `vi.mock('@/lib/api/client')` 全面拦截 get/post/delete。
- chat-store / 各 Zustand store：通过 `useXxxStore.setState()` 直接置入测试数据，或 `vi.mock` 选择器接口。
- `ArtifactCard` / `next/dynamic`：mock 以避开 `html2canvas` 动态 import 与 echarts canvas 在 jsdom 下不可用问题。
- `URL.createObjectURL` / `revokeObjectURL`：jsdom 不实现，测试内 `vi.fn` 桩。

## 修复迭代记录（共 3 轮）

| 轮次 | 通过/失败 | 主要修复点 |
|---|---|---|
| R1 | 17 / 8 | 初版 |
| R2 | 28 / 4 | placeholder 文本对齐；ArtifactCard/next/dynamic mock；ErrorBoundary 真实接口（无 `fallback` prop）；二次确认删除流程 |
| R3 | 32 / 0 | panel 主标题文本对齐（`Multi-Agent 实时数据流`）；events 完整文案；MessageBubble 多匹配项；删除按钮 aria-label 精准选取 |

## 已知非阻断警告

- vitest stderr 出现 "This error originated in conversation-sidebar.test.tsx" 提示，源于异步 fetch mock 在 cleanup 后仍 resolve；最终测试结果均为 PASS，不影响判定。

## 边界

- 严格 8 组件，未触及 layout/charts/ui/welcome 等周边。
- 周期约 18 min（含 3 轮调试）。
