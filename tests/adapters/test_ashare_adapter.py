# -*- coding: utf-8 -*-
"""
Ashare适配器单元测试 [NEW-FILE:#20260415-17]
Input: mock Ashare.get_price 返回DataFrame
Output: pytest结果，覆盖 _normalize / get_price / frequency校验 / health_check / BaseAdapter兜底
Pos: tests/adapters/ — 回归基线
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.adapters import ashare_adapter as asa  # noqa: E402


def _mk_kline_df(n: int = 5) -> pd.DataFrame:
    idx = pd.date_range("2026-04-01", periods=n, freq="D")
    return pd.DataFrame({
        "open":   [12.0 + i * 0.1 for i in range(n)],
        "close":  [12.1 + i * 0.1 for i in range(n)],
        "high":   [12.2 + i * 0.1 for i in range(n)],
        "low":    [11.9 + i * 0.1 for i in range(n)],
        "volume": [1000 + i * 10 for i in range(n)],
    }, index=idx)


# ==================== _normalize ====================
class TestNormalize:
    def test_sh_prefix(self):
        assert asa.AshareAdapter._normalize("600519") == "sh600519"
        assert asa.AshareAdapter._normalize("sh600519") == "sh600519"
        assert asa.AshareAdapter._normalize("600519.SH") == "sh600519"

    def test_sz_prefix(self):
        assert asa.AshareAdapter._normalize("000001") == "sz000001"
        assert asa.AshareAdapter._normalize("300750") == "sz300750"
        assert asa.AshareAdapter._normalize("000001.SZ") == "sz000001"

    def test_explicit_market(self):
        assert asa.AshareAdapter._normalize("000001", market="sh") == "sh000001"

    def test_empty(self):
        assert asa.AshareAdapter._normalize("") == ""
        assert asa.AshareAdapter._normalize(None) == ""


# ==================== get_price ====================
class TestGetPrice:
    def test_ok(self):
        with patch.object(asa, "_ashare_get_price", return_value=_mk_kline_df(10)), \
             patch.object(asa, "_ASHARE_AVAILABLE", True):
            a = asa.AshareAdapter()
            df = a.get_price("600519", frequency="1d", count=10)
        assert not df.empty
        assert len(df) == 10
        assert "close" in df.columns

    def test_invalid_freq_fallback(self):
        mock = MagicMock(return_value=_mk_kline_df(3))
        with patch.object(asa, "_ashare_get_price", mock), \
             patch.object(asa, "_ASHARE_AVAILABLE", True):
            a = asa.AshareAdapter()
            a.get_price("000001", frequency="2h", count=5)
        # 回退为1d
        kwargs = mock.call_args.kwargs
        assert kwargs.get("frequency") == "1d"

    def test_unavailable(self):
        with patch.object(asa, "_ASHARE_AVAILABLE", False):
            a = asa.AshareAdapter()
            assert a.get_price("600519").empty

    def test_exception_returns_empty(self):
        with patch.object(asa, "_ashare_get_price", side_effect=RuntimeError("net")), \
             patch.object(asa, "_ASHARE_AVAILABLE", True):
            a = asa.AshareAdapter()
            assert a.get_price("600519").empty

    def test_minute_freq(self):
        mock = MagicMock(return_value=_mk_kline_df(4))
        with patch.object(asa, "_ashare_get_price", mock), \
             patch.object(asa, "_ASHARE_AVAILABLE", True):
            a = asa.AshareAdapter()
            a.get_price("600519", frequency="5m", count=48)
        kwargs = mock.call_args.kwargs
        assert kwargs.get("frequency") == "5m"
        assert kwargs.get("count") == 48


# ==================== BaseAdapter 接口 ====================
class TestBaseAdapter:
    def test_get_stock_history_slice(self):
        # 造10根日线，切5天窗口
        with patch.object(asa, "_ashare_get_price", return_value=_mk_kline_df(10)), \
             patch.object(asa, "_ASHARE_AVAILABLE", True):
            a = asa.AshareAdapter()
            df = a.get_stock_history("600519", "20260403", "20260406")
        assert len(df) == 4  # 03,04,05,06

    def test_index_stocks_empty(self):
        a = asa.AshareAdapter()
        assert a.get_index_stocks("000300") == []

    def test_info_empty(self):
        a = asa.AshareAdapter()
        assert a.get_stock_info("600519") == {}

    def test_financial_empty(self):
        a = asa.AshareAdapter()
        assert a.get_financial_data("600519") == {}

    def test_health_unavailable(self):
        with patch.object(asa, "_ASHARE_AVAILABLE", False):
            assert asa.AshareAdapter().health_check() is False

    def test_health_ok(self):
        with patch.object(asa, "_ashare_get_price", return_value=_mk_kline_df(2)), \
             patch.object(asa, "_ASHARE_AVAILABLE", True):
            assert asa.AshareAdapter().health_check() is True


class TestMeta:
    def test_name(self):
        assert asa.AshareAdapter().name == "ashare"
