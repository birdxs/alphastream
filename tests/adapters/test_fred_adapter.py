# -*- coding: utf-8 -*-
"""
FRED 适配器单元测试 [NEW-FILE:#20260415-07]
Input: mock fredapi.Fred 的 get_series/search/get_release/get_series_info
Output: pytest 用例结果，覆盖 核心方法 + 无Key降级 + fredapi缺失降级
Pos: tests/adapters 层，CI 回归保护
"""
import sys
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.adapters import fred_adapter as fa  # noqa: E402
from app.adapters.fred_adapter import FREDAdapter  # noqa: E402


# ==================== helpers ====================

def _mk_series(data_dict):
    """构造带 DatetimeIndex 的 pd.Series"""
    idx = pd.to_datetime(list(data_dict.keys()))
    return pd.Series(list(data_dict.values()), index=idx)


SAMPLE_UNRATE = {
    "2023-01-01": 3.4,
    "2023-02-01": 3.6,
    "2023-03-01": 3.5,
}

SAMPLE_SEARCH_DF = pd.DataFrame([
    {"id": "CPIAUCSL", "title": "Consumer Price Index", "units": "Index",
     "frequency": "Monthly", "popularity": 95},
    {"id": "CPILFESL", "title": "Core CPI", "units": "Index",
     "frequency": "Monthly", "popularity": 80},
])


# ==================== TestNoAPIKey: 无Key降级 ====================

