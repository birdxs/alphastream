# Input  : pytest 用例 + mock 注入 (monkeypatch app.mcp.registry_server._call_registry)
# Output : 验证 16 工具 handler + list_tools + handle_mcp_tool_call + as_json 的行为
# Pos    : tests/backend/integration/, 隶属 W2-BE05 MCP 全覆盖测试
#
# 一旦此文件被修改, 请同步更新:
#   - tests/audit/reports/BE-05_mcp.md  用例数 / 覆盖率
#   - tests/backend/integration/README.md (如有)
"""W2-BE05: app.mcp.registry_server 集成回归测试。

设计要点:
1. 全部通过 monkeypatch `_call_registry` 与 `AdapterRegistry.default` 完成隔离,
   不真实调用 akshare/yfinance/edgar 等外部数据源 (遵守 DISABLE_NETWORK 约束)。
2. 每个工具至少 3 项:
     (1) 快乐路径 - 合法 tool_name + 合法 arguments -> schema 正确
     (2) 入参校验 - 缺参/错参/未知工具 -> 走 error 分支而非 500
     (3) 适配器 mock 映射 - 断言透传到 Registry 的 domain/method/kwargs 正确
3. 单独标注 B3 corporate_search 的「query -> name」签名转换断言。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.mcp import registry_server as rs


# --------------------------------------------------------------------------- #
# Fixture: 拦截 _call_registry, 记录每次 (domain, method, kwargs) 并允许伪造返回值
# --------------------------------------------------------------------------- #

class _RegistrySpy:
    """记录每次 _call_registry 调用 & 控制返回值的辅助类."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, str, Dict[str, Any]]] = []
        self._next_returns: List[Any] = []
        self._raise: BaseException | None = None

    def push_return(self, value: Any) -> None:
        self._next_returns.append(value)

    def raise_on_next(self, exc: BaseException) -> None:
        self._raise = exc

    def __call__(self, domain: str, method: str, **kwargs):
        self.calls.append((domain, method, dict(kwargs)))
        if self._raise is not None:
            exc, self._raise = self._raise, None
            raise exc
        if self._next_returns:
            return self._next_returns.pop(0)
        # 默认返回一个 DataFrame, 验证 _to_jsonable 路径
        return pd.DataFrame([{"x": 1}])


@pytest.fixture
def reg_spy(monkeypatch) -> _RegistrySpy:
    spy = _RegistrySpy()
    monkeypatch.setattr(rs, "_call_registry", spy)
    return spy


# --------------------------------------------------------------------------- #
# 0. 顶层 schema / 列表一致性
# --------------------------------------------------------------------------- #

class TestRegistrySchema:
    def test_registry_tools_count_is_16(self):
        assert len(rs.REGISTRY_TOOLS) == 16

    def test_handlers_count_matches_tools(self):
        tool_names = {t["name"] for t in rs.REGISTRY_TOOLS}
        handler_names = set(rs.HANDLERS.keys())
        assert tool_names == handler_names, (
            f"REGISTRY_TOOLS 与 HANDLERS 不一致: "
            f"only_in_tools={tool_names - handler_names}, "
            f"only_in_handlers={handler_names - tool_names}"
        )

    def test_every_tool_has_schema(self):
        # [Batch8-FIX 2026-05-19] REGISTRY_TOOLS 用 'parameters' 字段（非 MCP 标准 inputSchema）
        for tool in rs.REGISTRY_TOOLS:
            assert "name" in tool and isinstance(tool["name"], str)
            assert "description" in tool
            # 支持 parameters 或 inputSchema 任一格式
            has_params = "parameters" in tool or "inputSchema" in tool
            assert has_params, f"工具 {tool['name']} 缺少 parameters/inputSchema 字段"
            params = tool.get("parameters") or tool.get("inputSchema", {})
            assert isinstance(params, dict)

    def test_list_tools_returns_same_list(self):
        result = rs.list_tools()
        assert isinstance(result, list)
        assert len(result) == len(rs.REGISTRY_TOOLS)
        assert {t["name"] for t in result} == {t["name"] for t in rs.REGISTRY_TOOLS}

    def test_mcp_registry_config_meta(self):
        cfg = rs.MCP_REGISTRY_CONFIG
        assert cfg["name"] == "stockanal-registry-server"
        assert "version" in cfg
        assert cfg["tools"] is rs.REGISTRY_TOOLS


