# -*- coding: utf-8 -*-
# Input  : DamodaranAgent.analyze mock LLM
# Output : pytest 用例，覆盖快乐路径 + AI 失败降级
# Pos    : tests/backend/unit/test_investors_damodaran.py - BE-02b 达摩达兰人格 Agent 单元测试
"""BE-02b 达摩达兰 Agent 测试"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.agents.investors.damodaran import DamodaranAgent


def test_damodaran_happy_path_buy(minimal_state):
    ai_json = (
        '{"recommendation": "BUY", '
        '"confidence": "高", '
        '"reasoning": "DCF 估值显著高于当前价 30%，故事可信", '
        '"dcf_value": 25.5, '
        '"current_price": 19.2, '
        '"narrative_score": 0.8}'
    )
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=ai_json):
        out = DamodaranAgent.analyze(minimal_state)

    assert "investor_damodaran" in out
    view = out["investor_damodaran"]
    assert view["recommendation"] == "BUY"
    assert "DCF" in view["reasoning"] or "估值" in view["reasoning"]
    assert 0.0 <= view["confidence"] <= 1.0


def test_damodaran_fallback_on_llm_error(minimal_state):
    fake_client = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion",
               side_effect=RuntimeError("LLM unavailable")):
        out = DamodaranAgent.analyze(minimal_state)

    view = out["investor_damodaran"]
    assert view["recommendation"] == "HOLD"
    assert "error" in view
    log = out.get("execution_log", [])
    assert any(e.get("status") == "failed" for e in log)


def test_damodaran_no_ai_client(minimal_state):
    with patch("app.core.ai_client.get_ai_client", return_value=None):
        out = DamodaranAgent.analyze(minimal_state)
    assert out["investor_damodaran"]["recommendation"] == "HOLD"


def test_damodaran_full_state_with_markdown_json(minimal_state):
    state = dict(minimal_state)
    state["technical_report"] = {"ai_commentary": "技术面健康"}
    state["fundamental_report"] = {"FCF": 1e9}
    state["capital_flow_report"] = {"ai_commentary": "资金流入"}
    state["sentiment_report"] = "舆情正面"
    content = 'analysis: ```json\n{"recommendation":"BUY","confidence":"高","reasoning":"DCF折现高"}\n```'
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=content):
        out = DamodaranAgent.analyze(state)
    assert out["investor_damodaran"]["recommendation"] == "BUY"


def test_damodaran_empty_content(minimal_state):
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=""):
        out = DamodaranAgent.analyze(minimal_state)
    assert out["investor_damodaran"]["recommendation"] == "HOLD"
