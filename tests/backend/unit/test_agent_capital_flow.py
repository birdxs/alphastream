# -*- coding: utf-8 -*-
# Input  : CapitalFlowAnalystAgent.analyze + mock LLM/adapter/CapitalFlowAnalyzer
# Output : pytest 用例 BE-02c1 资金流向 Agent 单元测试
# Pos    : tests/backend/unit/test_agent_capital_flow.py
"""BE-02c1 CapitalFlowAnalystAgent 测试

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

from app.agents.capital_flow_analyst import CapitalFlowAnalystAgent


# ---------------------------------------------------------------- 1. 快乐路径
def test_capital_flow_happy_path(minimal_state):
    ai_json = (
        '{"score": 72, "main_force_trend": "净流入", "main_force_amount": "1.5亿", '
        '"big_order_ratio": 36.5, "retail_behavior": "跟进", '
        '"capital_intention": "建仓", "consecutive_days": 3, '
        '"flow_data": {"today_net_inflow": 15000, "5day_net_inflow": 50000, '
        '"10day_net_inflow": -2000}, "recommendation": "买入", '
        '"ai_commentary": "主力强势流入"}'
    )
    fake_client = MagicMock(name="ai_client")
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_with_tools",
               return_value=(ai_json, [{"tool": "get_flow", "args": {}}], None)):
        out = CapitalFlowAnalystAgent.analyze(minimal_state)

    assert "capital_flow_report" in out
    report = out["capital_flow_report"]
    assert report["score"] == 72
    assert report["main_force_trend"] == "净流入"
    assert report["recommendation"] == "买入"
    assert isinstance(report.get("flow_data"), dict)
    assert report["flow_data"]["today_net_inflow"] == 15000
    assert report.get("tool_calls") and len(report["tool_calls"]) == 1
    log = out.get("execution_log", [])
    assert any(e.get("mode") == "ai_agent" and e.get("status") == "success" for e in log)


# ---------------------------------------------------------------- 2. 数据源失败降级
def test_capital_flow_fallback_when_adapter_fails(minimal_state):
    fake_analyzer = MagicMock(name="CFAnalyzer")
    fake_analyzer.get_individual_fund_flow.return_value = {"today_net_inflow": 1000}
    fake_analyzer.calculate_capital_flow_score.return_value = {"total_score": 55}

    with patch("app.core.ai_client.get_ai_client", return_value=None), \
         patch("app.agents.capital_flow_analyst._registry_fetch",
               side_effect=RuntimeError("efinance down")), \
         patch("app.analysis.capital_flow_analyzer.CapitalFlowAnalyzer",
               return_value=fake_analyzer):
        out = CapitalFlowAnalystAgent.analyze(minimal_state)

    report = out["capital_flow_report"]
    assert ("score" in report) or ("error" in report)


def test_capital_flow_fallback_clean_path(minimal_state):
    fake_analyzer = MagicMock(name="CFAnalyzer")
    fake_analyzer.get_individual_fund_flow.return_value = {"today_net_inflow": 5000}
    fake_analyzer.calculate_capital_flow_score.return_value = {"total_score": 60}

    with patch("app.core.ai_client.get_ai_client", return_value=None), \
         patch("app.agents.capital_flow_analyst._registry_fetch", return_value=None), \
         patch("app.analysis.capital_flow_analyzer.CapitalFlowAnalyzer",
               return_value=fake_analyzer):
        out = CapitalFlowAnalystAgent.analyze(minimal_state)

    report = out["capital_flow_report"]
    assert "flow_data" in report
    assert report["score"]["total_score"] == 60
    log = out.get("execution_log", [])
    assert any(e.get("mode") == "fallback" for e in log)


# ---------------------------------------------------------------- 3. LLM 失败降级
def test_capital_flow_fallback_on_llm_error(minimal_state):
    fake_client = MagicMock(name="ai_client")
    fake_analyzer = MagicMock(name="CFAnalyzer")
    fake_analyzer.get_individual_fund_flow.return_value = {}
    fake_analyzer.calculate_capital_flow_score.return_value = {"total_score": 45}

    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_with_tools",
               side_effect=RuntimeError("LLM down")), \
         patch("app.agents.capital_flow_analyst._registry_fetch", return_value=None), \
         patch("app.analysis.capital_flow_analyzer.CapitalFlowAnalyzer",
               return_value=fake_analyzer):
        out = CapitalFlowAnalystAgent.analyze(minimal_state)

    report = out["capital_flow_report"]
    assert report.get("score") == {"total_score": 45}


def test_capital_flow_llm_returns_error(minimal_state):
    fake_client = MagicMock(name="ai_client")
    fake_analyzer = MagicMock(name="CFAnalyzer")
    fake_analyzer.get_individual_fund_flow.return_value = {}
    fake_analyzer.calculate_capital_flow_score.return_value = {"total_score": 50}

    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_with_tools",
               return_value=(None, [], "api error")), \
         patch("app.agents.capital_flow_analyst._registry_fetch", return_value=None), \
         patch("app.analysis.capital_flow_analyzer.CapitalFlowAnalyzer",
               return_value=fake_analyzer):
        out = CapitalFlowAnalystAgent.analyze(minimal_state)

    report = out["capital_flow_report"]
    assert report.get("score") == {"total_score": 50}


# ---------------------------------------------------------------- 4. 事件发布
def test_capital_flow_fallback_no_token_events(minimal_state, mock_event_bus):
    mock_event_bus.clear()
    fake_analyzer = MagicMock(name="CFAnalyzer")
    fake_analyzer.get_individual_fund_flow.return_value = {}
    fake_analyzer.calculate_capital_flow_score.return_value = {"total_score": 50}

    with patch("app.core.ai_client.get_ai_client", return_value=None), \
         patch("app.agents.capital_flow_analyst._registry_fetch", return_value=None), \
         patch("app.analysis.capital_flow_analyzer.CapitalFlowAnalyzer",
               return_value=fake_analyzer):
        CapitalFlowAnalystAgent.analyze(minimal_state)

    token_evts = [r for r in mock_event_bus.events if "token" in r[0].lower()]
    assert token_evts == []
