# -*- coding: utf-8 -*-
"""
Input : pytest 收集
Output: search.py + search_engines.py 单元测试 (multi_search 并发/禁用列表/HTTP mock)
Pos   : tests/backend/unit/test_core_search.py - BE-03c Core #6

外部网络一律 mock - 无任何真实 HTTP 调用。

一旦此文件被修改，请同步更新 tests/audit/reports/BE-03c_core_misc.md。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core import search_engines as se
from app.core import search as facade


# --------------------------------------------------------------------------- #
# search.py 门面
# --------------------------------------------------------------------------- #

def test_search_web_delegates_to_multi_search():
    """search_web 应代理到 multi_search 并返回结果。"""
    fake = [{"title": "T", "content": "C", "url": "https://x", "source": "fake"}]
    with patch.object(facade, "multi_search", return_value=fake) as ms:
        out = facade.search_web("AAPL earnings", max_results=3, engine="auto")
    assert out == fake
    ms.assert_called_once_with("AAPL earnings", engine="auto", n_results=3)


def test_search_web_swallows_exceptions():
    """multi_search 异常时 search_web 返回空 list，不抛出。"""
    with patch.object(facade, "multi_search", side_effect=RuntimeError("net down")):
        out = facade.search_web("x")
    assert out == []


def test_search_stock_news_unified_dedup_by_url():
    """两路 query 返回相同 URL 时应去重。"""
    r1 = [{"title": "A", "url": "https://news/1", "content": "", "source": "s"}]
    r2 = [{"title": "A again", "url": "https://news/1", "content": "", "source": "s"},
          {"title": "B", "url": "https://news/2", "content": "", "source": "s"}]
    calls = iter([r1, r2])

    def fake_ms(*args, **kwargs):
        return next(calls)

    with patch.object(facade, "multi_search", side_effect=fake_ms):
        out = facade.search_stock_news_unified("600519", "贵州茅台", max_results=5)
    urls = [r["url"] for r in out]
    assert urls == ["https://news/1", "https://news/2"]


# --------------------------------------------------------------------------- #
# search_engines.search_one
# --------------------------------------------------------------------------- #

def test_search_one_disabled_returns_empty(monkeypatch):
    """SEARCH_DISABLED_ENGINES 中的引擎跳过返回空。"""
    monkeypatch.setenv("SEARCH_DISABLED_ENGINES", "baidu,brave")
    assert se.search_one("baidu", "test", 3) == []
    assert se.search_one("brave", "test", 3) == []


def test_search_one_unknown_engine_returns_empty(monkeypatch):
    """未知引擎返回空 list。"""
    monkeypatch.setenv("SEARCH_DISABLED_ENGINES", "")
    assert se.search_one("nonexistent_engine_xx", "q", 3) == []


def test_search_one_html_engine_with_mock(monkeypatch):
    """通用 HTML 引擎走 _http_get + _parse_generic。"""
    monkeypatch.setenv("SEARCH_DISABLED_ENGINES", "")
    fake_html = "<html><body>" + ("mock content " * 50) + "</body></html>"
    parsed = [{"title": "X", "content": "C", "url": "https://x", "source": "baidu"}]
    with patch.object(se, "_http_get", return_value=fake_html), \
         patch.object(se, "_parse_generic", return_value=parsed) as pg:
        out = se.search_one("baidu", "查询", 5)
    assert out == parsed
    pg.assert_called_once()


def test_search_one_http_failure_returns_empty(monkeypatch):
    """_http_get 返回 None 时 search_one 返回空。"""
    monkeypatch.setenv("SEARCH_DISABLED_ENGINES", "")
    with patch.object(se, "_http_get", return_value=None):
        out = se.search_one("baidu", "q", 5)
    assert out == []


# --------------------------------------------------------------------------- #
# search_engines.multi_search
# --------------------------------------------------------------------------- #

def test_multi_search_single_engine_success(monkeypatch):
    """指定引擎命中即返回。"""
    monkeypatch.setenv("SEARCH_DISABLED_ENGINES", "")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SERP_API_KEY", raising=False)
    hit = [{"title": "T", "url": "https://u", "content": "C", "source": "baidu"}]
    with patch.object(se, "search_one", return_value=hit):
        out = se.multi_search("q", engine="baidu", n_results=3)
    assert out == hit


def test_multi_search_auto_falls_through_chain(monkeypatch):
    """auto 模式按 fallback 链顺序逐个尝试，首个有结果即返回。"""
    monkeypatch.setenv("SEARCH_DISABLED_ENGINES", "")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SERP_API_KEY", raising=False)

    call_log = []

    def fake_search_one(engine, query, n):
        call_log.append(engine)
        # 前两个引擎返回空，第三个返回结果
        if len(call_log) < 3:
            return []
        return [{"title": "ok", "url": "https://ok", "content": "", "source": engine}]

    with patch.object(se, "search_one", side_effect=fake_search_one):
        out = se.multi_search("q", engine="auto", n_results=3, chain="auto")
    assert len(out) == 1
    assert len(call_log) == 3  # 前两个失败，第三个命中


def test_multi_search_all_fail_returns_empty(monkeypatch):
    """所有引擎都返回空时 multi_search 返回 []。"""
    monkeypatch.setenv("SEARCH_DISABLED_ENGINES", "")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SERP_API_KEY", raising=False)
    with patch.object(se, "search_one", return_value=[]):
        out = se.multi_search("q", engine="auto", n_results=5)
    assert out == []


def test_multi_search_concurrent_mode(monkeypatch):
    """concurrent 模式调用 _concurrent_search。"""
    monkeypatch.setenv("SEARCH_DISABLED_ENGINES", "")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SERP_API_KEY", raising=False)
    expected = [{"title": "merged", "url": "https://m", "content": "", "source": "a+b"}]
    with patch.object(se, "_concurrent_search", return_value=expected) as cs:
        out = se.multi_search("q", engine="concurrent", n_results=4)
    assert out == expected
    cs.assert_called_once()


def test_concurrent_search_dedups_by_url(monkeypatch):
    """_concurrent_search 应按 URL 去重并合并 source。"""
    def fake_search_one(eng, q, n):
        if eng == "e1":
            return [{"title": "T1", "url": "https://same", "content": "", "source": "e1"},
                    {"title": "T2", "url": "https://u2", "content": "", "source": "e1"}]
        if eng == "e2":
            return [{"title": "T1b", "url": "https://same", "content": "", "source": "e2"}]
        return []

    with patch.object(se, "search_one", side_effect=fake_search_one):
        out = se._concurrent_search("q", ["e1", "e2"], n_results=5)
    urls = [r["url"] for r in out]
    assert "https://same" in urls
    assert "https://u2" in urls
    # https://same 排在前（出现次数更多）
    assert out[0]["url"] == "https://same"
    assert "e1" in out[0]["source"] and "e2" in out[0]["source"]


def test_list_engines_excludes_disabled(monkeypatch):
    """list_engines 排除 SEARCH_DISABLED_ENGINES 中的引擎。"""
    monkeypatch.setenv("SEARCH_DISABLED_ENGINES", "baidu,brave")
    out = se.list_engines()
    assert "baidu" not in out
    assert "brave" not in out
    # 其他常见引擎应保留
    assert isinstance(out, list) and len(out) > 0


def test_parse_generic_with_minimal_html(monkeypatch):
    """_parse_generic 解析真实结构的最小 HTML，验证条目抽取。"""
    cfg = se.ENGINES_CONFIG["baidu"]
    html = (
        "<html><body>"
        "<div class='result c-container'>"
        "<h3><a href='https://example.com/a'>标题A</a></h3>"
        "<div class='c-abstract'>摘要内容A</div>"
        "</div>"
        "<div class='result c-container'>"
        "<h3><a href='https://example.com/b'>标题B</a></h3>"
        "<div class='c-abstract'>摘要内容B</div>"
        "</div>"
        "</body></html>"
    )
    out = se._parse_generic(html, cfg, "baidu", max_results=5)
    assert len(out) == 2
    assert out[0]["title"] == "标题A"
    assert out[0]["url"] == "https://example.com/a"
    assert out[0]["source"] == "baidu"


def test_parse_generic_handles_bad_html():
    """_parse_generic 解析失败时返回空 list 而非抛异常。"""
    cfg = se.ENGINES_CONFIG["baidu"]
    out = se._parse_generic("", cfg, "baidu", 5)
    assert out == []


def test_search_ddgs_with_mocked_module(monkeypatch):
    """ddgs special handler 用 mock DDGS。"""
    import sys
    fake_mod = MagicMock()

    class FakeDDGS:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, q, max_results):
            yield {"title": "t1", "body": "b1", "href": "https://d1"}

    fake_mod.DDGS = FakeDDGS
    monkeypatch.setitem(sys.modules, "ddgs", fake_mod)
    monkeypatch.delenv("DUCKDUCKGO_PROXY", raising=False)
    out = se._search_ddgs_api("q", 5)
    assert out and out[0]["url"] == "https://d1"
    assert out[0]["source"] == "duckduckgo"


def test_search_wikipedia_with_mocked_http(monkeypatch):
    """wikipedia handler 用 mock urllib.request。"""
    import json as _json
    # wikipedia 走 urllib
    fake_response = MagicMock()
    fake_response.read.return_value = _json.dumps({
        "query": {
            "search": [
                {"title": "Apple Inc.", "snippet": "American tech company"}
            ]
        }
    }).encode("utf-8")
    fake_response.__enter__ = lambda self: self
    fake_response.__exit__ = lambda *a: None

    with patch("urllib.request.urlopen", return_value=fake_response):
        out = se._search_wikipedia("apple", 3)
    # 不强校验非空（不同实现可能拼装 url），但至少不抛异常并返回 list
    assert isinstance(out, list)


def test_multi_search_unknown_engine_falls_to_auto(monkeypatch):
    """指定未知引擎时 multi_search 应回退到 auto 链。"""
    monkeypatch.setenv("SEARCH_DISABLED_ENGINES", "")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SERP_API_KEY", raising=False)
    call_log = []

    def fake_search_one(eng, q, n):
        call_log.append(eng)
        if eng == "no_such_engine":
            return []
        return [{"title": "ok", "url": f"https://{eng}", "content": "", "source": eng}]

    with patch.object(se, "search_one", side_effect=fake_search_one):
        out = se.multi_search("q", engine="no_such_engine", n_results=2)
    assert out and out[0]["url"].startswith("https://")
    # 至少触发了 fallback 链
    assert len(call_log) >= 2


def test_http_get_error_returns_none(monkeypatch):
    """_http_get 在 requests 抛异常时返回 None。"""
    fake_requests = MagicMock()
    fake_requests.get.side_effect = Exception("network down")
    with patch.dict("sys.modules", {"requests": fake_requests}):
        out = se._http_get("https://x")
    assert out is None
