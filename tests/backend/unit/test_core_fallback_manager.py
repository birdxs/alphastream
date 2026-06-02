# -*- coding: utf-8 -*-
"""
Input : pytest 收集
Output: FallbackManager 单元测试 (优先级 / 跳过失败源 / 失败计数 / DataFrame 有效性)
Pos   : tests/backend/unit/test_core_fallback_manager.py - BE-03c Core #4

一旦此文件被修改，请同步更新 tests/audit/reports/BE-03c_core_misc.md。
"""
from __future__ import annotations

import time

import pandas as pd
import pytest

from app.core.fallback_manager import FallbackManager


class FakeAdapter:
    """简易适配器：可配置返回值或异常。"""

    def __init__(self, name: str, result=None, exc: Exception | None = None):
        self.name = name
        self._result = result
        self._exc = exc
        self.call_count = 0

    def get_data(self, *args, **kwargs):
        self.call_count += 1
        if self._exc is not None:
            raise self._exc
        return self._result


def test_first_adapter_success_no_fallback():
    """首选 adapter 成功时不调用次选。"""
    a1 = FakeAdapter("a1", result={"ok": True})
    a2 = FakeAdapter("a2", result={"ok": "ne"})
    fm = FallbackManager([a1, a2], max_retries=1, retry_delay=0.01)

    out = fm.execute("get_data", 1)
    assert out == {"ok": True}
    assert a1.call_count == 1
    assert a2.call_count == 0


def test_fallback_to_second_when_first_fails():
    """首选异常时降级到次选。"""
    a1 = FakeAdapter("a1", exc=RuntimeError("boom"))
    a2 = FakeAdapter("a2", result=[1, 2, 3])
    fm = FallbackManager([a1, a2], max_retries=1, retry_delay=0.01)

    out = fm.execute("get_data")
    assert out == [1, 2, 3]
    assert a1.call_count == 1  # max_retries=1
    assert a2.call_count == 1


def test_all_failures_raise():
    """所有 adapter 都失败时抛异常。"""
    a1 = FakeAdapter("a1", exc=RuntimeError("e1"))
    a2 = FakeAdapter("a2", exc=RuntimeError("e2"))
    fm = FallbackManager([a1, a2], max_retries=1, retry_delay=0.01)

    with pytest.raises(Exception, match="所有数据源均不可用"):
        fm.execute("get_data")


def test_retry_within_adapter():
    """单 adapter 内部按 max_retries 重试。"""
    a1 = FakeAdapter("a1", exc=RuntimeError("flaky"))
    fm = FallbackManager([a1], max_retries=3, retry_delay=0.001)

    with pytest.raises(Exception):
        fm.execute("get_data")
    assert a1.call_count == 3


def test_missing_method_skipped():
    """adapter 缺少方法时静默跳过到下一个。"""
    class NoSuchMethod:
        name = "nope"

    a1 = NoSuchMethod()
    a2 = FakeAdapter("a2", result=42)
    fm = FallbackManager([a1, a2], max_retries=1, retry_delay=0.01)
    assert fm.execute("get_data") == 42


def test_is_valid_result_dataframe():
    """DataFrame 空 / 非空判定。"""
    fm = FallbackManager([], max_retries=1)
    assert fm._is_valid_result(None) is False
    assert fm._is_valid_result(pd.DataFrame()) is False
    df = pd.DataFrame({"a": [1, 2]})
    assert fm._is_valid_result(df) is True
    # K 线必需列
    kline = pd.DataFrame({"date": [1], "open": [1], "high": [1],
                          "low": [1], "close": [1], "volume": [1]})
    assert fm._is_valid_result(kline) is True


def test_is_valid_result_collections():
    """空 list/dict 视为无效。"""
    fm = FallbackManager([], max_retries=1)
    assert fm._is_valid_result([]) is False
    assert fm._is_valid_result({}) is False
    assert fm._is_valid_result([1]) is True
    assert fm._is_valid_result({"a": 1}) is True
    assert fm._is_valid_result("non-empty") is True


