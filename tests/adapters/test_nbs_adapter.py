# -*- coding: utf-8 -*-
"""
国家统计局 NBS 适配器单元测试 — 纯 mock requests，无真实网络请求
Input: mock requests.Session.get 返回
Output: pytest 用例结果
Pos: tests/adapters 层，CI 回归保护
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.adapters.nbs_adapter import NBSAdapter


# ---------- helpers ----------

def _mk_resp(status=200, payload=None):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload or {}
    return m


def _cpi_payload():
    """仿NBS easyquery CPI同比返回结构"""
    return {
        "returncode": 200,
        "returndata": {
            "datanodes": [
                {
                    "code": "zb.A01010G01_sj.202401",
                    "data": {"data": 100.5, "strdata": "100.5"},
                    "wds": [
                        {"wdcode": "zb", "valuecode": "A01010G01"},
                        {"wdcode": "sj", "valuecode": "202401"},
                    ],
                },
                {
                    "code": "zb.A01010G01_sj.202402",
                    "data": {"data": 100.7, "strdata": "100.7"},
                    "wds": [
                        {"wdcode": "zb", "valuecode": "A01010G01"},
                        {"wdcode": "sj", "valuecode": "202402"},
                    ],
                },
            ],
            "wdnodes": [
                {"wdcode": "zb", "nodes": [
                    {"code": "A01010G01", "cname": "居民消费价格指数(上年同月=100)", "unit": ""}
                ]},
                {"wdcode": "sj", "nodes": [
                    {"code": "202401", "cname": "2024年1月"},
                    {"code": "202402", "cname": "2024年2月"},
                ]},
            ],
        },
    }


# ---------- tests ----------

class TestQuery:
    """通用 easyquery 解析"""

    def test_query_returns_flat_dataframe(self):
        ad = NBSAdapter()
        with patch.object(ad._session, "get", return_value=_mk_resp(200, _cpi_payload())):
            df = ad.query(dbcode="hgyd", rowcode="A01010G01", sj="LAST13")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert set(["date", "code", "value", "unit", "cname"]).issubset(df.columns)
        assert df.iloc[0]["code"] == "A01010G01"
        assert df.iloc[0]["value"] == 100.5

    def test_query_business_error_returns_empty(self):
        ad = NBSAdapter()
        bad = {"returncode": 400, "returndata": {}}
        with patch.object(ad._session, "get", return_value=_mk_resp(200, bad)):
            df = ad.query(dbcode="hgyd", rowcode="A01010G01")
        assert df.empty

    def test_query_http_error_retries_then_empty(self):
        ad = NBSAdapter()
        with patch.object(ad._session, "get", return_value=_mk_resp(503, {})) as g, \
             patch("app.adapters.nbs_adapter.time.sleep"):
            df = ad.query(dbcode="hgyd", rowcode="A01010G01")
        assert df.empty
        assert g.call_count == NBSAdapter.MAX_RETRIES  # 3次重试


class TestShortcuts:
    """GDP/CPI/PMI/工业 快捷封装"""

    def test_get_cpi_monthly(self):
        ad = NBSAdapter()
        with patch.object(ad, "query", return_value=pd.DataFrame([
            {"date": "202401", "code": "A01010G01", "value": 100.5, "unit": "", "cname": "CPI同比"},
        ])) as q:
            df = ad.get_cpi(freq="monthly")
        q.assert_called_once()
        kwargs = q.call_args.kwargs
        assert kwargs["dbcode"] == "hgyd"
        assert kwargs["rowcode"] == "A01010G01"
        assert df.iloc[0]["indicator"] == "CPI_YoY"
        assert df.iloc[0]["freq"] == "monthly"

    def test_get_gdp_quarterly_and_yearly(self):
        ad = NBSAdapter()
        stub = pd.DataFrame([{"date": "2024A", "code": "X", "value": 1, "unit": "", "cname": ""}])
        with patch.object(ad, "query", return_value=stub) as q:
            ad.get_gdp(freq="quarterly")
            ad.get_gdp(freq="yearly")
        calls = q.call_args_list
        assert calls[0].kwargs["dbcode"] == "hgjd"
        assert calls[1].kwargs["dbcode"] == "hgnd"

    def test_get_pmi(self):
        ad = NBSAdapter()
        stub = pd.DataFrame([{"date": "202402", "code": "A0B0101", "value": 50.2, "unit": "", "cname": ""}])
        with patch.object(ad, "query", return_value=stub) as q:
            df = ad.get_pmi()
        assert q.call_args.kwargs["rowcode"] == "A0B0101"
        assert df.iloc[0]["indicator"] == "PMI_Manufacturing"

    def test_get_industrial_output(self):
        ad = NBSAdapter()
        stub = pd.DataFrame([{"date": "202402", "code": "A020102", "value": 7.0, "unit": "%", "cname": ""}])
        with patch.object(ad, "query", return_value=stub) as q:
            df = ad.get_industrial_output()
        assert q.call_args.kwargs["rowcode"] == "A020102"
        assert df.iloc[0]["indicator"] == "IndustrialOutput_YoY"


class TestBaseAdapterContract:
    """BaseAdapter 抽象方法：宏观源不提供个股数据，返回空"""

    def test_stock_methods_return_empty(self):
        ad = NBSAdapter()
        assert ad.get_stock_history("000001", "20240101", "20240201").empty
        assert ad.get_index_stocks("000300") == []
        assert ad.get_stock_info("000001") == {}
        assert ad.get_financial_data("000001") == {}

    def test_name(self):
        assert NBSAdapter().name == "nbs"

    def test_health_check_pass(self):
        ad = NBSAdapter()
        with patch.object(ad, "query", return_value=pd.DataFrame([{"date": "1", "code": "x", "value": 1}])):
            assert ad.health_check() is True

    def test_health_check_fail(self):
        ad = NBSAdapter()
        with patch.object(ad, "query", return_value=pd.DataFrame()):
            assert ad.health_check() is False


class TestHeaders:
    def test_ua_is_browser(self):
        # K1 [NEW-FILE:#20260415-44] UA改为池化随机，不再固定Chrome
        ad = NBSAdapter()
        ua = ad._session.headers.get("User-Agent", "")
        assert "Mozilla" in ua
        assert any(k in ua for k in ("Chrome", "Firefox", "Safari", "Edg"))