class TestNoAPIKey:
    """无 FRED_API_KEY 时必须 log.warning 并返回空结构，不抛异常"""

    def test_no_key_env_not_set(self, monkeypatch, caplog):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with patch.object(fa, "_FREDAPI_AVAILABLE", True):
            with caplog.at_level("WARNING"):
                a = FREDAdapter()
            assert a._client is None
            assert any("FRED_API_KEY" in r.message for r in caplog.records)

    def test_no_key_all_methods_empty(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with patch.object(fa, "_FREDAPI_AVAILABLE", True):
            a = FREDAdapter()
        assert a.get_series("GDP").empty
        assert a.search_series("cpi").empty
        assert a.get_release(10) == {}
        assert a.get_common_indicators() == {}
        assert a.get_stock_info("GDP") == {}
        assert a.health_check() is False

    def test_env_key_picked_up(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "testkey123")
        fake_fred_cls = MagicMock()
        with patch.object(fa, "_FREDAPI_AVAILABLE", True), \
             patch.object(fa, "Fred", fake_fred_cls):
            a = FREDAdapter()
        assert a.api_key == "testkey123"
        fake_fred_cls.assert_called_once_with(api_key="testkey123")
        assert a._client is not None

    def test_explicit_key_wins(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "envkey")
        fake_fred_cls = MagicMock()
        with patch.object(fa, "_FREDAPI_AVAILABLE", True), \
             patch.object(fa, "Fred", fake_fred_cls):
            a = FREDAdapter(api_key="explicitkey")
        assert a.api_key == "explicitkey"
        fake_fred_cls.assert_called_once_with(api_key="explicitkey")


# ==================== TestFredapiMissing: 软依赖缺失 ====================

class TestFredapiMissing:
    """fredapi 未安装 → 所有方法降级返回空结构"""

    def test_unavailable_returns_empty(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "testkey")
        with patch.object(fa, "_FREDAPI_AVAILABLE", False), \
             patch.object(fa, "Fred", None):
            a = FREDAdapter()
        assert a._client is None
        assert a.get_series("GDP").empty
        assert a.search_series("x").empty
        assert a.get_release(1) == {}
        assert a.get_common_indicators() == {}
        assert a.health_check() is False


# ==================== TestCoreMethods: 核心方法 ====================

class TestCoreMethods:
    """正常路径：mock fredapi.Fred 实例返回预期结构"""

    def _mk_adapter(self, fake_client):
        """构造一个 _client 已注入的适配器（绕过 Fred 真实初始化）"""
        with patch.object(fa, "_FREDAPI_AVAILABLE", True), \
             patch.object(fa, "Fred", return_value=fake_client):
            a = FREDAdapter(api_key="testkey")
        return a

    def test_get_series_ok(self):
        fake = MagicMock()
        fake.get_series.return_value = _mk_series(SAMPLE_UNRATE)
        a = self._mk_adapter(fake)
        df = a.get_series("UNRATE", start="2023-01-01", end="2023-03-31")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert set(["date", "value", "series_id"]).issubset(df.columns)
        assert df["series_id"].iloc[0] == "UNRATE"
        assert df["value"].iloc[0] == pytest.approx(3.4)
        # 参数透传校验
        fake.get_series.assert_called_once_with(
            "UNRATE",
            observation_start="2023-01-01",
            observation_end="2023-03-31",
        )

    def test_get_series_empty(self):
        fake = MagicMock()
        fake.get_series.return_value = pd.Series(dtype=float)
        a = self._mk_adapter(fake)
        assert a.get_series("BADID").empty

    def test_get_series_exception(self):
        fake = MagicMock()
        fake.get_series.side_effect = ValueError("bad series")
        a = self._mk_adapter(fake)
        assert a.get_series("XXX").empty

    def test_search_series_ok(self):
        fake = MagicMock()
        fake.search.return_value = SAMPLE_SEARCH_DF
        a = self._mk_adapter(fake)
        df = a.search_series("inflation", limit=5)
        assert len(df) == 2
        assert "id" in df.columns
        fake.search.assert_called_once_with("inflation", limit=5)

    def test_search_series_exception(self):
        fake = MagicMock()
        fake.search.side_effect = RuntimeError("network")
        a = self._mk_adapter(fake)
        assert a.search_series("x").empty

    def test_get_release_dataframe_payload(self):
        fake = MagicMock()
        fake.get_release.return_value = pd.DataFrame([
            {"id": 53, "name": "Gross Domestic Product",
             "press_release": True, "link": "https://..."}
        ])
        a = self._mk_adapter(fake)
        info = a.get_release(53)
        assert info["id"] == 53
        assert info["name"] == "Gross Domestic Product"

    def test_get_release_dict_payload(self):
        fake = MagicMock()
        fake.get_release.return_value = {"id": 10, "name": "CPI"}
        a = self._mk_adapter(fake)
        assert a.get_release(10) == {"id": 10, "name": "CPI"}

    def test_get_release_exception(self):
        fake = MagicMock()
        fake.get_release.side_effect = Exception("boom")
        a = self._mk_adapter(fake)
        assert a.get_release(1) == {}

    def test_get_common_indicators(self):
        fake = MagicMock()
        fake.get_series.return_value = _mk_series(SAMPLE_UNRATE)
        a = self._mk_adapter(fake)
        out = a.get_common_indicators()
        # 覆盖所有 10 个常用指标 key
        assert set(out.keys()) == set(FREDAdapter.COMMON_INDICATORS.keys())
        for k, df in out.items():
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 3
        # get_series 被调用次数 == 常用指标数
        assert fake.get_series.call_count == len(FREDAdapter.COMMON_INDICATORS)

    def test_get_stock_info_series_metadata(self):
        fake = MagicMock()
        fake.get_series_info.return_value = pd.Series({
            "id": "GDP", "title": "Gross Domestic Product",
            "frequency": "Quarterly", "units": "Billions of Dollars",
        })
        a = self._mk_adapter(fake)
        info = a.get_stock_info("GDP")
        assert info["id"] == "GDP"
        assert info["frequency"] == "Quarterly"

    def test_health_check_ok(self):
        fake = MagicMock()
        fake.get_series.return_value = _mk_series(SAMPLE_UNRATE)
        a = self._mk_adapter(fake)
        assert a.health_check() is True

    def test_health_check_fail_empty(self):
        fake = MagicMock()
        fake.get_series.return_value = pd.Series(dtype=float)
        a = self._mk_adapter(fake)
        assert a.health_check() is False


# ==================== TestBaseAdapterInterface ====================

class TestBaseAdapterInterface:
    def _mk_adapter(self):
        fake = MagicMock()
        with patch.object(fa, "_FREDAPI_AVAILABLE", True), \
             patch.object(fa, "Fred", return_value=fake):
            return FREDAdapter(api_key="testkey")

    def test_name(self):
        assert self._mk_adapter().name == "fred"

    def test_get_stock_history_empty(self):
        df = self._mk_adapter().get_stock_history("AAPL", "20230101", "20231231")
        assert isinstance(df, pd.DataFrame) and df.empty

    def test_get_index_stocks_empty(self):
        assert self._mk_adapter().get_index_stocks("SPX") == []

    def test_get_financial_data_empty(self):
        assert self._mk_adapter().get_financial_data("AAPL") == {}

    def test_common_indicators_keys_cover_macros(self):
        """常用指标必须包含任务约定的5大核心"""
        keys = set(FREDAdapter.COMMON_INDICATORS.values())
        for must in ("GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS", "DGS10"):
            assert must in keys
