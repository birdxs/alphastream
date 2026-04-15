# -*- coding: utf-8 -*-
"""
CoinGecko适配器单元测试 [NEW-FILE:#20260415-12]
Input: mock requests.get 响应 /simple/price, /coins/{id}/market_chart, /global, /search/trending
Output: pytest结果，覆盖核心端点+限流+契约
Pos: tests/adapters/ — 回归基线
"""
import sys
import os
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.adapters import coingecko_adapter as cga  # noqa: E402


def _mock_response(status=200, payload=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    return r


class TestGetPrice:
    def test_price_normal(self):
        payload = {"bitcoin": {"usd": 65000.0}, "ethereum": {"usd": 3200.0}}
        with patch.object(cga.requests, "get", return_value=_mock_response(200, payload)) as g:
            a = cga.CoinGeckoAdapter()
            a._MIN_INTERVAL = 0  # 测试中跳过sleep
            out = a.get_price(["bitcoin", "ethereum"], vs="usd")
        assert out["bitcoin"]["usd"] == 65000.0
        assert out["ethereum"]["usd"] == 3200.0
        # 验证URL & params
        args, kwargs = g.call_args
        assert args[0].endswith("/simple/price")
        assert kwargs["params"]["ids"] == "bitcoin,ethereum"
        assert kwargs["params"]["vs_currencies"] == "usd"

    def test_price_empty_coins(self):
        with patch.object(cga.requests, "get") as g:
            a = cga.CoinGeckoAdapter()
            a._MIN_INTERVAL = 0
            assert a.get_price([]) == {}
            g.assert_not_called()

    def test_price_429_degraded(self):
        with patch.object(cga.requests, "get", return_value=_mock_response(429)), \
             patch.object(cga.time, "sleep"):
            a = cga.CoinGeckoAdapter()
            a._MIN_INTERVAL = 0
            assert a.get_price(["bitcoin"]) == {}


class TestMarketChart:
    def test_market_chart_dataframe(self):
        payload = {
            "prices": [[1713139200000, 65000.0], [1713225600000, 66000.0]],
            "market_caps": [[1713139200000, 1.3e12], [1713225600000, 1.32e12]],
            "total_volumes": [[1713139200000, 30e9], [1713225600000, 32e9]],
        }
        with patch.object(cga.requests, "get", return_value=_mock_response(200, payload)):
            a = cga.CoinGeckoAdapter()
            a._MIN_INTERVAL = 0
            df = a.get_market_chart("bitcoin", days=2)
        assert not df.empty
        assert list(df.columns) == ["date", "price", "market_cap", "volume"]
        assert len(df) == 2
        assert df.iloc[0]["price"] == 65000.0

    def test_market_chart_empty_response(self):
        with patch.object(cga.requests, "get", return_value=_mock_response(200, {})):
            a = cga.CoinGeckoAdapter()
            a._MIN_INTERVAL = 0
            df = a.get_market_chart("unknowncoin")
        assert df.empty


class TestTrendingAndGlobal:
    def test_trending_parsed(self):
        payload = {
            "coins": [
                {"item": {"id": "pepe", "name": "Pepe", "symbol": "PEPE",
                          "market_cap_rank": 40, "score": 0}},
                {"item": {"id": "sui", "name": "Sui", "symbol": "SUI",
                          "market_cap_rank": 25, "score": 1}},
            ]
        }
        with patch.object(cga.requests, "get", return_value=_mock_response(200, payload)):
            a = cga.CoinGeckoAdapter()
            a._MIN_INTERVAL = 0
            out = a.get_trending()
        assert len(out) == 2
        assert out[0]["id"] == "pepe"
        assert out[1]["market_cap_rank"] == 25

    def test_global_parsed(self):
        payload = {
            "data": {
                "total_market_cap": {"usd": 2.5e12},
                "total_volume": {"usd": 100e9},
                "market_cap_percentage": {"btc": 52.3, "eth": 17.5},
                "active_cryptocurrencies": 13500,
                "markets": 980,
                "updated_at": 1713139200,
            }
        }
        with patch.object(cga.requests, "get", return_value=_mock_response(200, payload)):
            a = cga.CoinGeckoAdapter()
            a._MIN_INTERVAL = 0
            g = a.get_global()
        assert g["total_market_cap_usd"] == 2.5e12
        assert g["btc_dominance"] == 52.3
        assert g["eth_dominance"] == 17.5
        assert g["active_cryptocurrencies"] == 13500


class TestThrottleAndContract:
    def test_throttle_sleeps_when_too_fast(self):
        # 两次连续调用，验证sleep被触发
        with patch.object(cga.requests, "get", return_value=_mock_response(200, {"gecko_says": "to the moon"})), \
             patch.object(cga.time, "sleep") as s, \
             patch.object(cga.time, "time", side_effect=[0.0, 0.0, 0.5, 0.5, 3.0, 3.0]):
            a = cga.CoinGeckoAdapter()
            a.health_check()
            a.health_check()
            # 第二次应触发sleep（elapsed<2.1）
            assert s.called

    def test_health_check_ping(self):
        with patch.object(cga.requests, "get", return_value=_mock_response(200, {"gecko_says": "ok"})):
            a = cga.CoinGeckoAdapter()
            a._MIN_INTERVAL = 0
            assert a.health_check() is True

    def test_get_stock_info_delegates(self):
        with patch.object(cga.requests, "get", return_value=_mock_response(200, {"bitcoin": {"usd": 65000}})):
            a = cga.CoinGeckoAdapter()
            a._MIN_INTERVAL = 0
            info = a.get_stock_info("bitcoin")
        assert info["usd"] == 65000

    def test_get_financial_data_empty(self):
        a = cga.CoinGeckoAdapter()
        assert a.get_financial_data("bitcoin") == {}

    def test_get_index_stocks_empty(self):
        a = cga.CoinGeckoAdapter()
        assert a.get_index_stocks("any") == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