# --------------------------------------------------------------------------- #
# 1. A 股 / 美股 / 港股 / 加密 (5 工具)
# --------------------------------------------------------------------------- #

class TestEquityHandlers:
    def test_a_stock_kline_happy(self, reg_spy):
        reg_spy.push_return(pd.DataFrame([{"date": "2024-01-02", "close": 10.0}]))
        out = rs._h_a_stock_kline("000001", "2024-01-01", "2024-01-31", adjust="qfq")
        domain, method, kwargs = reg_spy.calls[-1]
        assert domain == "a_stock_kline"
        assert method == "get_stock_history"
        assert kwargs == {
            "code": "000001",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "adjust": "qfq",
        }
        # _to_jsonable 对 DataFrame 输出含 data / total_rows / truncated
        assert isinstance(out, dict)
        assert "data" in out and out["total_rows"] == 1

    def test_a_stock_kline_missing_required_arg(self):
        # 缺 start_date / end_date -> handle_mcp_tool_call 应捕获 TypeError 返回 error
        ret = rs.handle_mcp_tool_call("a_stock_kline", {"code": "000001"})
        assert isinstance(ret, dict) and "error" in ret
        assert "参数错误" in ret["error"] or "missing" in ret["error"].lower()

    def test_a_stock_realtime_default_codes(self, reg_spy):
        rs._h_a_stock_realtime()
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("a_stock_realtime", "get_realtime_quotes")
        assert kwargs == {"codes": None}

    def test_a_stock_realtime_with_codes(self, reg_spy):
        rs._h_a_stock_realtime(["000001", "600519"])
        _, _, kwargs = reg_spy.calls[-1]
        assert kwargs["codes"] == ["000001", "600519"]

    def test_us_stock_quote_full(self, reg_spy):
        rs._h_us_stock_quote("AAPL", "2024-01-01", "2024-06-30")
        domain, method, kwargs = reg_spy.calls[-1]
        assert domain == "us_stock" and method == "get_stock_history"
        assert kwargs == {
            "code": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
        }

    def test_us_stock_quote_optional_dates_skipped(self, reg_spy):
        rs._h_us_stock_quote("AAPL")
        _, _, kwargs = reg_spy.calls[-1]
        # 仅 code, 不应混入 None 的 start_date/end_date
        assert kwargs == {"code": "AAPL"}

    def test_hk_stock_quote_mapping(self, reg_spy):
        rs._h_hk_stock_quote("00700", "2024-01-01", "2024-06-30")
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("hk_stock", "get_stock_history")
        assert kwargs == {
            "code": "00700",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
        }

    def test_crypto_ticker_default_symbol(self, reg_spy):
        rs._h_crypto_ticker()
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("crypto", "get_ticker")
        assert kwargs == {"symbol": "BTC/USDT"}

    def test_crypto_ticker_custom_symbol(self, reg_spy):
        rs._h_crypto_ticker("ETH/USDT")
        _, _, kwargs = reg_spy.calls[-1]
        assert kwargs == {"symbol": "ETH/USDT"}


# --------------------------------------------------------------------------- #
# 2. 宏观 / XBRL (4 工具)
# --------------------------------------------------------------------------- #