def test_reset_status_and_get_status():
    """reset_status 清零失败计数。"""
    a1 = FakeAdapter("a1", exc=RuntimeError("x"))
    a2 = FakeAdapter("a2", result={"v": 1})
    fm = FallbackManager([a1, a2], max_retries=1, retry_delay=0.001)

    fm.execute("get_data")  # a1 失败 1 次
    st = fm.get_status()
    assert st["fail_count"]["a1"] >= 1

    fm.reset_status()
    st2 = fm.get_status()
    assert st2["fail_count"]["a1"] == 0
    assert st2["status"]["a1"] is True


def test_invalid_result_triggers_fallback():
    """无效结果（空 DataFrame）应触发下一 adapter。"""
    a1 = FakeAdapter("a1", result=pd.DataFrame())
    a2 = FakeAdapter("a2", result=pd.DataFrame({"x": [1]}))
    fm = FallbackManager([a1, a2], max_retries=1, retry_delay=0.001)

    out = fm.execute("get_data")
    assert not out.empty
    assert a1.call_count == 1
    assert a2.call_count == 1


# ---------------------------------------------------------------------------
# per-call 超时治本修复回归（FALLBACK_PER_CALL_TIMEOUT / _call_with_timeout）
# ---------------------------------------------------------------------------

class SlowAdapter:
    """模拟 akshare 网络停顿永久阻塞的 adapter：get_data 长时间 sleep。"""

    def __init__(self, name: str, sleep_s: float):
        self.name = name
        self._sleep_s = sleep_s
        self.call_count = 0

    def get_data(self, *args, **kwargs):
        self.call_count += 1
        time.sleep(self._sleep_s)
        return {"slow": True}


def test_per_call_timeout_default_from_env(monkeypatch):
    """未显式传入时，per_call_timeout 取 env FALLBACK_PER_CALL_TIMEOUT。"""
    import importlib
    import app.core.fallback_manager as fm_mod
    monkeypatch.setenv("FALLBACK_PER_CALL_TIMEOUT", "7")
    importlib.reload(fm_mod)
    try:
        fm = fm_mod.FallbackManager([])
        assert fm._per_call_timeout == 7.0
        # 显式参数优先于 env
        fm2 = fm_mod.FallbackManager([], per_call_timeout=3.5)
        assert fm2._per_call_timeout == 3.5
    finally:
        monkeypatch.delenv("FALLBACK_PER_CALL_TIMEOUT", raising=False)
        importlib.reload(fm_mod)


def test_timeout_falls_back_to_next_adapter():
    """首选 adapter 超时挂死时，应在 per_call_timeout 内切换到下一 adapter。"""
    slow = SlowAdapter("slow", sleep_s=30)  # 远超下方 0.3s 超时
    fast = FakeAdapter("fast", result={"ok": True})
    fm = FallbackManager([slow, fast], max_retries=1, retry_delay=0.001,
                         per_call_timeout=0.3)

    start = time.monotonic()
    out = fm.execute("get_data")
    elapsed = time.monotonic() - start

    assert out == {"ok": True}
    assert slow.call_count == 1
    assert fast.call_count == 1
    # 不挂死：总耗时应接近一次超时窗，远小于 slow 的 30s
    assert elapsed < 5, f"超时未生效，elapsed={elapsed}"


def test_all_adapters_timeout_raises_not_hang():
    """所有 adapter 都超时时按现有语义抛最终异常，且不无限挂起。"""
    s1 = SlowAdapter("s1", sleep_s=30)
    s2 = SlowAdapter("s2", sleep_s=30)
    fm = FallbackManager([s1, s2], max_retries=1, retry_delay=0.001,
                         per_call_timeout=0.3)

    start = time.monotonic()
    with pytest.raises(Exception, match="所有数据源均不可用"):
        fm.execute("get_data")
    elapsed = time.monotonic() - start

    assert s1.call_count == 1
    assert s2.call_count == 1
    assert elapsed < 5, f"超时未生效，elapsed={elapsed}"
