# 验收报告 - BE-02b 投资者协调器 + HITL + 4 投资者人格

| 项 | 值 |
|---|---|
| 报告ID | BE-02b |
| 域 | Backend / Agents / 投资者编排 + 人工审批 |
| 执行时间 | 2026-05-17 20:22:00 +08:00 ~ 2026-05-17 20:55:00 +08:00 |
| 状态 | 通关（42/42 用例通过，6/6 模块覆盖率 ≥ 目标） |
| Commit 标签 | `[NEW-FILE:#20260517-01]` |

## 1. 测试范围

| 目标文件 | 行数 | 覆盖率 | 目标 |
|---|---|---|---|
| `app/agents/investors/investor_coordinator.py` | 426 | **81%** | ≥ 80% ✓ |
| `app/agents/hitl.py` | 137 | **81%** | ≥ 80% ✓ |
| `app/agents/investors/buffett.py` | 248 | **80%** | ≥ 70% ✓ |
| `app/agents/investors/munger.py` | 263 | **81%** | ≥ 70% ✓ |
| `app/agents/investors/lynch.py` | 266 | **80%** | ≥ 70% ✓ |
| `app/agents/investors/damodaran.py` | 265 | **82%** | ≥ 70% ✓ |
| **TOTAL** | 1605 | **81%** | — |

## 2. 测试矩阵

### A. InvestorCoordinator (8 用例)

| 用例 ID | 能力 | 类型 | 结果 |
|---|---|---|---|
| A1-T001 | analyze 调用 4 人格并返回 consensus | integration | 通过 |
| A1-T002 | 单投资者异常不阻断整体流程 | integration | 通过 |
| A2-T003 | `_compute_vote_stats` 全 BUY | unit | 通过 |
| A2-T004 | `_compute_vote_stats` 2BUY+2SELL（平票） | unit | 通过 |
| A2-T005 | `_compute_vote_stats` 全 HOLD | unit | 通过 |
| A2-T006 | `_compute_vote_stats` 空 results | unit | 通过 |
| A2-T007 | 忽略非 `investor_` 前缀键 | unit | 通过 |
| A2-T008 | 非法 recommendation 归一化为 HOLD | unit | 通过 |
| A3-T009 | `_build_consensus` mock LLM 返回 JSON | unit | 通过 |
| A3-T010 | `_build_consensus` 空 results -> 默认 HOLD | unit | 通过 |
| A4-T011 | `_fallback_consensus` 多数 BUY | unit | 通过 |
| A4-T012 | `_fallback_consensus` 全 HOLD 强共识 | unit | 通过 |
| A4-T013 | `_fallback_consensus` 分歧场景 | unit | 通过 |
| A4-T014 | LLM 抛错 -> `_build_consensus` 自动降级 | unit | 通过 |
| A4-T015 | chat_completion 返回 error -> 降级 | unit | 通过 |

### B. HITL HumanApprovalManager (6 用例)

| 用例 ID | 能力 | 类型 | 结果 |
|---|---|---|---|
| B1-T101 | `request_approval` 发布 EVENT_APPROVAL_NEEDED（reasoning 通道+[APPROVAL]） | integration | 通过 |
| B2-T102 | `submit_approval(approved=True)` 解除阻塞并标记 approved | integration | 通过 |
| B3-T103 | `submit_approval(approved=False)` 标记 rejected | integration | 通过 |
| B3-T104 | 对未知 task 提交返回 False | integration | 通过 |
| **H1-T105** | **进程重启风险**：新实例 `_pending_approvals` 全部丢失 | integration | **通过（暴露 H1）** |
| H1-T106 | 同进程内两实例字典不共享 | integration | 通过 |

### C. 4 投资者人格（每人 5 用例，共 20）

| 用例 ID | 投资者 | 场景 | 结果 |
|---|---|---|---|
| C-Buf-1 | Buffett | 快乐路径 BUY + 护城河 | 通过 |
| C-Buf-2 | Buffett | LLM 抛错 -> HOLD 兜底 | 通过 |
| C-Buf-3 | Buffett | get_ai_client=None -> HOLD | 通过 |
| C-Buf-4 | Buffett | 完整 state 触发 `_compile_reports` | 通过 |
| C-Buf-5 | Buffett | markdown 围栏 JSON 解析 | 通过 |
| C-Buf-6 | Buffett | 空 content -> HOLD | 通过 |
| C-Mun-1..5 | Munger | 同上 5 场景 | 通过 |
| C-Lyn-1..5 | Lynch | 同上 5 场景 | 通过 |
| C-Dam-1..5 | Damodaran | 同上 5 场景 | 通过 |

