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
    INTENT_SINGLE_STOCK_DEEP,
    classify_intent,
)
from app.core.tools import (
    execute_tool,
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
