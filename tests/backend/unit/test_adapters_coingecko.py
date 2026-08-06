"""
P2: CoinGecko Adapter AkShare 加密货币降级测试 (2026-08-05)
"""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from app.adapters.coingecko_adapter import CoinGeckoAdapter


class TestCoinGeckoAdapterAkShareFallback:
    """测试 CoinGecko Adapter AkShare 降级能力"""

    @pytest.fixture
    def adapter(self):
        return CoinGeckoAdapter()

    def test_price_fallback_success(self, adapter, monkeypatch):
        """价格获取失败 → AkShare 降级成功"""
        # Mock CoinGecko API 失败
        def mock_get_fail(endpoint, params):
            return {}

        monkeypatch.setattr(adapter, "_get", mock_get_fail)

        # Mock AkShare crypto_js_spot 成功
        mock_df = pd.DataFrame({
            "名称": ["比特币", "以太坊", "币安币"],
            "最新价": [66000.0, 3200.0, 580.0],
            "涨跌幅": [2.5, 1.8, 3.2],
        })
        with patch("akshare.crypto_js_spot", return_value=mock_df):
            result = adapter.get_price(["bitcoin"], "usd")

        assert "bitcoin" in result
        assert "usd" in result["bitcoin"]
        assert result["bitcoin"]["usd"] == 66000.0

    def test_price_fallback_multiple_coins(self, adapter, monkeypatch):
        """多币种价格获取 → AkShare 降级"""
        def mock_get_fail(endpoint, params):
            return {}

        monkeypatch.setattr(adapter, "_get", mock_get_fail)

        # Mock crypto_js_spot 返回多币种
        mock_df = pd.DataFrame({
            "名称": ["比特币", "以太坊", "币安币"],
            "最新价": [66000.0, 3200.0, 580.0],
            "涨跌幅": [2.5, 1.8, 3.2],
        })

        with patch("akshare.crypto_js_spot", return_value=mock_df):
            result = adapter.get_price(["bitcoin", "ethereum"], "usd")

        assert "bitcoin" in result
        assert "ethereum" in result
        assert result["bitcoin"]["usd"] == 66000.0
        assert result["ethereum"]["usd"] == 3200.0

    def test_price_fallback_unknown_coin(self, adapter, monkeypatch):
        """未知币种 → AkShare 降级返回空"""
        def mock_get_fail(endpoint, params):
            return {}

        monkeypatch.setattr(adapter, "_get", mock_get_fail)

        result = adapter.get_price(["unknown-coin"], "usd")

        # 未知币种应该不在结果中
        assert "unknown-coin" not in result

    def test_market_chart_fallback_success(self, adapter, monkeypatch):
        """历史数据获取失败 → AkShare 降级（返回空，因 AkShare 无历史接口）"""
        def mock_get_fail(endpoint, params):
            return {}

        monkeypatch.setattr(adapter, "_get", mock_get_fail)

        result = adapter.get_market_chart("bitcoin", days=30)

        # AkShare 不支持加密货币历史数据，应返回空 DataFrame
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_market_chart_fallback_unknown_coin(self, adapter, monkeypatch):
        """历史数据未知币种 → AkShare 降级返回空"""
        def mock_get_fail(endpoint, params):
            return {}

        monkeypatch.setattr(adapter, "_get", mock_get_fail)

        result = adapter.get_market_chart("unknown-coin", days=30)

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_fallback_akshare_not_installed(self, adapter, monkeypatch):
        """AkShare 未安装时降级失败"""
        def mock_get_fail(endpoint, params):
            return {}

        monkeypatch.setattr(adapter, "_get", mock_get_fail)

        # Mock akshare import 失败
        with patch.dict("sys.modules", {"akshare": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module akshare")):
                result = adapter.get_price(["bitcoin"], "usd")

        # CoinGecko 失败 + AkShare 不可用 → 空结果
        assert result == {}

    def test_fallback_all_fail(self, adapter, monkeypatch):
        """CoinGecko 失败 + AkShare 降级失败 → 空结果"""
        def mock_get_fail(endpoint, params):
            return {}

        monkeypatch.setattr(adapter, "_get", mock_get_fail)

        # Mock AkShare 也失败
        with patch("akshare.crypto_js_spot", side_effect=Exception("AkShare API error")):
            result = adapter.get_price(["bitcoin"], "usd")

        assert result == {}
