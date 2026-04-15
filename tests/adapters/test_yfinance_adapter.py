# -*- coding: utf-8 -*-
"""
yfinance适配器单元测试 [NEW-FILE:#20260415-05]
Input: mock yf.Ticker 的 history/info/financials/option_chain
Output: pytest结果，覆盖 normalize_symbol + 核心get_*方法
Pos: tests/adapters/ — 回归基线
"""
import sys
import os
import types
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.adapters import yfinance_adapter as yfa  # noqa: E402


# ==================== normalize_symbol ====================
class TestNormalizeSymbol:
    def setup_method(self):
        self.a = yfa.YFinanceAdapter()

    def test_a_share_sh(self):
        assert self.a.normalize_symbol("600519") == "600519.SS"

    def test_a_share_sz(self):
        assert self.a.normalize_symbol("000001") == "000001.SZ"
        assert self.a.normalize_symbol("300750") == "300750.SZ"

    def test_hk_short_code_padded(self):
        assert self.a.normalize_symbol("700", market="HK") == "0700.HK"
        assert self.a.normalize_symbol("00700", market="HK") == "00700.HK"

    def test_hk_auto_detect(self):
        # 5位数字 auto→HK (非6位A股)
        assert self.a.normalize_symbol("09988") == "9988.HK"

    def test_us_ticker_passthrough(self):
        assert self.a.normalize_symbol("AAPL", market="US") == "AAPL"
        assert self.a.normalize_symbol("tsla") == "TSLA"

    def test_already_suffixed(self):
        assert self.a.normalize_symbol("0700.HK") == "0700.HK"
        assert self.a.normalize_symbol("600519.SS") == "600519.SS"

    def test_empty(self):
        assert self.a.normalize_symbol("") == ""


# ==================== get_kline ====================
class TestGetKline:
    def setup_method(self):
        self.a = yfa.YFinanceAdapter()

    def _fake_df(self):
        return pd.DataFrame({
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Volume": [1000, 2000],
        }, index=pd.DatetimeIndex(["2026-04-14", "2026-04-15"], name="Date"))

    def test_kline_normal(self):
        fake_ticker = MagicMock()
        fake_ticker.history.return_value = self._fake_df()
        with patch.object(yfa, "_YF_AVAILABLE", True), \
             patch.object(yfa, "yf", MagicMock(Ticker=MagicMock(return_value=fake_ticker))):
            df = self.a.get_kline("AAPL", period="5d", interval="1d")
        assert not df.empty
        assert "date" in df.columns
        assert "close" in df.columns
        assert "amount" in df.columns
        assert len(df) == 2

    def test_kline_unavailable(self):
        with patch.object(yfa, "_YF_AVAILABLE", False):
            df = self.a.get_kline("AAPL")
        assert df.empty

    def test_kline_invalid_period_degrades(self):
        fake_ticker = MagicMock()
        fake_ticker.history.return_value = self._fake_df()
        with patch.object(yfa, "_YF_AVAILABLE", True), \
             patch.object(yfa, "yf", MagicMock(Ticker=MagicMock(return_value=fake_ticker))):
            df = self.a.get_kline("AAPL", period="999y")
        assert not df.empty
        # 确认降级后调用了history
        fake_ticker.history.assert_called_once()
        kwargs = fake_ticker.history.call_args.kwargs
        assert kwargs.get("period") == "1y"


# ==================== get_info / get_financials / options ====================
class TestMisc:
    def setup_method(self):
        self.a = yfa.YFinanceAdapter()

    def test_get_info(self):
        fake_ticker = MagicMock()
        fake_ticker.info = {"symbol": "AAPL", "marketCap": 3e12}
        with patch.object(yfa, "_YF_AVAILABLE", True), \
             patch.object(yfa, "yf", MagicMock(Ticker=MagicMock(return_value=fake_ticker))):
            info = self.a.get_info("AAPL")
        assert info.get("symbol") == "AAPL"
        assert info.get("marketCap") == 3e12

    def test_get_financials_structure(self):
        income = pd.DataFrame({"2025-12-31": [100, 50]}, index=["Revenue", "NetIncome"])
        balance = pd.DataFrame({"2025-12-31": [500]}, index=["TotalAssets"])
        cashflow = pd.DataFrame({"2025-12-31": [30]}, index=["OperatingCF"])
        fake_ticker = MagicMock()
        fake_ticker.income_stmt = income
        fake_ticker.balance_sheet = balance
        fake_ticker.cashflow = cashflow
        with patch.object(yfa, "_YF_AVAILABLE", True), \
             patch.object(yfa, "yf", MagicMock(Ticker=MagicMock(return_value=fake_ticker))):
            fin = self.a.get_financials("AAPL")
        assert set(fin.keys()) == {"income_stmt", "balance_sheet", "cashflow"}
        assert len(fin["income_stmt"]) == 2
        assert len(fin["balance_sheet"]) == 1

    def test_get_options_chain(self):
        calls_df = pd.DataFrame({"strike": [150, 155], "lastPrice": [5.0, 3.0]})
        puts_df = pd.DataFrame({"strike": [150, 145], "lastPrice": [4.0, 2.0]})
        fake_chain = types.SimpleNamespace(calls=calls_df, puts=puts_df)
        fake_ticker = MagicMock()
        fake_ticker.options = ["2026-05-15", "2026-06-19"]
        fake_ticker.option_chain.return_value = fake_chain
        with patch.object(yfa, "_YF_AVAILABLE", True), \
             patch.object(yfa, "yf", MagicMock(Ticker=MagicMock(return_value=fake_ticker))):
            oc = self.a.get_options_chain("AAPL")
        assert oc["expiry"] == "2026-05-15"
        assert len(oc["calls"]) == 2
        assert len(oc["puts"]) == 2
        assert "2026-06-19" in oc["expirations"]

    def test_options_unavailable(self):
        with patch.object(yfa, "_YF_AVAILABLE", False):
            oc = self.a.get_options_chain("AAPL")
        assert oc["expiry"] is None
        assert oc["calls"] == []

    def test_health_check_false_when_unavailable(self):
        with patch.object(yfa, "_YF_AVAILABLE", False):
            assert self.a.health_check() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
