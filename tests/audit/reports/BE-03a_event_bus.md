# BE-03a 审计报告 — app/core/event_bus.py 单元测试

- 任务编号：BE-03a（最小批 Core 测试 #1）
- 目标文件：`app/core/event_bus.py`（139 行，82 Stmts / 18 Branch）
- 测试文件：`tests/backend/unit/test_core_event_bus.py`
- 执行时间：2026-05-17 (Asia/Singapore +08:00)
- 执行人：香草少校 / Worker Agent
- 报告标签：[NEW-FILE:#20260517-01]

---

## 1. 执行摘要

| 项目 | 结果 |
|---|---|
| 用例总数 | 16 |
| 通过 | 15 |
| 失败 | 0 |
| Error | 0 |
| xfailed（已知缺陷暴露） | 1（T012 / H5） |
| 行覆盖率 | **99%**（82/82 Stmts，仅 1 个分支 87->exit 部分覆盖） |
| 覆盖率门槛 | ≥85% — **已达成** |
| 总耗时 | 0.56s |

---

## 2. 用例矩阵（任务目标对齐）

| ID | 用例 | 任务目标 | 结果 |
|---|---|---|---|
| T001 | `EventBus()` / `get_event_bus()` 单例同一 | C9 | PASS |
| T002 | 11 个事件常量存在性 + 唯一性 + 字符串非空 | A4 | PASS |
| T003 | `subscribe` + `publish` 基本分发 | A1/A2 | PASS |
| T004 | 多订阅者全广播 | A1/A2 | PASS |
| T005 | 异常隔离：bad subscriber 抛错不影响其他订阅者 | A3 | PASS |
| T006 | `unsubscribe` 正常移除回调 | A1 | PASS |
| T007 | publish 无订阅者静默 | A2 | PASS |
| T008 | `create_sse_bridge(filter_events)` 过滤准确 | B5 | PASS |
| T009 | `destroy_sse_bridge` 销毁后不再投递 | B6 | PASS |
| T010 | **30min TTL 自动清理** — 篡改 created_at=-31min 后 publish 触发清理 | B7 / C1 | PASS |
| T011 | SSE 桥接 maxsize=10000 上限验证 | B8 | PASS |
| T012 | **慢消费者背压暴露**：5000 条全堆积无丢弃策略 | B8 / H5 | XFAIL（按设计暴露缺陷） |
| T013 | 并发 publish 线程安全（8×100=800 事件全收齐） | A1/A2 | PASS |
| T014 | 异常+正常订阅者交替执行顺序 | A3 | PASS |
| T015 | topic 隔离 | A2 | PASS |
| T016 | SSE `filter_events=None` 接收全部事件 | B5 | PASS |

---

## 3. 覆盖率详情

```
Name                    Stmts   Miss Branch BrPart  Cover   Missing
-------------------------------------------------------------------
app/core/event_bus.py      82      0     18      1    99%   87->exit
TOTAL                      82      0     18      1    99%
```

- 行覆盖：100%（82/82）
- 分支覆盖：17/18（94.4%），唯一未覆盖分支 `line 87 -> exit`（属于 publish 内 `_cleanup_expired_bridges` 锁内空列表早退路径，影响可忽略）
- 综合 Cover：**99%**

---

## 4. 缺陷追踪结果

### C1 — SSE bridge 30min TTL 工作区改动是否真清理

- **结论：已生效**。
- 证据：T010 通过 — 通过篡改 `_sse_bridges[0]` 中的 `created_at` 为 `time.monotonic() - 31*60`，再 publish 一次，断言 `len(_sse_bridges) == 0` 成立。
- 实现位置：`event_bus.py` 中 `publish()` 调用 `_cleanup_expired_bridges()`，按 `time.monotonic() - created_at > 1800` 判定回收。
- 风险：**低**。但 publish 内联清理在高频事件下仍执行 O(n) 扫描；如果不发生 publish，过期桥不会主动清理（被动 TTL）。建议长期改为后台定时任务或弱引用回收。

### H5 — 慢消费者背压无上限

- **结论：部分缓解、仍存在堆积风险**。
- 证据：
  - T011 PASS：`q.maxsize == 10000`，已为队列加上限。注入 10001 条后 `q.qsize() <= 10000`，第 10001 条被 `queue.Full` 吞掉。
  - T012 XFAIL（按设计）：5000 条事件全部入队（qsize == 5000），证明 **在 maxsize 内无丢弃策略**，慢消费者仍可堆积到 10000 条上限。
- 影响：单桥最坏情况内存膨胀至 10000 × 单事件大小。若 SSE 连接断开但 `destroy_sse_bridge` 未被显式调用，需依赖 30min TTL 兜底回收。
- 建议改进（不在本任务范围）：
  1. 引入 `drop_oldest` 策略：队列满时丢弃最老事件（如 collections.deque(maxlen)）。
  2. 主动监控 `qsize() > threshold` 时记录告警日志。
  3. 心跳/弱引用替代被动 TTL。

---

## 5. 证据文件

| 文件 | 用途 |
|---|---|
| `tests/backend/unit/test_core_event_bus.py` | 测试源码（16 用例） |
| `tests/audit/evidence/BE-03a_pytest.log` | pytest 完整日志 + 覆盖率输出 |
| `tests/audit/reports/BE-03a_event_bus.md` | 本审计报告 |

---

## 6. 结论

`app/core/event_bus.py` 的核心 API（subscribe / unsubscribe / publish / 异常隔离 / 11 事件常量 / SSE 桥接 / 30min TTL / 单例工厂 / 并发安全）通过 15 用例全部验证；H5 已知缺陷通过 T012 显式 xfail 暴露并记录。行覆盖 99%，达成 ≥85% 关键模块门槛。

**验收建议：通过**。下一步建议在后续批次治理 H5（队列丢弃策略）。
