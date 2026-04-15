# -*- coding: utf-8 -*-
"""
ccxt适配器单元测试 [NEW-FILE:#20260415-11]
Input: mock ccxt.Exchange 的 fetch_ticker/fetch_ohlcv/fetch_order_book/load_markets
Output: pytest结果，覆盖核心方法+降级+契约
Pos: tests/adapters/ — 回归基线
"""
import sys
import os
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.adapters import ccxt_adapter as cca  # noqa: E402


def _make_adapter_with_mock(exchange_mock):
    """辅助：构造一个已注入mock exchange的CCXTAdapter。"""
    with patch.object(cca, "_CCXT_AVAILABLE", True), \
         patch.object(cca, "ccxt", MagicMock(binance=MagicMock(return_value=exchange_mock))):
        a = cca.CCXTAdapter("binance")
    return a


class TestCCXTAvailability:
    def test_unavailable_returns_empty(self):
        with patch.object(cca, "_CCXT_AVAILABLE", False):
            a = cca.CCXTAdapter("binance")
        assert a.get_ticker("BTC/USDT") == {}
        assert a.get_ohlcv("BTC/USDT").empty
        assert a.get_order_book("BTC/USDT")["bids"] == []
        assert a.list_markets().empty
        assert a.health_check() is False

    def test_name(self):
        with patch.object(cca, "_CCXT_AVAILABLE", False):
            a = cca.CCXTAdapter("okx")
        assert a.name == "ccxt:okx"


class TestGetTicker:
    def test_ticker_normal(self):
        ex = MagicMock()
        ex.fetch_ticker.return_value = {
            "symbol": "BTC/USDT", "last": 65000.0, "bid": 64999.0,
            "ask": 65001.0, "high": 66000.0, "low": 64000.0, "volume": 1234.5,
        }
        a = _make_adapter_with_mock(ex)
        t = a.get_ticker("BTC/USDT")
        assert t["last"] == 65000.0
        assert t["symbol"] == "BTC/USDT"
        ex.fetch_ticker.assert_called_once_with("BTC/USDT")

    def test_ticker_exception_degraded(self):
        ex = MagicMock()
        ex.fetch_ticker.side_effect = RuntimeError("network down")
        a = _make_adapter_with_mock(ex)
        assert a.get_ticker("BTC/USDT") == {}


class TestGetOHLCV:
    def test_ohlcv_normal(self):
        ex = MagicMock()
        ex.fetch_ohlcv.return_value = [
            [1713139200000, 65000.0, 66000.0, 64000.0, 65500.0, 1000.0],
            [1713225600000, 65500.0, 67000.0, 65000.0, 66500.0, 1200.0],
        ]
        a = _make_adapter_with_mock(ex)
        df = a.get_ohlcv("BTC/USDT", timeframe="1d", limit=2)
        assert not df.empty
        assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
        assert len(df) == 2
        assert df.iloc[0]["close"] == 65500.0

    def test_ohlcv_invalid_timeframe_degrades(self):
        ex = MagicMock()
        ex.fetch_ohlcv.return_value = [[1713139200000, 1, 2, 0.5, 1.5, 10]]
        a = _make_adapter_with_mock(ex)
        df = a.get_ohlcv("BTC/USDT", timeframe="999x")
        assert not df.empty
        kwargs = ex.fetch_ohlcv.call_args.kwargs
        assert kwargs.get("timeframe") == "1d"

    def test_ohlcv_empty_response(self):
        ex = MagicMock()
        ex.fetch_ohlcv.return_value = []
        a = _make_adapter_with_mock(ex)
        assert a.get_ohlcv("BTC/USDT").empty


class TestOrderBookAndMarkets:
    def test_order_book_normal(self):
        ex = MagicMock()
        ex.fetch_order_book.return_value = {
            "bids": [[65000.0, 0.5], [64999.0, 1.0]],
            "asks": [[65001.0, 0.3], [65002.0, 2.0]],
            "timestamp": 1713139200000,
        }
        a = _make_adapter_with_mock(ex)
        ob = a.get_order_book("BTC/USDT", limit=10)
        assert ob["symbol"] == "BTC/USDT"
        assert len(ob["bids"]) == 2
        assert ob["bids"][0][0] == 65000.0
        assert ob["timestamp"] == 1713139200000

    def test_list_markets_normal(self):
        ex = MagicMock()
        ex.load_markets.return_value = {
            "BTC/USDT": {"base": "BTC", "quote": "USDT", "active": True, "spot": True, "type": "spot"},
            "ETH/USDT": {"base": "ETH", "quote": "USDT", "active": True, "type": "spot"},
        }
        a = _make_adapter_with_mock(ex)
        df = a.list_markets()
        assert not df.empty
        assert len(df) == 2
        assert set(df["symbol"]) == {"BTC/USDT", "ETH/USDT"}
        assert set(df.columns) >= {"symbol", "base", "quote", "active", "type"}

    def test_health_check_ok(self):
        ex = MagicMock()
        ex.load_markets.return_value = {"BTC/USDT": {"base": "BTC", "quote": "USDT"}}
        a = _make_adapter_with_mock(ex)
        assert a.health_check() is True


class TestContract:
    def test_get_stock_history_filters_by_date(self):
        ex = MagicMock()
        ex.fetch_ohlcv.return_value = [
            [pd.Timestamp("2026-04-10").value // 10**6, 1, 2, 0.5, 1.5, 10],
            [pd.Timestamp("2026-04-14").value // 10**6, 2, 3, 1.5, 2.5, 20],
            [pd.Timestamp("2026-04-20").value // 10**6, 3, 4, 2.5, 3.5, 30],
        ]
        a = _make_adapter_with_mock(ex)
        df = a.get_stock_history("BTC/USDT", "20260412", "20260415")
        assert len(df) == 1
        assert "amount" in df.columns

    def test_get_index_stocks_empty(self):
        with patch.object(cca, "_CCXT_AVAILABLE", False):
            a = cca.CCXTAdapter("binance")
        assert a.get_index_stocks("any") == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
