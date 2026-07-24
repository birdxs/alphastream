# Input: pytest 收集/导入 API 测试模块
# Output: 导入前写入 STOCKANAL_DISABLE_BACKGROUND=1，并清理模块级 cache（防顺序污染）
# Pos: tests/backend/api/conftest — 与根 conftest 双保险减少 atexit 噪声

from __future__ import annotations

import os

# 必须在 import app.web.web_server 之前
os.environ.setdefault("DISABLE_NETWORK", "1")
os.environ.setdefault("MOCK_LLM", "1")
os.environ.setdefault("AUTH_REQUIRED", "false")
os.environ["STOCKANAL_DISABLE_BACKGROUND"] = "1"

"""
Sprint 3-I：autouse fixture 清模块级缓存，防止跨测顺序污染
Input: 每个 api/ 测试用例
Output: 测试前后清空 5 个已知模块级 dict 缓存
Pos: tests/backend/api/ 测试基础设施
"""
import pytest


@pytest.fixture(autouse=True)
def _clear_module_caches():
    """每测前后清模块级 dict 缓存，防止 S3-I 已知顺序污染。

    覆盖：
    - app.web.web_server._market_indices_cache（污染源，30s TTL）
    - app.web.web_server._PROFILE_CACHE
    - app.web.web_server._STOCK_NAME_CACHE
    - app.web.web_server._INDEX_CACHE
    - app.adapters.akshare_adapter._AKSHARE_HC_CACHE

    锁对象（_LOCK 后缀）不动。
    """
    _clear_all()
    yield
    _clear_all()


def _clear_all():
    try:
        from app.web import web_server
    except ImportError:
        web_server = None
    try:
        from app.adapters import akshare_adapter
    except ImportError:
        akshare_adapter = None

    if web_server is not None:
        for cache_name in (
            "_market_indices_cache",
            "_PROFILE_CACHE",
            "_STOCK_NAME_CACHE",
            "_INDEX_CACHE",
        ):
            cache = getattr(web_server, cache_name, None)
            if isinstance(cache, dict):
                cache.clear()

    if akshare_adapter is not None:
        hc = getattr(akshare_adapter, "_AKSHARE_HC_CACHE", None)
        if isinstance(hc, dict):
            hc.clear()
