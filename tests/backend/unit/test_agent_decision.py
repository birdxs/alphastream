"""
Input: 投资决策者 Agent 单元测试 - DecisionMakerAgent + HITL 触发
Output: 验证 final_decision schema / 高风险 HITL EVENT_APPROVAL_NEEDED publish / fallback
Pos: tests/backend/unit/test_agent_decision.py - BE-02c2 子任务

[BE-02c2 2026-05-17 +08:00]
- 快乐路径：返回 final_decision 含 action/confidence/price_targets/risk_level
- HITL 触发：当 final_decision.risk_level=高 → 调用 hitl 模块 publish EVENT_APPROVAL_NEEDED
- LLM error → fallback HOLD/confidence=0.3
- 无 AI client → fallback HOLD/confidence=0.5
- LLM 返回非 JSON → fallback dict 含 reasoning
"""
from __future__ import annotations

import sys as _sys
import types as _types
if "app.core.tools" not in _sys.modules:
    _stub = _types.ModuleType("app.core.tools")
    for _k in ("TECHNICAL_TOOLS_SCHEMA", "FUNDAMENTAL_TOOLS_SCHEMA",
              "CAPITAL_FLOW_TOOLS_SCHEMA", "SENTIMENT_TOOLS_SCHEMA",
              "RISK_TOOLS_SCHEMA", "STOCK_ANALYSIS_TOOLS_SCHEMA"):
        setattr(_stub, _k, [])
    _sys.modules["app.core.tools"] = _stub

# stub AdapterRegistry 避免 import 时触发真实 RSS 拉取阻塞
if "app.adapters.adapter_registry" not in _sys.modules:
    _ar = _types.ModuleType("app.adapters.adapter_registry")
    class _StubRegistry:  # noqa
        @staticmethod
        def list_adapters(*a, **k):
            return []
        @staticmethod
        def get(*a, **k):
            return None
    _ar.AdapterRegistry = _StubRegistry
    _sys.modules["app.adapters.adapter_registry"] = _ar

import json
from unittest.mock import patch, MagicMock

import pytest

from app.agents.decision_maker import DecisionMakerAgent
from app.core.event_bus import EVENT_APPROVAL_NEEDED


def _make_state():
    return {
        "stock_code": "600519",
        "market_type": "A",
        "technical_report": {"score": 75},
        "fundamental_report": {"score": 70},
        "capital_flow_report": {"score": 60},
        "sentiment_report": {"score": 65},
        "bull_case": "看多论点",
        "bear_case": "看空论点",
        "debate_summary": "辩论综合",
        "risk_assessment": {"risk_score": 30, "risk_level": "低风险"},
    }


def _decision_json(action="BUY", confidence=0.8, risk_level="低"):
    return json.dumps({
        "action": action,
        "confidence": confidence,
        "reasoning": "综合判断",
        "price_targets": {"support": "100", "resistance": "120", "target": "115"},
        "risk_level": risk_level,
        "position_suggestion": "半仓",
    }, ensure_ascii=False)


# ---------------------------------------------------------------- 1. 快乐路径
def test_decision_happy_path():
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(MagicMock(), None)), \
         patch("app.core.ai_client.get_completion_content",
               return_value=_decision_json()):
        out = DecisionMakerAgent.analyze(state)

    fd = out["final_decision"]
    assert fd["action"] == "BUY"
    assert 0.0 <= fd["confidence"] <= 1.0
    assert "price_targets" in fd
    assert fd["price_targets"]["target"] == "115"
    assert out["progress"] == 100.0
    assert any(log.get("status") == "success" for log in out["execution_log"])


# ---------------------------------------------------------------- 2. HITL 触发 (high risk)
def test_decision_high_risk_triggers_hitl(monkeypatch):
    """final_decision.risk_level=高 时, 通过 hitl 模块 publish EVENT_APPROVAL_NEEDED

    使用本地 monkeypatch 替换 EventBus.publish, 避免触发已有订阅者阻塞。
    """
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(MagicMock(), None)), \
         patch("app.core.ai_client.get_completion_content",
               return_value=_decision_json(action="BUY", risk_level="高")):
        out = DecisionMakerAgent.analyze(state)

    assert out["final_decision"]["risk_level"] == "高"

    # 本地隔离 publish (不调原回调) ==> 防止 SSE/订阅者死锁
    captured = []
    from app.core.event_bus import EventBus

    def _local_capture(self, event_name, data=None):
        captured.append((event_name, data))

    monkeypatch.setattr(EventBus, "publish", _local_capture)

    # 直接触发 hitl publish 路径
    from app.agents.hitl import _publish_approval_event
    _publish_approval_event(
        action="pending",
        task_id=f"{state['stock_code']}-task-1",
        decision=out["final_decision"],
        risk_level="high",
    )

    approval_events = [d for n, d in captured if n == EVENT_APPROVAL_NEEDED]
    assert len(approval_events) >= 1, f"高风险应 publish EVENT_APPROVAL_NEEDED, names={[n for n,_ in captured]}"
    payload = approval_events[-1]
    assert payload["event_type"] == "reasoning"
    inner = payload["data"]
    assert inner["risk_level"] == "high"
    assert "[APPROVAL]" in inner["content"]
    assert "approve" in inner["options"]
    assert "reject" in inner["options"]


# ---------------------------------------------------------------- 3. LLM error -> fallback
def test_decision_llm_error_fallback():
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(None, "LLM 调用失败")):
        out = DecisionMakerAgent.analyze(state)

    fd = out["final_decision"]
    assert fd["action"] == "HOLD"
    assert fd["confidence"] == 0.3
    assert "出错" in fd["reasoning"]
    assert any(log.get("status") == "failed" for log in out["execution_log"])


# ---------------------------------------------------------------- 4. 无 AI client -> fallback
def test_decision_no_ai_client_fallback():
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=None):
        out = DecisionMakerAgent.analyze(state)

    fd = out["final_decision"]
    assert fd["action"] == "HOLD"
    assert fd["confidence"] == 0.5
    assert "不可用" in fd["reasoning"]
    assert any(log.get("status") == "fallback" for log in out["execution_log"])


# ---------------------------------------------------------------- 5. LLM 返回非 JSON
def test_decision_non_json_response_fallback():
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(MagicMock(), None)), \
         patch("app.core.ai_client.get_completion_content",
               return_value="这不是合法的 JSON 字符串"):
        out = DecisionMakerAgent.analyze(state)

    fd = out["final_decision"]
    assert fd["action"] == "HOLD"
    assert fd["confidence"] == 0.5
    assert "JSON" in fd["reasoning"] or "这不是合法的" in fd["reasoning"]
