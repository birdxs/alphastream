# 验收报告 - BE-01b 股票数据路由小批量

| 项 | 值 |
|---|---|
| 报告ID | BE-01b |
| 域 | 后端 / Flask Web API / 股票数据 |
| 执行时间 | 2026-05-17 20:04:30 +08:00 ~ 2026-05-17 20:09:00 +08:00 |
| 状态 | 通关（23/23 全通过） |
| 关联模板 | tests/audit/reports/REPORT_TEMPLATE.md |
| 上批参照 | BE-01a `tests/backend/api/test_health_and_analysis_routes.py` |

## 1. 测试范围

覆盖 `app/web/web_server.py` 中股票数据相关的 **9 条真实路由**（10 个测试类，含 `/api/stock_data` 的 3 个分支用例），路径与行号均以 grep 实际结果为准：

| # | 方法 | 路径 | 实现文件:行号 |
|---|---|---|---|
| 1 | GET | `/api/stock_data` | `app/web/web_server.py:1136` |
| 2 | GET | `/api/stock_name` | `app/web/web_server.py:1339` |
| 3 | GET | `/api/stock_profile` | `app/web/web_server.py:1247` |
| 4 | GET | `/api/stock_name_search` | `app/web/web_server.py:1354` |
| 5 | GET | `/api/market_indices` | `app/web/web_server.py:1639` |
| 6 | GET | `/api/latest_news` | `app/web/web_server.py:2212` |
| 7 | GET | `/api/news_sentiment` | `app/web/web_server.py:2345` |
| 8 | POST | `/api/north_flow_history` | `app/web/web_server.py:622` |
| 9 | GET | `/search_us_stocks` | `app/web/web_server.py:649` |

> 说明：原任务清单第 8 条 `/api/board_stocks` 经 grep 全文未发现真实实现（仓库已删除/未启用），按"严格本批不扩展"原则不替换为他项；落实第 10 条由 `/api/stock_data` 拆出 4 个用例（缺失参数 / 非法代码 / 历史快乐 / 空数据 404），确保 ≥8 路由 + 每条 ≥2 用例的硬约束。

落盘代码：`tests/backend/api/test_stock_data_routes.py`（426 行）。

## 2. 测试矩阵

| 用例 ID | 路由 | 类型 | 关键断言 | 结果 |
|---|---|---|---|---|
| BE-01b-T001 | GET `/api/stock_data` | 错误 | 缺 `stock_code` → 400 + JSON.error | PASS |
| BE-01b-T002 | GET `/api/stock_data` | 错误 | 非法 A 股代码 → 400 + 无堆栈 | PASS |
| BE-01b-T003 | GET `/api/stock_data` | 快乐 | mock analyzer 返回 5 行 → 200 + data 列表 + stock_name | PASS |
| BE-01b-T004 | GET `/api/stock_data` | 边界 | 空 DataFrame → 404 + 无堆栈 | PASS |
| BE-01b-T005 | GET `/api/stock_name` | 错误 | 缺 `stock_code` → 400 | PASS |
| BE-01b-T006 | GET `/api/stock_name` | 快乐 | 缓存命中 → 200 + 名称匹配 | PASS |
| BE-01b-T007 | GET `/api/stock_name` | 边界 | 未命中 → 200 + name 回填为 code | PASS |
| BE-01b-T008 | GET `/api/stock_profile` | 错误 | 缺 `stock_code` → 400 | PASS |
| BE-01b-T009 | GET `/api/stock_profile` | 快乐 | mock baostock 全套 RS → 行业/PE/PB/ROE 全字段 | PASS |
| BE-01b-T010 | GET `/api/stock_name_search` | 错误 | 缺 `q` → 400 + results=[] | PASS |
| BE-01b-T011 | GET `/api/stock_name_search` | 快乐 | exact > prefix > contains 排序 | PASS |
| BE-01b-T012 | GET `/api/market_indices` | 快乐 | 注入 2 条指数 → 200 + 透传 | PASS |
| BE-01b-T013 | GET `/api/market_indices` | 边界 | 空 indices → 200 + 等价空 | PASS |
| BE-01b-T014 | GET `/api/latest_news` | 快乐 | 2 条新闻 → success=True + len=2 | PASS |
| BE-01b-T015 | GET `/api/latest_news` | 过滤 | `important=1` → 仅保留命中关键词条目 | PASS |
| BE-01b-T016 | GET `/api/latest_news` | 错误 | `days=abc` → 500 + success=False + 无堆栈 | PASS |
| BE-01b-T017 | GET `/api/news_sentiment` | 快乐 | bullish=1 / bearish=1 / neutral=1 + score∈[1,10] | PASS |
| BE-01b-T018 | GET `/api/news_sentiment` | 边界 | 空新闻 → total=0 + score=5.0 | PASS |
| BE-01b-T019 | POST `/api/north_flow_history` | 错误 | 缺 `stock_code` → 400 | PASS |
| BE-01b-T020 | POST `/api/north_flow_history` | 快乐 | mock CapitalFlowAnalyzer → 200 + history 透传 | PASS |
| BE-01b-T021 | GET `/search_us_stocks` | 错误 | 缺 `keyword` → 400 | PASS |
| BE-01b-T022 | GET `/search_us_stocks` | 快乐 | mock us_stock_service → 200 + 2 条结果 | PASS |
| BE-01b-T023 | GET `/search_us_stocks` | 异常 | 上游 RuntimeError → 500 + 无堆栈 | PASS |