class TestMacroHandlers:
    def test_macro_us_mapping(self, reg_spy):
        rs._h_macro_us("GDPC1")
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("macro_us", "get_series")
        assert kwargs == {"series_id": "GDPC1"}

    @pytest.mark.parametrize("indicator,expected_method", [
        ("gdp", "get_gdp"),
        ("cpi", "get_cpi"),
        ("pmi", "get_pmi"),
        ("industrial_output", "get_industrial_output"),
        ("GDP", "get_gdp"),  # 大小写无关
    ])
    def test_macro_cn_indicator_routing(self, reg_spy, indicator, expected_method):
        rs._h_macro_cn(indicator)
        domain, method, _ = reg_spy.calls[-1]
        assert domain == "macro_cn" and method == expected_method

    def test_macro_cn_unknown_indicator_returns_error(self, reg_spy):
        out = rs._h_macro_cn("unknown_xx")
        assert isinstance(out, dict) and "error" in out
        # 不应触发 registry 调用
        assert reg_spy.calls == []

    def test_macro_global_default_country(self, reg_spy):
        rs._h_macro_global("NY.GDP.MKTP.CD")
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("macro_global", "get_indicator")
        assert kwargs == {"indicator": "NY.GDP.MKTP.CD", "country": "USA"}

    def test_macro_global_custom_country(self, reg_spy):
        rs._h_macro_global("NY.GDP.MKTP.CD", country="CHN")
        _, _, kwargs = reg_spy.calls[-1]
        assert kwargs["country"] == "CHN"

    def test_xbrl_financials_mapping(self, reg_spy):
        rs._h_xbrl_financials("AAPL")
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("xbrl_financials", "get_financial_data")
        assert kwargs == {"code": "AAPL"}


# --------------------------------------------------------------------------- #
# 3. 另类数据 (news / esg / corporate / jobs / shipping / satellite)
# --------------------------------------------------------------------------- #

class TestAltDataHandlers:
    def test_news_feed_default(self, reg_spy):
        rs._h_news_feed()
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("news", "get_feed")
        assert kwargs == {"source": "wallstreetcn", "limit": 20}

    def test_news_feed_custom(self, reg_spy):
        rs._h_news_feed(source="cls", limit=5)
        _, _, kwargs = reg_spy.calls[-1]
        assert kwargs == {"source": "cls", "limit": 5}

    def test_esg_rating_default_source(self, reg_spy):
        rs._h_esg_rating("AAPL")
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("esg_rating", "get_esg_score")
        assert kwargs == {"ticker": "AAPL", "source": "esgbook"}

    # ---- B3 已知签名转换点 ----
    def test_corporate_search_query_is_mapped_to_name(self, reg_spy):
        """B3 已知 bug 暴露点: MCP 入参 `query` 应被映射为 Registry 入参 `name=`.

        当前实现 (registry_server.py:269-273) 把 `query` 透传为 `name=query`,
        若任一侧改动而对面未跟进将导致 search_company() 抛 TypeError.
        本测试明确锁定该映射, 便于回归监控。
        """
        rs._h_corporate_search("Apple Inc", jurisdiction="us_ca", per_page=10)
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("corporate_entity", "search_company")
        # 关键断言: query 已被改名为 name
        assert "query" not in kwargs, "MCP 不应把 query 原样透传给 Registry"
        assert kwargs["name"] == "Apple Inc"
        assert kwargs["jurisdiction"] == "us_ca"
        assert kwargs["per_page"] == 10

    def test_corporate_search_minimal(self, reg_spy):
        rs._h_corporate_search("Tesla")
        _, _, kwargs = reg_spy.calls[-1]
        assert kwargs == {"name": "Tesla", "jurisdiction": None, "per_page": 30}

    def test_jobs_search_all_optional(self, reg_spy):
        rs._h_jobs_search()
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("hiring_signal", "get_hiring_trend")
        assert kwargs == {"query": None, "company": None}

    def test_jobs_search_with_args(self, reg_spy):
        rs._h_jobs_search(query="ai engineer", company="OpenAI")
        _, _, kwargs = reg_spy.calls[-1]
        assert kwargs == {"query": "ai engineer", "company": "OpenAI"}

    def test_shipping_bdi_default_days(self, reg_spy):
        rs._h_shipping_bdi()
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("commodity_shipping", "get_bdi_index")
        assert kwargs == {"days": 30}

    def test_shipping_bdi_custom_days(self, reg_spy):
        rs._h_shipping_bdi(days=90)
        _, _, kwargs = reg_spy.calls[-1]
        assert kwargs == {"days": 90}

    def test_satellite_search_mapping(self, reg_spy):
        rs._h_satellite_search("flood china", limit=5)
        domain, method, kwargs = reg_spy.calls[-1]
        assert (domain, method) == ("earth_observation", "search_datasets")
        assert kwargs == {"keyword": "flood china", "limit": 5}


