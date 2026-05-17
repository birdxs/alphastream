# -*- coding: utf-8 -*-
# Input  : SentimentAnalystAgent.analyze + mock LLM/adapter/NewsFetcher
# Output : pytest 用例 BE-02c1 舆情 Agent 单元测试
# Pos    : tests/backend/unit/test_agent_sentiment.py
"""BE-02c1 SentimentAnalystAgent 测试

注意：sentiment_analyst 没有 _fallback_analyze，
但 try/except 兜底逻辑等同：异常时返回 {'sentiment_report': {'error': ...}}。
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

from app.agents.sentiment_analyst import SentimentAnalystAgent


def _news_fixture(stock_code: str):
    return [
        {"title": f"{stock_code} 业绩超预期", "content": "净利润同比增长 30%",
         "summary": "看好后市", "date": "2026-05-17"},
        {"title": f"{stock_code} 获大单买入", "content": "主力资金流入明显",
         "summary": "市场关注度提升", "date": "2026-05-17"},
        {"title": "市场普涨", "content": "大盘走强",
         "summary": "整体偏暖", "date": "2026-05-16"},
    ]


# ---------------------------------------------------------------- 1. 快乐路径
def test_sentiment_happy_path(minimal_state):
    """mock chat_completion 返回情绪分析 -> sentiment_report 含 total_news 等字段"""
    stock_code = minimal_state["stock_code"]
    news = _news_fixture(stock_code)
    fake_client = MagicMock(name="ai_client")

    with patch("app.analysis.news_fetcher.NewsFetcher") as MockFetcher, \
         patch("app.agents.sentiment_analyst._registry_fetch", return_value=news), \
         patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion",
               return_value=({"choices": [{"message": {"content": "整体偏乐观, 评分 7/10"}}]}, None)), \
         patch("app.core.ai_client.get_completion_content",
               return_value="整体偏乐观, 评分 7/10"):
        MockFetcher.return_value.get_latest_news.return_value = news
        out = SentimentAnalystAgent.analyze(minimal_state)

    assert "sentiment_report" in out
    report = out["sentiment_report"]
    assert report["total_news"] == 3
    assert report["relevant_news_count"] >= 2  # 至少有 stock_code 相关 2 条
    assert "news_items" in report
    assert report.get("ai_commentary") == "整体偏乐观, 评分 7/10"
    log = out.get("execution_log", [])
    assert any(e.get("status") == "success" for e in log)


# ---------------------------------------------------------------- 2. 数据源失败降级
def test_sentiment_fallback_news_fetcher_fails(minimal_state):
    """registry_fetch 返回 None + NewsFetcher 抛错 -> 进入异常分支返回 error"""
    with patch("app.agents.sentiment_analyst._registry_fetch", return_value=None), \
         patch("app.analysis.news_fetcher.NewsFetcher") as MockFetcher:
        MockFetcher.return_value.get_latest_news.side_effect = RuntimeError("akshare 504")
        out = SentimentAnalystAgent.analyze(minimal_state)

    report = out["sentiment_report"]
    assert "error" in report
    log = out.get("execution_log", [])
    assert any(e.get("status") == "failed" for e in log)


def test_sentiment_empty_news_safe(minimal_state):
    """registry/NewsFetcher 均返回 [] + AI 客户端 None -> 不报错, 返回空 report"""
    with patch("app.agents.sentiment_analyst._registry_fetch", return_value=None), \
         patch("app.analysis.news_fetcher.NewsFetcher") as MockFetcher, \
         patch("app.core.ai_client.get_ai_client", return_value=None):
        MockFetcher.return_value.get_latest_news.return_value = []
        out = SentimentAnalystAgent.analyze(minimal_state)

    report = out["sentiment_report"]
    assert "error" not in report
    assert report["total_news"] == 0
    assert report["relevant_news_count"] == 0


# ---------------------------------------------------------------- 3. LLM 失败降级
def test_sentiment_fallback_on_llm_error(minimal_state):
    """chat_completion 抛错 -> 进入 except 分支返回 error"""
    stock_code = minimal_state["stock_code"]
    news = _news_fixture(stock_code)
    fake_client = MagicMock(name="ai_client")

    with patch("app.agents.sentiment_analyst._registry_fetch", return_value=news), \
         patch("app.analysis.news_fetcher.NewsFetcher") as MockFetcher, \
         patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion",
               side_effect=RuntimeError("LLM down")):
        MockFetcher.return_value.get_latest_news.return_value = news
        out = SentimentAnalystAgent.analyze(minimal_state)

    report = out["sentiment_report"]
    # LLM 异常未被 try 局部捕获 -> 进入外层 except 返回 error
    assert "error" in report


def test_sentiment_llm_error_field_keeps_report(minimal_state):
    """chat_completion 返回 (response, error) error 非空 -> 不写 ai_commentary, 但报告其他字段正常"""
    stock_code = minimal_state["stock_code"]
    news = _news_fixture(stock_code)
    fake_client = MagicMock(name="ai_client")

    with patch("app.agents.sentiment_analyst._registry_fetch", return_value=news), \
         patch("app.analysis.news_fetcher.NewsFetcher") as MockFetcher, \
         patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
         patch("app.core.ai_client.chat_completion",
               return_value=(None, "api timeout")), \
         patch("app.core.ai_client.get_completion_content",
               return_value=""):
        MockFetcher.return_value.get_latest_news.return_value = news
        out = SentimentAnalystAgent.analyze(minimal_state)

    report = out["sentiment_report"]
    assert "error" not in report
    assert report["total_news"] == 3
    # 不应有非空 ai_commentary
    assert not report.get("ai_commentary")


# ---------------------------------------------------------------- 4. 事件发布
def test_sentiment_no_token_events_when_llm_unused(minimal_state, mock_event_bus):
    """AI 客户端为 None -> chat_completion 不被调用 -> 无 token 事件"""
    stock_code = minimal_state["stock_code"]
    news = _news_fixture(stock_code)
    mock_event_bus.clear()

    with patch("app.agents.sentiment_analyst._registry_fetch", return_value=news), \
         patch("app.analysis.news_fetcher.NewsFetcher") as MockFetcher, \
         patch("app.core.ai_client.get_ai_client", return_value=None):
        MockFetcher.return_value.get_latest_news.return_value = news
        SentimentAnalystAgent.analyze(minimal_state)

    token_evts = [r for r in mock_event_bus.events if "token" in r[0].lower()]
    assert token_evts == []
