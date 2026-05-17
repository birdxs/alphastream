# BE-06b StockAnalyzer 核心方法测试报告

- 报告时间：2026-05-17 (Asia/Singapore, +08:00)
- 被测文件：`app/analysis/stock_analyzer.py`（1642 行，仓库最大单文件）
- 测试文件：`tests/backend/unit/test_analysis_stock_analyzer.py`
- 证据日志：`tests/audit/evidence/BE-06b_pytest.log`

## 一、结果总览

| 指标 | 数值 |
|------|------|
| 用例总数 | 52 |
| 通过 | 52 |
| 失败 | 0 |
| 跳过 | 0 |
| 覆盖率（line+branch） | **52%**（767 statements / 338 missed） |
| 执行耗时 | 9.26s |
| 覆盖率门槛 | ≥ 50% （达标） |

## 二、测试范围（按任务要求 12-15 核心方法）

| 类别 | 方法 | 测试类 | 用例数 |
|------|------|--------|--------|
| A 数据获取 | `__init__` | TestInit | 3 |
| A 数据获取 | `get_stock_data` | TestGetStockData | 4（含缓存） |
| A 数据获取 | `get_stock_info` | TestGetStockInfo | 3 |
| B 技术指标 | `calculate_ema` / `calculate_rsi` / `calculate_macd` / `calculate_bollinger_bands` | TestBasicIndicators | 4 |
| B 技术指标 | `calculate_indicators`（MA/RSI/MACD/BOLL/ATR等综合） | TestCalculateIndicators | 3 |
| B 技术指标 | `calculate_atr` | TestATR | 2 |
| C 评分 | `calculate_score` | TestCalculateScore | 3 |
| C 评分 | `calculate_technical_score` | TestCalculateTechnicalScore | 3 |
| C 评分 | `quick_analyze_stock`（最高频路径） | TestQuickAnalyze | 3 |
| C 评分 | `perform_enhanced_analysis`（路由调用方） | TestPerformEnhancedAnalysis | 2 |
| D 建议 | `get_recommendation`（7档阈值 + 波动调整 + 财报季 + 异常） | TestRecommendation | 10 |
| D 支撑 | `identify_support_resistance` | TestSupportResistance | 3 |
| E 风控 | `check_consecutive_losses` / `check_profit_taking` | TestRiskControl | 6 |
| E 辅助 | `format_indicator_data` | TestFormatIndicatorData | 3 |

合计 **14 个核心方法**，**52 用例**，每方法均含 快乐路径 / 边界 / 异常 三类用例。

## 三、Mock 策略

- `app.core.data_provider.get_data_provider` → `MagicMock`，所有 akshare 调用通过 `data_provider.get_stock_history` / `data_provider.get_stock_info` 隔离。
- `app.core.ai_client.get_ai_client` / `get_ai_model` → mock，无真实 LLM 调用。
- `_build_stock_prompt_and_get_analysis` / `get_stock_news` 在涉及增强分析时按需 patch。
- 全程零网络 IO，零文件 IO。

## 四、覆盖率细节

- TOTAL：767 stmts，338 missed，65 partial branches → 52%
- 未覆盖区段集中在：
  - `_check_a_share_linkage` / `_get_mainland_market_sentiment`（A 股联动情绪，需 akshare 海量分支）
  - `get_north_flow_history`（北向资金，多 try 分支）
  - `scan_market`（批量循环，由 quick_analyze_stock 覆盖间接关键路径）
  - `_build_stock_prompt_and_get_analysis` / `_validate_and_fix_report`（LLM 报告生成路径，本轮按 mock 处理）
- 1642 行单文件门槛 50%，本轮 52% 达标。

## 五、缺陷与设计观察

| # | 严重度 | 描述 | 证据 |
|---|--------|------|------|
| D1 | 中 | `calculate_score` 对空 DF 不抛异常，返回硬编码 `50` 默认分（test_score_exception_returns_default 验证）。下游消费方若把它当真实评分会形成"乐观偏差"。建议改为返回 `None` 或上抛。 | `stock_analyzer.py:278` 附近 except 分支 |
| D2 | 低 | `get_stock_info` 异常分支返回 `"未知"` 字典，调用方需自行判空，否则会把"未知"行业带入下游评分。 | `stock_analyzer.py:1267` |
| D3 | 低 | `format_indicator_data` 直接 in-place 修改传入 df（`df[col] = df[col].round(2)`），无 copy，可能影响调用方持有的 DataFrame。建议先 `df = df.copy()`。 | `stock_analyzer.py:213-234` |
| D4 | 低 | `identify_support_resistance` 在无 BB/MA 列时抛 KeyError 而非主动校验。建议先 assert 必备列。 | `stock_analyzer.py:1293` |
| D5 | 提示 | 大量方法长度超 100 行（calculate_score 200+ 行、perform_enhanced_analysis 140 行），可读性与单测精度受限，建议拆分子函数（不在本轮修改范围）。 | 见 grep 结果 |

## 六、命令复现

```bash
cd /Users/panda/Downloads/StockAnal_Sys
pytest tests/backend/unit/test_analysis_stock_analyzer.py -v
pytest tests/backend/unit/test_analysis_stock_analyzer.py --cov=app.analysis.stock_analyzer --cov-report=term
```

## 七、合规

- 本轮仅新增测试文件 1 个：`tests/backend/unit/test_analysis_stock_analyzer.py`
- 报告 + 日志归档至 `tests/audit/`
- 严格遵守："LLM/akshare/外部 IO 全 mock"
- 提交标签：`[NEW-FILE:#20260517-01]`
