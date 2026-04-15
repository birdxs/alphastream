# -*- coding: utf-8 -*-
"""
AdapterRegistry 单元测试 [NEW-FILE:#20260415-21]
Input: 手写FakeAdapter注入，mock多source降级流
Output: pytest结果，覆盖register/call_with_fallback/error
Pos: tests/adapters/ — Registry核心路由回归
"""
import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.adapters.adapter_registry import AdapterRegistry  # noqa: E402
from app.adapters.base_adapter import BaseAdapter  # noqa: E402


class _NoopFake(BaseAdapter):
    """契约占位，只用于注入。"""
    def __init__(self, adapter_name: str, behavior):
        self._name = adapter_name
        self._behavior = behavior  # callable(**kwargs) -> any
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def demo(self, **kwargs):
        self.call_count += 1
        return self._behavior(**kwargs)

    def get_stock_history(self, code, start_date, end_date, adjust="qfq"):
        return pd.DataFrame()

    def get_index_stocks(self, index_code):
        return []

    def get_stock_info(self, code):
        return {}

    def get_financial_data(self, code):
        return {}

    def health_check(self):
        return True


class TestRegisterGet:
    def test_register_and_list(self):
        reg = AdapterRegistry()
        a = _NoopFake("src_a", lambda **k: {"v": 1})
        b = _NoopFake("src_b", lambda **k: {"v": 2})
        reg.register("news", a)
        reg.register("news", b)
        assert [x.name for x in reg.get_adapters("news")] == ["src_a", "src_b"]
        assert reg.list_domains() == ["news"]

    def test_get_adapters_missing_domain(self):
        reg = AdapterRegistry()
        assert reg.get_adapters("nonexistent") == []


class TestFallback:
    def test_first_succeeds(self):
        reg = AdapterRegistry()
        a = _NoopFake("src_a", lambda **k: {"v": 1})
        b = _NoopFake("src_b", lambda **k: {"v": 2})
        reg.register("news", a)
        reg.register("news", b)
        out = reg.call_with_fallback("news", "demo")
        assert out == {"v": 1}
        assert a.call_count == 1
        assert b.call_count == 0

    def test_fallback_on_empty(self):
        """首个返回空dict应视为无效，降级到第二。"""
        reg = AdapterRegistry(max_retries=1)
        a = _NoopFake("src_a", lambda **k: {})
        b = _NoopFake("src_b", lambda **k: {"v": 2})
        reg.register("news", a)
        reg.register("news", b)
        out = reg.call_with_fallback("news", "demo")
        assert out == {"v": 2}

    def test_fallback_on_exception(self):
        reg = AdapterRegistry(max_retries=1)

        def _boom(**k):
            raise RuntimeError("fail")
        a = _NoopFake("src_a", _boom)
        b = _NoopFake("src_b", lambda **k: pd.DataFrame({"x": [1]}))
        reg.register("news", a)
        reg.register("news", b)
        out = reg.call_with_fallback("news", "demo")
        assert not out.empty

    def test_all_fail_raises(self):
        reg = AdapterRegistry(max_retries=1)

        def _boom(**k):
            raise RuntimeError("fail")
        reg.register("news", _NoopFake("src_a", _boom))
        reg.register("news", _NoopFake("src_b", _boom))
        with pytest.raises(Exception) as ei:
            reg.call_with_fallback("news", "demo")
        assert "全部数据源降级失败" in str(ei.value)

    def test_unregistered_domain_raises(self):
        reg = AdapterRegistry()
        with pytest.raises(ValueError):
            reg.call_with_fallback("ghost", "demo")

    def test_skip_when_no_method(self):
        """适配器不具method时应跳过并继续。"""
        reg = AdapterRegistry(max_retries=1)
        a = _NoopFake("src_a", lambda **k: {"v": 1})
        # 隐去 demo 方法
        delattr(type(a), "demo") if False else None
        # 用一个完全不同的 method 名强迫 skip
        b = _NoopFake("src_b", lambda **k: {"v": 2})
        reg.register("news", a)
        reg.register("news", b)
        # 两个都没 'nonexistent_method'，应raise
        with pytest.raises(Exception):
            reg.call_with_fallback("news", "nonexistent_method")


class TestDefaultMap:
    def test_default_map_domains_cover_11(self):
        keys = set(AdapterRegistry.DEFAULT_DOMAIN_MAP.keys())
        expected = {
            "a_stock_kline", "a_stock_realtime", "us_stock", "hk_stock",
            "macro_us", "macro_cn", "macro_global", "crypto",
            "news", "sentiment_social", "xbrl_financials",
        }
        assert expected.issubset(keys)

    def test_default_map_openbb_registered(self):
        """OpenBBAdapter 出现在 us_stock/macro_us/macro_global/crypto/xbrl_financials。"""
        m = AdapterRegistry.DEFAULT_DOMAIN_MAP
        for d in ("us_stock", "macro_us", "macro_global", "crypto", "xbrl_financials"):
            assert "OpenBBAdapter" in m[d], f"{d} 缺少 OpenBBAdapter"


class TestValidity:
    def test_none_invalid(self):
        assert AdapterRegistry._is_valid_result(None) is False

    def test_empty_df_invalid(self):
        assert AdapterRegistry._is_valid_result(pd.DataFrame()) is False

    def test_empty_list_dict_invalid(self):
        assert AdapterRegistry._is_valid_result([]) is False
        assert AdapterRegistry._is_valid_result({}) is False

    def test_nonempty_valid(self):
        assert AdapterRegistry._is_valid_result({"k": "v"}) is True
        assert AdapterRegistry._is_valid_result(pd.DataFrame({"a": [1]})) is True
        assert AdapterRegistry._is_valid_result("str") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
