# -*- coding: utf-8 -*-
"""
Input: _retry_utils 模块函数
Output: pytest 8 用例
Pos: tests/adapters — K1 [NEW-FILE:#20260415-45] 重试工具单测

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
import requests

from app.adapters._retry_utils import (
    UA_POOL,
    random_ua,
    retry_with_backoff,
    build_session_with_ua,
    rotate_ua,
    DEFAULT_RETRY_STATUS,
)


# ---------- UA 池 ----------

def test_ua_pool_size_and_content():
    """UA池至少5条，且均为字符串含 Mozilla"""
    assert len(UA_POOL) >= 5
    assert all(isinstance(u, str) and "Mozilla" in u for u in UA_POOL)


def test_random_ua_in_pool_and_varies():
    """random_ua返回UA池内，且多次调用有差异 (概率上)"""
    uas = {random_ua() for _ in range(50)}
    # 50次随机至少覆盖2种 (对≥5容量池 概率≈1)
    assert len(uas) >= 2
    assert all(u in UA_POOL for u in uas)


# ---------- retry_with_backoff ----------

def test_retry_success_first_call():
    """首次成功：不重试"""
    mock = MagicMock(return_value="ok")
    result = retry_with_backoff(mock, max_retries=3, backoff_base=0.01)
    assert result == "ok"
    assert mock.call_count == 1


def test_retry_on_429_then_success():
    """首次429, 第二次200 — 重试并返回最后Response"""
    r_bad = MagicMock(spec=requests.Response)
    r_bad.status_code = 429
    r_ok = MagicMock(spec=requests.Response)
    r_ok.status_code = 200
    calls = iter([r_bad, r_ok])
    result = retry_with_backoff(lambda: next(calls),
                                max_retries=3, backoff_base=0.01, jitter=0)
    assert result.status_code == 200


def test_retry_all_status_bad_returns_last():
    """全部429，返回最后一个Response (由调用方软降级)"""
    r_bad = MagicMock(spec=requests.Response)
    r_bad.status_code = 429
    mock = MagicMock(return_value=r_bad)
    result = retry_with_backoff(mock, max_retries=3, backoff_base=0.01, jitter=0)
    assert result.status_code == 429
    assert mock.call_count == 3


def test_retry_exception_raised_after_max():
    """RequestException 重试耗尽后 raise"""
    def _boom():
        raise requests.ConnectionError("boom")
    with pytest.raises(requests.ConnectionError):
        retry_with_backoff(_boom, max_retries=2, backoff_base=0.01, jitter=0)


def test_retry_backoff_timing_exponential():
    """指数退避：3次重试 (base=0.1) 至少耗时 0.1 + 0.2 = 0.3s"""
    def _boom():
        raise requests.Timeout("t")
    start = time.time()
    with pytest.raises(requests.Timeout):
        retry_with_backoff(_boom, max_retries=3, backoff_base=0.1,
                           backoff_cap=10, jitter=0)
    elapsed = time.time() - start
    # 两次sleep: 0.1 + 0.2 = 0.3 (最后一次不sleep)
    assert elapsed >= 0.25


def test_default_retry_status_includes_429_5xx():
    assert 429 in DEFAULT_RETRY_STATUS
    assert 503 in DEFAULT_RETRY_STATUS
    assert 500 in DEFAULT_RETRY_STATUS


# ---------- Session构建 ----------

def test_build_session_with_ua_has_headers():
    s = build_session_with_ua(referer="https://example.com/")
    assert "User-Agent" in s.headers
    assert s.headers["Referer"] == "https://example.com/"
    assert s.headers["User-Agent"] in UA_POOL


def test_rotate_ua_changes_header():
    s = build_session_with_ua()
    before = s.headers["User-Agent"]
    # 尝试若干次，期望至少有1次变化 (≥5池容量, 单次概率>0.8)
    changed = False
    for _ in range(30):
        new = rotate_ua(s)
        if new != before:
            changed = True
            break
    assert changed
    assert s.headers["User-Agent"] in UA_POOL
