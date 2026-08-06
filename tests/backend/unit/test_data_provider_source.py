"""
DP-P1-1/P1-2: DataProvider source 透传单元测试

测试范围:
1. get_stock_history 返回 (df, source) 元组
2. source 反映真实命中 adapter
3. 缓存命中时 source='cache'
4. Registry 降级链顺序
5. web_server meta.source 透传
"""
import os
import pytest
import pandas as pd
from unittest.mock import Mock, patch
from app.core.data_provider import DataProvider


class TestDataProviderSource:
    """DataProvider source 透传测试"""

    def test_get_stock_history_returns_tuple(self):
        """get_stock_history 返回 (DataFrame, source) 元组"""
        dp = DataProvider()

        # Mock Registry 返回
        with patch.object(dp._registry, 'call_with_fallback') as mock_call:
            mock_call.return_value = {
                'data': pd.DataFrame({'close': [100, 101]}),
                'source': 'akshare'
            }

            result = dp.get_stock_history('600519', '20240101', '20240131')

            # 验证返回值类型
            assert isinstance(result, tuple)
            assert len(result) == 2
            df, source = result
            assert isinstance(df, pd.DataFrame)
            assert isinstance(source, str)

    def test_source_reflects_actual_adapter(self):
        """source 反映真实命中的 adapter"""
        # 清空缓存
        from app.core.data_provider import DataProvider
        dp = DataProvider()
        dp._cache.clear()

        # 场景1: akshare 成功
        with patch.object(dp._registry, 'call_with_fallback') as mock_call:
            mock_call.return_value = {
                'data': pd.DataFrame({'close': [100]}),
                'source': 'akshare',
                'domain': 'a_stock_kline'
            }
            df, source = dp.get_stock_history('600001', '20240101', '20240131')
            assert source == 'akshare'

        # 清空缓存
        dp._cache.clear()

        # 场景2: 降级到 baostock
        with patch.object(dp._registry, 'call_with_fallback') as mock_call:
            mock_call.return_value = {
                'data': pd.DataFrame({'close': [100]}),
                'source': 'baostock',
                'domain': 'a_stock_kline'
            }
            df, source = dp.get_stock_history('600002', '20240101', '20240131')
            assert source == 'baostock'

    def test_cache_hit_returns_cache_source(self):
        """缓存命中时 source='cache'"""
        from app.core.data_provider import DataProvider
        dp = DataProvider()
        dp._cache.clear()

        # 第一次调用（填充缓存）
        with patch.object(dp._registry, 'call_with_fallback') as mock_call:
            mock_call.return_value = {
                'data': pd.DataFrame({'close': [100]}),
                'source': 'akshare',
                'domain': 'a_stock_kline'
            }
            df1, source1 = dp.get_stock_history('600519', '20240101', '20240131')
            assert source1 == 'akshare'
            mock_call.assert_called_once()

        # 第二次调用（缓存命中，不再调用 Registry）
        df2, source2 = dp.get_stock_history('600519', '20240101', '20240131')
        assert source2 == 'cache'
        assert not df2.empty

    def test_registry_fallback_to_fallback_manager(self):
        """Registry 失败时回退 FallbackManager"""
        from app.core.data_provider import DataProvider
        dp = DataProvider()
        dp._cache.clear()

        # Mock Registry 抛异常
        with patch.object(dp._registry, 'call_with_fallback') as mock_registry:
            mock_registry.side_effect = Exception("Registry 全部失败")

            # Mock FallbackManager 成功
            with patch.object(dp.fallback, 'execute') as mock_fallback:
                mock_fallback.return_value = pd.DataFrame({'close': [100]})

                df, source = dp.get_stock_history('600519', '20240101', '20240131')

                assert source == 'fallback'
                assert not df.empty
                mock_registry.assert_called_once()
                mock_fallback.assert_called_once()

    def test_empty_result_returns_empty_df(self):
        """数据为空时返回空 DataFrame 和 'empty' source"""
        from app.core.data_provider import DataProvider
        dp = DataProvider()
        dp._cache.clear()

        # Mock Registry 返回空 DataFrame
        with patch.object(dp._registry, 'call_with_fallback') as mock_call:
            mock_call.return_value = {
                'data': pd.DataFrame(),
                'source': 'akshare',
                'domain': 'a_stock_kline'
            }

            df, source = dp.get_stock_history('600519', '20240101', '20240131')
            assert df.empty
            assert source == 'empty'


