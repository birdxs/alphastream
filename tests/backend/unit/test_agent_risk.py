"""
Input: 风险管理官 Agent 单元测试 - RiskManagerAgent
Output: 验证 risk_score / EVENT_RISK_ALERT publish / fallback / 多档级 schema
Pos: tests/backend/unit/test_agent_risk.py - BE-02c2 子任务

[BE-02c2 2026-05-17 +08:00]
- 快乐路径：返回含 risk_score / risk_level 的 risk_assessment
- 高风险触发：mock LLM 返回 risk_level=高风险 → EVENT_RISK_ALERT 被 publish
- 中等风险不触发 alert（低噪音）
- 低风险不触发 alert
- LLM 失败 → fallback 路径
- 风险评级各档 schema 完整性
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

import json
from unittest.mock import patch, MagicMock

import pytest

from app.agents.risk_manager import RiskManagerAgent, _publish_risk_alert
from app.core.event_bus import EVENT_RISK_ALERT


def _make_state():
    return {
        "stock_code": "600519",
        "market_type": "A",
        "technical_report": {"score": 60, "trend": "震荡"},
        "fundamental_report": {"score": 55},
        "capital_flow_report": {"score": 50},
    }


def _llm_json(risk_score=35, risk_level="低风险", **extra):
    payload = {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "volatility_risk": "低",
        "trend_risk": "低",
        "reversal_risk": "低",
        "volume_risk": "低",
        "max_drawdown_risk": "低",
        "risk_factors": ["风险因素A", "风险因素B"],
        "stop_loss_suggestion": 95.0,
        "position_suggestion": "半仓",
        "recommendation": "持有",
        "ai_commentary": f"风险评估说明 (level={risk_level})",
    }
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------- 1. 快乐路径
def test_risk_happy_path(mock_event_bus):
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_with_tools",
               return_value=(_llm_json(risk_score=35, risk_level="低风险"), [], None)):
        out = RiskManagerAgent.analyze(state)

    assert "risk_assessment" in out
    ra = out["risk_assessment"]
    assert ra["risk_score"] == 35
    assert "低风险" in ra["risk_level"]
    assert out["progress"] == 70.0
    assert any(log.get("status") == "success" for log in out["execution_log"])


# ---------------------------------------------------------------- 2. 高风险 -> publish alert
def test_risk_high_publishes_alert(mock_event_bus):
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_with_tools",
               return_value=(_llm_json(risk_score=85, risk_level="高风险",
                                       risk_factors=["黑天鹅", "退市预警"]), [], None)):
        out = RiskManagerAgent.analyze(state)

    ra = out["risk_assessment"]
    assert ra["risk_score"] == 85
    # 断言 EVENT_RISK_ALERT 被 publish
    events = mock_event_bus.filter(EVENT_RISK_ALERT)
    assert len(events) >= 1, f"应至少 publish 1 次 EVENT_RISK_ALERT，实际事件: {mock_event_bus.names()}"
    payload = events[-1]
    inner = payload["data"]
    assert inner["level"] == "high"
    assert inner["stock_code"] == "600519"
    assert "[RISK_ALERT]" in inner["content"]


# ---------------------------------------------------------------- 3. 中高风险 -> medium alert
def test_risk_medium_high_publishes_medium_alert(mock_event_bus):
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_with_tools",
               return_value=(_llm_json(risk_score=65, risk_level="中高风险"), [], None)):
        RiskManagerAgent.analyze(state)

    events = mock_event_bus.filter(EVENT_RISK_ALERT)
    assert len(events) >= 1
    assert events[-1]["data"]["level"] == "medium"


# ---------------------------------------------------------------- 4. 低风险 不发 alert
def test_risk_low_no_alert(mock_event_bus):
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_with_tools",
               return_value=(_llm_json(risk_score=15, risk_level="低风险"), [], None)):
        RiskManagerAgent.analyze(state)

    events = mock_event_bus.filter(EVENT_RISK_ALERT)
    assert len(events) == 0


# ---------------------------------------------------------------- 5. LLM error -> fallback
def test_risk_llm_error_fallback(mock_event_bus, monkeypatch):
    """LLM error -> 走 _fallback_analyze; mock RiskMonitor 避免真实数据访问"""
    state = _make_state()
    fake_rm = MagicMock()
    fake_rm.analyze_stock_risk.return_value = {
        "risk_score": 25, "risk_level": "低风险", "ai_commentary": "fallback"
    }

    # 通过 monkeypatch.setitem 注入 sys.modules，确保测试结束后自动回滚
    risk_mod = _types.ModuleType("app.analysis.risk_monitor")
    risk_mod.RiskMonitor = MagicMock(return_value=fake_rm)
    sa_mod = _types.ModuleType("app.analysis.stock_analyzer")
    sa_mod.StockAnalyzer = MagicMock()
    monkeypatch.setitem(_sys.modules, "app.analysis.risk_monitor", risk_mod)
    monkeypatch.setitem(_sys.modules, "app.analysis.stock_analyzer", sa_mod)

    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_with_tools",
               return_value=("", [], "LLM 调用失败")):
        out = RiskManagerAgent.analyze(state)

    assert "risk_assessment" in out
    assert out["risk_assessment"]["risk_score"] == 25
    assert any(log.get("mode") == "fallback" for log in out["execution_log"])


# ---------------------------------------------------------------- 6. schema 完整性
def test_risk_schema_completeness(mock_event_bus):
    """parse 后必含 risk_score / risk_level / recommendation / ai_commentary"""
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_with_tools",
               return_value=(_llm_json(risk_score=50, risk_level="中等风险"), [], None)):
        out = RiskManagerAgent.analyze(state)

    ra = out["risk_assessment"]
    for k in ("risk_score", "risk_level", "recommendation", "ai_commentary"):
        assert k in ra, f"缺少字段 {k}"


# ---------------------------------------------------------------- 7. _publish_risk_alert 边界
def test_publish_risk_alert_isolated(mock_event_bus):
    """直接调用 _publish_risk_alert 测分级判断"""
    # 高 score
    _publish_risk_alert("600000", {"risk_level": "高风险", "risk_score": 90})
    high_events = mock_event_bus.filter(EVENT_RISK_ALERT)
    assert any(e["data"]["level"] == "high" for e in high_events)

    mock_event_bus.clear()
    # 中等 -> level=low
    _publish_risk_alert("600000", {"risk_level": "中等风险", "risk_score": 45})
    medium_events = mock_event_bus.filter(EVENT_RISK_ALERT)
    assert len(medium_events) >= 1
    assert medium_events[-1]["data"]["level"] == "low"

    mock_event_bus.clear()
    # 低风险不发
    _publish_risk_alert("600000", {"risk_level": "低风险", "risk_score": 10})
    assert len(mock_event_bus.filter(EVENT_RISK_ALERT)) == 0
