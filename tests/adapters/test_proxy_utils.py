# -*- coding: utf-8 -*-
"""
_proxy_utils 测试 [NEW-FILE:#20260415-39]
Input: 模拟 HTTP_PROXY/HTTPS_PROXY env
Output: pytest 断言 get_proxies/get_proxy_url 行为
Pos: tests/adapters层，覆盖 H4 全局代理工具单元路径

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
from __future__ import annotations

import os
import importlib
import pytest

from app.adapters import _proxy_utils


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """每用例清理 4 个代理 env，避免CI宿主污染。"""
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(k, raising=False)
    yield


def test_get_proxies_returns_none_when_no_env():
    """无任何代理 env 时应返回 None（不干扰直连）。"""
    assert _proxy_utils.get_proxies() is None
    assert _proxy_utils.get_proxy_url() is None


def test_get_proxies_reads_http_proxy_uppercase(monkeypatch):
    """HTTP_PROXY 大写 env 应被识别，http/https 同填。"""
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
    p = _proxy_utils.get_proxies()
    assert p is not None
    assert p["http"] == "http://127.0.0.1:7890"
    # 单端口通吃：https 亦填充
    assert p["https"] == "http://127.0.0.1:7890"


def test_get_proxies_reads_lowercase_http_proxy(monkeypatch):
    """小写 http_proxy 兼容。"""
    monkeypatch.setenv("http_proxy", "http://proxy.example:3128")
    p = _proxy_utils.get_proxies()
    assert p is not None
    assert p["http"] == "http://proxy.example:3128"


def test_get_proxies_both_http_and_https(monkeypatch):
    """HTTP_PROXY 与 HTTPS_PROXY 同时存在，分别注入。"""
    monkeypatch.setenv("HTTP_PROXY", "http://h:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://s:2")
    p = _proxy_utils.get_proxies()
    assert p == {"http": "http://h:1", "https": "http://s:2"}


def test_get_proxy_url_prefers_https(monkeypatch):
    """get_proxy_url 应优先 HTTPS_PROXY（境外源多为 https）。"""
    monkeypatch.setenv("HTTP_PROXY", "http://h:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://s:2")
    assert _proxy_utils.get_proxy_url() == "http://s:2"


def test_get_proxy_url_falls_back_to_http(monkeypatch):
    """仅有 HTTP_PROXY 时 get_proxy_url 回退。"""
    monkeypatch.setenv("HTTP_PROXY", "http://only-http:1")
    assert _proxy_utils.get_proxy_url() == "http://only-http:1"


def test_module_reimport_safe():
    """反复 import 不应抛错（证明无模块级副作用）。"""
    importlib.reload(_proxy_utils)
    assert callable(_proxy_utils.get_proxies)
    assert callable(_proxy_utils.get_proxy_url)
