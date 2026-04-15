# -*- coding: utf-8 -*-
"""
SEC EDGAR 适配器单元测试（纯 mock，无真实网络请求）
Input: mock 的 requests.Session.get 响应
Output: pytest 用例结果
Pos: tests/adapters 层，CI 回归保护
"""
import time
import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.adapters.edgar_adapter import EDGARAdapter


# ---------- helpers ----------

def _mk_resp(status: int = 200, payload: dict = None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload or {}
    return m


TICKERS_PAYLOAD = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp."},
}

CONCEPT_REVENUES_PAYLOAD = {
    "cik": 320193,
    "taxonomy": "us-gaap",
    "tag": "Revenues",
    "units": {
        "USD": [
            {"end": "2022-09-24", "val": 394328000000, "fy": 2022,
             "fp": "FY", "form": "10-K", "accn": "0000320193-22-000108"},
            {"end": "2023-09-30", "val": 383285000000, "fy": 2023,
             "fp": "FY", "form": "10-K", "accn": "0000320193-23-000106"},
        ]
    },
}


# ---------- tests ----------

class TestCIKPadding:
    """CIK padding 规则：SEC 要求 10 位数字左填零"""

    def test_pad_short_cik(self):
        assert EDGARAdapter._pad_cik(320193) == "0000320193"
        assert EDGARAdapter._pad_cik("320193") == "0000320193"

    def test_pad_already_padded(self):
        assert EDGARAdapter._pad_cik("0000320193") == "0000320193"

    def test_pad_with_prefix(self):
        assert EDGARAdapter._pad_cik("CIK0000320193") == "0000320193"
        assert EDGARAdapter._pad_cik("cik320193") == "0000320193"


class TestUserAgent:
    """UA 必填且格式须含空格与 @"""

    def test_default_ua(self):
        a = EDGARAdapter()
        assert " " in a.user_agent and "@" in a.user_agent
        assert a.session.headers["User-Agent"] == a.user_agent

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("SEC_EDGAR_UA", "MyCo ops@myco.com")
        a = EDGARAdapter()
        assert a.user_agent == "MyCo ops@myco.com"

    def test_explicit_ua_wins(self, monkeypatch):
        monkeypatch.setenv("SEC_EDGAR_UA", "MyCo ops@myco.com")
        a = EDGARAdapter(user_agent="Other team@other.com")
        assert a.user_agent == "Other team@other.com"


class TestRateLimit:
    """限流：连续调用 _throttle 间隔须 ≥0.11s"""

    def test_min_interval_enforced(self):
        a = EDGARAdapter()
        # 预热一次，设置基准时间戳
        a._throttle()
        t0 = time.monotonic()
        a._throttle()
        a._throttle()
        elapsed = time.monotonic() - t0
        # 两次 throttle 之间至少经历 1 个最小间隔
        assert elapsed >= a._MIN_INTERVAL * 0.9

    def test_429_backoff(self):
        a = EDGARAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(429, {})) as mg, \
             patch("time.sleep") as msleep:
            out = a._get_json("https://data.sec.gov/whatever")
            assert out == {}
            # 429 路径应触发退避 sleep
            assert any(c.args and c.args[0] >= 1.0 for c in msleep.call_args_list)
            assert mg.called


class TestEndpoints:
    """端点URL与返回解析"""

    def test_ticker_cik_map_cache(self):
        a = EDGARAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, TICKERS_PAYLOAD)) as mg:
            mp1 = a.get_ticker_cik_map()
            mp2 = a.get_ticker_cik_map()  # 第二次命中缓存
            assert mp1["AAPL"] == "0000320193"
            assert mp1["MSFT"] == "0000789019"
            assert mg.call_count == 1  # 24h TTL 命中缓存

    def test_get_cik(self):
        a = EDGARAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, TICKERS_PAYLOAD)):
            assert a.get_cik("aapl") == "0000320193"
            assert a.get_cik("NOTEXIST") == ""

    def test_get_submissions_url(self):
        a = EDGARAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, {"cik": "320193"})) as mg:
            a.get_submissions("320193")
            called_url = mg.call_args.args[0]
            assert called_url == \
                "https://data.sec.gov/submissions/CIK0000320193.json"

    def test_get_company_facts_url(self):
        a = EDGARAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, {"facts": {}})) as mg:
            a.get_company_facts(320193)
            called_url = mg.call_args.args[0]
            assert called_url == (
                "https://data.sec.gov/api/xbrl/companyfacts/"
                "CIK0000320193.json"
            )

    def test_get_concept_url_and_taxonomy(self):
        a = EDGARAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, {})) as mg:
            a.get_concept("320193", "Revenues", taxonomy="us-gaap")
            called_url = mg.call_args.args[0]
            assert called_url == (
                "https://data.sec.gov/api/xbrl/companyconcept/"
                "CIK0000320193/us-gaap/Revenues.json"
            )

    def test_get_revenue_series(self):
        a = EDGARAdapter()
        # 第一次: ticker_map;  第二次: concept(Revenues) 命中
        responses = [
            _mk_resp(200, TICKERS_PAYLOAD),
            _mk_resp(200, CONCEPT_REVENUES_PAYLOAD),
        ]
        with patch.object(a.session, "get", side_effect=responses):
            df = a.get_revenue_series("AAPL")
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert set(["end", "val", "fy", "unit", "tag"]).issubset(df.columns)
            assert df["unit"].iloc[0] == "USD"
            assert df["tag"].iloc[0] == "Revenues"

    def test_get_revenue_series_fallback_tag(self):
        """Revenues 空 → 回落到 RevenueFromContractWithCustomer..."""
        a = EDGARAdapter()
        empty_concept = {"units": {}}
        fallback_payload = {
            "units": {
                "USD": [{"end": "2024-06-29", "val": 100, "fy": 2024,
                         "fp": "Q3", "form": "10-Q", "accn": "x"}]
            }
        }
        responses = [
            _mk_resp(200, TICKERS_PAYLOAD),
            _mk_resp(200, empty_concept),     # Revenues 空
            _mk_resp(200, fallback_payload),  # RevenueFromContract... 命中
        ]
        with patch.object(a.session, "get", side_effect=responses):
            df = a.get_revenue_series("AAPL")
            assert len(df) == 1
            assert df["tag"].iloc[0] == \
                "RevenueFromContractWithCustomerExcludingAssessedTax"


class TestBaseAdapterInterface:
    """BaseAdapter 抽象方法兼容性"""

    def test_get_stock_history_empty(self):
        df = EDGARAdapter().get_stock_history("AAPL", "20230101", "20231231")
        assert isinstance(df, pd.DataFrame) and df.empty

    def test_get_index_stocks_empty(self):
        assert EDGARAdapter().get_index_stocks("SPX") == []

    def test_name(self):
        assert EDGARAdapter().name == "sec_edgar"
