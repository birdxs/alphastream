# BE-03c 剩余 6 核心模块测试报告

- 任务编号：BE-03c
- 完成时间：2026-05-17 21:54:54 +0800
- 标签：[NEW-FILE:#20260517-01]
- 周期：≤ 15 min

## 一、范围

| # | 模块 | 测试文件 | 用例数 |
|---|---|---|---|
| 1 | `app/core/cache.py` | `test_core_cache.py` | 8 |
| 2 | `app/core/database.py` | `test_core_database.py` | 6 |
| 3 | `app/core/agent_memory.py` | `test_core_agent_memory.py` | 11 |
| 4 | `app/core/fallback_manager.py` | `test_core_fallback_manager.py` | 9 |
| 5 | `app/core/data_provider.py` | `test_core_data_provider.py` | 7 |
| 6 | `app/core/search.py` + `search_engines.py` | `test_core_search.py` | 19 |
| | **合计** | | **60** |

每模块均 ≥ 4 用例，达成下达指标。

## 二、执行结果

```
60 passed, 0 failed, 12 warnings in ~9s
```

证据：`tests/audit/evidence/BE-03c_pytest.log`

## 三、覆盖率

| 模块 | Stmts | Miss | Branch | Cover |
|---|---|---|---|---|
| `app/core/cache.py` | 83 | 5 | 22 | **93%** |
| `app/core/database.py` | 50 | 3 | 2 | **92%** |
| `app/core/search.py` | 27 | 3 | 6 | **91%** |
| `app/core/fallback_manager.py` | 79 | 7 | 32 | **89%** |
| `app/core/data_provider.py` | 99 | 23 | 20 | **75%** |
| `app/core/agent_memory.py` | 143 | 42 | 46 | **68%** |
| `app/core/search_engines.py` | 216 | 87 | 62 | **60%** |
| **TOTAL** | **697** | **170** | **190** | **74%** |

覆盖率目标 ≥ 70% **达成**（74%）。

未覆盖行主要为：
- `agent_memory.py` 行 104-169：TF-IDF 异常分支、search_similar 高级路径，需深度构造大规模历史与 sklearn 模拟，超出本批边界
- `search_engines.py` 行 251-349：wolframalpha / tavily / serp 三个外部 API handler 与 ddgs 部分异常分支，需更深的 HTTP/SDK mock
- `data_provider.py` 行 101-155：board / industry / concept / capital_flow / north_flow 等直通方法（部分已覆盖代表用例）

## 四、关键设计与策略

1. **单例污染防护**：`UnifiedCache` / `DataProvider` 在 fixture 中 `_instance = None`，避免测试间相互污染
2. **网络全 mock**：`requests` / `urllib.request.urlopen` / `ddgs.DDGS` 全用 `unittest.mock.patch` 拦截
3. **DB in-memory**：`sqlite:///:memory:` + 独立 `sessionmaker`，不触碰 `data/stock_analyzer.db`
4. **临时目录**：`agent_memory` 测试通过 `monkeypatch.setattr(am_mod, "MEMORY_DIR", tmp_path)` 隔离落盘
5. **LLM 零调用**：本批未涉及 LLM；`conftest.py` 已 mock OpenAI

## 五、缺陷列表

| ID | 严重度 | 模块 | 描述 |
|---|---|---|---|
| D-03c-01 | P3 | `cache.py` | 类 docstring 声称 "Redis优先/内存降级"，但**未实现 LRU 淘汰**。注释提到的 LRU 实际只有 TTL 与无界 dict，内存占用无上限。建议补 `OrderedDict` + `maxsize`。 |
| D-03c-02 | P3 | `cache.py` | `_redis` 失败 → 内存 `set` 成功，但后续 Redis 恢复后旧数据仍在 Redis 中未同步，可能产生不一致。 |
| D-03c-03 | P3 | `agent_memory.py` | `_memory_dir` 用模块级常量 `MEMORY_DIR` (相对项目 root)，单元测试需 monkeypatch。建议改实例属性，方便注入。 |
| D-03c-04 | P3 | `fallback_manager.py` | 失败计数 ≥ 5 即跳过该 adapter，但**没有冷却时间机制**；只能靠 `reset_status()` 手动恢复或全部 adapter 都阻塞时清零。 |
| D-03c-05 | P2 | `database.py` | 模块顶层 `engine = create_engine(DATABASE_URL)` 在 import 时立即创建文件夹/连接，无法做 lazy。测试中无法直接复用 `init_db()`，须自建 engine。 |
| D-03c-06 | P3 | `search_engines.py` | `multi_search` 在 engine 不在 `("auto","concurrent")` 时调用 `search_one`，但若 `search_one` 返回 `[]` 后会进入 auto 链——日志中显示 "{engine} 无结果，启用 auto 兜底"，但实际是 `engine` 被重新赋值为 "auto"。未明确文档化此行为，调用方可能误以为指定引擎就 strict。 |

## 六、`tools.py` Pydantic 兼容性预检

- 命令：`python -c "from app.core.tools import *; print('ok')"`
- 输出：`ok`（仅 PydanticDeprecatedSince212 / Since211 警告，无 import 错误）
- 结论：本批未直接测 `tools.py`（不在 6 模块范围），但 import 不抛错；BE-02c1 D3 的"不兼容"风险目前**仍为警告级**，未阻断。

## 七、artifact_wrapper 回归

- 现有 `tests/backend/unit/test_artifact_wrapper_p3.py` 共 20 用例
- 本批未重写，未运行（按指令仅作回归确认）

## 八、产出物清单

```
tests/backend/unit/test_core_cache.py
tests/backend/unit/test_core_database.py
tests/backend/unit/test_core_agent_memory.py
tests/backend/unit/test_core_fallback_manager.py
tests/backend/unit/test_core_data_provider.py
tests/backend/unit/test_core_search.py
tests/audit/reports/BE-03c_core_misc.md           (本报告)
tests/audit/evidence/BE-03c_pytest.log
```
