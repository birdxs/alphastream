# -*- coding: utf-8 -*-
# Input  : BuffettAgent.analyze mock LLM 场景
# Output : pytest 用例，覆盖快乐路径 + AI 失败降级
# Pos    : tests/backend/unit/test_investors_buffett.py - BE-02b 巴菲特人格 Agent 单元测试
"""BE-02b 巴菲特 Agent 测试

1. 快乐路径：合法 state + mock LLM 返回 BUY -> view 含 action + reasoning
2. AI 失败降级：mock LLM 抛错 -> _error_result 兜底 -> HOLD
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.agents.investors.buffett import BuffettAgent


# -------- 快乐路径 ------------------------------------------------------------
def test_buffett_happy_path_buy(minimal_state):
    """LLM 返回 BUY 的合法 JSON -> 返回 view 包含 recommendation + reasoning"""
    ai_json = (
        '{"recommendation": "BUY", '
        '"confidence": "高", '
        '"reasoning": "护城河宽广、ROE 持续 20%+、估值合理", '
        '"key_metrics": {"ROE": "22%", "PE": "12"}, '
        '"moat_analysis": "品牌+网络效应", '
        '"warning_signs": []}'
    )
    fake_client = MagicMock(name="client")
    fake_resp = MagicMock(name="resp")

    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=ai_json):
        out = BuffettAgent.analyze(minimal_state)

    assert "investor_buffett" in out
    view = out["investor_buffett"]
    assert view["recommendation"] == "BUY"
    assert view["analyst"] == "巴菲特风格"
    assert "护城河" in view["reasoning"]
    assert 0.0 <= view["confidence"] <= 1.0
    # execution_log 标记 success
    log = out.get("execution_log", [])
    assert any(e.get("status") == "success" for e in log)


# -------- AI 失败降级 ---------------------------------------------------------
def test_buffett_fallback_on_llm_error(minimal_state):
    """LLM 抛错 -> _error_result -> HOLD"""
    fake_client = MagicMock(name="client")
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion",
               side_effect=RuntimeError("LLM down")):
        out = BuffettAgent.analyze(minimal_state)

    view = out["investor_buffett"]
    assert view["recommendation"] == "HOLD"
    assert view["confidence"] <= 0.2
    assert "error" in view
    log = out.get("execution_log", [])
    assert any(e.get("status") == "failed" for e in log)


def test_buffett_fallback_when_ai_client_missing(minimal_state):
    """get_ai_client 返回 None -> _error_result -> HOLD"""
    with patch("app.core.ai_client.get_ai_client", return_value=None):
        out = BuffettAgent.analyze(minimal_state)

    view = out["investor_buffett"]
    assert view["recommendation"] == "HOLD"
    assert "AI客户端不可用" in view.get("reasoning", "") or "error" in view


def test_buffett_with_full_state_triggers_report_compile(minimal_state):
    """填充完整 state -> 触发 _compile_reports + _format_report 路径"""
    state = dict(minimal_state)
    state["technical_report"] = {"ai_commentary": "趋势向上"}
    state["fundamental_report"] = {"PE": 12, "ROE": 0.22, "flow_data": "skip"}
    state["capital_flow_report"] = {"net_inflow": 1e8}
    state["sentiment_report"] = "舆情中性"
    ai_json = '{"recommendation":"BUY","confidence":"高","reasoning":"r"}'
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=ai_json):
        out = BuffettAgent.analyze(state)
    assert out["investor_buffett"]["recommendation"] == "BUY"


def test_buffett_parses_json_with_extra_text(minimal_state):
    """LLM 返回 markdown 围栏 + JSON -> _parse_json_response 提取 JSON 块"""
    content = '这是分析:```json\n{"recommendation":"SELL","confidence":"中","reasoning":"r"}\n```后记'
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=content):
        out = BuffettAgent.analyze(minimal_state)
    assert out["investor_buffett"]["recommendation"] == "SELL"


def test_buffett_empty_ai_content_falls_back(minimal_state):
    """LLM 返回空字符串 -> _error_result"""
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=""):
        out = BuffettAgent.analyze(minimal_state)
    assert out["investor_buffett"]["recommendation"] == "HOLD"
