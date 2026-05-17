# -*- coding: utf-8 -*-
# Input  : LynchAgent.analyze mock LLM
# Output : pytest 用例，覆盖快乐路径 + AI 失败降级
# Pos    : tests/backend/unit/test_investors_lynch.py - BE-02b 林奇人格 Agent 单元测试
"""BE-02b 彼得林奇 Agent 测试"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.agents.investors.lynch import LynchAgent


def test_lynch_happy_path_buy(minimal_state):
    ai_json = (
        '{"recommendation": "BUY", '
        '"confidence": "高", '
        '"reasoning": "PEG=0.7 显著低于 1，业绩稳健成长", '
        '"category": "快速成长型", '
        '"peg_ratio": 0.7}'
    )
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=ai_json):
        out = LynchAgent.analyze(minimal_state)

    assert "investor_lynch" in out
    view = out["investor_lynch"]
    assert view["recommendation"] == "BUY"
    assert "PEG" in view["reasoning"] or "成长" in view["reasoning"]
    assert 0.0 <= view["confidence"] <= 1.0


def test_lynch_fallback_on_llm_error(minimal_state):
    fake_client = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion",
               side_effect=RuntimeError("LLM unavailable")):
        out = LynchAgent.analyze(minimal_state)

    view = out["investor_lynch"]
    assert view["recommendation"] == "HOLD"
    assert "error" in view
    log = out.get("execution_log", [])
    assert any(e.get("status") == "failed" for e in log)


def test_lynch_no_ai_client(minimal_state):
    with patch("app.core.ai_client.get_ai_client", return_value=None):
        out = LynchAgent.analyze(minimal_state)
    assert out["investor_lynch"]["recommendation"] == "HOLD"


def test_lynch_full_state_with_markdown_json(minimal_state):
    state = dict(minimal_state)
    state["technical_report"] = {"ai_commentary": "突破均线"}
    state["fundamental_report"] = {"growth": 0.3, "PEG": 0.7}
    state["capital_flow_report"] = "净流入显著"
    state["sentiment_report"] = {"ai_commentary": "市场关注度上升"}
    content = '前言```json\n{"recommendation":"BUY","confidence":"中","reasoning":"成长股"}\n```'
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=content):
        out = LynchAgent.analyze(state)
    assert out["investor_lynch"]["recommendation"] == "BUY"


def test_lynch_empty_content(minimal_state):
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=""):
        out = LynchAgent.analyze(minimal_state)
    assert out["investor_lynch"]["recommendation"] == "HOLD"
