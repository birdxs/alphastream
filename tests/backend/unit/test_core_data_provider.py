# -*- coding: utf-8 -*-
"""
Input : pytest 收集
Output: DataProvider 单元测试 (统一接口 / 缓存命中 / 限流 / 故障转移代理)
Pos   : tests/backend/unit/test_core_data_provider.py - BE-03c Core #5

一旦此文件被修改，请同步更新 tests/audit/reports/BE-03c_core_misc.md。
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.core import data_provider as dp_mod
from app.core.data_provider import DataProvider, get_data_provider
from app.core.cache import UnifiedCache


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch):
    """每个用例前后清掉 DataProvider / Cache 单例，避免互相污染。"""
    dp_mod._data_provider = None
    DataProvider._instance = None
    UnifiedCache._instance = None
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("USE_REDIS_CACHE", "false")
    yield
    dp_mod._data_provider = None
    DataProvider._instance = None
    UnifiedCache._instance = None


def _build_provider_with_mock_fallback():
    """构造 DataProvider 并替换 fallback 为 MagicMock。"""
    dp = DataProvider()
    dp.fallback = MagicMock()
    dp._cache._memory_cache.clear()
    dp._cache._memory_ttl.clear()
    dp._min_interval = 0  # 关掉限流以加速测试
    return dp


def test_singleton_identity():
    """DataProvider 单例 + get_data_provider 一致。"""
    a = get_data_provider()
    b = get_data_provider()
    assert a is b
    assert isinstance(a, DataProvider)


def test_get_stock_history_uses_fallback_and_cache():
    """get_stock_history 走 fallback，第二次走缓存（返回原始 source）。"""
    dp = _build_provider_with_mock_fallback()
    df = pd.DataFrame({"date": ["2025-01-01"], "open": [1.0],
                       "high": [2.0], "low": [0.9], "close": [1.5],
                       "volume": [100]})

    # Mock Registry 抛异常，强制走 FallbackManager（整个测试期间有效）
    with patch.object(dp._registry, 'call_with_fallback', side_effect=Exception("Registry failed")):
        with patch.object(dp.fallback, 'execute', return_value=df) as mock_fallback:
            # 第一次调用
            r1, source1 = dp.get_stock_history("600519", "2025-01-01", "2025-01-31")
            assert not r1.empty
            assert source1 == 'fallback'
            assert mock_fallback.call_count == 1

            # 第二次调用：缓存命中，但返回原始 source（设计行为）
            r2, source2 = dp.get_stock_history("600519", "2025-01-01", "2025-01-31")
            assert mock_fallback.call_count == 1  # fallback 不再被调用
            assert source2 == 'fallback'  # 缓存返回原始 source
            assert list(r2.columns) == list(df.columns)


def test_get_stock_info_caches_dict():
    """get_stock_info 缓存 dict 结果。"""
    dp = _build_provider_with_mock_fallback()
    dp.fallback.execute.return_value = {"name": "贵州茅台", "industry": "白酒"}

    r1 = dp.get_stock_info("600519")
    r2 = dp.get_stock_info("600519")
    assert r1 == {"name": "贵州茅台", "industry": "白酒"}
    assert r2 == r1
    assert dp.fallback.execute.call_count == 1


def test_pass_through_methods_call_fallback():
    """get_index_stocks / get_capital_flow 等无缓存方法直通 fallback；
    get_board_stocks 等专属方法直接走 akshare。"""
    dp = _build_provider_with_mock_fallback()
    dp.fallback.execute.return_value = ["600000", "600036"]
    out = dp.get_index_stocks("000300")
    assert out == ["600000", "600036"]
    dp.fallback.execute.assert_called_with("get_index_stocks", "000300")

    # board/industry/concept 仅 akshare 支持，直接走 akshare 而非 fallback
    dp.akshare = MagicMock()
    dp.akshare.get_board_stocks.return_value = ["a", "b"]
    assert dp.get_board_stocks("半导体") == ["a", "b"]
    dp.akshare.get_board_stocks.assert_called_once_with("半导体")


def test_health_and_status_delegated():
    """health_check / get_status 委托给 fallback。"""
    dp = _build_provider_with_mock_fallback()
    dp.fallback.get_status.return_value = {"status": {"akshare": True}, "fail_count": {}}
    st = dp.get_status()
    assert "status" in st
    dp.reset_status()
    dp.fallback.reset_status.assert_called_once()


def test_rate_limiter_sleeps_between_calls():
    """_rate_limit 在 min_interval 内会 sleep。"""
    dp = _build_provider_with_mock_fallback()
    dp._min_interval = 0.05
    dp._last_request_time = time.time()  # 刚刚才调过
    t0 = time.time()
    dp._rate_limit()
    elapsed = time.time() - t0
    # 应至少接近 min_interval
    assert elapsed >= 0.04


def test_empty_history_not_cached():
    """空 DataFrame 不应写入缓存。"""
    dp = _build_provider_with_mock_fallback()
    dp.fallback.execute.return_value = pd.DataFrame()
    r1, source1 = dp.get_stock_history("000001", "2025-01-01", "2025-01-31")
    assert r1.empty
    assert source1 == 'empty'
    # 第二次还会再调 fallback（未缓存）
    r2, source2 = dp.get_stock_history("000001", "2025-01-01", "2025-01-31")
    assert dp.fallback.execute.call_count == 2
    assert source2 == 'empty'
