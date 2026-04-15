# -*- coding: utf-8 -*-
"""
CorporateAdapter 单元测试（纯 mock, 无真实网络请求）
Input: mock 的 requests.Session.get 响应
Output: pytest 用例结果
Pos: tests/adapters, CI 回归保护 [NEW-FILE:#20260415-25]
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.adapters.corporate_adapter import CorporateAdapter


# ---------- helpers ----------

def _mk_resp(status: int = 200, payload: dict = None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload or {}
    return m


SEARCH_PAYLOAD = {
    "api_version": "0.4",
    "results": {
        "companies": [
            {
                "company": {
                    "name": "APPLE INC.",
                    "company_number": "C0806592",
                    "jurisdiction_code": "us_ca",
                    "incorporation_date": "1977-01-03",
                    "company_type": "DOMESTIC STOCK",
                    "current_status": "Active",
                    "opencorporates_url": (
                        "https://opencorporates.com/companies/us_ca/C0806592"
                    ),
                }
            },
            {
                "company": {
                    "name": "APPLE UK LTD",
                    "company_number": "01234567",
                    "jurisdiction_code": "gb",
                    "incorporation_date": "1984-01-01",
                    "company_type": "Private Limited",
                    "current_status": "Active",
                    "opencorporates_url": (
                        "https://opencorporates.com/companies/gb/01234567"
                    ),
                }
            },
        ]
    },
}

DETAILS_PAYLOAD = {
    "results": {
        "company": {
            "name": "APPLE INC.",
            "company_number": "C0806592",
            "jurisdiction_code": "us_ca",
            "incorporation_date": "1977-01-03",
            "company_type": "DOMESTIC STOCK",
            "current_status": "Active",
            "registered_address_in_full": "1 Apple Park Way, Cupertino CA",
            "opencorporates_url": (
                "https://opencorporates.com/companies/us_ca/C0806592"
            ),
            "controlling_entity": None,
            "subsidiaries": [
                {"subsidiary": {
                    "name": "BEATS ELECTRONICS LLC",
                    "jurisdiction_code": "us_de",
                    "company_number": "5533567",
                }}
            ],
            "officers": [
                {"officer": {
                    "name": "Tim Cook",
                    "position": "CEO",
                    "start_date": "2011-08-24",
                    "end_date": None,
                }}
            ],
        }
    }
}


# ---------- tests ----------

class TestInit:
    def test_default_anonymous(self, monkeypatch):
        monkeypatch.delenv("OPENCORPORATES_API_KEY", raising=False)
        a = CorporateAdapter()
        assert a.api_key == ""
        assert a.name == "opencorporates"
        assert "User-Agent" in a.session.headers

    def test_env_api_key(self, monkeypatch):
        monkeypatch.setenv("OPENCORPORATES_API_KEY", "env_token_xyz")
        a = CorporateAdapter()
        assert a.api_key == "env_token_xyz"

    def test_explicit_key_wins(self, monkeypatch):
        monkeypatch.setenv("OPENCORPORATES_API_KEY", "env_token_xyz")
        a = CorporateAdapter(api_key="explicit_abc")
        assert a.api_key == "explicit_abc"


class TestSearchCompany:
    def test_search_returns_df(self):
        a = CorporateAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, SEARCH_PAYLOAD)) as mg:
            df = a.search_company("apple")
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert df.iloc[0]["name"] == "APPLE INC."
            assert df.iloc[0]["jurisdiction_code"] == "us_ca"
            # URL 指向 search 端点
            called_url = mg.call_args.args[0]
            assert called_url.endswith("/companies/search")

    def test_search_empty_name(self):
        a = CorporateAdapter()
        df = a.search_company("   ")
        assert isinstance(df, pd.DataFrame) and df.empty

    def test_search_with_jurisdiction(self):
        a = CorporateAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, SEARCH_PAYLOAD)) as mg:
            a.search_company("apple", jurisdiction="US_CA")
            params = mg.call_args.kwargs.get("params") or {}
            assert params.get("jurisdiction_code") == "us_ca"
            assert params.get("q") == "apple"

    def test_search_api_key_attached(self):
        a = CorporateAdapter(api_key="tok123")
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, SEARCH_PAYLOAD)) as mg:
            a.search_company("apple")
            params = mg.call_args.kwargs.get("params") or {}
            assert params.get("api_token") == "tok123"

    def test_search_http_error_returns_empty(self):
        a = CorporateAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(500, {})):
            df = a.search_company("apple")
            assert isinstance(df, pd.DataFrame) and df.empty

    def test_search_403_free_tier_exhausted(self):
        a = CorporateAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(403, {})):
            df = a.search_company("apple")
            assert df.empty


class TestCompanyDetails:
    def test_details_ok(self):
        a = CorporateAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, DETAILS_PAYLOAD)) as mg:
            d = a.get_company_details("us_ca/C0806592")
            assert d["name"] == "APPLE INC."
            assert d["jurisdiction_code"] == "us_ca"
            called_url = mg.call_args.args[0]
            assert "/companies/us_ca/C0806592" in called_url

    def test_details_bad_id(self):
        a = CorporateAdapter()
        assert a.get_company_details("") == {}
        assert a.get_company_details("no_slash_here") == {}


class TestCompanyNetwork:
    def test_network_structure(self):
        a = CorporateAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, DETAILS_PAYLOAD)):
            net = a.get_company_network("us_ca/C0806592")
            assert set(net.keys()) == {
                "company_id", "parents", "children", "officers"
            }
            assert net["company_id"] == "us_ca/C0806592"
            # controlling_entity=None → 无parents
            assert net["parents"] == []
            # subsidiary 抽出
            assert len(net["children"]) == 1
            assert net["children"][0]["name"] == "BEATS ELECTRONICS LLC"
            # officer 抽出
            assert len(net["officers"]) == 1
            assert net["officers"][0]["name"] == "Tim Cook"

    def test_network_invalid_id_returns_skeleton(self):
        a = CorporateAdapter()
        net = a.get_company_network("")
        assert net == {
            "company_id": "", "parents": [], "children": [], "officers": []
        }

    def test_network_empty_details(self):
        a = CorporateAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, {"results": {}})):
            net = a.get_company_network("gb/99999")
            assert net["parents"] == []
            assert net["children"] == []
            assert net["officers"] == []


class TestBaseAdapterInterface:
    def test_get_stock_history_empty(self):
        assert CorporateAdapter().get_stock_history("x", "1", "2").empty

    def test_get_index_stocks_empty(self):
        assert CorporateAdapter().get_index_stocks("SPX") == []

    def test_name(self):
        assert CorporateAdapter().name == "opencorporates"

    def test_get_financial_data_empty(self):
        assert CorporateAdapter().get_financial_data("us_ca/C0806592") == {}

    def test_get_stock_info(self):
        a = CorporateAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, DETAILS_PAYLOAD)):
            info = a.get_stock_info("us_ca/C0806592")
            assert info["name"] == "APPLE INC."
            assert info["jurisdiction_code"] == "us_ca"

    def test_health_check_true(self):
        a = CorporateAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, SEARCH_PAYLOAD)):
            assert a.health_check() is True

    def test_health_check_false_on_empty(self):
        a = CorporateAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, {"results": {"companies": []}})):
            assert a.health_check() is False
