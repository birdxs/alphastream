# -*- coding: utf-8 -*-
"""
ShippingAdapter 单元测试 — 纯 mock requests，无真实网络
Input: mock _get_text / _get_json 返回
Output: pytest 用例结果
Pos: tests/adapters 层，CI 回归保护 (P3-D1 [NEW-FILE:#20260415-23])
"""
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from app.adapters.shipping_adapter import ShippingAdapter


# ---------- fixtures ----------

@pytest.fixture
def adapter():
    # 强制注入 aishub_username，让 AIS 路径进入 mock
    return ShippingAdapter(aishub_username="test_user")


# ---------- name & BaseAdapter 抽象 ----------

def test_name_is_shipping():
    assert ShippingAdapter().name == "shipping"


def test_stock_methods_return_empty_defaults():
    a = ShippingAdapter()
    assert a.get_stock_history("600000", "20250101", "20260101").empty
    assert a.get_index_stocks("000300") == []
    assert a.get_stock_info("600000") == {}
    assert a.get_financial_data("600000") == {}


# ---------- BDI ----------

def test_get_bdi_index_parses_timeseries(adapter):
    fake_html = """
    <script>
    data: [[1704067200000, 2100.5],[1704153600000, 2150.2],[1704240000000, 2180.0]]
    </script>
    """
    with patch.object(adapter, "_get_text", return_value=fake_html):
        df = adapter.get_bdi_index(days=10)
    assert not df.empty
    assert {"date", "value", "indicator", "source"}.issubset(df.columns)
    assert (df["indicator"] == "BDI").all()
    assert len(df) == 3
    assert df["value"].iloc[-1] == 2180.0


def test_get_bdi_index_all_endpoints_fail(adapter):
    with patch.object(adapter, "_get_text", return_value=None):
        df = adapter.get_bdi_index()
    assert df.empty


def test_get_bdi_index_tail_days(adapter):
    # 50条样本 → days=5 → 仅保留最近5条
    pieces = ",".join([f"[{1704067200000 + i*86400000}, {2000+i}]" for i in range(50)])
    fake_html = f"<script>data: [{pieces}]</script>"
    with patch.object(adapter, "_get_text", return_value=fake_html):
        df = adapter.get_bdi_index(days=5)
    assert len(df) == 5


# ---------- 港口吞吐量 ----------

def test_get_port_throughput_shanghai(adapter):
    fake_html = "2026年3月完成集装箱吞吐量 420.5 万TEU；2026年2月完成 385.1 万TEU"
    with patch.object(adapter, "_get_text", return_value=fake_html):
        df = adapter.get_port_throughput(port="shanghai", period="monthly")
    assert not df.empty
    assert set(df["port"].unique()) == {"shanghai"}
    assert (df["unit"] == "万TEU").all()
    assert df["value"].max() == 420.5


def test_get_port_throughput_unknown_port(adapter):
    df = adapter.get_port_throughput(port="not_exists")
    assert df.empty


def test_get_port_throughput_empty_text(adapter):
    with patch.object(adapter, "_get_text", return_value=None):
        df = adapter.get_port_throughput(port="ningbo")
    assert df.empty


# ---------- AIS ----------

def test_get_ais_vessels_without_username_returns_empty():
    a = ShippingAdapter(aishub_username=None)
    # 清掉可能的env变量污染
    a.aishub_username = None
    assert a.get_ais_vessels(bbox=(100, 20, 130, 45)).empty


def test_get_ais_vessels_parses_payload(adapter):
    fake = [
        {"ERROR": False, "USERNAME": "test_user"},
        [
            {"MMSI": 413000001, "NAME": "EVER GIVEN", "LATITUDE": 31.2,
             "LONGITUDE": 121.5, "SOG": 12.1, "COG": 95.0, "HEADING": 90,
             "NAVSTAT": 0, "TYPE": 70, "TIME": "2026-04-15 11:00:00"},
            {"MMSI": 413000002, "NAME": "COSCO SHANGHAI", "LAT": 29.8,
             "LON": 122.1, "SOG": 0.0, "COG": 0.0, "HEADING": 0,
             "NAVSTAT": 1, "TYPE": 80, "TIME": "2026-04-15 11:05:00"},
        ],
    ]
    with patch.object(adapter, "_get_json", return_value=fake):
        df = adapter.get_ais_vessels(bbox=(100, 20, 130, 45))
    assert len(df) == 2
    assert {"mmsi", "name", "lat", "lon", "sog", "nav_status"}.issubset(df.columns)
    assert df.iloc[0]["name"] == "EVER GIVEN"


def test_get_ais_vessels_api_error(adapter):
    fake = [{"ERROR": True, "ERROR_MESSAGE": "Invalid username"}, []]
    with patch.object(adapter, "_get_json", return_value=fake):
        df = adapter.get_ais_vessels()
    assert df.empty


# ---------- health_check ----------

def test_health_check_pass(adapter):
    with patch.object(adapter, "_get_text", return_value="<html>ok</html>"):
        assert adapter.health_check() is True


def test_health_check_fail(adapter):
    with patch.object(adapter, "_get_text", return_value=None):
        assert adapter.health_check() is False
