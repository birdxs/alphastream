# -*- coding: utf-8 -*-
# Input  : StockQA + mock analyzer/chat_completion/search
# Output : pytest 用例 BE-06a 智能问答单元测试
# Pos    : tests/backend/unit/test_analysis_qa.py
"""BE-06a StockQA 单元测试

覆盖：
1. 未配置 API key → 直接返回 error
2. 快乐路径：LLM 返回内容（无工具调用）
3. LLM 调用 search 工具 → 二阶段返回
4. LLM 调用失败（chat_completion 返回 err）
5. clear_conversation 各分支
6. get_conversation_history
7. search_stock_news 兜底（unified 抛错 + 无 key）
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest


# -- mock analyzer ------------------------------------------------------------
def _build_indicator_df(n=120):
    rng = np.random.default_rng(11)
    prices = 10 + np.cumsum(rng.normal(0, 0.05, n))
    return pd.DataFrame({
        "close": prices,
        "MA5": prices, "MA20": prices, "MA60": prices,
        "RSI": 55.0, "MACD": 0.1, "Signal": 0.0,
        "BB_upper": prices * 1.05, "BB_middle": prices, "BB_lower": prices * 0.95,
        "Volatility": 2.0,
    })


@pytest.fixture
def mock_analyzer():
    m = MagicMock()
    m.get_stock_info.return_value = {"股票名称": "测试股", "行业": "测试"}
    m.get_stock_data.return_value = _build_indicator_df()
    m.calculate_indicators.side_effect = lambda df: df
    m.calculate_score.return_value = 75
    m.identify_support_resistance.return_value = {
        "support_levels": {"short_term": [9.5], "medium_term": [9.0]},
        "resistance_levels": {"short_term": [10.5], "medium_term": [11.0]},
    }
    return m


@pytest.fixture
def qa(mock_analyzer, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    with patch("app.analysis.stock_qa.get_ai_client", return_value=MagicMock()), \
         patch("app.analysis.stock_qa.get_ai_model", return_value="gpt-test"):
        from app.analysis.stock_qa import StockQA
        return StockQA(mock_analyzer)


# ---------------------------------------------------------------- 1. 无 API key
def test_answer_question_no_api_key(mock_analyzer, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch("app.analysis.stock_qa.get_ai_client", return_value=MagicMock()), \
         patch("app.analysis.stock_qa.get_ai_model", return_value="gpt-test"):
        from app.analysis.stock_qa import StockQA
        q = StockQA(mock_analyzer, openai_api_key=None)
    result = q.answer_question("600519", "估值如何？")
    assert "error" in result


# ---------------------------------------------------------------- 2. 快乐路径
def test_answer_question_happy_path(qa):
    fake_msg = MagicMock()
    fake_msg.content = "这是回答"
    fake_msg.tool_calls = None
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=fake_msg)]
    with patch("app.analysis.stock_qa.chat_completion",
               return_value=(fake_resp, None)):
        result = qa.answer_question("600519", "估值如何？")

    assert result["answer"] == "这是回答"
    assert result["stock_code"] == "600519"
    assert result["used_search_tool"] is False
    assert "conversation_id" in result


# ---------------------------------------------------------------- 3. 工具调用路径
def test_answer_question_with_tool_call(qa):
    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.function.name = "search_stock_news"
    tool_call.function.arguments = '{"query": "测试股 财报"}'

    first_msg = MagicMock()
    first_msg.content = None
    first_msg.tool_calls = [tool_call]
    first_resp = MagicMock()
    first_resp.choices = [MagicMock(message=first_msg)]

    second_msg = MagicMock()
    second_msg.content = "结合新闻的最终回答"
    second_resp = MagicMock()
    second_resp.choices = [MagicMock(message=second_msg)]

    with patch("app.analysis.stock_qa.chat_completion",
               side_effect=[(first_resp, None), (second_resp, None)]), \
         patch.object(qa, "search_stock_news",
                      return_value={"message": "ok", "results": [], "summary": ""}):
        result = qa.answer_question("600519", "最近新闻？")

    assert result["used_search_tool"] is True
    assert result["answer"] == "结合新闻的最终回答"


# ---------------------------------------------------------------- 4. LLM 失败
def test_answer_question_llm_failure(qa):
    mock_fa = MagicMock()
    mock_fa.get_financial_indicators.return_value = {}
    with patch("app.analysis.stock_qa.chat_completion",
               return_value=(None, "API quota exhausted")), \
         patch("app.analysis.fundamental_analyzer.FundamentalAnalyzer",
               return_value=mock_fa):
        result = qa.answer_question("600519", "估值")
    assert "error" in result
    assert result["error"] == "API quota exhausted"


# ---------------------------------------------------------------- 5. clear_conversation
def test_clear_conversation_branches(qa):
    qa.conversation_history["600519_abc"] = [{"role": "user", "content": "q"}]
    qa.conversation_history["600519_def"] = [{"role": "user", "content": "q"}]
    qa.conversation_history["000001_xyz"] = [{"role": "user", "content": "q"}]

    # 按 conversation_id
    r1 = qa.clear_conversation(conversation_id="600519_abc")
    assert "message" in r1
    assert "600519_abc" not in qa.conversation_history

    # 按 stock_code
    r2 = qa.clear_conversation(stock_code="600519")
    assert "message" in r2
    assert "600519_def" not in qa.conversation_history

    # 清所有
    r3 = qa.clear_conversation()
    assert qa.conversation_history == {}
    assert "message" in r3


# ---------------------------------------------------------------- 6. get_conversation_history
def test_get_conversation_history_not_found(qa):
    result = qa.get_conversation_history("nonexistent")
    assert "error" in result


def test_get_conversation_history_returns_rounds(qa):
    qa.conversation_history["test_id"] = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2"},
    ]
    result = qa.get_conversation_history("test_id")
    assert result["round_count"] == 2
    assert result["history"][0]["question"] == "Q1"
    assert result["history"][1]["answer"] == "A2"


# ---------------------------------------------------------------- 7. search_stock_news 兜底
def test_search_stock_news_unified_fallback(qa):
    """unified 抛错 + 无 serp/tavily key → 应返回兜底 dict"""
    qa.serp_api_key = None
    qa.tavily_api_key = None
    # mock unified 抛错
    with patch("app.core.search.search_stock_news_unified",
               side_effect=Exception("unified err")):
        result = qa.search_stock_news("query", "测试股", "600519", "测试", "A")
    assert isinstance(result, dict)
