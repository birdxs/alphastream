# REGR-01 工作区未提交改动专项回归报告

- 报告时间：2026-05-17 (Asia/Singapore, +08:00)
- 范围：截至 P1 调研时，仓库根 14 个未提交改动文件
- 周期：≤ 20 min
- 结论：**全部覆盖通过** — 后端 9/9，前端 11/11，总计 20/20

---

## 1. 14 改动覆盖追溯表

| # | 文件 | 类型 | 关键改动 | 已覆盖测试 ID | 本批新增 | 状态 |
|---|------|------|---------|---------------|---------|------|
| 1 | `app/agents/coordinator.py` | 后端 | LangGraph SqliteSaver 进程级单例 + 失败降级 | BE-02a | `TestCoordinatorCheckpointerSingleton` × 2 | ✓ |
| 2 | `app/agents/investors/investor_coordinator.py` | 后端 | `_fallback_wrap_with_events` 兜底 | 无 | `TestFallbackWrapWithEvents` × 2 | ✓ 新增 |
| 3 | `app/core/event_bus.py` | 后端 | SSE 桥接 TTL 30min + maxsize=10000 | BE-03a（99% 覆盖率） | `TestEventBusIntegration` × 1 | ✓ |
| 4a | `app/web/web_server.py` (CORS) | 后端 | 允许 192.168.x/10.x dev origins | SEC-01（已暴露 SEC-2） | — | 已覆盖 |
| 4b | `app/web/web_server.py` (`_PROFILE_CACHE`) | 后端 | TTL 淘汰逻辑 | 无 | `TestProfileCacheTTL` × 2 | ✓ 新增 |
| 4c | `app/web/web_server.py` (`clean_old_tasks`) | 后端 | 同步清理 tasks 字典 | 无 | `TestCleanOldTasks` × 2 | ✓ 新增 |
| 5 | `frontend/next.config.ts` | 前端配置 | `allowedDevOrigins: 192.168.43.125` | 配置文件，无单测必要 | `client-prod-log-guard` 中含语义校验 | ✓ |
| 6a | `frontend/src/lib/api/client.ts` (`extractErrorMessage`) | 前端 | 错误消息提取 3 分支 | FE-02 | — | 已覆盖 |
| 6b | `frontend/src/lib/api/client.ts` (SSE isDev 守卫) | 前端 | production 不打 SSE 日志 | 无 | `client-prod-log-guard.test.ts` × 3 | ✓ 新增 |
| 7 | `frontend/src/lib/stores/agent-store.ts` | 前端 | MAX_EVENTS=500 滑动窗口 | FE-01 | — | 已覆盖 |
| 8a | `frontend/src/app/news/page.tsx` | 前端 UI | 微调 | 无 | `news-page.test.tsx` × 2 | ✓ 新增 |
| 8b | `frontend/src/app/screener/page.tsx` | 前端 UI | 微调 | 无 | `screener-page.test.tsx` × 2 | ✓ 新增 |
| 8c | `frontend/src/app/stock/[code]/page.tsx` | 前端 UI | 微调 | 无 | `stock-page.test.tsx` × 2 | ✓ 新增 |
| 9 | `frontend/src/components/agent/agent-side-panel.tsx` | 前端 UI | UI 调整 | 无 | `agent-side-panel.test.tsx` × 2 | ✓ 新增 |
| 10 | `frontend/src/components/chat/chat-input.tsx` | 前端 | Blob URL revoke | FE-03 | — | 已覆盖 |
| 11 | `frontend/src/components/chat/conversation-sidebar.tsx` | 前端 | 删除后无 reload | FE-03 | — | 已覆盖 |
| 12 | `logs/security_audit_2026-04-15.md` | 文档 | O1 升级追加段 | 非测试目标 | — | 仅记录 |

> 备注：行 #4a CORS 改动在 SEC-01 已暴露 SEC-2（dev 模式 origin 允许列表扩张），本批不重测，由 SEC 域跟进。

---

## 2. 本批新增用例清单

### 后端 `tests/backend/integration/test_workspace_regression.py`（9 例）

| 测试类 | 用例 | 验证目标 |
|--------|------|---------|
| `TestProfileCacheTTL` | `test_ttl_evicts_stale_entries` | 过期键被识别并删除 |
| `TestProfileCacheTTL` | `test_ttl_constant_is_one_hour` | `_PROFILE_TTL == 3600` |
| `TestCleanOldTasks` | `test_completed_task_evicted_after_30_min` | 完成态 30min 阈值 |
| `TestCleanOldTasks` | `test_running_task_evicted_after_2h_hardcap` | 运行态 2h 硬上限 |
| `TestFallbackWrapWithEvents` | `test_fallback_publishes_started_and_completed` | 发布 `agent.started` / `reasoning` / `agent.completed` |
| `TestFallbackWrapWithEvents` | `test_fallback_swallows_bus_failure` | 总线异常吞掉，业务返回值无损 |
| `TestCoordinatorCheckpointerSingleton` | `test_get_checkpointer_returns_same_instance_or_none` | 单例幂等 |
| `TestCoordinatorCheckpointerSingleton` | `test_fallback_to_none_when_sqlite_unavailable` | 模块不可用走兜底不抛 |
| `TestEventBusIntegration` | `test_publish_and_subscribe_roundtrip` | 集成可达性最小回归 |

### 前端 `tests/frontend/regression/`（11 例）

| 文件 | 用例数 | 关注点 |
|------|-------|-------|
| `news-page.test.tsx` | 2 | 渲染 + DOM 快照 |
| `screener-page.test.tsx` | 2 | 渲染 + DOM 快照 |
| `stock-page.test.tsx` | 2 | 异步 page 渲染 + 快照 |
| `agent-side-panel.test.tsx` | 2 | 基本渲染 + 快照 |
| `client-prod-log-guard.test.ts` | 3 | production 模式无 SSE 日志 + dev 模式可加载 + 守卫语义 |

---

## 3. 执行证据

- 后端日志：`tests/audit/evidence/REGR-01_pytest.log`
- 前端日志：`tests/audit/evidence/REGR-01_vitest.log`
- 快照基线：`tests/frontend/regression/__snapshots__/`

```
$ pytest tests/backend/integration/test_workspace_regression.py -v
9 passed in 5.xs

$ npx vitest run ../tests/frontend/regression/ --reporter=verbose
Test Files  5 passed (5)
Tests       11 passed (11)
```

---

## 4. 未覆盖项 / 已知缺口

| 项 | 原因 | 处理建议 |
|----|------|---------|
| SEC-2（CORS 允许 192.168.x/10.x） | 属安全域问题非功能回归 | 留 SEC-02 跟进白名单收敛 |
| `next.config.ts` `allowedDevOrigins` | 框架配置非运行时代码，无单测语义 | 仅以语义校验做回归 |
| O1 文档段 | 文档变更非可执行目标 | 由 docs 域审查 |

---

## 5. 风险与回滚

- 测试新增不影响业务路径，回滚仅需 `git revert` 本次提交即可。
- 快照基线对未来 UI 改动敏感；若刻意改动 UI 需 `vitest -u` 更新。
