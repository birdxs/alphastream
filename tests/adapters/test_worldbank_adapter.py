# -*- coding: utf-8 -*-
"""
WorldBank 适配器单元测试（纯 mock，无真实网络请求）
Input: mock 的 requests.Session.get 响应
Output: pytest 用例结果
Pos: tests/adapters 层，CI 回归保护
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.adapters.worldbank_adapter import WorldBankAdapter


def _mk_resp(status: int = 200, payload=None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload if payload is not None else {}
    return m


# --- 典型 WB 响应：[meta, rows] ---
GDP_PAYLOAD = [
    {"page": 1, "pages": 1, "per_page": 1000, "total": 2},
    [
        {
            "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
            "country": {"id": "CN", "value": "China"},
            "countryiso3code": "CHN",
            "date": "2021",
            "value": 17734062645371.3,
            "unit": "",
            "obs_status": "",
            "decimal": 0,
        },
        {
            "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
            "country": {"id": "CN", "value": "China"},
            "countryiso3code": "CHN",
            "date": "2020",
            "value": 14687743811992.1,
            "unit": "",
            "obs_status": "",
            "decimal": 0,
        },
    ],
]

COMPARE_PAYLOAD = [
    {"page": 1, "pages": 1, "per_page": 1000, "total": 3},
    [
        {
            "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP"},
            "country": {"id": "CN", "value": "China"},
            "date": "2022",
            "value": 17963170521079.0,
            "unit": "",
        },
        {
            "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP"},
            "country": {"id": "US", "value": "United States"},
            "date": "2022",
            "value": 25462700000000.0,
            "unit": "",
        },
        {
            "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP"},
            "country": {"id": "JP", "value": "Japan"},
            "date": "2022",
            "value": 4231141200000.0,
            "unit": "",
        },
    ],
]

INDICATORS_PAYLOAD = [
    {"page": 1, "pages": 1, "per_page": 1000, "total": 2},
    [
        {
            "id": "NY.GDP.MKTP.CD",
            "name": "GDP (current US$)",
            "source": {"id": "2", "value": "World Development Indicators"},
            "sourceNote": "GDP at purchaser's prices...",
            "topics": [{"id": "3", "value": "Economy & Growth"}],
        },
        {
            "id": "FP.CPI.TOTL",
            "name": "Consumer price index (2010 = 100)",
            "source": {"id": "2", "value": "World Development Indicators"},
            "sourceNote": "CPI reflects changes...",
            "topics": [{"id": "3", "value": "Economy & Growth"}],
        },
    ],
]


class TestBasics:
    def test_name(self):
        assert WorldBankAdapter().name == "worldbank"

    def test_ua_and_session(self):
        a = WorldBankAdapter()
        assert "StockAnalSys" in a.session.headers.get("User-Agent", "")

    def test_parse_rows_malformed(self):
        assert WorldBankAdapter._parse_rows(None) == []
        assert WorldBankAdapter._parse_rows([{}]) == []
        assert WorldBankAdapter._parse_rows([{}, "nope"]) == []


class TestGetIndicator:
    def test_get_indicator_basic(self):
        a = WorldBankAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, GDP_PAYLOAD)) as mg:
            df = a.get_indicator("CN", "NY.GDP.MKTP.CD",
                                 start=2020, end=2021)
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert set(["country", "country_id", "indicator",
                        "indicator_id", "date", "value"]).issubset(df.columns)
            # 升序按 date
            assert list(df["date"]) == ["2020", "2021"]
            # URL 正确
            called_url = mg.call_args.args[0]
            assert called_url == (
                "https://api.worldbank.org/v2/country/CN/"
                "indicator/NY.GDP.MKTP.CD"
            )
            params = mg.call_args.kwargs.get("params") or {}
            assert params.get("date") == "2020:2021"
            assert params.get("format") == "json"

    def test_get_indicator_empty_input(self):
        a = WorldBankAdapter()
        assert a.get_indicator("", "X").empty
        assert a.get_indicator("CN", "").empty

    def test_get_indicator_http_error(self):
        a = WorldBankAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(500, {})):
            df = a.get_indicator("CN", "NY.GDP.MKTP.CD")
            assert df.empty


class TestListIndicators:
    def test_list_indicators_all(self):
        a = WorldBankAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, INDICATORS_PAYLOAD)):
            df = a.list_indicators()
            assert len(df) == 2
            assert set(["id", "name", "source", "source_note",
                        "topics"]).issubset(df.columns)

    def test_list_indicators_keyword_filter(self):
        a = WorldBankAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, INDICATORS_PAYLOAD)):
            df = a.list_indicators(keyword="cpi")
            assert len(df) == 1
            assert df["id"].iloc[0] == "FP.CPI.TOTL"


class TestCompareCountries:
    def test_compare_sorted_desc(self):
        a = WorldBankAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, COMPARE_PAYLOAD)) as mg:
            df = a.compare_countries(
                ["CN", "US", "JP"], "NY.GDP.MKTP.CD", year=2022
            )
            assert len(df) == 3
            # 按 value 降序：US > CN > JP
            assert list(df["country_id"]) == ["US", "CN", "JP"]
            called_url = mg.call_args.args[0]
            assert "country/CN;US;JP/indicator/NY.GDP.MKTP.CD" in called_url

    def test_compare_empty_input(self):
        a = WorldBankAdapter()
        assert a.compare_countries([], "X", 2022).empty
        assert a.compare_countries(["CN"], "", 2022).empty


class TestBaseAdapterInterface:
    def test_stock_history_empty(self):
        a = WorldBankAdapter()
        assert a.get_stock_history("CN", "20200101", "20201231").empty

    def test_index_stocks_empty(self):
        assert WorldBankAdapter().get_index_stocks("000300") == []

    def test_stock_info_empty(self):
        assert WorldBankAdapter().get_stock_info("CN") == {}

    def test_financial_data_empty(self):
        assert WorldBankAdapter().get_financial_data("CN") == {}

    def test_health_check_ok(self):
        a = WorldBankAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, GDP_PAYLOAD)):
            assert a.health_check() is True

    def test_health_check_fail(self):
        a = WorldBankAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(500, {})):
            assert a.health_check() is False