class TestAdapterRegistryMetadata:
    """AdapterRegistry 返回元数据测试"""

    def test_call_with_fallback_returns_metadata(self):
        """call_with_fallback(_return_metadata=True) 返回标准化 dict"""
        from app.adapters.adapter_registry import AdapterRegistry

        registry = AdapterRegistry()

        # Mock 适配器
        mock_adapter = Mock()
        mock_adapter.name = 'test_adapter'
        test_df = pd.DataFrame({'close': [100]})
        mock_adapter.get_stock_history = Mock(return_value=test_df)

        with patch.object(registry, 'get_adapters', return_value=[mock_adapter]):
            with patch.object(registry, '_is_valid_result', return_value=True):
                result = registry.call_with_fallback(
                    'a_stock_kline',
                    'get_stock_history',
                    stock_code='600519',
                    start_date='20240101',
                    end_date='20240131',
                    _return_metadata=True
                )

                # 验证返回结构
                assert isinstance(result, dict)
                assert 'data' in result
                assert 'source' in result
                assert 'domain' in result
                assert result['source'] == 'test_adapter'
                assert result['domain'] == 'a_stock_kline'
                assert isinstance(result['data'], pd.DataFrame)

    def test_call_with_fallback_backward_compatible(self):
        """不带 _return_metadata 时保持向后兼容（返回原始结果）"""
        from app.adapters.adapter_registry import AdapterRegistry

        registry = AdapterRegistry()

        mock_adapter = Mock()
        mock_adapter.name = 'test_adapter'
        test_df = pd.DataFrame({'close': [100]})
        mock_adapter.get_stock_history = Mock(return_value=test_df)

        with patch.object(registry, 'get_adapters', return_value=[mock_adapter]):
            with patch.object(registry, '_is_valid_result', return_value=True):
                result = registry.call_with_fallback(
                    'a_stock_kline',
                    'get_stock_history',
                    stock_code='600519',
                    start_date='20240101',
                    end_date='20240131'
                )

                # 应返回原始 DataFrame（不是 dict）
                assert isinstance(result, pd.DataFrame)
                assert not result.empty


class TestWebServerMetaSource:
    """REST /api/stock_data meta.source 透传测试"""

    @pytest.fixture
    def client(self):
        """Flask 测试客户端"""
        os.environ['AUTH_REQUIRED'] = 'false'
        os.environ['DISABLE_NETWORK'] = '1'
        os.environ['MOCK_LLM'] = '1'

        from app.web.web_server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_stock_data_meta_source(self, client, monkeypatch):
        """REST /api/stock_data 返回 meta.source"""
        from app.analysis import stock_analyzer

        # Mock analyzer.get_stock_data 返回带 _data_source 的 DataFrame
        def mock_get_stock_data(*args, **kwargs):
            df = pd.DataFrame({
                'date': ['2024-01-01', '2024-01-02'],
                'close': [100, 101],
                'open': [99, 100],
                'high': [101, 102],
                'low': [98, 99],
                'volume': [1000, 1100]
            })
            df.attrs['_data_source'] = 'baostock'
            return df

        monkeypatch.setattr(stock_analyzer.StockAnalyzer, 'get_stock_data', mock_get_stock_data)

        resp = client.get('/api/stock_data?stock_code=600519&period=1m')
        assert resp.status_code == 200

        data = resp.get_json()
        assert 'meta' in data
        assert 'source' in data['meta']
        assert data['meta']['source'] == 'baostock'  # 真实 adapter 名

    def test_stock_data_default_source(self, client, monkeypatch):
        """meta.source 默认值（df.attrs 无 _data_source 时）"""
        from app.analysis import stock_analyzer

        def mock_get_stock_data(*args, **kwargs):
            df = pd.DataFrame({
                'date': ['2024-01-01'],
                'close': [100],
                'open': [99],
                'high': [101],
                'low': [98],
                'volume': [1000]
            })
            # 不设置 attrs['_data_source']
            return df

        monkeypatch.setattr(stock_analyzer.StockAnalyzer, 'get_stock_data', mock_get_stock_data)

        resp = client.get('/api/stock_data?stock_code=600519&period=1m&market_type=A')
        data = resp.get_json()

        # A 股默认 'akshare'
        assert data['meta']['source'] == 'akshare'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
