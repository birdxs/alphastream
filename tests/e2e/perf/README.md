# tests/e2e/perf — 性能与可靠性基线

文件: `test_performance_baseline.py` (PERF-01), `__init__.py`
地位: e2e 三级 — 性能/容量/超时/并发的契约级断言, 全部用 mock 加速, 不依赖真实长跑
功能: P01-P08 八场景基线 (SSE TTL / 并发隔离 / LLM 重试 / 流式 OOM / 字典清理 / 截断 / sqlite 体积 / 背压)

一旦这里的结构发生变化, 请务必更新我... 就像重新标记领地一样。