# --------------------------------------------------------------------------- #
# 4. registry_status (走 AdapterRegistry.default 而非 _call_registry)
# --------------------------------------------------------------------------- #

class TestRegistryStatus:
    def test_registry_status_returns_dict(self, monkeypatch):
        fake_reg = MagicMock()
        fake_reg.get_status.return_value = {
            "domains": ["a_stock_kline", "us_stock"],
            "primary_only": False,
        }
        monkeypatch.setattr(
            "app.adapters.adapter_registry.AdapterRegistry.default",
            classmethod(lambda cls: fake_reg),
        )
        out = rs._h_registry_status()
        assert isinstance(out, dict)
        assert "domains" in out
        fake_reg.get_status.assert_called_once()


# --------------------------------------------------------------------------- #
# 5. handle_mcp_tool_call 异常路径 / list_tools / as_json
# --------------------------------------------------------------------------- #

class TestDispatcher:
    def test_handle_unknown_tool_returns_error(self):
        out = rs.handle_mcp_tool_call("not_a_real_tool", {})
        assert isinstance(out, dict)
        assert "error" in out
        assert "未知" in out["error"]

    def test_handle_none_arguments_treated_as_empty(self, reg_spy):
        # registry_status 无需 arguments, None 应被替换为 {}
        with pytest.MonkeyPatch.context() as mp:
            fake_reg = MagicMock()
            fake_reg.get_status.return_value = {"ok": True}
            mp.setattr(
                "app.adapters.adapter_registry.AdapterRegistry.default",
                classmethod(lambda cls: fake_reg),
            )
            out = rs.handle_mcp_tool_call("registry_status", None)
        assert out == {"ok": True}

    def test_handle_internal_exception_returns_structured_error(self, reg_spy):
        reg_spy.raise_on_next(RuntimeError("registry exploded"))
        out = rs.handle_mcp_tool_call(
            "a_stock_kline",
            {"code": "000001", "start_date": "2024-01-01", "end_date": "2024-01-31"},
        )
        assert isinstance(out, dict) and "error" in out
        assert "RuntimeError" in out["error"]
        assert "registry exploded" in out["error"]

    def test_handle_type_error_returns_param_error(self, reg_spy):
        # 多传未知 kwarg, handler 签名不接受 -> TypeError -> 走 "参数错误"
        out = rs.handle_mcp_tool_call("crypto_ticker", {"not_a_param": "xx"})
        assert isinstance(out, dict) and "error" in out
        assert "参数错误" in out["error"]

    def test_handle_happy_path_returns_payload(self, reg_spy):
        reg_spy.push_return({"price": 123.4})
        out = rs.handle_mcp_tool_call("crypto_ticker", {"symbol": "BTC/USDT"})
        assert out == {"price": 123.4}

    def test_as_json_serializes_result(self, reg_spy):
        reg_spy.push_return({"price": 123.4})
        s = rs.as_json("crypto_ticker", {"symbol": "BTC/USDT"})
        assert isinstance(s, str)
        parsed = json.loads(s)
        assert parsed == {"price": 123.4}

    def test_as_json_serializes_error(self):
        s = rs.as_json("not_a_real_tool", {})
        assert isinstance(s, str)
        parsed = json.loads(s)
        assert "error" in parsed


