# Input  : RiskMonitor 单元测试，mock 内置 analyzer（get_stock_data + indicators）
# Output : pytest 用例（实例化/各风险/组合风险/边界）
# Pos    : tests/backend/unit/test_analysis_risk_monitor.py - BE-06c 第 4/5
"""BE-06c #4: RiskMonitor 单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from app.analysis.risk_monitor import RiskMonitor


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _build_df(n=30, close_trend="up", vol_recent=2.0, ma_pattern="up",
              rsi=50.0, macd_above=True, volume_recent=1e8):
    """构造 RiskMonitor 所需指标完整的 DataFrame。"""
    idx = pd.date_range("2026-04-01", periods=n)
    if close_trend == "up":
        close = np.linspace(10.0, 15.0, n)
    elif close_trend == "down":
        close = np.linspace(15.0, 10.0, n)
    else:
        close = np.full(n, 12.0)

    if ma_pattern == "up":
        ma5, ma20, ma60 = 14.0, 13.0, 12.0
    elif ma_pattern == "down":
        ma5, ma20, ma60 = 12.0, 13.0, 14.0
    else:
        ma5, ma20, ma60 = 13.0, 13.0, 13.0

    df = pd.DataFrame(
        {
            "close": close,
            "volume": np.concatenate([np.full(n - 1, 1e7), [volume_recent]]),
            "MA5": ma5,
            "MA20": ma20,
            "MA60": ma60,
            "RSI": rsi,
            "MACD": 1.0 if macd_above else -1.0,
            "Signal": 0.5 if macd_above else 0.0,
            # 历史均值 1.0，最近一日替换为 vol_recent 以制造波动率变化
            "Volatility": np.concatenate([np.full(n - 1, 1.0), [vol_recent]]),
        },
        index=idx,
    )
    return df


@pytest.fixture
def fake_analyzer():
    base = MagicMock()
    return base


@pytest.fixture
def monitor(fake_analyzer):
    return RiskMonitor(fake_analyzer)


# --------------------------------------------------------------------------- #
# Cases
# --------------------------------------------------------------------------- #
def test_instantiate(monitor, fake_analyzer):
    """用例 1：实例化。"""
    assert monitor.analyzer is fake_analyzer


def test_analyze_stock_risk_normal(monitor, fake_analyzer):
    """用例 2：常规情形 - mock get_stock_data + calculate_indicators。"""
    df = _build_df()
    fake_analyzer.get_stock_data.return_value = df.copy()
    fake_analyzer.calculate_indicators.return_value = df
    result = monitor.analyze_stock_risk("000001")
    assert "error" not in result
    assert "total_risk_score" in result
    assert result["risk_level"] in {"极高", "高", "中等", "低", "极低"}
    assert isinstance(result["alerts"], list)
    # 子模块字段
    for k in ("volatility_risk", "trend_risk", "reversal_risk", "volume_risk"):
        assert "score" in result[k]


def test_analyze_stock_risk_high_volatility(monitor, fake_analyzer):
    """用例 3：高波动率 - 触发警报。"""
    df = _build_df(vol_recent=6.0, ma_pattern="down", rsi=80.0, volume_recent=1e9)
    fake_analyzer.get_stock_data.return_value = df.copy()
    fake_analyzer.calculate_indicators.return_value = df
    result = monitor.analyze_stock_risk("000001")
    assert result["volatility_risk"]["score"] >= 60
    alert_types = {a["type"] for a in result["alerts"]}
    assert "volatility" in alert_types


def test_analyze_stock_risk_exception(monitor, fake_analyzer):
    """用例 4：底层异常 - 返回 error。"""
    fake_analyzer.get_stock_data.side_effect = RuntimeError("network")
    result = monitor.analyze_stock_risk("000001")
    assert "error" in result


def test_analyze_volatility_risk_low(monitor):
    """用例 5：私有 - 低波动率分支。"""
    df = _build_df(vol_recent=0.5)
    out = monitor._analyze_volatility_risk(df)
    assert out["score"] == 0
    assert out["risk_level"] == "低"


def test_analyze_trend_risk_up(monitor):
    """用例 6：私有 - 上升趋势风险低。"""
    df = _build_df(ma_pattern="up")
    out = monitor._analyze_trend_risk(df)
    assert out["trend"] == "上升"
    assert out["score"] == 20


def test_analyze_trend_risk_down(monitor):
    """用例 7：私有 - 下降趋势风险升高。"""
    df = _build_df(ma_pattern="down")
    out = monitor._analyze_trend_risk(df)
    assert out["trend"] == "下降"
    assert out["score"] >= 50


def test_analyze_volume_risk_spike(monitor):
    """用例 8：私有 - 量能暴增。"""
    df = _build_df(volume_recent=1e9)  # 远高于均值
    out = monitor._analyze_volume_risk(df)
    assert out["score"] >= 70


def test_analyze_portfolio_risk_empty(monitor):
    """用例 9：组合 - 空。"""
    out = monitor.analyze_portfolio_risk([])
    assert "error" in out


def test_analyze_portfolio_risk_basic(monitor, fake_analyzer):
    """用例 10：组合分析 - 两只股票（mock analyze_stock_risk + get_stock_info）。"""
    fake_analyzer.get_stock_info.return_value = {"行业": "半导体"}
    # 直接 patch monitor.analyze_stock_risk 避免深层
    monitor.analyze_stock_risk = MagicMock(  # type: ignore[method-assign]
        side_effect=[
            {"total_risk_score": 75, "risk_level": "高",
             "alerts": [{"type": "volatility", "level": "高", "message": "x"}]},
            {"total_risk_score": 30, "risk_level": "低", "alerts": []},
        ]
    )
    portfolio = [
        {"stock_code": "000001", "weight": 0.6, "market_type": "A"},
        {"stock_code": "000002", "weight": 0.4, "market_type": "A"},
    ]
    out = monitor.analyze_portfolio_risk(portfolio)
    assert "error" not in out
    assert "portfolio_risk_score" in out
    assert out["risk_level"] in {"极高", "高", "中等", "低", "极低"}
    # 加权 = (75*0.6 + 30*0.4)/1.0 = 57
    assert out["portfolio_risk_score"] == pytest.approx(57.0)
    # 高风险股票列表
    assert any(s["stock_code"] == "000001" for s in out["high_risk_stocks"])
