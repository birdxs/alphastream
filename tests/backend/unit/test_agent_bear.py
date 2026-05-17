"""
Input: 看空研究员 Agent 单元测试 - BearResearcherAgent
Output: 验证 bear_case 快乐路径 / LLM 失败 / R2 反驳式 prompt 注入
Pos: tests/backend/unit/test_agent_bear.py - BE-02c2 子任务

[BE-02c2 2026-05-17 +08:00]
- 快乐路径
- LLM 失败 fallback
- AI 客户端缺失 fallback
- R2 反驳式 prompt：state 含 bull_case 时 prompt 注入"看多观点（需质疑）"
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

from unittest.mock import patch, MagicMock

import pytest

from app.agents.bear_researcher import BearResearcherAgent


def _make_state(with_bull: bool = False):
    s = {
        "stock_code": "600519",
        "market_type": "A",
        "technical_report": {"score": 78},
        "fundamental_report": {"score": 70},
        "sentiment_report": {"score": 65},
        "capital_flow_report": {"score": 60},
    }
    if with_bull:
        s["bull_case"] = "看多分析：核心买入逻辑是估值低 + 技术面突破。"
    return s


# ---------------------------------------------------------------- 1. 快乐路径
def test_bear_happy_path():
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(MagicMock(), None)), \
         patch("app.core.ai_client.get_completion_content",
               return_value="看空分析：估值偏高，下跌风险显著。"):
        out = BearResearcherAgent.analyze(state)

    assert "bear_case" in out
    assert isinstance(out["bear_case"], str)
    assert "看空" in out["bear_case"] or "下跌" in out["bear_case"]


# ---------------------------------------------------------------- 2. LLM 失败
def test_bear_llm_error_fallback():
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(None, "服务不可用")):
        out = BearResearcherAgent.analyze(state)

    assert "bear_case" in out
    assert isinstance(out["bear_case"], str)
    assert "服务不可用" in out["bear_case"] or "失败" in out["bear_case"] \
           or "出错" in out["bear_case"]


# ---------------------------------------------------------------- 3. 无 AI 客户端
def test_bear_no_ai_client_fallback():
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=None):
        out = BearResearcherAgent.analyze(state)

    assert "bear_case" in out
    assert isinstance(out["bear_case"], str)


# ---------------------------------------------------------------- 4. R2 反驳式 prompt
def test_bear_rebuttal_prompt_when_bull_case_present():
    """state 含 bull_case 时, bear prompt 必须包含"看多观点（需质疑）" section"""
    state = _make_state(with_bull=True)
    captured = {}

    def _spy_chat(client, messages, **kwargs):
        captured["messages"] = messages
        return (MagicMock(), None)

    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion", side_effect=_spy_chat), \
         patch("app.core.ai_client.get_completion_content",
               return_value="看空反驳分析"):
        BearResearcherAgent.analyze(state)

    assert "messages" in captured
    prompt_text = captured["messages"][0]["content"]
    # R2 反驳式 prompt 关键字：看多观点 + 质疑
    assert "看多观点" in prompt_text
    assert "质疑" in prompt_text or "反驳" in prompt_text
    # bull_case 内容被注入
    assert "估值低" in prompt_text or "技术面突破" in prompt_text


# ---------------------------------------------------------------- 5. 无 bull_case 时 prompt 不含反驳片段
def test_bear_no_bull_case_no_rebuttal_section():
    state = _make_state(with_bull=False)
    captured = {}

    def _spy_chat(client, messages, **kwargs):
        captured["messages"] = messages
        return (MagicMock(), None)

    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion", side_effect=_spy_chat), \
         patch("app.core.ai_client.get_completion_content", return_value="x"):
        BearResearcherAgent.analyze(state)

    prompt_text = captured["messages"][0]["content"]
    # 没有 bull_case 时不会出现"看多观点（需质疑）"段落标题
    assert "看多观点（需质疑）" not in prompt_text
