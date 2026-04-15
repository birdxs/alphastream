# -*- coding: utf-8 -*-
"""
ESGAdapter 单元测试（纯 mock，不发真实请求） [NEW-FILE:#20260415-27]
Input: mock 的 requests.Session.get / EDGARAdapter.get_concept 响应
Output: pytest 用例结果
Pos: tests/adapters 层，P3-D3 ESG 公开源回归保护
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.adapters.esg_adapter import ESGAdapter, _letter_to_score, _safe_float


# --------------------------- helpers ---------------------------

def _mk_resp(status: int = 200, payload=None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload if payload is not None else {}
    return m


ESGBOOK_PAYLOAD = {
    "company": "Apple Inc.",
    "isin": "US0378331005",
    "scores": {"esg": 72.5, "e": 80.1, "s": 65.0, "g": 72.4},
    "grade": "AA",
    "as_of": "2025-12-31",
}

CDP_PAYLOAD = {
    "responses": [
        {
            "company": "Apple Inc.",
            "year": 2025,
            "climate_score": "A",
            "water_score": "A-",
            "forests_score": "B",
        }
    ]
}

BCORP_PAYLOAD = {
    "companies": [
        {
            "name": "Patagonia",
            "industry": "Apparel",
            "country": "US",
            "overall_score": 151.4,
            "status": "Certified",
            "certified_on": "2024-06-15",
            "url": "https://bcorporation.net/patagonia",
        }
    ]
}

EDGAR_CONCEPT_SCOPE1 = {
    "units": {
        "tCO2e": [
            {"end": "2023-12-31", "val": 55_000, "fy": 2023, "fp": "FY", "form": "10-K"},
            {"end": "2024-12-31", "val": 48_200, "fy": 2024, "fp": "FY", "form": "10-K"},
        ]
    }
}


# --------------------------- 基础契约 ---------------------------

class TestBasics:
    def test_name_and_ua(self):
        a = ESGAdapter()
        assert a.name == "esg_public"
        assert "StockAnalSys-ESG" in a.session.headers["User-Agent"]

    def test_custom_ua(self):
        a = ESGAdapter(user_agent="MyESG bot@my.co")
        assert a.user_agent == "MyESG bot@my.co"

    def test_base_abstract_methods_safe(self):
        """不支持的能力返回空对象，不抛异常"""
        a = ESGAdapter()
        assert a.get_stock_history("AAPL", "20240101", "20240201").empty
        assert a.get_index_stocks("000300") == []


# --------------------------- _get_json 软降级 ---------------------------

class TestHttpLayer:
    def test_non_200_returns_empty(self):
        a = ESGAdapter(max_retries=1)
        with patch.object(a.session, "get", return_value=_mk_resp(404)):
            assert a._get_json("http://x") == {}

    def test_exception_returns_empty(self):
        a = ESGAdapter(max_retries=2)
        with patch.object(a.session, "get", side_effect=Exception("boom")):
            assert a._get_json("http://x") == {}

    def test_429_retry_then_empty(self):
        a = ESGAdapter(max_retries=2)
        with patch.object(a.session, "get",
                          side_effect=[_mk_resp(429), _mk_resp(429)]) as mg:
            out = a._get_json("http://x")
            assert out == {}
            assert mg.call_count == 2  # 2次重试均失败


# --------------------------- get_esg_score 多源 ---------------------------

class TestGetESGScore:
    def test_esgbook_happy_path(self):
        a = ESGAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, ESGBOOK_PAYLOAD)):
            out = a.get_esg_score("AAPL", source="esgbook")
            assert out["source"] == "esgbook"
            assert out["ticker"] == "AAPL"
            assert out["esg_score"] == 72.5
            assert out["e_score"] == 80.1
            assert out["grade"] == "AA"
            assert out["raw"]["company"] == "Apple Inc."

    def test_cdp_source(self):
        a = ESGAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, CDP_PAYLOAD)):
            out = a.get_esg_score("AAPL", source="cdp")
            assert out["source"] == "cdp"
            assert out["grade"] == "A"
            assert out["esg_score"] == 95.0  # A→95

    def test_unknown_source_fallback_to_esgbook(self):
        a = ESGAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, ESGBOOK_PAYLOAD)):
            out = a.get_esg_score("AAPL", source="wind_esg")  # 付费源
            assert out["source"] == "esgbook"
            assert out["esg_score"] == 72.5

    def test_softfail_fallback_chain(self):
        """首选源 200 但空 payload → 自动降级下一源"""
        a = ESGAdapter()
        responses = [
            _mk_resp(200, {}),            # esgbook 空
            _mk_resp(200, CDP_PAYLOAD),   # cdp 命中
        ]
        with patch.object(a.session, "get", side_effect=responses):
            out = a.get_esg_score("AAPL", source="esgbook")
            assert out["source"] == "cdp"
            assert out["grade"] == "A"

    def test_all_sources_fail_returns_empty_struct(self):
        a = ESGAdapter(max_retries=1)
        with patch.object(a.session, "get", return_value=_mk_resp(500)):
            out = a.get_esg_score("AAPL", source="esgbook")
            assert out["ticker"] == "AAPL"
            assert out["esg_score"] is None
            assert out["grade"] is None

    def test_empty_ticker(self):
        a = ESGAdapter()
        out = a.get_esg_score("", source="esgbook")
        assert out["esg_score"] is None


# --------------------------- SEC 气候披露 ---------------------------

class TestClimateDisclosure:
    def test_climate_via_edgar_concept(self):
        # 注入 fake edgar
        fake_edgar = MagicMock()
        # 只有 Scope1 返回数据；其余返回空
        def _concept(cik, tag, taxonomy="us-gaap"):
            if tag == "GreenhouseGasEmissionsScope1":
                return EDGAR_CONCEPT_SCOPE1
            return {}
        fake_edgar.get_concept.side_effect = _concept

        a = ESGAdapter(edgar_adapter=fake_edgar)
        out = a.get_climate_disclosure("0000320193")
        assert out["cik"] == "0000320193"
        assert out["source"] == "sec_edgar_climate"
        assert out["scope1_latest"] == 48_200.0  # 取最新 end=2024-12-31
        assert out["scope2_latest"] is None
        key = "us-gaap:GreenhouseGasEmissionsScope1"
        assert key in out["tags"]
        assert len(out["tags"][key]) == 2

    def test_empty_cik(self):
        a = ESGAdapter(edgar_adapter=MagicMock())
        out = a.get_climate_disclosure("")
        assert out["tags"] == {}
        assert out["scope1_latest"] is None

    def test_edgar_unavailable(self):
        a = ESGAdapter(edgar_adapter=None)
        # 强制懒加载失败
        with patch(
            "app.adapters.esg_adapter.ESGAdapter._lazy_edgar",
            return_value=None,
        ):
            out = a.get_climate_disclosure("0000320193")
            assert out["tags"] == {}

    def test_edgar_concept_exception_softfail(self):
        fake_edgar = MagicMock()
        fake_edgar.get_concept.side_effect = Exception("network")
        a = ESGAdapter(edgar_adapter=fake_edgar)
        out = a.get_climate_disclosure("0000320193")
        # 全异常时 tags 为空但结构完整
        assert out["tags"] == {}
        assert out["source"] == "sec_edgar_climate"


# --------------------------- CDP ---------------------------

class TestCDP:
    def test_cdp_happy(self):
        a = ESGAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, CDP_PAYLOAD)):
            out = a.get_cdp_response("Apple Inc.", year=2025)
            assert out["climate_score"] == "A"
            assert out["water_score"] == "A-"
            assert out["year"] == 2025
            assert len(out["disclosures"]) == 1

    def test_cdp_empty_company(self):
        a = ESGAdapter()
        out = a.get_cdp_response("", year=2025)
        assert out["climate_score"] is None
        assert out["disclosures"] == []

    def test_cdp_no_responses(self):
        a = ESGAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, {"responses": []})):
            out = a.get_cdp_response("XCo", year=2024)
            assert out["climate_score"] is None
            assert out["disclosures"] == []


# --------------------------- B Corp ---------------------------

class TestBCorp:
    def test_search_b_corps(self):
        a = ESGAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, BCORP_PAYLOAD)):
            df = a.search_b_corps(industry="Apparel")
            assert isinstance(df, pd.DataFrame)
            assert not df.empty
            row = df.iloc[0]
            assert row["company_name"] == "Patagonia"
            assert row["overall_b_impact_score"] == 151.4
            assert row["certification_status"] == "Certified"

    def test_b_corps_empty(self):
        a = ESGAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, {"companies": []})):
            df = a.search_b_corps()
            assert df.empty

    def test_b_corps_api_fail(self):
        a = ESGAdapter(max_retries=1)
        with patch.object(a.session, "get", return_value=_mk_resp(503)):
            df = a.search_b_corps(industry="Tech")
            assert df.empty


# --------------------------- 辅助函数 ---------------------------

class TestHelpers:
    def test_safe_float(self):
        assert _safe_float(None) is None
        assert _safe_float("") is None
        assert _safe_float("abc") is None
        assert _safe_float("3.14") == 3.14
        assert _safe_float(42) == 42.0

    def test_letter_to_score(self):
        assert _letter_to_score("A") == 95.0
        assert _letter_to_score("a-") == 88.0
        assert _letter_to_score(" B ") == 78.0
        assert _letter_to_score("F") == 10.0
        assert _letter_to_score("") is None
        assert _letter_to_score(None) is None
        assert _letter_to_score("Z") is None


# --------------------------- health_check ---------------------------

class TestHealthCheck:
    def test_health_ok_on_200(self):
        a = ESGAdapter()
        with patch.object(a.session, "get", return_value=_mk_resp(200)):
            assert a.health_check() is True

    def test_health_ok_on_403_alive(self):
        a = ESGAdapter()
        with patch.object(a.session, "get", return_value=_mk_resp(403)):
            assert a.health_check() is True

    def test_health_all_fail(self):
        a = ESGAdapter()
        with patch.object(a.session, "get", side_effect=Exception("down")):
            assert a.health_check() is False


# --------------------------- get_financial_data 整合 ---------------------------

class TestFinancialDataIntegration:
    def test_financial_data_combines(self):
        fake_edgar = MagicMock()
        fake_edgar.get_cik.return_value = "0000320193"
        fake_edgar.get_concept.return_value = {}
        a = ESGAdapter(edgar_adapter=fake_edgar, max_retries=1)
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, ESGBOOK_PAYLOAD)):
            out = a.get_financial_data("AAPL")
            assert "esg" in out and "climate" in out
            assert out["esg"]["esg_score"] == 72.5
            assert out["climate"]["source"] == "sec_edgar_climate"
