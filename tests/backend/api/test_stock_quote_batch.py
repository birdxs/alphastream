"""
/api/stock_quote_batch 批量报价接口测试
[DP-P1-3] 新增实时域测试 + 降级测试
"""
import os
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def clear_cache():
    """清理 adapters 缓存避免测试污染"""
    yield
    # 测试后清理
    import app.web.web_server as ws
    if hasattr(ws, '_adapters_status_cache'):
        ws._adapters_status_cache = None


@pytest.fixture
def mock_realtime_adapter():
    """模拟实时域 adapter 返回"""
    with patch('app.adapters.adapter_registry.AdapterRegistry.default') as mock_registry:
        registry = MagicMock()
        mock_registry.return_value = registry
        yield registry


class TestStockQuoteBatch:
    """批量报价测试套件"""

    def test_quote_batch_realtime_success(self, flask_client, mock_realtime_adapter):
        """[DP-P1-3] 实时域成功返回"""
        # 模拟实时域返回 dict 格式
        mock_realtime_adapter.call_with_fallback.return_value = {
            '600519': {
                'price': 1800.50,
                'change_pct': 2.5,
                'change': 43.8,
                'name': '贵州茅台'
            },
            '000001': {
                'price': 15.23,
                'change_pct': -1.2,
                'change': -0.18,
                'name': '平安银行'
            }
        }

        resp = flask_client.get('/api/stock_quote_batch?codes=600519,000001&market_type=A')
        assert resp.status_code == 200
        data = resp.get_json()

        assert data['source'] == 'realtime'
        assert len(data['results']) == 2
        assert resp.headers.get('X-Data-Source') == 'realtime'

        # 验证数据正确性
        result_600519 = next((r for r in data['results'] if r['code'] == '600519'), None)
        assert result_600519 is not None
        assert result_600519['latest_price'] == 1800.5
        assert result_600519['change_pct'] == 2.5

    def test_quote_batch_realtime_list_format(self, flask_client, mock_realtime_adapter):
        """[DP-P1-3] 实时域返回 list 格式"""
        mock_realtime_adapter.call_with_fallback.return_value = [
            {
                'code': '600519',
                'price': 1800.50,
                'change_pct': 2.5,
                'change': 43.8,
                'name': '贵州茅台'
            }
        ]

        resp = flask_client.get('/api/stock_quote_batch?codes=600519&market_type=A')
        assert resp.status_code == 200
        data = resp.get_json()

        assert data['source'] == 'realtime'
        assert len(data['results']) == 1

    def test_quote_batch_fallback_to_kline(self, flask_client, mock_realtime_adapter, monkeypatch):
        """[DP-P1-3] 实时域失败降级 K 线"""
        # 模拟实时域抛异常
        mock_realtime_adapter.call_with_fallback.side_effect = Exception("realtime failed")

        # 模拟 K 线数据
        import pandas as pd
        mock_df = pd.DataFrame({
            'close': [1800.0, 1820.0, 1850.0]
        })

        with patch('app.web.web_server.analyzer.get_stock_data', return_value=mock_df):
            resp = flask_client.get('/api/stock_quote_batch?codes=600519&market_type=A')
            assert resp.status_code == 200
            data = resp.get_json()

            assert data['source'] == 'kline_fallback'
            assert resp.headers.get('X-Data-Source') == 'kline_fallback'
            assert len(data['results']) == 1

    def test_quote_batch_hk_skip_realtime(self, flask_client, monkeypatch):
        """[DP-P1-3] 非 A 股跳过实时域直接 K 线"""
        import pandas as pd
        mock_df = pd.DataFrame({
            'close': [100.0, 102.0]
        })

        with patch('app.web.web_server.analyzer.get_stock_data', return_value=mock_df):
            resp = flask_client.get('/api/stock_quote_batch?codes=00700&market_type=HK')
            assert resp.status_code == 200
            data = resp.get_json()

            # HK 直接走 K 线
            assert data['source'] == 'kline_fallback'

    def test_quote_batch_empty_codes(self, flask_client):
        """空 codes 参数"""
        resp = flask_client.get('/api/stock_quote_batch?codes=')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_quote_batch_exceed_limit(self, flask_client):
        """超过 100 个限制"""
        codes = ','.join([f'60{i:04d}' for i in range(101)])
        resp = flask_client.get(f'/api/stock_quote_batch?codes={codes}')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'codes 最多 100 个' in data['error']

    def test_quote_batch_max_codes_param(self, flask_client, monkeypatch):
        """max_codes 参数限制"""
        import pandas as pd
        mock_df = pd.DataFrame({'close': [100.0, 102.0]})

        with patch('app.web.web_server.analyzer.get_stock_data', return_value=mock_df):
            resp = flask_client.get('/api/stock_quote_batch?codes=600519,000001,000002&max_codes=2')
            assert resp.status_code == 200
            data = resp.get_json()
            # 应该只处理前 2 个
            assert len(data['results']) + len(data['errors']) <= 2
