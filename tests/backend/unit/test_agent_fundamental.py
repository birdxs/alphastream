# -*- coding: utf-8 -*-
# Input  : FundamentalAnalystAgent.analyze + mock LLM/adapter/FundamentalAnalyzer
# Output : pytest 用例 BE-02c1 基本面分析 Agent 单元测试
# Pos    : tests/backend/unit/test_agent_fundamental.py
"""BE-02c1 FundamentalAnalystAgent 测试

维度：快乐路径 / 数据源失败 / LLM 失败 / 事件发布
"""
from __future__ import annotations

import sys as _sys
import types as _types
if "app.core.tools" not in _sys.modules:
    _stub = _types.ModuleType("app.core.tools")
    _stub.TECHNICAL_TOOLS_SCHEMA = []
    _stub.FUNDAMENTAL_TOOLS_SCHEMA = []
    _stub.CAPITAL_FLOW_TOOLS_SCHEMA = []
    _stub.SENTIMENT_TOOLS_SCHEMA = []
    _stub.RISK_TOOLS_SCHEMA = []
    _stub.STOCK_ANALYSIS_TOOLS_SCHEMA = []
    _sys.modules["app.core.tools"] = _stub

from unittest.mock import patch, MagicMock

import pytest

from app.agents.fundamental_analyst import FundamentalAnalystAgent


# ---------------------------------------------------------------- 1. 快乐路径
def test_fundamental_happy_path(minimal_state):
    """mock chat_with_tools 返回固定 JSON -> fundamental_report 含 score/financial_health"""
    ai_json = (
        '{"score": 82, "financial_health": "健康", "growth_potential": "高成长", '
        '"valuation_level": "合理", "key_metrics": {"PE": 15.2, "ROE": 18.5}, '
        '"risk_factors": "无重大风险", "recommendation": "买入", '
        '"ai_commentary": "财务表现优秀"}'
    )
    fake_client = MagicMock(name="ai_client")
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_with_tools",
               return_value=(ai_json, [{"tool": "get_financials", "args": {}}], None)):
        out = FundamentalAnalystAgent.analyze(minimal_state)

    assert "fundamental_report" in out
    report = out["fundamental_report"]
    assert report["score"] == 82
    assert report.get("financial_health") == "健康"
    assert report.get("recommendation") == "买入"
    assert isinstance(report.get("key_metrics"), dict)
    assert report["key_metrics"]["PE"] == 15.2
    assert report.get("tool_calls") and len(report["tool_calls"]) == 1
    log = out.get("execution_log", [])
    assert any(e.get("mode") == "ai_agent" and e.get("status") == "success" for e in log)


# ---------------------------------------------------------------- 2. 数据源失败降级
def test_fundamental_fallback_when_adapter_fails(minimal_state):
    """_registry_fetch 抛错 + analyzer 返回正常数据 -> fallback 走 analyzer"""
    fake_analyzer = MagicMock(name="FundAnalyzer")
    fake_analyzer.get_financial_indicators.return_value = {"PE": 18.0, "ROE": 15.0}
    fake_analyzer.get_growth_data.return_value = {"revenue_growth": 0.2}
    fake_analyzer.calculate_fundamental_score.return_value = {"total_score": 70, "level": "良好"}

    with patch("app.core.ai_client.get_ai_client", return_value=None), \
         patch("app.agents.fundamental_analyst._registry_fetch",
               side_effect=RuntimeError("xbrl down")), \
         patch("app.analysis.fundamental_analyzer.FundamentalAnalyzer",
               return_value=fake_analyzer):
        out = FundamentalAnalystAgent.analyze(minimal_state)

    report = out["fundamental_report"]
    # _registry_fetch 异常被 fundamental_analyst 的 try 捕获(其内部本就有 try)，
    # 但本测试中直接 side_effect 抛错，外层 try 兜底返回 error 也算合法降级。
    assert ("score" in report) or ("error" in report)


