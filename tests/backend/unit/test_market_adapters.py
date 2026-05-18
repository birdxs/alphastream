"""
Input: mock akshare/yfinance + 股票代码
Output: 验证 market_data_adapter 港股/美股 / A 股路由 + 归一化 + 故障兜底
Pos: tests/backend/unit/test_market_adapters.py - FIX-8 配套测试
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.adapters import market_data_adapter as mda
from app.adapters.market_data_adapter import (
    get_kline,
    get_quote,
    get_fundamentals,
    UnsupportedMarketError,
    _normalize_kline_df,
)
from app.core.network_resilience import reset_cache_for_tests


@pytest.fixture(autouse=True)
def _clean_cache():
    reset_cache_for_tests()
    yield
    reset_cache_for_tests()


# ===== 归一化 =====

class TestNormalize:
    def test_normalize_chinese_columns(self):
        raw = pd.DataFrame({
            '日期': ['2026-05-01', '2026-05-02'],
            '开盘': [10.0, 10.1], '收盘': [10.5, 10.3],
            '最高': [10.6, 10.4], '最低': [9.9, 10.0],
            '成交量': [1000, 1100],
        })
        df = _normalize_kline_df(raw)
        assert list(df.columns)[:6] == ['date', 'open', 'close', 'high', 'low', 'volume']
        assert len(df) == 2

    def test_normalize_empty_returns_empty(self):
        df = _normalize_kline_df(pd.DataFrame())
        assert df.empty

    def test_normalize_missing_essential_returns_empty(self):
        raw = pd.DataFrame({'日期': ['2026-05-01'], '开盘': [10.0]})
        df = _normalize_kline_df(raw)
        assert df.empty


# ===== 不支持的市场 =====

class TestUnsupportedMarket:
    def test_get_kline_unknown_market(self):
        # adapter 内部 catch DataSourceUnavailableError, 但 UnsupportedMarketError
        # 在 try 之外被吞掉前会先到 try 块 — 设计上不支持的 market 直接 raise
        # 当前实现: 不支持的 market 走 else 抛 UnsupportedMarketError，包在 try 内
        # 但 except 只 catch DataSourceTimeoutError / DataSourceUnavailableError
        # → UnsupportedMarketError 会向上抛出
        with pytest.raises(UnsupportedMarketError):
            get_kline("X", market="XYZ")

    def test_get_quote_unknown_market(self):
        with pytest.raises(UnsupportedMarketError):
            get_quote("X", market="XYZ")

    def test_get_fundamentals_unknown_market(self):
        with pytest.raises(UnsupportedMarketError):
            get_fundamentals("X", market="XYZ")


# ===== 港股 =====

class TestHKAdapter:
    def test_hk_kline_via_akshare(self):
        fake_df = pd.DataFrame({
            '日期': ['2026-05-15', '2026-05-16'],
            '开盘': [300.0, 305.0], '收盘': [310.0, 308.0],
            '最高': [315.0, 309.0], '最低': [299.0, 304.0],
            '成交量': [50000, 60000],
        })
        with patch.object(mda, '_fetch_hk_kline_raw', return_value=fake_df) as mock_fn:
            df = get_kline('00700', 'HK', start_date='20260501', end_date='20260516')
        assert not df.empty
        assert df.iloc[-1]['close'] == 308.0
        assert mock_fn.called

    def test_hk_quote(self):
        fake_quote = {
            'code': '00700', 'name': '腾讯控股',
            'price': 308.0, 'change_pct': -0.65,
            'volume': 60000, 'amount': 0, 'market': 'HK',
        }
        with patch.object(mda, '_fetch_hk_spot_raw', return_value=fake_quote):
            q = get_quote('00700', 'HK')
        assert q['name'] == '腾讯控股'
        assert q['price'] == 308.0
        assert q['market'] == 'HK'


# ===== 美股 =====

class TestUSAdapter:
    def test_us_kline(self):
        fake_df = pd.DataFrame({
            '日期': ['2026-05-15', '2026-05-16'],
            '开盘': [180.0, 182.0], '收盘': [185.0, 184.0],
            '最高': [186.0, 185.0], '最低': [179.0, 181.0],
            '成交量': [1000000, 1100000],
        })
        with patch.object(mda, '_fetch_us_kline_raw', return_value=fake_df):
            df = get_kline('AAPL', 'US', start_date='20260501', end_date='20260516')
        assert not df.empty
        assert df.iloc[0]['open'] == 180.0

    def test_us_quote(self):
        fake_quote = {
            'code': 'AAPL', 'name': 'Apple Inc.',
            'price': 184.0, 'change_pct': -0.5,
            'volume': 1100000, 'market': 'US',
        }
        with patch.object(mda, '_fetch_us_spot_raw', return_value=fake_quote):
            q = get_quote('AAPL', 'US')
        assert q['code'] == 'AAPL'
        assert q['price'] == 184.0

    def test_us_kline_failure_returns_empty(self):
        """akshare + yfinance 都失败 → 返回空 DataFrame, 不抛"""
        def boom(*args, **kwargs):
            raise ConnectionError("network down")

        with patch.object(mda, '_fetch_us_kline_raw', side_effect=boom):
            df = get_kline('AAPL', 'US')
        # 韧性层降级到空 DataFrame
        assert df.empty


# ===== 基本面 =====

class TestFundamentals:
    def test_fundamentals_assembles_from_quote(self):
        with patch.object(mda, '_fetch_hk_spot_raw',
                          return_value={'name': '腾讯控股', 'price': 308.0,
                                        'code': '00700', 'market': 'HK',
                                        'change_pct': -0.5, 'volume': 1, 'amount': 0}):
            f = get_fundamentals('00700', 'HK')
        assert f['name'] == '腾讯控股'
        assert f['market'] == 'HK'
        assert f['price'] == 308.0


# ===== A 股委托 DataProvider =====

class TestADelegate:
    def test_a_share_calls_data_provider(self):
        """A 股路径委托 DataProvider.get_stock_history"""
        fake_df = pd.DataFrame({
            '日期': ['2026-05-15', '2026-05-16'],
            '开盘': [10.5, 10.6], '收盘': [10.7, 10.8],
            '最高': [10.9, 10.85], '最低': [10.4, 10.55],
            '成交量': [1000, 1100],
        })
        # patch DataProvider 类
        with patch('app.core.data_provider.DataProvider') as MockDP:
            instance = MagicMock()
            instance.get_stock_history.return_value = fake_df
            MockDP.return_value = instance
            df = get_kline('000001', 'A', start_date='20260515', end_date='20260516')
        assert not df.empty
        assert df.iloc[-1]['close'] == 10.8