## 3. 执行记录

命令：
```
pytest tests/backend/api/test_stock_data_routes.py -v 2>&1 | tee tests/audit/evidence/BE-01b_pytest.log
```

尾部输出：
```
tests/backend/api/test_stock_data_routes.py::TestSearchUsStocksRoute::test_upstream_exception_returns_500_no_stacktrace PASSED [100%]
======================= 23 passed, 11 warnings in 5.01s ========================
```

用时：5.01 s。证据日志：`tests/audit/evidence/BE-01b_pytest.log`。

## 4. 结果统计

- 通过：23
- 失败：0
- 跳过：0
- 警告：11（均来自 openbb / pydantic 上游依赖弃用提示，与本批无关）
- 外部 IO：全 mock（analyzer / news_fetcher / us_stock_service / CapitalFlowAnalyzer / `sys.modules['baostock']` / `_STOCK_NAME_CACHE` / `_fetch_market_indices_data`），未触发 akshare / baostock 真实网络调用

## 5. 缺陷清单

| ID | 等级 | 描述 | 复现 | 建议 |
|---|---|---|---|---|
| — | — | 本批未发现真实 bug | — | — |

观察项（非阻塞，留作后续批次）：

1. `/api/latest_news` 的 `days=abc` 入参未做显式 400 校验，依赖外层 `try/except` 兜底返回 500（`{success:False, error:"invalid literal for int()..."}`）。语义上更适合返回 400；当前已不泄露堆栈，故不计入缺陷。
2. `/api/north_flow_history` 路由内部 `CapitalFlowAnalyzer = CapitalFlowAnalyzer()` 重新实例化（line 640），未复用模块级 `capital_flow_analyzer`（line 133），存在轻度冗余，建议后续 `[DEDUP]` 治理时合并。
3. 任务清单中的 `/api/board_stocks` 在仓库实际不存在，建议下一批清单维护时同步剔除或核对路由变更。

## 6. 结论

通关。本批 9 条真实股票数据路由的快乐路径、错误路径、上游异常路径全部具备稳定 mock 测试，零外部 IO 副作用，全部 5 秒内完成。未发现阻断性缺陷，可推进至下一小批（建议：portfolio / scenario / fundamental 域）。

## 7. 时间锚点

- 开始：2026-05-17 20:04:30 +08:00（本机 `date` 实测；时区 Asia/Singapore +08:00）
- 结束：2026-05-17 20:09:00 +08:00
- 时间真实性校验：依本机系统时间锚点；本批无远端写操作，无新增外网依赖。
- 证据：`tests/audit/evidence/BE-01b_pytest.log`
