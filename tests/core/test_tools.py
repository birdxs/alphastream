"""
DP-P2-2: 测试 get_fundamental_data 统一走 registry xbrl_financials
"""
import pytest
from unittest.mock import patch, MagicMock


def test_fundamental_registry_wind_success():
    """测试 registry Wind 成功路径"""
    from app.core.tools import get_fundamental_data

    mock_result = {
        'data': {'pe_ttm': 20.5, 'pb': 6.2, 'roe': 10.5},
        'source': 'wind'
    }

    # Mock 动态导入的 AdapterRegistry
    with patch('app.adapters.adapter_registry.AdapterRegistry') as mock_registry_cls:
        mock_registry = MagicMock()
        mock_registry_cls.return_value = mock_registry
        mock_registry.call_with_fallback.return_value = mock_result

        result = get_fundamental_data('600519')

        # 验证调用 registry
        mock_registry.call_with_fallback.assert_called_once_with(
            domain='xbrl_financials',
            method='get_financial_data',
            stock_code='600519',
            market_type='A'
        )

        # 验证返回格式
        assert '来源：wind' in result
        assert 'pe_ttm' in result or '20.5' in result


def test_fundamental_registry_fallback_edgar():
    """测试 registry 降级到 EDGAR"""
    from app.core.tools import get_fundamental_data

    mock_result = {
        'data': {'revenue': 120000000000, 'net_income': 50000000000},
        'source': 'edgar'
    }

    with patch('app.adapters.adapter_registry.AdapterRegistry') as mock_registry_cls:
        mock_registry = MagicMock()
        mock_registry_cls.return_value = mock_registry
        mock_registry.call_with_fallback.return_value = mock_result

        result = get_fundamental_data('600519')

        # 验证 source 标记
        assert '来源：edgar' in result.lower() or 'edgar' in result.lower()


def test_fundamental_registry_all_fail_use_analyzer():
    """测试 registry 全失败降级到 FundamentalAnalyzer"""
    from app.core.tools import get_fundamental_data

    with patch('app.adapters.adapter_registry.AdapterRegistry') as mock_registry_cls:
        mock_registry = MagicMock()
        mock_registry_cls.return_value = mock_registry
        # registry 返回空结果
        mock_registry.call_with_fallback.return_value = None

        with patch('app.analysis.fundamental_analyzer.FundamentalAnalyzer') as mock_fa_cls:
            mock_fa = MagicMock()
            mock_fa_cls.return_value = mock_fa
            mock_fa.get_financial_indicators.return_value = {'pe': 18.5, 'pb': 5.8}

            result = get_fundamental_data('600519')

            # 验证调用了 FundamentalAnalyzer
            mock_fa.get_financial_indicators.assert_called_once_with('600519')
            assert 'pe' in result.lower() or '18.5' in result


def test_fundamental_registry_exception_fallback():
    """测试 registry 异常时降级"""
    from app.core.tools import get_fundamental_data

    with patch('app.adapters.adapter_registry.AdapterRegistry') as mock_registry_cls:
        mock_registry_cls.side_effect = Exception("Registry init failed")

        with patch('app.analysis.fundamental_analyzer.FundamentalAnalyzer') as mock_fa_cls:
            mock_fa = MagicMock()
            mock_fa_cls.return_value = mock_fa
            mock_fa.get_financial_indicators.return_value = {'metrics': 'data'}

            result = get_fundamental_data('600519')

            # 异常不阻塞降级路径
            mock_fa.get_financial_indicators.assert_called_once()
            assert 'metrics' in result or 'data' in result


def test_fundamental_final_failure():
    """测试所有路径失败"""
    from app.core.tools import get_fundamental_data

    with patch('app.adapters.adapter_registry.AdapterRegistry') as mock_registry_cls:
        mock_registry = MagicMock()
        mock_registry_cls.return_value = mock_registry
        mock_registry.call_with_fallback.return_value = None

        with patch('app.analysis.fundamental_analyzer.FundamentalAnalyzer') as mock_fa_cls:
            mock_fa = MagicMock()
            mock_fa_cls.return_value = mock_fa
            mock_fa.get_financial_indicators.return_value = None

            result = get_fundamental_data('600519')

            # 铁律 #1：不造假财务数据
            assert '未获取到' in result or '失败' in result
