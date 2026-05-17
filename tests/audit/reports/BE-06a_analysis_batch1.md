# BE-06a 分析模块批量测试 #1 报告

- 任务编号: BE-06a
- 执行时间: 2026-05-17 (Asia/Singapore +08:00)
- 范围: `app/analysis/` 5 个中小模块（避开 stock_analyzer.py 1642 行）
- 输出: 5 测试文件、pytest 日志、本报告

## 1. 目标模块

| 模块 | 主类 | 主要依赖 |
|---|---|---|
| `app/analysis/capital_flow_analyzer.py` | `CapitalFlowAnalyzer` | `akshare`, `data_provider` |
| `app/analysis/etf_analyzer.py` | `EtfAnalyzer` | `akshare`, `stock_analyzer`, `chat_completion` |
| `app/analysis/fundamental_analyzer.py` | `FundamentalAnalyzer` | `akshare`, `data_provider` |
| `app/analysis/scenario_predictor.py` | `ScenarioPredictor` | `stock_analyzer`, `chat_completion` |
| `app/analysis/stock_qa.py` | `StockQA` | `stock_analyzer`, `chat_completion`, `search` |

## 2. 用例统计

| 测试文件 | 用例数 | 通过 | 失败 |
|---|---|---|---|
| `test_analysis_capital_flow.py` | 12 | 12 | 0 |
| `test_analysis_etf.py` | 13 | 13 | 0 |
| `test_analysis_fundamental.py` | 11 | 11 | 0 |
| `test_analysis_scenario.py` | 6 | 6 | 0 |
| `test_analysis_qa.py` | 8 | 8 | 0 |
| 合计 | **55** | **55** | **0** |

执行命令：
```
pytest tests/backend/unit/test_analysis_*.py -v
```

## 3. 覆盖率

| 模块 | Stmts | Miss | Branch | BrPart | Cover |
|---|---|---|---|---|---|
| capital_flow_analyzer.py | 252 | 65 | 88 | 14 | **65%** |
| etf_analyzer.py | 366 | 146 | 92 | 21 | **57%** |
| fundamental_analyzer.py | 172 | 55 | 96 | 30 | **65%** |
| scenario_predictor.py | 113 | 9 | 20 | 6 | **89%** |
| stock_qa.py | 192 | 76 | 62 | 7 | **56%** |
| **TOTAL** | **1095** | **351** | **358** | **78** | **63%** |

总覆盖率 **63%**，超过 60% 门槛。

## 4. 测试维度覆盖

每模块均覆盖 5 维度（部分模块超量）：

1. **快乐路径**：mock akshare/LLM 返回有效数据，验证主要输出字段
2. **数据源失败**：akshare 抛异常 → 验证降级 mock 或 error 字段
3. **LLM 失败**：`chat_completion` 返回 `(None, err)` → 验证降级到默认分析
4. **空 DataFrame 边界**：返回 `pd.DataFrame()` → 验证不崩溃并兜底
5. **关键计算正确性**：
   - `_parse_percent` 各格式
   - `calculate_capital_flow_score` 强正向流入评分偏高
   - `_calculate_cagr(200/100, 4y) ≈ 18.92%`
   - `_calculate_scenarios` 乐观/悲观目标价排序正确
   - `_safe_get_column` PE/PB 字段抽取
6. **额外**：
   - `clear_conversation` 三分支
   - `get_conversation_history` 轮次解析
   - `run_analysis` 子模块整合调用验证

## 5. 缺陷列表（来自首轮迭代）

| # | 模块 | 问题 | 处理 |
|---|---|---|---|
| 1 | etf | 测试假设 `get_basic_info` 返回 dict，源码实际写入 `self.analysis_result['basic_info']`；akshare 接口名误用 `fund_etf_spot_em` → 应为 `fund_etf_fund_info_em`（键值对纵向 DataFrame） | 重写测试，校对真实 API |
| 2 | fundamental | 测试 CAGR 用 `[100,120,...,200]`，但源码以 `iloc[0]` 为最新值（应为 `[200,170,...,100]`） | 反转序列 |
| 3 | etf fund_flow | 内部依赖 `self.hist_df`（在 `analyze_market_performance` 中设置），独立调用需先注入 | 添加 fixture 数据 |

所有缺陷为**测试代码自身**问题，已修复。**源码未修改**。

## 6. 已识别的源码薄弱点（建议后续追踪，非本批阻塞）

1. `EtfAnalyzer.get_ai_summary` (501-568 行)、`analyze_sector` (501-616 行) 内含较多 akshare 调用与 LLM JSON 解析分支，需大量 mock 才能覆盖；本批仅覆盖兜底路径。
2. `StockQA.search_stock_news` (412-517 行) 含 SerpAPI / Tavily / unified 三套搜索逻辑，本批仅覆盖兜底，可在 BE-06c 增强。
3. `FundamentalAnalyzer.get_growth_data` (88-137 行) 依赖 `stock_financial_abstract` 真实字段，可能与 mock DataFrame 字段名不一致；本批覆盖了空/异常路径。

## 7. 证据

- pytest 日志: `tests/audit/evidence/BE-06a_pytest.log`
- 测试文件:
  - `tests/backend/unit/test_analysis_capital_flow.py`
  - `tests/backend/unit/test_analysis_etf.py`
  - `tests/backend/unit/test_analysis_fundamental.py`
  - `tests/backend/unit/test_analysis_scenario.py`
  - `tests/backend/unit/test_analysis_qa.py`

## 8. 完成状态

- [x] 5 模块各 ≥ 5 用例（实际 6~13 用例/模块）
- [x] LLM/akshare/外部 IO 全 mock（未触网络）
- [x] 总覆盖率 ≥ 60%（实际 63%）
- [x] 55/55 通过 0 失败
- [x] 中文输出
