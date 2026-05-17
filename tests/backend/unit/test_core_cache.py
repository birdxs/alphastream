# -*- coding: utf-8 -*-
"""
Input : pytest 收集
Output: UnifiedCache 单元测试 (TTL / 内存降级 / 并发安全 / Redis mock)
Pos   : tests/backend/unit/test_core_cache.py - BE-03c Core 系列 #1

一旦此文件被修改，请同步更新 tests/audit/reports/BE-03c_core_misc.md。
"""
from __future__ import annotations

import time
import threading
from unittest.mock import MagicMock, patch

import pytest

from app.core import cache as cache_mod
from app.core.cache import UnifiedCache, get_cache


@pytest.fixture
def fresh_cache(monkeypatch):
    """重置单例并强制使用内存模式，避免污染。"""
    # 清掉单例
    UnifiedCache._instance = None
    # 关闭 Redis
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("USE_REDIS_CACHE", "false")
    c = UnifiedCache()
    # 完全重置内部状态
    c._redis = None
    c._memory_cache.clear()
    c._memory_ttl.clear()
    yield c
    UnifiedCache._instance = None


def test_set_get_roundtrip(fresh_cache):
    """基本 set/get 行为。"""
    fresh_cache.set("k1", {"v": 1}, ttl=60)
    assert fresh_cache.get("k1") == {"v": 1}
    assert fresh_cache.is_redis is False


def test_ttl_expiry(fresh_cache):
    """TTL 到期后返回 None。"""
    fresh_cache.set("k_ttl", "x", ttl=1)
    # 手动把过期时间倒回去
    fresh_cache._memory_ttl["k_ttl"] = time.time() - 0.1
    assert fresh_cache.get("k_ttl") is None
    assert "k_ttl" not in fresh_cache._memory_cache


def test_delete_and_missing(fresh_cache):
    """delete 与不存在 key 返回 None。"""
    fresh_cache.set("k_del", 123, ttl=60)
    fresh_cache.delete("k_del")
    assert fresh_cache.get("k_del") is None
    assert fresh_cache.get("not_exist") is None


def test_clear_expired(fresh_cache):
    """clear_expired 仅清理过期项。"""
    fresh_cache.set("alive", "ok", ttl=300)
    fresh_cache.set("dead", "ko", ttl=1)
    fresh_cache._memory_ttl["dead"] = time.time() - 1
    n = fresh_cache.clear_expired()
    assert n == 1
    assert fresh_cache.get("alive") == "ok"
    assert fresh_cache.get("dead") is None


def test_singleton_identity(monkeypatch):
    """get_cache 返回同一实例。"""
    monkeypatch.delenv("REDIS_URL", raising=False)
    UnifiedCache._instance = None
    a = get_cache()
    b = get_cache()
    assert a is b
    UnifiedCache._instance = None


def test_concurrent_writes(fresh_cache):
    """并发写入不应丢失计数 (50 线程 * 20 次)。"""
    counter = {"x": 0}
    lock = threading.Lock()

    def worker(i):
        for j in range(20):
            fresh_cache.set(f"k{i}-{j}", i * 100 + j, ttl=60)
            with lock:
                counter["x"] += 1

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert counter["x"] == 50 * 20
    # 抽样验证一致性
    assert fresh_cache.get("k0-0") == 0
    assert fresh_cache.get("k49-19") == 49 * 100 + 19


def test_redis_path_with_mock(monkeypatch):
    """Redis 路径走 mock，验证 get/set/delete 调用。"""
    UnifiedCache._instance = None
    monkeypatch.setenv("REDIS_URL", "redis://fake")
    monkeypatch.setenv("USE_REDIS_CACHE", "true")
    fake_redis = MagicMock()
    fake_redis.ping.return_value = True
    fake_redis.get.return_value = '{"hit": true}'

    with patch("redis.from_url", return_value=fake_redis):
        c = UnifiedCache()
        assert c.is_redis is True
        c.set("x", {"y": 1}, ttl=10)
        fake_redis.setex.assert_called_once()
        assert c.get("x") == {"hit": True}
        c.delete("x")
        fake_redis.delete.assert_called_once()
    UnifiedCache._instance = None


def test_redis_failure_falls_back_to_memory(monkeypatch):
    """Redis get 失败时不抛异常，降级到内存。"""
    UnifiedCache._instance = None
    monkeypatch.setenv("REDIS_URL", "redis://fake")
    monkeypatch.setenv("USE_REDIS_CACHE", "true")
    fake_redis = MagicMock()
    fake_redis.ping.return_value = True
    fake_redis.get.side_effect = Exception("boom")
    fake_redis.setex.side_effect = Exception("boom-set")

    with patch("redis.from_url", return_value=fake_redis):
        c = UnifiedCache()
        c.set("kk", "vv", ttl=5)
        # Redis set 失败后会降级到内存
        assert c.get("kk") == "vv"
    UnifiedCache._instance = None
