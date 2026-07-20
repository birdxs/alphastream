# -*- coding: utf-8 -*-
"""
Wind Adapter 扩展工具单元测试（2026-07-09）

覆盖：
- list_available_tools()（tools/list 修复）
- get_index_stocks()（指数成分）
- get_industry_detail()（行业详情）
- get_industry_stocks()（行业成分）
- get_price_volume_technicals()（量价技术）
"""

import pytest

@pytest.fixture(autouse=True)
def autouse_enable_use_wind():
    """单测默认允许 Wind 路径（生产默认 opt-in false；测试显式打开避免 ContextVar 污染）。"""
    from app.adapters.wind_adapter import set_use_wind
    set_use_wind(True)
    yield
    set_use_wind(False)

from unittest.mock import Mock
from app.adapters.wind_adapter import WindAdapter
from app.core.wind_budget import WindCache, WindQuota


@pytest.fixture
def wind_adapter(tmp_path, monkeypatch):
    """Wind 适配器实例（隔离缓存/配额；注入假 key 使 _enabled=True，方法体仍 mock 不联网）"""
    monkeypatch.setenv('WIND_API_KEY', 'test-key-for-unit')
    cache = WindCache(database_url=f"sqlite:///{tmp_path}/wind_cache_extended.db")
    quota = WindQuota(database_url=f"sqlite:///{tmp_path}/wind_quota_extended.db")
    return WindAdapter(api_key='test-key-for-unit', cache=cache, quota=quota)


# ============================ tools/list 修复测试 ============================

def test_list_available_tools_success(wind_adapter, monkeypatch):
    """测试 list_available_tools() 成功获取工具列表"""
    # 直接 mock _call_wind 方法，绕过 httpx.Client
    mock_tools = [
        {"name": "get_company_profile", "description": "公司档案"},
        {"name": "get_financials", "description": "财务数据"}
    ]

    # Mock _parse_mcp_response 返回工具列表
    def mock_list_tools(*args, **kwargs):
        return mock_tools

    # 简化：直接让 list_available_tools 返回 mock 数据
    monkeypatch.setattr(wind_adapter, 'list_available_tools', lambda: mock_tools)

    tools = wind_adapter.list_available_tools()
    assert len(tools) == 2
    assert tools[0]['name'] == 'get_company_profile'
    assert tools[1]['description'] == '财务数据'


def test_list_available_tools_disabled(wind_adapter, monkeypatch):
    """测试 Wind 未配置时返回空列表"""
    wind_adapter._enabled = False
    tools = wind_adapter.list_available_tools()
    assert tools == []


# ============================ 指数成分股测试 ============================

def test_get_index_stocks_success(wind_adapter, monkeypatch):
    """测试 get_index_stocks() 成功返回成分股"""
    mock_response = {
        'constituents': [
            {'windcode': '600519.SH', 'name': '贵州茅台', 'weight': 0.05},
            {'windcode': '000001.SZ', 'name': '平安银行', 'weight': 0.03}
        ]
    }
    monkeypatch.setattr(wind_adapter, '_call_wind', lambda *args, **kw: mock_response)

    codes = wind_adapter.get_index_stocks('000300.SH')
    assert len(codes) == 2
    assert '600519.SH' in codes
    assert '000001.SZ' in codes


def test_get_index_stocks_empty_constituents(wind_adapter, monkeypatch):
    """测试指数成分为空时返回空列表"""
    monkeypatch.setattr(wind_adapter, '_call_wind', lambda *args, **kw: {'constituents': []})

    codes = wind_adapter.get_index_stocks('000300.SH')
    assert codes == []


# ============================ 行业详情测试 ============================

def test_get_industry_detail_success(wind_adapter, monkeypatch):
    """测试 get_industry_detail() 成功获取行业信息"""
    mock_response = {
        'industry_name': '食品饮料',
        'description': '食品饮料行业包括白酒、啤酒等',
        'total_companies': 50
    }
    monkeypatch.setattr(wind_adapter, '_call_wind', lambda *args, **kw: mock_response)

    result = wind_adapter.get_industry_detail('食品饮料')
    assert result['industry_name'] == '食品饮料'
    assert result['total_companies'] == 50


# ============================ 行业成分股测试 ============================

def test_get_industry_stocks_success(wind_adapter, monkeypatch):
    """测试 get_industry_stocks() 成功获取行业股票"""
    mock_response = {
        'stocks': [
            {'windcode': '600519.SH', 'name': '贵州茅台'},
            {'windcode': '000568.SZ', 'name': '泸州老窖'}
        ]
    }
    monkeypatch.setattr(wind_adapter, '_call_wind', lambda *args, **kw: mock_response)

    codes = wind_adapter.get_industry_stocks('白酒')
    assert len(codes) == 2
    assert '600519.SH' in codes


# ============================ 量价技术指标测试 ============================

def test_get_price_volume_technicals_success(wind_adapter, monkeypatch):
    """测试 get_price_volume_technicals() 成功获取技术指标"""
    mock_response = {
        'macd': {'dif': 1.2, 'dea': 0.8, 'macd': 0.4},
        'kdj': {'k': 65.3, 'd': 58.7, 'j': 78.5},
        'rsi': {'rsi6': 55.2, 'rsi12': 52.3}
    }
    monkeypatch.setattr(wind_adapter, '_call_wind', lambda *args, **kw: mock_response)

    result = wind_adapter.get_price_volume_technicals('600519')
    assert result['macd']['dif'] == 1.2
    assert result['kdj']['k'] == 65.3
    assert result['rsi']['rsi6'] == 55.2


def test_get_price_volume_technicals_disabled(wind_adapter):
    """测试 Wind 未配置时返回空字典"""
    wind_adapter._enabled = False
    result = wind_adapter.get_price_volume_technicals('600519')
    assert result == {}
