"""
Input: 自然语言 message + 可选 portfolio 上下文
Output: 断言 intent 标签、空/有持仓 snapshot 工具结果（无假仓）
Pos: tests/backend/unit/test_sprint2_intent_portfolio.py — Sprint2 意图路由 + 持仓只读工具

[NEW-FILE:#20260723-S2] 最小单元测试；离线可跑。
"""
from __future__ import annotations

import json
import os

import pytest

# 强制离线，避免 risk 路径联网
os.environ.setdefault("DISABLE_NETWORK", "1")
os.environ.setdefault("MOCK_LLM", "1")
os.environ.setdefault("AUTH_REQUIRED", "false")

from app.core.intent_router import (
    INTENT_CROSS_MARKET_EVENT,
    INTENT_GENERAL,
    INTENT_MARKET_OVERVIEW,
    INTENT_PORTFOLIO,
    INTENT_PORTFOLIO_WRITE,
    INTENT_SINGLE_STOCK_DEEP,
    classify_intent,
)
from app.core.tools import (
    execute_tool,
    is_write_tool_name,
    normalize_portfolio_snapshot,
    portfolio_context,
)


class TestIntentRouterRules:
    def test_portfolio_keyword(self):
        r = classify_intent("帮我看看持仓风险和集中度")
        assert r.intent == INTENT_PORTFOLIO
        assert r.inject_portfolio is True
        assert r.confidence >= 0.8

    def test_cross_market_event(self):
        r = classify_intent("美联储加息对 A 股有什么冲击？")
        assert r.intent == INTENT_CROSS_MARKET_EVENT
        assert "search_web" in r.system_hint or "工具" in r.system_hint

    def test_market_overview(self):
        r = classify_intent("今日大盘怎么样，上证走势如何")
        assert r.intent == INTENT_MARKET_OVERVIEW

    def test_single_stock_deep_with_code_and_verb(self):
        r = classify_intent("深度分析 600519 基本面")
        assert r.intent == INTENT_SINGLE_STOCK_DEEP
        assert "600519" in r.stock_codes

    def test_code_only_single_stock(self):
        r = classify_intent("600519")
        assert r.intent == INTENT_SINGLE_STOCK_DEEP
        assert "600519" in r.stock_codes

    def test_general(self):
        r = classify_intent("你好，介绍一下你自己")
        assert r.intent == INTENT_GENERAL

    def test_snapshot_weak_portfolio_signal(self):
        r = classify_intent("帮我看下风险分散", has_portfolio_snapshot=True)
        assert r.intent == INTENT_PORTFOLIO
        assert r.inject_portfolio is True

    def test_stock_code_hint(self):
        r = classify_intent("全面分析一下", stock_code_hint="000001")
        assert r.intent == INTENT_SINGLE_STOCK_DEEP
        assert "000001" in r.stock_codes

    def test_meta_has_no_fake_prices(self):
        meta = classify_intent("持仓").to_meta()
        # 契约字段齐全，且不含价格类假值键
        assert meta["intent"] == INTENT_PORTFOLIO
        assert "price" not in meta
        assert "fake" not in json.dumps(meta).lower()
        assert meta["router"] == "rules_v1"

    def test_portfolio_write_intent_hard_refuse_hint(self):
        """P0-2：拟写仓关键词优先于持仓分析，system_hint 硬拒绝假成功。"""
        r = classify_intent("帮我加仓600519")
        assert r.intent == INTENT_PORTFOLIO_WRITE
        assert "写仓" in r.system_hint or "硬拦" in r.system_hint
        assert "禁止" in r.system_hint
        assert r.inject_portfolio is True
        assert r.confidence >= 0.9

    def test_portfolio_write_precedence_over_portfolio_kw(self):
        r = classify_intent("把持仓调仓，减仓一半")
        assert r.intent == INTENT_PORTFOLIO_WRITE


