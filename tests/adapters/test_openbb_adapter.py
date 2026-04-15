# -*- coding: utf-8 -*-
"""
OpenBB适配器单元测试 [NEW-FILE:#20260415-20]
Input: mock obb.equity/crypto/economy 路由返回 OBBject
Output: pytest结果
Pos: tests/adapters/ — OpenBB桥接回归基线
"""
import sys
import os
import types
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.adapters import openbb_adapter as oba  # noqa: E402


def _fake_obbject_df(df: pd.DataFrame):
    """构造一个拥有 .to_df() 的 fake OBBject。"""
    obj = MagicMock()
    obj.to_df.return_value = df
    # 去除 .results，强迫走 to_df 分支
    del obj.results
    return obj


def _fake_obbject_results(dicts: list):
    obj = MagicMock()
    obj.results = [types.SimpleNamespace(model_dump=lambda d=d: d) for d in dicts]
    # 去除 to_df 以强迫走 results 分支
    del obj.to_df
    return obj


class TestOpenBBUnavailable:
    """openbb未安装时全接口降级。"""
    def setup_method(self):
        self.a = oba.OpenBBAdapter()

    def test_equity_price_empty(self):
        with patch.object(oba, "_OBB_AVAILABLE", False):
            df = self.a.get_equity_price("AAPL")
        assert df.empty

    def test_profile_empty(self):
        with patch.object(oba, "_OBB_AVAILABLE", False):
            assert self.a.get_equity_profile("AAPL") == {}

    def test_crypto_empty(self):
        with patch.object(oba, "_OBB_AVAILABLE", False):
            assert self.a.get_crypto_price("BTC-USD").empty

    def test_economy_empty(self):
        with patch.object(oba, "_OBB_AVAILABLE", False):
            assert self.a.get_economy_indicator("gdp").empty

    def test_health_false(self):
        with patch.object(oba, "_OBB_AVAILABLE", False):
            assert self.a.health_check() is False


class TestEquityPrice:
    def setup_method(self):
        self.a = oba.OpenBBAdapter()

    def test_equity_price_happy(self):
        fake_df = pd.DataFrame({
            "Date": ["2026-04-14", "2026-04-15"],
            "Open": [100, 101], "High": [102, 103],
            "Low": [99, 100], "Close": [101, 102], "Volume": [1000, 2000],
        })
        fake_obb = MagicMock()
        fake_obb.equity.price.historical.return_value = _fake_obbject_df(fake_df)
        with patch.object(oba, "_OBB_AVAILABLE", True), \
             patch.object(oba, "obb", fake_obb):
            df = self.a.get_equity_price("AAPL", start="2026-04-14", end="2026-04-15")
        assert not df.empty
        assert "date" in df.columns and "close" in df.columns
        assert len(df) == 2
        # 验证参数传递
        _, kwargs = fake_obb.equity.price.historical.call_args
        assert kwargs["symbol"] == "AAPL"
        assert kwargs["start_date"] == "2026-04-14"
        assert kwargs["provider"] == "yfinance"

    def test_equity_price_guards_provider(self):
        """非免费provider自动降级yfinance。"""
        fake_obb = MagicMock()
        fake_obb.equity.price.historical.return_value = _fake_obbject_df(pd.DataFrame())
        with patch.object(oba, "_OBB_AVAILABLE", True), \
             patch.object(oba, "obb", fake_obb):
            self.a.get_equity_price("AAPL", provider="polygon_paid")
        _, kwargs = fake_obb.equity.price.historical.call_args
        assert kwargs["provider"] == "yfinance"

    def test_equity_price_exception(self):
        fake_obb = MagicMock()
        fake_obb.equity.price.historical.side_effect = RuntimeError("boom")
        with patch.object(oba, "_OBB_AVAILABLE", True), \
             patch.object(oba, "obb", fake_obb):
            df = self.a.get_equity_price("AAPL")
        assert df.empty


class TestProfileAndCrypto:
    def setup_method(self):
        self.a = oba.OpenBBAdapter()

    def test_profile_returns_dict(self):
        fake_obb = MagicMock()
        fake_obb.equity.profile.return_value = _fake_obbject_results(
            [{"symbol": "AAPL", "name": "Apple"}]
        )
        with patch.object(oba, "_OBB_AVAILABLE", True), \
             patch.object(oba, "obb", fake_obb):
            p = self.a.get_equity_profile("AAPL")
        assert p["symbol"] == "AAPL"
        assert p["name"] == "Apple"

    def test_crypto_price(self):
        fake_df = pd.DataFrame({"date": ["2026-04-15"], "close": [65000.0]})
        fake_obb = MagicMock()
        fake_obb.crypto.price.historical.return_value = _fake_obbject_df(fake_df)
        with patch.object(oba, "_OBB_AVAILABLE", True), \
             patch.object(oba, "obb", fake_obb):
            df = self.a.get_crypto_price("BTC-USD")
        assert not df.empty
        assert df.iloc[0]["close"] == 65000.0


class TestEconomy:
    def setup_method(self):
        self.a = oba.OpenBBAdapter()

    def test_economy_gdp(self):
        fake_df = pd.DataFrame({"date": ["2026-01-01"], "value": [3.2]})
        fake_obb = MagicMock()
        fake_obb.economy.gdp.real.return_value = _fake_obbject_df(fake_df)
        with patch.object(oba, "_OBB_AVAILABLE", True), \
             patch.object(oba, "obb", fake_obb):
            df = self.a.get_economy_indicator("gdp")
        assert not df.empty
        assert fake_obb.economy.gdp.real.called

    def test_economy_cpi(self):
        fake_df = pd.DataFrame({"date": ["2026-01-01"], "value": [3.1]})
        fake_obb = MagicMock()
        fake_obb.economy.cpi.return_value = _fake_obbject_df(fake_df)
        with patch.object(oba, "_OBB_AVAILABLE", True), \
             patch.object(oba, "obb", fake_obb):
            df = self.a.get_economy_indicator("cpi")
        assert not df.empty
        assert fake_obb.economy.cpi.called


class TestBaseContract:
    def setup_method(self):
        self.a = oba.OpenBBAdapter()

    def test_name(self):
        assert self.a.name == "openbb"

    def test_get_stock_history_a_share_symbol(self):
        fake_df = pd.DataFrame({
            "Date": ["2024-01-02"], "Open": [10], "High": [11],
            "Low": [9], "Close": [10.5], "Volume": [1000],
        })
        fake_obb = MagicMock()
        fake_obb.equity.price.historical.return_value = _fake_obbject_df(fake_df)
        with patch.object(oba, "_OBB_AVAILABLE", True), \
             patch.object(oba, "obb", fake_obb):
            df = self.a.get_stock_history("600519", "20240101", "20240201")
        _, kwargs = fake_obb.equity.price.historical.call_args
        assert kwargs["symbol"] == "600519.SS"
        assert kwargs["start_date"] == "2024-01-01"
        assert kwargs["end_date"] == "2024-02-01"
        assert not df.empty

    def test_get_index_stocks_empty(self):
        assert self.a.get_index_stocks("000300") == []

    def test_get_financial_data_empty(self):
        assert self.a.get_financial_data("AAPL") == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
