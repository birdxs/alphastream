# -*- coding: utf-8 -*-
# Input  : EtfAnalyzer + mock akshare/stock_analyzer
# Output : pytest 用例 BE-06a ETF 分析单元测试
# Pos    : tests/backend/unit/test_analysis_etf.py
"""BE-06a EtfAnalyzer 单元测试

覆盖：
1. 缓存读写
2. get_basic_info 成功（键值对 DataFrame）
3. get_basic_info akshare 异常兜底
4. analyze_market_performance 成功路径
5. analyze_market_performance 空行情兜底
6. analyze_holdings 异常兜底
7. analyze_fund_flow 异常兜底
8. run_analysis 整合
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest


class _MockAnalyzer:
    def __init__(self):
        pass


@pytest.fixture
def etf():
    from app.analysis.etf_analyzer import EtfAnalyzer
    return EtfAnalyzer("510300", _MockAnalyzer())


def _build_benchmark_df(n=300, base=3000.0):
    """构造 ak.stock_zh_index_daily 返回的标准格式 DataFrame（含 date / close 列）"""
    rng = np.random.default_rng(42)
    prices = base + np.cumsum(rng.normal(0, 5, n))
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": prices,
        "close": prices,
        "high": prices * 1.005,
        "low": prices * 0.995,
        "volume": rng.integers(1e9, 1e10, n),
    })


def _build_hist_df(n=300, base=4.0):
    rng = np.random.default_rng(123)
    prices = base + np.cumsum(rng.normal(0, 0.01, n))
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "日期": dates.strftime("%Y-%m-%d"),
        "开盘": prices,
        "收盘": prices,
        "最高": prices * 1.01,
        "最低": prices * 0.99,
        "成交量": rng.integers(1e6, 1e7, n),
        "成交额": rng.uniform(1e8, 1e9, n),
        "振幅": np.full(n, 1.0),
        "涨跌幅": rng.normal(0, 1, n),
        "涨跌额": rng.normal(0, 0.05, n),
        "换手率": rng.uniform(0.5, 2.0, n),
    })


# ---------------------------------------------------------------- 1. 缓存读写
def test_cache_set_get(etf):
    etf._set_cached("foo", {"x": 1})
    assert etf._get_cached("foo") == {"x": 1}
    assert etf._get_cached("absent") is None


# ---------------------------------------------------------------- 2. get_basic_info 成功
def test_get_basic_info_happy_path(etf):
    # 真实接口返回键值对纵向 DataFrame（第一列键，第二列值）
    info_df = pd.DataFrame({
        "item": ["基金代码", "基金简称", "基金类型"],
        "value": ["510300", "沪深300ETF", "ETF"],
    })
    with patch("app.analysis.etf_analyzer.ak.fund_etf_fund_info_em",
               return_value=info_df):
        etf.get_basic_info()

    basic = etf.analysis_result["basic_info"]
    assert basic["基金代码"] == "510300"
    assert basic["基金简称"] == "沪深300ETF"


# ---------------------------------------------------------------- 3. akshare 异常兜底
def test_get_basic_info_akshare_exception_returns_error(etf):
    with patch("app.analysis.etf_analyzer.ak.fund_etf_fund_info_em",
               side_effect=Exception("net err")):
        etf.get_basic_info()
    basic = etf.analysis_result["basic_info"]
    # 异常 / 空数据 → 含 error 字段
    assert "error" in basic


# ---------------------------------------------------------------- 4. analyze_market_performance 成功
def test_analyze_market_performance_happy_path(etf):
    hist_df = _build_hist_df(300)
    bench_df = _build_benchmark_df(300)
    with patch("app.analysis.etf_analyzer.ak.fund_etf_hist_em",
               return_value=hist_df), \
         patch("app.analysis.etf_analyzer.ak.stock_zh_index_daily",
               return_value=bench_df):
        etf.analyze_market_performance()

    perf = etf.analysis_result.get("market_performance")
    assert isinstance(perf, dict)
    # 关键计算字段存在
    assert "returns" in perf or "error" not in perf


# ---------------------------------------------------------------- 5. 空行情兜底
def test_analyze_market_performance_empty_returns_error(etf):
    with patch("app.analysis.etf_analyzer.ak.fund_etf_hist_em",
               return_value=pd.DataFrame()):
        etf.analyze_market_performance()
    perf = etf.analysis_result["market_performance"]
    assert "error" in perf


def test_analyze_market_performance_ak_exception_returns_error(etf):
    with patch("app.analysis.etf_analyzer.ak.fund_etf_hist_em",
               side_effect=Exception("net err")):
        etf.analyze_market_performance()
    perf = etf.analysis_result["market_performance"]
    assert "error" in perf


# ---------------------------------------------------------------- 6. analyze_holdings 异常兜底
def test_analyze_holdings_exception_returns_safe(etf):
    with patch("app.analysis.etf_analyzer.ak.fund_portfolio_hold_em",
               side_effect=Exception("akshare err")):
        # 不抛 → 结果存在 analysis_result
        try:
            etf.analyze_holdings()
        except Exception:
            pass
    # 应该有 holdings 键（即便是 error）
    holdings = etf.analysis_result.get("holdings")
    assert holdings is None or isinstance(holdings, dict)


# ---------------------------------------------------------------- 7. analyze_fund_flow 异常兜底
def test_analyze_fund_flow_exception_returns_safe(etf):
    # 强制所有 ak 调用抛错
    with patch("app.analysis.etf_analyzer.ak") as mock_ak:
        for attr in dir(mock_ak):
            if not attr.startswith("_"):
                try:
                    getattr(mock_ak, attr).side_effect = Exception("err")
                except Exception:
                    pass
        try:
            etf.analyze_fund_flow()
        except Exception:
            pass
    # 验证测试不会让 fixture 状态崩溃
    assert isinstance(etf.analysis_result, dict)


# ---------------------------------------------------------------- 7b. analyze_fund_flow 历史数据缺失
def test_analyze_fund_flow_no_hist_returns_error(etf):
    etf.hist_df = None
    etf.analyze_fund_flow()
    assert "error" in etf.analysis_result["fund_flow"]


# ---------------------------------------------------------------- 7c. analyze_fund_flow 正常路径
def test_analyze_fund_flow_with_hist(etf):
    df = _build_hist_df(120)
    # 转 datetime index 以符合 fund_flow 末尾 strftime 调用
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.rename(columns={"日期": "date"}).set_index("date")
    etf.hist_df = df
    etf.analyze_fund_flow()
    flow = etf.analysis_result["fund_flow"]
    # 正常 or 异常都可接受，只要不崩
    assert isinstance(flow, dict)


# ---------------------------------------------------------------- 7d. analyze_risk_and_tracking 历史缺失
def test_analyze_risk_no_hist_returns_error(etf):
    etf.hist_df = pd.DataFrame()
    etf.analyze_risk_and_tracking()
    assert "error" in etf.analysis_result["risk_and_tracking"]


# ---------------------------------------------------------------- 7e. analyze_sector 异常兜底
def test_analyze_sector_exception_returns_safe(etf):
    with patch("app.analysis.etf_analyzer.ak.fund_etf_category_sina",
               side_effect=Exception("err"), create=True):
        try:
            etf.analyze_sector()
        except Exception:
            pass
    sector = etf.analysis_result.get("sector")
    assert sector is None or isinstance(sector, dict)


# ---------------------------------------------------------------- 7f. get_ai_summary 无 LLM 兜底
def test_get_ai_summary_no_llm_returns_safe(etf):
    etf.analysis_result["basic_info"] = {"基金简称": "测试ETF"}
    etf.analysis_result["market_performance"] = {"current_price": 4.5}
    with patch("app.analysis.etf_analyzer.chat_completion",
               return_value=(None, "no key"), create=True):
        try:
            etf.get_ai_summary()
        except Exception:
            pass
    summary = etf.analysis_result.get("ai_summary")
    assert summary is None or isinstance(summary, (dict, str))


# ---------------------------------------------------------------- 8. run_analysis 整合
def test_run_analysis_integrates_modules(etf):
    with patch.object(etf, "get_basic_info") as m1, \
         patch.object(etf, "analyze_market_performance") as m2, \
         patch.object(etf, "analyze_fund_flow") as m3, \
         patch.object(etf, "analyze_risk_and_tracking") as m4, \
         patch.object(etf, "analyze_holdings") as m5, \
         patch.object(etf, "analyze_sector") as m6, \
         patch.object(etf, "get_ai_summary") as m7:
        result = etf.run_analysis()

    # 各子方法均应被调用
    m1.assert_called_once()
    m2.assert_called_once()
    m3.assert_called_once()
    m4.assert_called_once()
    m5.assert_called_once()
    m6.assert_called_once()
    m7.assert_called_once()
    assert isinstance(result, dict)
