# BE-06c 分析模块批量测试 #3 报告

- 任务编号: BE-06c
- 执行时间: 2026-05-17 (Asia/Singapore +08:00)
- 范围: `app/analysis/` 剩余 5 个模块
- 输出: 5 测试文件、pytest 日志、本报告

## 1. 目标模块

| 模块 | 主类 / 关键函数 | 主要依赖 |
|---|---|---|
| `app/analysis/industry_analyzer.py` | `IndustryAnalyzer` | `akshare`, `data_provider` |
| `app/analysis/index_industry_analyzer.py` | `IndexIndustryAnalyzer` | `StockAnalyzer`, `data_provider` |
| `app/analysis/news_fetcher.py` | `NewsFetcher` + `fetch_news_task` / `start_news_scheduler` | `akshare`, `threading` |
| `app/analysis/risk_monitor.py` | `RiskMonitor` | `StockAnalyzer` |
| `app/analysis/us_stock_service.py` | `USStockService` | `akshare.stock_us_spot_em` |

## 2. 用例统计

| 测试文件 | 用例数 | 通过 | 失败 |
|---|---|---|---|
| `test_analysis_industry.py` | 17 | 17 | 0 |
| `test_analysis_index_industry.py` | 8 | 8 | 0 |
| `test_analysis_news_fetcher.py` | 12 | 12 | 0 |
| `test_analysis_risk_monitor.py` | 10 | 10 | 0 |
| `test_analysis_us_stock.py` | 7 | 7 | 0 |
| 合计 | **54** | **54** | **0** |

执行命令：

```
pytest tests/backend/unit/test_analysis_industry.py \
       tests/backend/unit/test_analysis_index_industry.py \
       tests/backend/unit/test_analysis_news_fetcher.py \
       tests/backend/unit/test_analysis_risk_monitor.py \
       tests/backend/unit/test_analysis_us_stock.py -v
```

## 3. 覆盖率

| 模块 | Stmts | Miss | Branch | BrPart | Cover |
|---|---|---|---|---|---|
| industry_analyzer.py | 287 | 78 | 120 | 28 | **69%** |
| index_industry_analyzer.py | 131 | 27 | 38 | 8 | **77%** |
| news_fetcher.py | 220 | 51 | 70 | 16 | **75%** |
| risk_monitor.py | 193 | 51 | 96 | 24 | **69%** |
| us_stock_service.py | 20 | 0 | 2 | 0 | **100%** |
| **TOTAL** | **851** | **207** | **326** | **76** | **72%** |

阈值 ≥ 60%，结论：**达标**。

## 4. 关键设计

### 4.1 全外部 IO Mock 化

- akshare 全部以 `unittest.mock.patch` 在对应模块命名空间打桩：
  - `app.analysis.industry_analyzer.ak.stock_fund_flow_industry`
  - `app.analysis.industry_analyzer.ak.stock_board_industry_hist_em`
  - `app.analysis.news_fetcher.ak.stock_info_global_cls`
  - `app.analysis.us_stock_service.ak.stock_us_spot_em`
- `data_provider`、`StockAnalyzer` 等业务依赖一律 `MagicMock` 替换。
- 落盘路径用 `tmp_path` 替代 `data/news/`，避免污染仓库。

### 4.2 调度器测试（无真线程）

`test_start_news_scheduler_no_real_thread` 用 `monkeypatch.setattr(threading, "Thread", MagicMock(...))` 直接拦截后台线程构造，仅验证：

- `Thread` 构造被调用一次；
- 返回的实例 `daemon=True`；
- `start()` 被调用一次。

实际 `_run_scheduler` 死循环不会进入。`test_fetch_news_task` 通过替换 `news_fetcher.fetch_and_save` 单步验证调度函数。

### 4.3 RiskMonitor DataFrame 构造

使用 `_build_df` helper 生成完整指标列（MA5/MA20/MA60/RSI/MACD/Signal/Volatility/close/volume），通过参数化生成上升/下降/波动率突增等不同场景，独立验证 `_analyze_volatility_risk` / `_analyze_trend_risk` / `_analyze_volume_risk` 三个私有方法的分数分支。

### 4.4 IndustryAnalyzer 缓存命中路径

通过直接预置 `analyzer.data_cache[key] = (datetime.now(), payload)` 模拟缓存命中，覆盖 `get_industry_fund_flow` / `get_industry_stocks` 的快速返回分支。

## 5. 缺陷列表

无。54 用例全通过，未发现业务源码 bug。

## 6. 未覆盖代码说明

- industry_analyzer 未覆盖行：`generate_industry_recommendation` 的 detail 字符串拼接分支（依赖 `_compute_history_changes` 大量历史数据），价值低；`_generate_mock_industry_stocks` 仅部分行业触发，剩余分支跳过。
- index_industry_analyzer 未覆盖：行业列表大批量 + 完整指数比较的整合路径，需深层 mock，性价比低。
- news_fetcher 未覆盖：`_load_existing_hashes` 异常分支与 `get_latest_news` 跨日历史回溯路径。
- risk_monitor 未覆盖：组合分析中行业集中度细节 + 异常路径多分支。

均为非核心边角逻辑，不影响主路径验收。

## 7. 提交标签

- 新文件：`[NEW-FILE:#20260517-01]`
- commit 见仓库历史。
- 仅本地 commit，**不 push**（遵守硬约束）。

## 8. 时间真实性校验引用

引用 BE-06a/06b 已建立的时间锚点（Asia/Singapore +08:00, 2026-05-17）。
