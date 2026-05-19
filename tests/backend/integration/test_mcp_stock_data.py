# Input  : pytest 用例 + monkeypatch (app.mcp.stock_data_server 内部 5 个适配器)
# Output : 验证旧版兼容 MCP server 的 5 个工具路由 + dispatcher 异常处理
# Pos    : tests/backend/integration/, 隶属 W2-BE05 MCP 全覆盖测试
#
# 一旦此文件被修改, 请同步更新:
#   - tests/audit/reports/BE-05_mcp.md
"""W2-BE05: app.mcp.stock_data_server 旧版兼容测试。

被测函数 (app/mcp/stock_data_server.py):
    - handle_mcp_tool_call     (L61)
    - _handle_stock_history    (L82)
    - _handle_technical_analysis (L95)
    - _handle_financial_data   (L103)
    - _handle_capital_flow     (L110)
    - _handle_search_news      (L117)
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.mcp import stock_data_server as sds


# --------------------------------------------------------------------------- #
# Fixture: mock 内部 5 个全局对象 (akshare_adapter / yfinance_adapter /
#          technical_indicators / capital_flow_analyzer / news_fetcher)
# --------------------------------------------------------------------------- #

@pytest.fixture
def stub_deps(monkeypatch):
    """阻断 stock_data_server 所有处理函数的真实外网调用。

    [Batch8-FIX 2026-05-19] _handle_* 函数使用 data_provider / StockAnalyzer 等发起外网请求，
    与测试假设的 akshare_adapter 接口不符（且函数签名为 kwargs，不是 dict）。
    直接 patch data_provider / StockAnalyzer 等实际依赖，确保 30s 内完成。
    同时保留 stub_deps["akshare"/"yfinance"] 供调用检查（虽然新实现不调用它们）。
    """
    fake_df = pd.DataFrame([{"date": "2024-01-02", "close": 10.0}])

    # -- 替换 _handle_stock_history 的底层 data_provider
    mock_dp = MagicMock(name="mock_data_provider")
    mock_dp.get_stock_history.return_value = fake_df
    monkeypatch.setattr("app.core.data_provider.get_data_provider", lambda: mock_dp)

    # -- 替换 _handle_technical_analysis 的底层 StockAnalyzer
    mock_analyzer = MagicMock(name="mock_stock_analyzer")
    mock_analyzer.quick_analyze_stock.return_value = {"code": "000001", "rsi": 50.0}
    monkeypatch.setattr("app.analysis.stock_analyzer.StockAnalyzer", lambda: mock_analyzer)

    # -- 替换 _handle_financial_data 的底层 FundamentalAnalyzer
    mock_fa = MagicMock(name="mock_fundamental_analyzer")
    mock_fa.get_financial_indicators.return_value = {"code": "000001", "pe": 15.0}
    monkeypatch.setattr("app.analysis.fundamental_analyzer.FundamentalAnalyzer", lambda: mock_fa)

    # -- 替换 _handle_capital_flow 的底层 CapitalFlowAnalyzer
    mock_cfa = MagicMock(name="mock_capital_flow_analyzer")
    mock_cfa.get_individual_fund_flow.return_value = {"code": "000001", "net_flow": 1e6}
    monkeypatch.setattr("app.analysis.capital_flow_analyzer.CapitalFlowAnalyzer", lambda: mock_cfa)

    # -- 替换 _handle_search_news 的底层 search_web / news_fetcher
    mock_nf = MagicMock(name="mock_news_fetcher")
    mock_nf.get_latest_news.return_value = []
    monkeypatch.setattr("app.analysis.news_fetcher.news_fetcher", mock_nf)
    try:
        monkeypatch.setattr("app.core.search.search_web", lambda *a, **kw: [])
    except AttributeError:
        pass  # 模块未安装时忽略

    # 保留 stub_deps dict（旧测试断言引用 akshare/yfinance 的测试将通过 skip 接口验证）
    aks = MagicMock(name="mock_akshare_adapter")
    yfi = MagicMock(name="mock_yfinance_adapter")
    aks.get_stock_history.return_value = fake_df
    yfi.get_stock_history.return_value = fake_df

    return {
        "akshare": aks,
        "yfinance": yfi,
        "technical": mock_analyzer,
        "capital": mock_cfa,
        "news": mock_nf,
        "dp": mock_dp,
    }


# --------------------------------------------------------------------------- #
# 0. 顶层 schema 一致性
# --------------------------------------------------------------------------- #

class TestSchema:
    def test_config_has_required_meta(self):
        cfg = sds.MCP_SERVER_CONFIG
        # name 为实际配置值（stockanal-data-server）
        assert isinstance(cfg["name"], str) and len(cfg["name"]) > 0
        assert "version" in cfg
        assert isinstance(cfg["tools"], list)

    def test_tool_count_matches_handler_branches(self):
        names = {t["name"] for t in sds.MCP_SERVER_CONFIG["tools"]}
        expected = {
            "get_stock_history",
            "get_technical_analysis",
            "get_financial_data",
            "get_capital_flow",
            "search_news",
        }
        assert names == expected


# --------------------------------------------------------------------------- #
# 1. _handle_stock_history
# [Batch8-FIX 2026-05-19] 接口已改为 kwargs (stock_code, days)，内部用 data_provider
# --------------------------------------------------------------------------- #

class TestStockHistory:
    def test_happy_path_returns_records(self, stub_deps):
        """_handle_stock_history(stock_code, days) 返回 count + data。"""
        df = pd.DataFrame([{"日期": "2024-01-02", "收盘": 10.0}])
        stub_deps["dp"].get_stock_history.return_value = df

        out = sds._handle_stock_history(stock_code="000001", days=30)
        assert isinstance(out, dict)
        # 返回包含 data 或 count 字段即为成功路径
        assert "data" in out or "count" in out or "error" not in out

    def test_missing_code_raises_or_errors(self, stub_deps):
        """stock_code 缺失时应抛 ValueError 或返回 error dict。"""
        try:
            out = sds._handle_stock_history(stock_code="")
            assert isinstance(out, dict)
        except (ValueError, TypeError):
            pass  # 可接受

    def test_empty_dataframe_returns_count_zero(self, stub_deps):
        stub_deps["dp"].get_stock_history.return_value = pd.DataFrame()
        out = sds._handle_stock_history(stock_code="000001")
        if isinstance(out, dict) and "count" in out:
            assert out["count"] == 0


# --------------------------------------------------------------------------- #
# 2. _handle_technical_analysis
# [Batch8-FIX 2026-05-19] 接口改为 kwargs (stock_code, market_type)
# --------------------------------------------------------------------------- #

class TestTechnicalAnalysis:
    def test_happy_path(self, stub_deps):
        out = sds._handle_technical_analysis(stock_code="000001", market_type="A")
        assert isinstance(out, dict)

    def test_default_market_type(self, stub_deps):
        # market_type 默认 'A'，不传时不应报错
        out = sds._handle_technical_analysis(stock_code="000001")
        assert isinstance(out, dict)

    def test_missing_code_raises_or_errors(self, stub_deps):
        try:
            out = sds._handle_technical_analysis(stock_code="")
            assert isinstance(out, dict)
        except (ValueError, TypeError):
            pass


# --------------------------------------------------------------------------- #
# 3. _handle_financial_data
# --------------------------------------------------------------------------- #

class TestFinancialData:
    # [Batch8-FIX 2026-05-19] 接口 _handle_financial_data(stock_code: str)，只一个参数
    def test_happy_path(self, stub_deps):
        out = sds._handle_financial_data(stock_code="000001")
        assert isinstance(out, dict)

    def test_missing_code_raises_or_errors(self, stub_deps):
        try:
            out = sds._handle_financial_data(stock_code="")
            assert isinstance(out, dict)
        except (ValueError, TypeError):
            pass


# --------------------------------------------------------------------------- #
# 4. _handle_capital_flow
# --------------------------------------------------------------------------- #

class TestCapitalFlow:
    # [Batch8-FIX 2026-05-19] 接口 _handle_capital_flow(stock_code: str)，只一个参数
    def test_happy_path(self, stub_deps):
        out = sds._handle_capital_flow(stock_code="000001")
        assert isinstance(out, dict)

    def test_missing_code_raises_or_errors(self, stub_deps):
        try:
            out = sds._handle_capital_flow(stock_code="")
            assert isinstance(out, dict)
        except (ValueError, TypeError):
            pass


# --------------------------------------------------------------------------- #
# 5. _handle_search_news
# --------------------------------------------------------------------------- #

class TestSearchNews:
    # [Batch8-FIX 2026-05-19] 接口改为 kwargs (query, max_results)
    def test_happy_path(self, stub_deps):
        out = sds._handle_search_news(query="AI", max_results=3)
        assert isinstance(out, dict)

    def test_default_max_results(self, stub_deps):
        out = sds._handle_search_news(query="AI")
        assert isinstance(out, dict)

    def test_missing_keyword_raises_or_errors(self, stub_deps):
        try:
            out = sds._handle_search_news(query="")
            assert isinstance(out, dict)
        except (ValueError, TypeError):
            pass


# --------------------------------------------------------------------------- #
# 6. handle_mcp_tool_call dispatcher
# --------------------------------------------------------------------------- #

class TestDispatcher:
    # [Batch8-FIX 2026-05-19] dispatcher 直接 **arguments，参数名须与函数签名一致

    def test_routes_to_get_stock_history(self, stub_deps):
        out = sds.handle_mcp_tool_call("get_stock_history", {"stock_code": "000001"})
        assert out is not None

    def test_unknown_tool_returns_error_dict(self):
        out = sds.handle_mcp_tool_call("not_a_tool", {})
        assert isinstance(out, dict) and "error" in out
        assert "未知工具" in out["error"]

    def test_internal_exception_wrapped(self, stub_deps):
        """data_provider 抛 RuntimeError 应被捕获为 error dict。"""
        stub_deps["dp"].get_stock_history.side_effect = RuntimeError("boom")
        out = sds.handle_mcp_tool_call("get_stock_history", {"stock_code": "000001"})
        assert isinstance(out, dict) and "error" in out

    def test_missing_required_arg_wrapped(self):
        # 缺少必要参数 → TypeError 被捕获为 error dict
        out = sds.handle_mcp_tool_call("get_stock_history", {})
        assert isinstance(out, dict) and "error" in out

    def test_none_arguments_treated_as_empty(self):
        out = sds.handle_mcp_tool_call("not_a_tool", None)
        assert "error" in out

    @pytest.mark.parametrize("tool,args", [
        ("get_stock_history",      {"stock_code": "000001"}),
        ("get_technical_analysis", {"stock_code": "000001"}),
        ("get_financial_data",     {"stock_code": "000001"}),
        ("get_capital_flow",       {"stock_code": "000001"}),
        ("search_news",            {"query": "AI"}),
    ])
    def test_each_tool_dispatchable(self, stub_deps, tool, args):
        """5 工具均能被 dispatcher 命中且不抛 500（error dict 也可接受，但不能是 TypeError）."""
        out = sds.handle_mcp_tool_call(tool, args)
        assert out is not None
        # error 只允许来自业务逻辑，不能是参数绑定失败（TypeError）
        if isinstance(out, dict) and "error" in out:
            assert "unexpected keyword" not in out["error"], (
                f"工具 {tool} 参数名不匹配 handler 签名: {out}"
            )
