# -*- coding: utf-8 -*-
"""
RSSNewsAdapter 单元测试 — 纯 mock feedparser.parse，无真实网络
Input: mock feedparser.parse 返回
Output: pytest 用例结果
Pos: tests/adapters 层，CI 回归保护
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.adapters import rss_news_adapter as rna_mod
from app.adapters.rss_news_adapter import RSSNewsAdapter, FEED_SOURCES


# ---------- helpers ----------

def _mk_entry(title, link="http://x/a", published="2026-04-15 08:00:00",
              summary="摘要", author="王小二", tags=None):
    tag_objs = [SimpleNamespace(term=t) for t in (tags or [])]
    return SimpleNamespace(
        title=title,
        link=link,
        published=published,
        summary=summary,
        author=author,
        tags=tag_objs,
    )


def _mk_parsed(entries, bozo=0):
    return SimpleNamespace(entries=entries, bozo=bozo, bozo_exception=None)


# ---------- fixtures ----------

@pytest.fixture(autouse=True)
def _enable_feedparser(monkeypatch):
    """强制打开 _HAS_FEEDPARSER 标记，让测试能进入主路径"""
    monkeypatch.setattr(rna_mod, "_HAS_FEEDPARSER", True)
    # 保证 feedparser 模块对象存在（即使未装）
    if rna_mod.feedparser is None:
        fake = MagicMock()
        monkeypatch.setattr(rna_mod, "feedparser", fake)
    yield


# ---------- 测试 ----------

def test_feed_sources_covers_required_6():
    required = {"wallstreetcn", "cls", "xueqiu", "sina_finance", "jrj", "cctv_finance"}
    assert required.issubset(set(FEED_SOURCES.keys()))
    for k, v in FEED_SOURCES.items():
        assert "url" in v and v["url"].startswith("http")
        assert "name" in v


def test_get_feed_unknown_source_returns_empty():
    a = RSSNewsAdapter()
    df = a.get_feed("not_exist")
    assert isinstance(df, pd.DataFrame) and df.empty
    assert list(df.columns) == ["source", "title", "link", "published", "summary", "author", "tags"]


def test_get_feed_happy_path(monkeypatch):
    a = RSSNewsAdapter()
    entries = [
        _mk_entry("央行降准0.5%", tags=["宏观", "货币政策"]),
        _mk_entry("A股三大指数收涨", tags=["市场"]),
    ]
    monkeypatch.setattr(a, "_parse_feed", lambda url: _mk_parsed(entries))

    df = a.get_feed("wallstreetcn", limit=50)
    assert len(df) == 2
    assert df.iloc[0]["source"] == "wallstreetcn"
    assert df.iloc[0]["title"] == "央行降准0.5%"
    assert df.iloc[0]["tags"] == "宏观,货币政策"
    assert df.iloc[0]["author"] == "王小二"


def test_get_feed_fallback_on_primary_fail(monkeypatch):
    """主URL返回None → fallback URL成功"""
    a = RSSNewsAdapter()
    calls = {"n": 0}

    def fake_parse(url):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # 主URL失败
        return _mk_parsed([_mk_entry("fallback成功")])

    monkeypatch.setattr(a, "_parse_feed", fake_parse)
    df = a.get_feed("cls")
    assert len(df) == 1
    assert df.iloc[0]["title"] == "fallback成功"
    assert calls["n"] == 2


def test_get_feed_limit_cuts_entries(monkeypatch):
    a = RSSNewsAdapter()
    entries = [_mk_entry(f"title-{i}") for i in range(10)]
    monkeypatch.setattr(a, "_parse_feed", lambda url: _mk_parsed(entries))
    df = a.get_feed("sina_finance", limit=3)
    assert len(df) == 3


def test_get_all_feeds_concurrent_and_dedup(monkeypatch):
    a = RSSNewsAdapter()

    def fake_get_feed(source, limit):
        # 不同源返回，含重复标题
        rows = {
            "wallstreetcn": [("央行降准", "http://w/1"), ("A股涨", "http://w/2")],
            "cls":          [("央行降准", "http://c/1"), ("财联社独家", "http://c/2")],
            "sina_finance": [("新浪头条", "http://s/1")],
        }.get(source, [])
        return pd.DataFrame(
            [{"source": source, "title": t, "link": l, "published": "",
              "summary": "", "author": "", "tags": ""} for t, l in rows],
            columns=["source", "title", "link", "published", "summary", "author", "tags"],
        )

    monkeypatch.setattr(a, "get_feed", fake_get_feed)

    df = a.get_all_feeds(sources=["wallstreetcn", "cls", "sina_finance"])
    # 3源 5行 → 去重"央行降准"后 4 行
    assert len(df) == 4
    # 验证至少含 3 个来源
    assert set(df["source"].unique()) >= {"wallstreetcn", "cls", "sina_finance"}
    assert (df["title"] == "央行降准").sum() == 1  # 去重生效


def test_get_all_feeds_filters_unknown_sources(monkeypatch):
    a = RSSNewsAdapter()
    monkeypatch.setattr(a, "get_feed",
                        lambda s, l: pd.DataFrame(columns=["source","title","link","published","summary","author","tags"]))
    df = a.get_all_feeds(sources=["fake_source_xxx"])
    assert df.empty


def test_search_news_keyword_hits_title_or_summary(monkeypatch):
    a = RSSNewsAdapter()
    pool = pd.DataFrame([
        {"source": "wallstreetcn", "title": "央行降准0.5%", "link": "", "published": "",
         "summary": "货币宽松", "author": "", "tags": "宏观"},
        {"source": "cls", "title": "A股涨停潮", "link": "", "published": "",
         "summary": "题材炒作", "author": "", "tags": "市场"},
        {"source": "sina_finance", "title": "人民币汇率", "link": "", "published": "",
         "summary": "美联储降准预期", "author": "", "tags": ""},
    ], columns=["source","title","link","published","summary","author","tags"])

    monkeypatch.setattr(a, "get_all_feeds", lambda sources=None, limit_per_source=50: pool)

    hit = a.search_news("降准")
    # title 命中 + summary 命中 = 2
    assert len(hit) == 2
    assert set(hit["title"]) == {"央行降准0.5%", "人民币汇率"}


def test_search_news_empty_keyword_returns_all(monkeypatch):
    a = RSSNewsAdapter()
    pool = pd.DataFrame([{"source":"x","title":"a","link":"","published":"","summary":"","author":"","tags":""}],
                       columns=["source","title","link","published","summary","author","tags"])
    monkeypatch.setattr(a, "get_all_feeds", lambda sources=None, limit_per_source=50: pool)
    assert len(a.search_news("")) == 1
    assert len(a.search_news("   ")) == 1


def test_feedparser_missing_degrades(monkeypatch):
    monkeypatch.setattr(rna_mod, "_HAS_FEEDPARSER", False)
    a = RSSNewsAdapter()
    assert a.health_check() is False
    assert a.get_feed("wallstreetcn").empty
    assert a.get_all_feeds().empty
    assert a.search_news("x").empty


def test_base_adapter_contract_methods():
    a = RSSNewsAdapter()
    assert a.name == "rss_news"
    assert a.get_stock_history("000001", "20240101", "20240201").empty
    assert a.get_index_stocks("000300") == []
    assert a.get_stock_info("000001") == {}
    assert a.get_financial_data("000001") == {}


def test_parse_feed_retry_then_success(monkeypatch):
    """模拟 feedparser.parse 前两次 bozo 失败，第三次成功"""
    a = RSSNewsAdapter(max_retries=3)
    call = {"n": 0}

    def fake_parse(url, request_headers=None):
        call["n"] += 1
        if call["n"] < 3:
            # 无 entries + bozo=1 → 触发重试
            return SimpleNamespace(entries=[], bozo=1, bozo_exception=RuntimeError("x"))
        return _mk_parsed([_mk_entry("第三次成")])

    monkeypatch.setattr(rna_mod.feedparser, "parse", fake_parse)
    # 加速测试：sleep 置空
    monkeypatch.setattr(rna_mod.time, "sleep", lambda *_: None)

    parsed = a._parse_feed("http://any")
    assert parsed is not None
    assert len(parsed.entries) == 1
    assert call["n"] == 3
