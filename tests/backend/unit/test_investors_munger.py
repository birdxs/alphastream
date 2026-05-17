# -*- coding: utf-8 -*-
# Input  : MungerAgent.analyze mock LLM
# Output : pytest 用例，覆盖快乐路径 + AI 失败降级
# Pos    : tests/backend/unit/test_investors_munger.py - BE-02b 芒格人格 Agent 单元测试
"""BE-02b 芒格 Agent 测试"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.agents.investors.munger import MungerAgent


def test_munger_happy_path_sell(minimal_state):
    ai_json = (
        '{"recommendation": "SELL", '
        '"confidence": "中", '
        '"reasoning": "心理偏差明显、安全边际不足、避免愚蠢决策", '
        '"mental_models_applied": ["逆向思维", "复利"], '
        '"red_flags": ["管理层激励错位"]}'
    )
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=ai_json):
        out = MungerAgent.analyze(minimal_state)

    assert "investor_munger" in out
    view = out["investor_munger"]
    assert view["recommendation"] == "SELL"
    assert "心理偏差" in view["reasoning"] or "逆向" in view.get("reasoning", "")
    assert 0.0 <= view["confidence"] <= 1.0


def test_munger_fallback_on_llm_error(minimal_state):
    fake_client = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion",
               side_effect=RuntimeError("LLM down")):
        out = MungerAgent.analyze(minimal_state)

    view = out["investor_munger"]
    assert view["recommendation"] == "HOLD"
    assert "error" in view
    log = out.get("execution_log", [])
    assert any(e.get("status") == "failed" for e in log)


def test_munger_no_ai_client(minimal_state):
    with patch("app.core.ai_client.get_ai_client", return_value=None):
        out = MungerAgent.analyze(minimal_state)
    assert out["investor_munger"]["recommendation"] == "HOLD"


def test_munger_full_state_and_json_block(minimal_state):
    state = dict(minimal_state)
    state["technical_report"] = {"trend": "up"}
    state["fundamental_report"] = {"ROIC": 0.15}
    state["capital_flow_report"] = {"net_inflow": 1e7}
    state["sentiment_report"] = {"ai_commentary": "正面"}
    content = '```json\n{"recommendation":"BUY","confidence":"高","reasoning":"OK"}\n```'
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=content):
        out = MungerAgent.analyze(state)
    assert out["investor_munger"]["recommendation"] == "BUY"


def test_munger_empty_content(minimal_state):
    fake_client = MagicMock()
    fake_resp = MagicMock()
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content", return_value=""):
        out = MungerAgent.analyze(minimal_state)
    assert out["investor_munger"]["recommendation"] == "HOLD"
