"""
Input: pytest 运行 (mock AdapterRegistry)
Output: 验证 MCP Registry Server tools 发现与调用链路
Pos: tests/mcp/test_registry_server.py - L2 MCP Server 扩展 单元测试

[NEW-FILE:#20260415-51]

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pandas as pd
import pytest

from app.mcp import registry_server as rs


# ============================================================
# Fixture: mock _call_registry — 不真实触达 adapter
# ============================================================
@pytest.fixture
def mock_registry():
    """monkeypatch _call_registry, 记录调用并返回可控数据."""
    calls = []

    def fake(domain, method, **kwargs):
        calls.append({"domain": domain, "method": method, "kwargs": kwargs})
        # 不同 method 返回不同结构以覆盖序列化分支
        if method in ("get_stock_history", "get_realtime_quotes", "get_bdi_index", "get_feed"):
            return pd.DataFrame(
                [{"date": "2026-04-14", "close": 100.0}, {"date": "2026-04-15", "close": 101.5}]
            )
        if method == "get_ticker":
            return {"symbol": kwargs.get("symbol"), "last": 62345.5}
        if method in ("get_series", "get_indicator", "get_gdp", "get_cpi", "get_pmi", "get_industrial_output"):
            return pd.DataFrame([{"period": "2025Q4", "value": 27000}])
        if method == "get_financial_data":
            return {"revenue": 1e11, "net_income": 2e10}
        if method == "get_esg_score":
            return {"ticker": kwargs.get("ticker"), "score": 72}
        if method == "search_company":
            return pd.DataFrame([{"name": "ACME Corp", "company_number": "123"}])
        if method == "get_hiring_trend":
            return pd.DataFrame([{"company": "X", "postings": 42}])
        if method == "search_datasets":
            return [{"id": "LANDSAT_C2_L2", "title": "Landsat Collection 2"}]
        return {"ok": True}

    with patch.object(rs, "_call_registry", side_effect=fake) as p:
        yield {"patch": p, "calls": calls}


# ============================================================
# T1: discovery 列出全部 tools
# ============================================================
def test_list_tools_discovery():
    tools = rs.list_tools()
    names = {t["name"] for t in tools}
    # 至少覆盖 10+ tools
    assert len(tools) >= 10
    # 关键 tools 必须存在
    for must in [
        "a_stock_kline", "us_stock_quote", "crypto_ticker",
        "macro_us", "news_feed", "esg_rating",
        "corporate_search", "jobs_search", "shipping_bdi",
        "registry_status",
    ]:
        assert must in names, f"missing tool: {must}"
    # HANDLERS 与 REGISTRY_TOOLS 一致 (registry_status 在两边都有)
    assert names.issubset(set(rs.HANDLERS.keys()))


# ============================================================
# T2: 每个 tool 都有参数 schema 且结构合法
# ============================================================
def test_tool_schema_shape():
    for tool in rs.REGISTRY_TOOLS:
        assert "name" in tool and isinstance(tool["name"], str)
        assert "description" in tool and tool["description"]
        assert "parameters" in tool and isinstance(tool["parameters"], dict)
        for pname, pdef in tool["parameters"].items():
            assert "type" in pdef, f"{tool['name']}.{pname} 缺 type"
            assert "description" in pdef, f"{tool['name']}.{pname} 缺 description"


# ============================================================
# T3: tool → Registry 调用链路 (a_stock_kline)
# ============================================================
def test_a_stock_kline_routes_to_registry(mock_registry):
    result = rs.handle_mcp_tool_call(
        "a_stock_kline",
        {"code": "000001", "start_date": "20260101", "end_date": "20260415"},
    )
    assert "error" not in result
    assert result["total_rows"] == 2
    assert len(result["data"]) == 2
    # 调用链路校验
    call = mock_registry["calls"][-1]
    assert call["domain"] == "a_stock_kline"
    assert call["method"] == "get_stock_history"
    assert call["kwargs"]["code"] == "000001"
    assert call["kwargs"]["adjust"] == "qfq"  # default 透传


# ============================================================
# T4: crypto_ticker 返回 dict 的序列化
# ============================================================
def test_crypto_ticker_dict_return(mock_registry):
    result = rs.handle_mcp_tool_call("crypto_ticker", {"symbol": "ETH/USDT"})
    assert result["symbol"] == "ETH/USDT"
    assert result["last"] == 62345.5
    call = mock_registry["calls"][-1]
    assert call["domain"] == "crypto"
    assert call["method"] == "get_ticker"


# ============================================================
# T5: macro_cn 指标 → 方法映射 + 非法指标错误
# ============================================================
def test_macro_cn_method_mapping(mock_registry):
    ok = rs.handle_mcp_tool_call("macro_cn", {"indicator": "gdp"})
    assert "error" not in ok
    assert mock_registry["calls"][-1]["method"] == "get_gdp"

    bad = rs.handle_mcp_tool_call("macro_cn", {"indicator": "unknown_xyz"})
    assert "error" in bad
    assert "不支持" in bad["error"]


# ============================================================
# T6: 未知工具 + 参数错误 → 统一 error
# ============================================================
def test_unknown_tool_and_bad_args(mock_registry):
    r1 = rs.handle_mcp_tool_call("nonexistent_tool", {})
    assert "error" in r1 and "未知" in r1["error"]

    # a_stock_kline 缺必填
    r2 = rs.handle_mcp_tool_call("a_stock_kline", {})
    assert "error" in r2


# ============================================================
# T7: corporate_search / jobs_search / shipping_bdi / satellite 链路
# ============================================================
def test_misc_domains_routing(mock_registry):
    r = rs.handle_mcp_tool_call("corporate_search", {"query": "Apple", "jurisdiction": "us_ca"})
    assert mock_registry["calls"][-1]["domain"] == "corporate_entity"
    assert mock_registry["calls"][-1]["kwargs"]["name"] == "Apple"
    assert r["total_rows"] == 1

    rs.handle_mcp_tool_call("jobs_search", {"query": "engineer", "company": "Apple"})
    assert mock_registry["calls"][-1]["domain"] == "hiring_signal"

    rs.handle_mcp_tool_call("shipping_bdi", {"days": 90})
    c = mock_registry["calls"][-1]
    assert c["domain"] == "commodity_shipping" and c["kwargs"]["days"] == 90

    sat = rs.handle_mcp_tool_call("satellite_search", {"keyword": "landsat"})
    assert mock_registry["calls"][-1]["domain"] == "earth_observation"
    # list 返回
    assert isinstance(sat, list) and sat[0]["id"] == "LANDSAT_C2_L2"


# ============================================================
# T8: as_json 可序列化
# ============================================================
def test_as_json_serialisable(mock_registry):
    payload = rs.as_json("crypto_ticker", {"symbol": "BTC/USDT"})
    obj = json.loads(payload)
    assert obj["symbol"] == "BTC/USDT"


# ============================================================
# T9: registry_status 不走 _call_registry
# ============================================================
def test_registry_status(mock_registry):
    fake_status = {"domains": {"a_stock_kline": ["AkshareAdapter"]}, "fail_count": {}}
    with patch("app.adapters.adapter_registry.AdapterRegistry.default") as md:
        md.return_value.get_status.return_value = fake_status
        r = rs.handle_mcp_tool_call("registry_status", {})
    assert r == fake_status