class TestWriteToolHardBlock:
    """P0-2：写仓/下单工具名服务端 no-op + 明确错误，不假成功。"""

    def test_is_write_tool_name(self):
        assert is_write_tool_name("add_holding") is True
        assert is_write_tool_name("buy") is True
        assert is_write_tool_name("place_order") is True
        assert is_write_tool_name("get_stock_data") is False
        assert is_write_tool_name("get_portfolio_snapshot") is False

    def test_execute_write_tool_blocked_json(self):
        raw = execute_tool("add_holding", {"code": "600519", "shares": 100})
        data = json.loads(raw)
        assert data["success"] is False
        assert data.get("executed") is False
        assert data["error_code"] == "WRITE_TOOL_BLOCKED"
        assert data.get("data") is None
        assert "写" in data["message"] or "硬拦" in data["message"]

    def test_execute_buy_alias_blocked(self):
        raw = execute_tool("buy", {"symbol": "600519"})
        data = json.loads(raw)
        assert data["error_code"] == "WRITE_TOOL_BLOCKED"
        assert data["success"] is False


class TestPortfolioSnapshotTools:
    def test_normalize_empty(self):
        snap = normalize_portfolio_snapshot(None)
        assert snap["holdings"] == []
        assert snap["source"] in ("none", "invalid", "client")
        assert "as_of" in snap

    def test_normalize_scrubs_code_as_name(self):
        snap = normalize_portfolio_snapshot(
            {
                "source": "unit",
                "holdings": [
                    {"code": "600519", "name": "600519", "weight": 0.4},
                    {"code": "000001", "name": "平安银行", "weight": 0.6},
                ],
            }
        )
        by_code = {h["code"]: h for h in snap["holdings"]}
        assert by_code["600519"]["name"] == ""
        assert by_code["000001"]["name"] == "平安银行"

    def test_empty_context_tool_returns_empty_structure(self):
        with portfolio_context(None):
            raw = execute_tool("get_portfolio_snapshot", {})
        data = json.loads(raw)
        assert data["holdings"] == []
        assert data["empty"] is True
        assert data["count"] == 0
        # 铁律 #1：不得出现像真持仓的编造条目
        assert not data["holdings"]

    def test_filled_context_tool_returns_true_holdings(self):
        snap = {
            "source": "unit",
            "holdings": [
                {
                    "code": "600519",
                    "name": "贵州茅台",
                    "weight": 0.5,
                    "shares": 100,
                    "cost": 1500.0,
                }
            ],
        }
        with portfolio_context(snap):
            raw = execute_tool("get_portfolio_snapshot", {})
            risk = execute_tool("get_portfolio_risk_summary", {})
        data = json.loads(raw)
        assert data["count"] == 1
        assert data["holdings"][0]["code"] == "600519"
        assert data["holdings"][0]["name"] == "贵州茅台"
        assert data["holdings"][0]["weight"] == 0.5

        risk_data = json.loads(risk)
        assert risk_data["structural"]["count"] == 1
        assert risk_data["structural"]["max_weight_code"] == "600519"
        # 离线默认不造 market_risk 假分
        assert risk_data.get("market_risk") is None

    def test_risk_summary_empty(self):
        with portfolio_context({"holdings": [], "source": "unit"}):
            raw = execute_tool("get_portfolio_risk_summary", {})
        data = json.loads(raw)
        assert data["structural"]["empty"] is True


class TestAiChatSchemaPortfolioField:
    def test_schema_accepts_portfolio_snapshot(self):
        from app.web.schema import AiChatStreamSchema

        loaded = AiChatStreamSchema().load(
            {
                "message": "看下持仓",
                "portfolio_snapshot": {
                    "holdings": [{"code": "600519", "name": "贵州茅台"}],
                    "source": "unit",
                },
            }
        )
        assert loaded["message"] == "看下持仓"
        assert loaded["portfolio_snapshot"]["holdings"][0]["code"] == "600519"

    def test_schema_optional_snapshot_none(self):
        from app.web.schema import AiChatStreamSchema

        loaded = AiChatStreamSchema().load({"message": "hello"})
        assert loaded.get("portfolio_snapshot") is None