# --------------------------------------------------------------------------- #
# 6. _to_jsonable 行为校验 (覆盖 truncate / 标量 / None / 兜底)
# --------------------------------------------------------------------------- #

class TestToJsonable:
    def test_dataframe_truncated(self):
        df = pd.DataFrame([{"i": i} for i in range(150)])
        out = rs._to_jsonable(df, limit=100)
        assert out["total_rows"] == 150
        assert out["truncated"] is True
        assert len(out["data"]) == 100

    def test_dataframe_not_truncated(self):
        df = pd.DataFrame([{"i": i} for i in range(5)])
        out = rs._to_jsonable(df, limit=100)
        assert out["truncated"] is False
        assert out["total_rows"] == 5

    def test_scalars_passthrough(self):
        assert rs._to_jsonable(None) is None
        assert rs._to_jsonable(42) == 42
        assert rs._to_jsonable("hi") == "hi"
        assert rs._to_jsonable([1, 2]) == [1, 2]
        assert rs._to_jsonable({"k": "v"}) == {"k": "v"}

    def test_unknown_object_fallback(self):
        class _Weird:
            def __str__(self):
                return "WEIRD"
        out = rs._to_jsonable(_Weird())
        assert out == {"value": "WEIRD"}


# --------------------------------------------------------------------------- #
# 7. 全量 dispatch round-trip: 每个工具至少被 handle_mcp_tool_call 触达一次
# --------------------------------------------------------------------------- #

# 每个工具的最小合法参数集 (用于 dispatcher 冒烟)
_MIN_ARGS: Dict[str, Dict[str, Any]] = {
    "a_stock_kline":     {"code": "000001", "start_date": "2024-01-01", "end_date": "2024-01-31"},
    "a_stock_realtime":  {},
    "us_stock_quote":    {"symbol": "AAPL"},
    "hk_stock_quote":    {"code": "00700", "start_date": "2024-01-01", "end_date": "2024-06-30"},
    "crypto_ticker":     {"symbol": "BTC/USDT"},
    "macro_us":          {"indicator": "GDPC1"},
    "macro_cn":          {"indicator": "gdp"},
    "macro_global":      {"indicator": "NY.GDP.MKTP.CD"},
    "xbrl_financials":   {"ticker": "AAPL"},
    "news_feed":         {},
    "esg_rating":        {"ticker": "AAPL"},
    "corporate_search":  {"query": "Apple Inc"},
    "jobs_search":       {},
    "shipping_bdi":      {},
    "satellite_search":  {"keyword": "flood"},
    "registry_status":   {},
}


class TestDispatcherFullSweep:
    @pytest.mark.parametrize("tool_name", list(_MIN_ARGS.keys()))
    def test_dispatch_each_tool(self, monkeypatch, tool_name):
        """对 16 工具逐个走一遍 handle_mcp_tool_call, 验证不抛 500."""
        spy = _RegistrySpy()
        spy.push_return({"ok": True})  # 给 _call_registry 走的工具
        monkeypatch.setattr(rs, "_call_registry", spy)

        # registry_status 走 AdapterRegistry.default(), 单独 mock
        if tool_name == "registry_status":
            fake_reg = MagicMock()
            fake_reg.get_status.return_value = {"status": "ok"}
            monkeypatch.setattr(
                "app.adapters.adapter_registry.AdapterRegistry.default",
                classmethod(lambda cls: fake_reg),
            )

        out = rs.handle_mcp_tool_call(tool_name, _MIN_ARGS[tool_name])
        # 1) 不能返回 None
        assert out is not None
        # 2) 即使返回 error 也必须是 dict
        assert isinstance(out, (dict, list))
        # 3) error 字段若存在, 必须是字符串且非空 (而非异常抛出)
        if isinstance(out, dict) and "error" in out:
            assert isinstance(out["error"], str) and out["error"]
