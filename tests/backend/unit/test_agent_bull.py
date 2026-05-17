"""
Input: 多空研究员 Agent 单元测试 - BullResearcherAgent
Output: 验证 bull_case 快乐路径 / LLM 失败 fallback / AI 客户端缺失 fallback
Pos: tests/backend/unit/test_agent_bull.py - BE-02c2 子任务

[BE-02c2 2026-05-17 +08:00]
- 快乐路径：mock 上游 4 个 report → 返回 bull_case
- LLM 失败 (error path) → fallback 字符串
- AI 客户端缺失 → fallback 字符串
- 上下文构建：技术/基本/情绪/资金面 report 全注入 prompt
"""
from __future__ import annotations

# --- 隔离 langchain @tool 装饰器在 coverage 模式下的 pydantic 冲突 -----------
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

from app.agents.bull_researcher import BullResearcherAgent


def _make_state():
    return {
        "stock_code": "600519",
        "market_type": "A",
        "technical_report": {"score": 78, "trend": "上涨", "recommendation": "买入"},
        "fundamental_report": {"score": 70, "valuation": "合理"},
        "sentiment_report": {"score": 65, "summary": "情绪积极"},
        "capital_flow_report": {"score": 60, "trend": "净流入"},
    }


# ---------------------------------------------------------------- 1. 快乐路径
def test_bull_happy_path():
    """mock chat_completion 返回看多文本 -> state['bull_case'] 含该文本"""
    state = _make_state()
    fake_client = MagicMock(name="ai_client")
    fake_resp = MagicMock(name="resp")
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion",
               return_value=(fake_resp, None)), \
         patch("app.core.ai_client.get_completion_content",
               return_value="看多分析：上涨趋势明确，建议买入。"):
        out = BullResearcherAgent.analyze(state)

    assert "bull_case" in out
    assert "看多" in out["bull_case"] or "上涨" in out["bull_case"]
    assert out["progress"] == 50.0
    assert any(log.get("agent") == "看多研究员" and log.get("status") == "success"
               for log in out["execution_log"])


# ---------------------------------------------------------------- 2. LLM 失败
def test_bull_llm_error_fallback():
    """chat_completion 返回 error -> fallback 字符串"""
    state = _make_state()
    fake_client = MagicMock(name="ai_client")
    with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion",
               return_value=(None, "LLM 调用超时")):
        out = BullResearcherAgent.analyze(state)

    assert "bull_case" in out
    assert isinstance(out["bull_case"], str)
    assert "出错" in out["bull_case"] or "LLM 调用超时" in out["bull_case"]
    assert any(log.get("status") == "failed" for log in out["execution_log"])


# ---------------------------------------------------------------- 3. AI 客户端缺失
def test_bull_no_ai_client_fallback():
    """get_ai_client 返回 None -> fallback"""
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=None):
        out = BullResearcherAgent.analyze(state)

    assert "bull_case" in out
    assert isinstance(out["bull_case"], str)
    assert "AI" in out["bull_case"]
    assert any(log.get("status") == "failed" for log in out["execution_log"])


# ---------------------------------------------------------------- 4. 上下文注入
def test_bull_context_injects_upstream_reports():
    """4 份上游 report 全部需要进入 LLM prompt"""
    state = _make_state()
    captured = {}

    def _spy_chat(client, messages, **kwargs):
        captured["messages"] = messages
        return (MagicMock(), None)

    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion", side_effect=_spy_chat), \
         patch("app.core.ai_client.get_completion_content", return_value="ok"):
        BullResearcherAgent.analyze(state)

    assert "messages" in captured
    prompt_text = captured["messages"][0]["content"]
    # 4 个 report 至少要有标识词出现
    assert "技术" in prompt_text
    assert "基本面" in prompt_text or "基本" in prompt_text
    assert "舆情" in prompt_text or "情绪" in prompt_text
    assert "资金" in prompt_text