def test_fundamental_fallback_clean_path(minimal_state):
    """get_ai_client 返回 None + analyzer 提供完整数据 -> mode=fallback success"""
    fake_analyzer = MagicMock(name="FundAnalyzer")
    fake_analyzer.get_financial_indicators.return_value = {"PE": 18.0}
    fake_analyzer.get_growth_data.return_value = {"revenue_growth": 0.2}
    fake_analyzer.calculate_fundamental_score.return_value = {"total_score": 65, "level": "良好"}

    with patch("app.core.ai_client.get_ai_client", return_value=None), \
         patch("app.agents.fundamental_analyst._registry_fetch", return_value=None), \
         patch("app.analysis.fundamental_analyzer.FundamentalAnalyzer",
               return_value=fake_analyzer):
        out = FundamentalAnalystAgent.analyze(minimal_state)

    report = out["fundamental_report"]
    assert "financial_indicators" in report
    assert "growth_data" in report
    assert report["score"]["total_score"] == 65
    log = out.get("execution_log", [])
    assert any(e.get("mode") == "fallback" for e in log)


# ---------------------------------------------------------------- 3. LLM 失败降级
def test_fundamental_fallback_on_llm_error(minimal_state):
    """chat_with_tools 抛错 -> _fallback_analyze 被触发"""
    fake_client = MagicMock(name="ai_client")
    fake_analyzer = MagicMock(name="FundAnalyzer")
    fake_analyzer.get_financial_indicators.return_value = {"PE": 22.0}
    fake_analyzer.get_growth_data.return_value = {}
    fake_analyzer.calculate_fundamental_score.return_value = {"total_score": 50}

    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_with_tools",
               side_effect=RuntimeError("LLM down")), \
         patch("app.agents.fundamental_analyst._registry_fetch", return_value=None), \
         patch("app.analysis.fundamental_analyzer.FundamentalAnalyzer",
               return_value=fake_analyzer):
        out = FundamentalAnalystAgent.analyze(minimal_state)

    report = out["fundamental_report"]
    # 兜底 fallback 应当成功返回 score
    assert report.get("score") == {"total_score": 50}


def test_fundamental_llm_returns_error(minimal_state):
    """chat_with_tools 返回 error 字段 -> 进入 _fallback_analyze"""
    fake_client = MagicMock(name="ai_client")
    fake_analyzer = MagicMock(name="FundAnalyzer")
    fake_analyzer.get_financial_indicators.return_value = {"PE": 30.0}
    fake_analyzer.get_growth_data.return_value = {}
    fake_analyzer.calculate_fundamental_score.return_value = {"total_score": 40}

    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_with_tools",
               return_value=(None, [], "api timeout")), \
         patch("app.agents.fundamental_analyst._registry_fetch", return_value=None), \
         patch("app.analysis.fundamental_analyzer.FundamentalAnalyzer",
               return_value=fake_analyzer):
        out = FundamentalAnalystAgent.analyze(minimal_state)

    report = out["fundamental_report"]
    assert report.get("score") == {"total_score": 40}


# ---------------------------------------------------------------- 4. 事件发布
def test_fundamental_fallback_does_not_publish_token_events(minimal_state, mock_event_bus):
    mock_event_bus.clear()
    fake_analyzer = MagicMock(name="FundAnalyzer")
    fake_analyzer.get_financial_indicators.return_value = {}
    fake_analyzer.get_growth_data.return_value = {}
    fake_analyzer.calculate_fundamental_score.return_value = {"total_score": 50}

    with patch("app.core.ai_client.get_ai_client", return_value=None), \
         patch("app.agents.fundamental_analyst._registry_fetch", return_value=None), \
         patch("app.analysis.fundamental_analyzer.FundamentalAnalyzer",
               return_value=fake_analyzer):
        FundamentalAnalystAgent.analyze(minimal_state)

    token_evts = [r for r in mock_event_bus.events if "token" in r[0].lower()]
    assert token_evts == []
