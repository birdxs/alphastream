# -*- coding: utf-8 -*-
"""
easyquotation适配器单元测试 [NEW-FILE:#20260415-18]
Input: mock easyquotation.use() client 返回dict
Output: pytest结果，覆盖 get_realtime / get_stocks_all / get_fund_nav / 非法source / 降级
Pos: tests/adapters/ — 回归基线
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.adapters import easyquotation_adapter as eqa  # noqa: E402


def _mk_realtime():
    return {
        "000001": {"name": "平安银行", "now": 12.2, "open": 12.1, "high": 12.3, "low": 12.0},
        "600519": {"name": "贵州茅台", "now": 1680.0, "open": 1660.0, "high": 1690.0, "low": 1650.0},
    }


def _mk_jsl_funda():
    return {
        "150019": {"base_fund_id": "150019", "name": "银华锐进", "price": 1.25},
        "150023": {"base_fund_id": "150023", "name": "申万进取", "price": 0.85},
    }


# ==================== 初始化 ====================
class TestInit:
    def test_default_sina(self):
        fake_eq = MagicMock()
        fake_eq.use.return_value = MagicMock()
        with patch.object(eqa, "easyquotation", fake_eq), \
             patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter()
        assert a.source == "sina"
        assert a.name == "easyquotation:sina"

    def test_invalid_source_fallback(self):
        fake_eq = MagicMock()
        fake_eq.use.return_value = MagicMock()
        with patch.object(eqa, "easyquotation", fake_eq), \
             patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter(source="yahoo")
        assert a.source == "sina"

    def test_unavailable(self):
        with patch.object(eqa, "_EQ_AVAILABLE", False):
            a = eqa.EasyquotationAdapter()
        assert a._client is None


# ==================== get_realtime ====================
class TestRealtime:
    def test_ok_stocks(self):
        client = MagicMock()
        client.stocks.return_value = _mk_realtime()
        fake_eq = MagicMock()
        fake_eq.use.return_value = client
        with patch.object(eqa, "easyquotation", fake_eq), \
             patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter(source="sina")
            data = a.get_realtime(["000001", "600519"])
        assert len(data) == 2
        assert data["000001"]["now"] == 12.2

    def test_fallback_real(self):
        client = MagicMock(spec=["real"])
        client.real.return_value = _mk_realtime()
        fake_eq = MagicMock()
        fake_eq.use.return_value = client
        with patch.object(eqa, "easyquotation", fake_eq), \
             patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter()
            data = a.get_realtime(["000001"])
        assert "000001" in data

    def test_empty_codes(self):
        with patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter()
            # 即使 client 存在，空 codes 直接返回 {}
            assert a.get_realtime([]) == {}

    def test_unavailable(self):
        with patch.object(eqa, "_EQ_AVAILABLE", False):
            a = eqa.EasyquotationAdapter()
            assert a.get_realtime(["000001"]) == {}

    def test_exception(self):
        client = MagicMock()
        client.stocks.side_effect = RuntimeError("net")
        fake_eq = MagicMock()
        fake_eq.use.return_value = client
        with patch.object(eqa, "easyquotation", fake_eq), \
             patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter()
            assert a.get_realtime(["000001"]) == {}


# ==================== get_stocks_all ====================
class TestStocksAll:
    def test_ok(self):
        client = MagicMock()
        client.market_snapshot.return_value = _mk_realtime()
        fake_eq = MagicMock()
        fake_eq.use.return_value = client
        with patch.object(eqa, "easyquotation", fake_eq), \
             patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter()
            data = a.get_stocks_all()
        assert len(data) == 2
        client.market_snapshot.assert_called_once_with(prefix=False)

    def test_unavailable(self):
        with patch.object(eqa, "_EQ_AVAILABLE", False):
            assert eqa.EasyquotationAdapter().get_stocks_all() == {}


# ==================== get_fund_nav (jsl) ====================
class TestFundNav:
    def test_ok(self):
        jsl_client = MagicMock(spec=["funda", "fundb", "fundm"])
        jsl_client.funda.return_value = _mk_jsl_funda()
        jsl_client.fundb.return_value = {}
        jsl_client.fundm.return_value = {}
        fake_eq = MagicMock()
        fake_eq.use.return_value = jsl_client
        with patch.object(eqa, "easyquotation", fake_eq), \
             patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter(source="jsl")
            data = a.get_fund_nav()
        assert "150019" in data

    def test_filter_by_codes(self):
        jsl_client = MagicMock(spec=["funda", "fundb", "fundm"])
        jsl_client.funda.return_value = _mk_jsl_funda()
        jsl_client.fundb.return_value = {}
        jsl_client.fundm.return_value = {}
        fake_eq = MagicMock()
        fake_eq.use.return_value = jsl_client
        with patch.object(eqa, "easyquotation", fake_eq), \
             patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter(source="jsl")
            data = a.get_fund_nav(codes=["150019"])
        assert list(data.keys()) == ["150019"]

    def test_list_response_adapted(self):
        """jsl 部分接口返回 list[dict] 时应按 base_fund_id 归档"""
        jsl_client = MagicMock(spec=["funda", "fundb", "fundm"])
        jsl_client.funda.return_value = [
            {"base_fund_id": "150019", "name": "银华锐进"},
            {"base_fund_id": "150023", "name": "申万进取"},
        ]
        jsl_client.fundb.return_value = []
        jsl_client.fundm.return_value = []
        fake_eq = MagicMock()
        fake_eq.use.return_value = jsl_client
        with patch.object(eqa, "easyquotation", fake_eq), \
             patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter(source="jsl")
            data = a.get_fund_nav()
        assert "150019" in data and "150023" in data

    def test_unavailable(self):
        with patch.object(eqa, "_EQ_AVAILABLE", False):
            assert eqa.EasyquotationAdapter().get_fund_nav() == {}


# ==================== BaseAdapter 接口 ====================
class TestBaseAdapter:
    def test_index_stocks_empty(self):
        with patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter()
            assert a.get_index_stocks("000300") == []

    def test_financial_empty(self):
        with patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter()
            assert a.get_financial_data("600519") == {}

    def test_info_from_realtime(self):
        client = MagicMock()
        client.stocks.return_value = _mk_realtime()
        fake_eq = MagicMock()
        fake_eq.use.return_value = client
        with patch.object(eqa, "easyquotation", fake_eq), \
             patch.object(eqa, "_EQ_AVAILABLE", True):
            a = eqa.EasyquotationAdapter()
            info = a.get_stock_info("000001")
        assert info.get("name") == "平安银行"

    def test_health_ok(self):
        client = MagicMock()
        client.stocks.return_value = _mk_realtime()
        fake_eq = MagicMock()
        fake_eq.use.return_value = client
        with patch.object(eqa, "easyquotation", fake_eq), \
             patch.object(eqa, "_EQ_AVAILABLE", True):
            assert eqa.EasyquotationAdapter().health_check() is True

    def test_health_unavailable(self):
        with patch.object(eqa, "_EQ_AVAILABLE", False):
            assert eqa.EasyquotationAdapter().health_check() is False