## 3. 缺陷与风险暴露

### H1（高危）— HITL 审批状态非持久化

**位置**：`app/agents/hitl.py:47` `self._pending_approvals = {}`

**风险**：所有 pending approval 仅存于进程内存字典。服务重启 / 工作进程切换 / 实例重建后，所有未决审批立即丢失，触发以下二次故障：

1. 已发布到前端的 `[APPROVAL]` 事件无人响应 -> request_approval 阻塞直至 timeout（默认 300s）-> 上游 LangGraph 节点超时失败；
2. 同进程内多实例无法共享状态（B-H1-T106 验证）；
3. 多 worker 部署下，前端 PUT `/approve/{task_id}` 路由到与 request 不同的进程时直接 404 / 返回 False。

**复现证据**：
- `test_hitl.py::TestProcessRestartRisk::test_new_instance_loses_all_pending_approvals` 已通过断言 `mgr_new._pending_approvals == {}` + `len == 0` + `submit_approval(...) is False`。

**修复建议**：
1. 引入持久层（Redis / SQLite checkpoint），与 LangGraph SqliteSaver 同 db；
2. `HumanApprovalManager` 改为模块级单例 + 进程间通过持久层同步；
3. 提供 `recover_pending_on_startup()` 启动钩子。

### M1（中危）— Coordinator AI 共识 JSON 解析依赖正则

**位置**：`investor_coordinator.py:_build_consensus` JSON 解析使用 markdown 围栏匹配，模型偶发 JSON 异常时直接退到 fallback，损失共识丰度。

**修复建议**：增加重试一次 + JSON 解析失败时降级为 `_fallback_consensus` + 记录 metrics。

### L1（低危）— 投资者 Agent 副作用未隔离

**位置**：`buffett.py / munger.py / lynch.py / damodaran.py` 在 analyze 内部直接调用 `agent_memory.save_agent_analysis`。测试中通过 `_stub_agent_memory` autouse fixture 兜底，生产可能引发文件 IO 噪音。

## 4. 执行命令与证据

### 4.1 命令
```bash
cd /Users/panda/Downloads/StockAnal_Sys
pytest tests/backend/integration/test_investor_coordinator.py \
       tests/backend/integration/test_hitl.py \
       tests/backend/unit/test_investors_*.py -v
pytest ... --cov=app.agents.investors --cov=app.agents.hitl --cov-report=term
```

### 4.2 结果摘要
- **42 passed, 0 failed, 0 errors** in 355.25s
- **TOTAL coverage: 81%** (670 stmts, 113 miss, 212 branch, 49 BrPart)

### 4.3 证据文件
- `tests/audit/evidence/BE-02b_pytest.log`（128 行，含完整用例列表 + 覆盖率表）

## 5. 时间真实性校验

| 项 | 值 |
|---|---|
| 校验来源 1 | 本机 `date` 命令 |
| 校验时间 | 2026-05-17 20:22:24 +0800 |
| 时区 | Asia/Singapore (+08:00) |
| 判定 | 通过（与 currentDate 2026-05-17 一致） |

## 6. 结论

- **42/42 测试用例通过**；
- 6 个目标文件覆盖率均达 / 超目标（hitl 81%、coordinator 81%、4 人格 80~82%）；
- **H1 内存字典风险被显式断言暴露**（test_new_instance_loses_all_pending_approvals）；
- 缺陷 1 高 + 1 中 + 1 低，详见第 3 节修复建议。

## 7. 下一步

1. BE-02c 覆盖 9 个分析 Agent（technical / fundamental / sentiment / risk / debate_bull / debate_bear / capital_flow / news / strategy）；
2. H1 修复纳入 R5 sprint 待办（建议接入 Redis 持久化）；
3. 投资者 Agent 抽取公共 helper（`_parse_json_response` + `_compile_reports` 重复 4 份，建议 DEDUP）。