# --- G4 写意图硬拦回归矩阵 ---
class TestWriteGuardMatrixG4:
    """mutate 名拦截 + portfolio_write 意图不得假成功。"""

    def test_mutate_name_matrix(self):
        from app.core.tools import is_write_tool_name, _refuse_write_tool, execute_tool
        import json
        mutates = [
            "mutate",
            "mutate_state",
            "system_mutate",
            "admin_write",
            "set_holding",
            "upsert_holding",
            "rebalance_portfolio",
            "liquidate",
            "batch_update_holdings",
            "force_write",
        ]
        for name in mutates:
            assert is_write_tool_name(name) is True, name
            blocked = _refuse_write_tool(name)
            data = json.loads(blocked)
            assert data.get("error_code") == "WRITE_TOOL_BLOCKED"
            assert data.get("success") is False
            assert data.get("executed") is False
            # execute_tool 不得假成功
            out = execute_tool(name, {})
            assert "WRITE_TOOL_BLOCKED" in out

    def test_readonly_still_allowed_names(self):
        from app.core.tools import is_write_tool_name
        for name in ("get_stock_data", "get_portfolio_snapshot", "get_fundamental_data", "search_web"):
            assert is_write_tool_name(name) is False, name

    def test_portfolio_write_intent_system_refuses_success(self):
        """intent portfolio_write → system_hint 硬拒绝文案，非成功暗示。"""
        from app.core.intent_router import classify_intent, INTENT_PORTFOLIO_WRITE
        r = classify_intent("帮我把茅台加进持仓并下单买入")
        assert r.intent == INTENT_PORTFOLIO_WRITE
        hint = (r.system_hint or "").lower()
        assert "拒绝" in r.system_hint or "不得" in r.system_hint or "block" in hint or "不可" in r.system_hint
        # 不得出现鼓励写仓的假成功措辞
        for bad in ("已成功下单", "已写入持仓", "order placed", "portfolio updated"):
            assert bad not in (r.system_hint or "")



class TestMarketSectorFacadeG9:
    """G9：get_market_overview_brief / get_sector_snapshot 薄 facade。"""

    def test_registered_in_executors(self):
        from app.core.tools import TOOL_EXECUTORS, READ_ONLY_TOOL_NAMES

        assert "get_market_overview_brief" in TOOL_EXECUTORS
        assert "get_sector_snapshot" in TOOL_EXECUTORS
        assert "get_market_overview_brief" in READ_ONLY_TOOL_NAMES
        assert "get_sector_snapshot" in READ_ONLY_TOOL_NAMES
        assert is_write_tool_name("get_market_overview_brief") is False
        assert is_write_tool_name("get_sector_snapshot") is False

    def test_offline_market_overview_no_fake_prices(self, monkeypatch):
        """DISABLE_NETWORK=1：indices=[] + source=offline_disabled，正文无假指数点位。"""
        monkeypatch.setenv("DISABLE_NETWORK", "1")
        raw = execute_tool("get_market_overview_brief", {})
        data = json.loads(raw) if isinstance(raw, str) else raw
        assert isinstance(data, dict)
        assert data.get("indices") == []
        assert data.get("source") == "offline_disabled"
        assert data.get("count") == 0
        # 不得出现像真价的数字字段顶层
        for k in ("price", "close", "change_pct", "上证", "point"):
            assert k not in data
        note = str(data.get("note") or "")
        assert "编造" in note or "DISABLE_NETWORK" in note

    def test_offline_sector_snapshot_empty(self, monkeypatch):
        monkeypatch.setenv("DISABLE_NETWORK", "1")
        raw = execute_tool(
            "get_sector_snapshot",
            {"industry": "白酒", "symbol": "即时"},
        )
        data = json.loads(raw) if isinstance(raw, str) else raw
        assert data.get("data") == []
        assert data.get("source") == "offline_disabled"
        assert data.get("count") == 0
        assert data.get("industry") in ("白酒", None) or data.get("industry") == "白酒"

    def test_market_overview_upstream_error_returns_empty(self, monkeypatch):
        """上游抛错 → source=error / indices=[]，不抛、不造假。"""
        monkeypatch.delenv("DISABLE_NETWORK", raising=False)
        monkeypatch.setenv("DISABLE_NETWORK", "0")

        def _boom():
            raise RuntimeError("upstream down")

        # patch web_server 取数函数
        import app.web.web_server as ws

        monkeypatch.setattr(ws, "_fetch_market_indices_data", _boom)
        # force not offline
        monkeypatch.setenv("DISABLE_NETWORK", "")
        raw = execute_tool("get_market_overview_brief", {})
        data = json.loads(raw) if isinstance(raw, str) else raw
        assert data.get("indices") == []
        assert data.get("source") in ("error", "offline_disabled")
