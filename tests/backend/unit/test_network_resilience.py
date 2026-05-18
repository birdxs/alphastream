"""
Input: mock 函数模拟网络异常 / 超时 / 成功
Output: 验证 resilient_call 重试 + 超时 + stale 缓存 + 装饰器
Pos: tests/backend/unit/test_network_resilience.py - FIX-7 配套测试
"""
import time
from unittest.mock import MagicMock

import pytest

from app.core.network_resilience import (
    resilient_call,
    resilient,
    reset_cache_for_tests,
    DataSourceTimeoutError,
    DataSourceUnavailableError,
    _is_retryable_exception,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    reset_cache_for_tests()
    yield
    reset_cache_for_tests()


# ===== 异常分类 =====

class TestIsRetryable:
    def test_remote_disconnected_by_name(self):
        class RemoteDisconnected(Exception):
            pass
        assert _is_retryable_exception(RemoteDisconnected("eof"))

    def test_connection_error(self):
        assert _is_retryable_exception(ConnectionError("aborted"))

    def test_connection_reset(self):
        assert _is_retryable_exception(ConnectionResetError("reset"))

    def test_timeout_error(self):
        assert _is_retryable_exception(TimeoutError("timed out"))

    def test_connection_aborted_by_msg(self):
        """通过消息关键字识别"""
        assert _is_retryable_exception(Exception("Connection aborted. Remote end closed connection"))

    def test_value_error_not_retryable(self):
        assert not _is_retryable_exception(ValueError("bad"))


# ===== 重试 =====

class TestRetry:
    def test_first_success_no_retry(self):
        fn = MagicMock(return_value="ok")
        out = resilient_call(fn, ("x",))
        assert out == "ok"
        assert fn.call_count == 1

    def test_retry_then_succeed(self):
        attempts = {"n": 0}

        def fn(x):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise ConnectionError("aborted")
            return f"ok-{x}"

        out = resilient_call(fn, ("y",), base_wait=0.01, max_wait=0.05)
        assert out == "ok-y"
        assert attempts["n"] == 3

    def test_non_retryable_raised(self):
        def fn():
            raise ValueError("bad arg")

        with pytest.raises(DataSourceUnavailableError):
            resilient_call(fn, base_wait=0.01)

    def test_all_retries_fail_no_cache(self):
        def fn():
            raise ConnectionError("aborted")

        with pytest.raises(DataSourceUnavailableError):
            resilient_call(fn, base_wait=0.01, max_wait=0.05, max_attempts=3)


# ===== 超时 =====

class TestTimeout:
    def test_per_call_timeout_raises(self):
        def slow_fn():
            time.sleep(2)
            return "should-not-reach"

        with pytest.raises(DataSourceTimeoutError):
            resilient_call(slow_fn, per_call_timeout=0.3, use_stale_on_failure=False)

    def test_timeout_with_stale_cache_returns_stale(self):
        """先 set 一份缓存，再让函数超时 → 返回 stale"""
        from app.core.network_resilience import _GLOBAL_CACHE, _make_cache_key

        def slow_fn(x):
            time.sleep(2)
            return "fresh"

        key = _make_cache_key(slow_fn, ("a",), {})
        _GLOBAL_CACHE.set(key, "stale-value", ttl=1)
        time.sleep(1.2)  # 让缓存过期
        out = resilient_call(slow_fn, ("a",),
                             per_call_timeout=0.3,
                             use_stale_on_failure=True)
        assert out == "stale-value"


# ===== 缓存兜底 =====

class TestCacheFallback:
    def test_fresh_cache_hit_skips_call(self):
        fn = MagicMock(return_value="first")
        out1 = resilient_call(fn, ("k",), cache_ttl=60)
        out2 = resilient_call(fn, ("k",), cache_ttl=60)
        assert out1 == "first"
        assert out2 == "first"
        assert fn.call_count == 1  # 第二次命中缓存

    def test_stale_cache_returned_on_failure(self):
        from app.core.network_resilience import _GLOBAL_CACHE, _make_cache_key

        def fail_fn(x):
            raise ConnectionError("aborted")

        key = _make_cache_key(fail_fn, ("z",), {})
        _GLOBAL_CACHE.set(key, "stale-z", ttl=1)
        time.sleep(1.2)
        out = resilient_call(fail_fn, ("z",), base_wait=0.01, max_wait=0.02)
        assert out == "stale-z"

    def test_no_stale_when_use_stale_disabled(self):
        from app.core.network_resilience import _GLOBAL_CACHE, _make_cache_key

        def fail_fn(x):
            raise ConnectionError("aborted")

        key = _make_cache_key(fail_fn, ("z",), {})
        _GLOBAL_CACHE.set(key, "stale-z", ttl=1)
        time.sleep(1.2)
        with pytest.raises(DataSourceUnavailableError):
            resilient_call(fail_fn, ("z",), base_wait=0.01,
                           max_wait=0.02, use_stale_on_failure=False)


# ===== 装饰器形式 =====

class TestDecorator:
    def test_decorator_wraps_function(self):
        @resilient(per_call_timeout=2, cache_ttl=60)
        def my_fn(x):
            return x * 2

        assert my_fn(5) == 10
        # 第二次走缓存
        assert my_fn(5) == 10

    def test_decorator_retries(self):
        attempts = {"n": 0}

        @resilient(max_attempts=3, per_call_timeout=2)
        def flaky(x):
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ConnectionError("aborted")
            return f"ok-{x}"

        out = flaky("v")
        assert out == "ok-v"
        assert attempts["n"] == 2
