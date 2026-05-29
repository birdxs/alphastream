# -*- coding: utf-8 -*-
"""
Input: 临时 sqlite 引擎、构造的 MCP 信封、monkeypatch httpx
Output: WindCache/WindQuota/WindAdapter 行为断言（全 mock，不连网、不启服务）
Pos: tests/backend/unit/test_wind_budget.py - Wind P1 离线层单测

[NEW-FILE:#20260529-WIND-03]
"""
import time
import importlib

import pytest


def _make_url(tmp_path):
    return f"sqlite:///{tmp_path}/wind_cache.db"


# ───────────────────────────── WindCache ─────────────────────────────

def test_cache_set_then_get_hit(tmp_path):
    from app.core.wind_budget import WindCache
    cache = WindCache(database_url=_make_url(tmp_path))
    payload = {'name': '贵州茅台', 'pe': 20.0}
    cache.set('get_stock_basicinfo', '600519.SH', {'windcode': '600519.SH'},
              payload, ttl_seconds=3600, tier='B')
    got = cache.get('get_stock_basicinfo', '600519.SH', {'windcode': '600519.SH'})
    assert got == payload


def test_cache_get_expired_returns_none(tmp_path):
    from app.core.wind_budget import WindCache
    cache = WindCache(database_url=_make_url(tmp_path))
    cache.set('t', 'X.SH', {'a': 1}, {'v': 1}, ttl_seconds=0, tier='B')
    # ttl=0 → expires_at <= now，立即过期
    time.sleep(0.01)
    assert cache.get('t', 'X.SH', {'a': 1}) is None


def test_cache_different_params_different_key(tmp_path):
    from app.core.wind_budget import WindCache
    cache = WindCache(database_url=_make_url(tmp_path))
    cache.set('t', 'X.SH', {'a': 1}, {'v': 'one'}, ttl_seconds=3600, tier='B')
    cache.set('t', 'X.SH', {'a': 2}, {'v': 'two'}, ttl_seconds=3600, tier='B')
    assert cache.get('t', 'X.SH', {'a': 1}) == {'v': 'one'}
    assert cache.get('t', 'X.SH', {'a': 2}) == {'v': 'two'}
    # 未写过的 params → miss
    assert cache.get('t', 'X.SH', {'a': 3}) is None


def test_cache_key_order_independent(tmp_path):
    from app.core.wind_budget import WindCache
    cache = WindCache(database_url=_make_url(tmp_path))
    cache.set('t', 'X.SH', {'a': 1, 'b': 2}, {'v': 1}, ttl_seconds=3600, tier='B')
    # 参数顺序不同应命中同一 key
    assert cache.get('t', 'X.SH', {'b': 2, 'a': 1}) == {'v': 1}


# ───────────────────────────── WindQuota ─────────────────────────────

def test_quota_consume_within_budget(tmp_path, monkeypatch):
    monkeypatch.setenv('WIND_QUOTA_B', '3')
    from app.core.wind_budget import WindQuota
    q = WindQuota(database_url=_make_url(tmp_path))
    assert q.remaining()['B'] == 3
    assert q.try_consume('B') is True
    assert q.remaining()['B'] == 2
    assert q.try_consume('B') is True
    assert q.try_consume('B') is True
    assert q.remaining()['B'] == 0


def test_quota_exhausted_returns_false(tmp_path, monkeypatch):
    monkeypatch.setenv('WIND_QUOTA_A', '1')
    from app.core.wind_budget import WindQuota
    q = WindQuota(database_url=_make_url(tmp_path))
    assert q.try_consume('A') is True
    assert q.try_consume('A') is False  # 超预算
    assert q.remaining()['A'] == 0


def test_quota_tier_hard_isolation(tmp_path, monkeypatch):
    # A 耗尽不应影响 S
    monkeypatch.setenv('WIND_QUOTA_S', '5')
    monkeypatch.setenv('WIND_QUOTA_A', '1')
    monkeypatch.setenv('WIND_QUOTA_B', '2')
    from app.core.wind_budget import WindQuota
    q = WindQuota(database_url=_make_url(tmp_path))
    assert q.try_consume('A') is True
    assert q.try_consume('A') is False  # A 耗尽
    # S 不受影响
    assert q.try_consume('S') is True
    assert q.remaining()['S'] == 4
    assert q.remaining()['A'] == 0
    assert q.remaining()['B'] == 2


def test_quota_resets_across_day(tmp_path, monkeypatch):
    monkeypatch.setenv('WIND_QUOTA_B', '1')
    import app.core.wind_budget as wb
    q = wb.WindQuota(database_url=_make_url(tmp_path))
    assert q.try_consume('B') is True
    assert q.try_consume('B') is False
    # 模拟跨日：patch _today 返回新日期
    monkeypatch.setattr(q, '_today', staticmethod(lambda: '2099-01-01'))
    assert q.remaining()['B'] == 1  # 新 day 重置
    assert q.try_consume('B') is True


def test_quota_unknown_tier_rejected(tmp_path):
    from app.core.wind_budget import WindQuota
    q = WindQuota(database_url=_make_url(tmp_path))
    assert q.try_consume('Z') is False


# ───────────────────────────── WindAdapter ─────────────────────────────

def _mcp_envelope(text_payload):
    """构造一条成功的 MCP tools/call 响应（result.content[0].text 为 JSON 串）。"""
    import json as _json

    class _Resp:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    init_data = {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26"}}
    call_data = {
        "jsonrpc": "2.0", "id": 2,
        "result": {"content": [{"type": "text", "text": _json.dumps(text_payload, ensure_ascii=False)}]},
    }
    return _Resp(init_data), _Resp(call_data)


class _FakeClient:
    """替换 httpx.Client：第一次 post=initialize，第二次=tools/call。"""

    def __init__(self, init_resp, call_resp, counter):
        self._init = init_resp
        self._call = call_resp
        self._counter = counter

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, headers=None, json=None, timeout=None):
        self._counter['posts'] += 1
        method = (json or {}).get('method')
        if method == 'initialize':
            return self._init
        return self._call


def _patch_httpx(monkeypatch, text_payload, counter):
    import app.adapters.wind_adapter as wa
    init_resp, call_resp = _mcp_envelope(text_payload)

    def _client_factory(*a, **k):
        return _FakeClient(init_resp, call_resp, counter)

    monkeypatch.setattr(wa.httpx, 'Client', _client_factory)


def test_to_windcode_branches():
    from app.adapters.wind_adapter import _to_windcode
    assert _to_windcode('600519') == '600519.SH'
    assert _to_windcode('000001') == '000001.SZ'
    assert _to_windcode('300750') == '300750.SZ'
    assert _to_windcode('688981') == '688981.SH'
    assert _to_windcode('600519.SH') == '600519.SH'  # 已有后缀原样


def test_adapter_disabled_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv('WIND_API_KEY', raising=False)
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter
    ad = WindAdapter(cache=WindCache(_make_url(tmp_path)), quota=WindQuota(_make_url(tmp_path)))
    assert ad.health_check() is False
    assert ad.get_stock_info('600519') == {}
    assert ad.get_financial_data('600519') == {}
    assert ad.name == 'Wind'


def test_adapter_health_check_true_with_key(tmp_path, monkeypatch):
    monkeypatch.setenv('WIND_API_KEY', 'fake-key')
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter
    ad = WindAdapter(cache=WindCache(_make_url(tmp_path)), quota=WindQuota(_make_url(tmp_path)))
    assert ad.health_check() is True


def test_adapter_cache_miss_consumes_then_hit_no_consume(tmp_path, monkeypatch):
    monkeypatch.setenv('WIND_API_KEY', 'fake-key')
    monkeypatch.setenv('WIND_QUOTA_B', '5')
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter

    cache = WindCache(_make_url(tmp_path))
    quota = WindQuota(_make_url(tmp_path))
    counter = {'posts': 0}
    _patch_httpx(monkeypatch, {'name': '贵州茅台', 'industry': '白酒'}, counter)

    ad = WindAdapter(cache=cache, quota=quota)

    # 首次：缓存未命中 → 消费额度 → HTTP 调用 → 写缓存
    info1 = ad.get_stock_info('600519')
    assert info1 == {'name': '贵州茅台', 'industry': '白酒'}
    assert quota.remaining()['B'] == 4  # 消费 1 次
    assert counter['posts'] == 2  # initialize + tools/call

    # 二次同参：缓存命中 → 不再消费额度、不再发 HTTP
    info2 = ad.get_stock_info('600519')
    assert info2 == info1
    assert quota.remaining()['B'] == 4  # 额度未变
    assert counter['posts'] == 2  # post 次数未增


def test_adapter_quota_error_returns_none_and_degrades(tmp_path, monkeypatch):
    monkeypatch.setenv('WIND_API_KEY', 'fake-key')
    monkeypatch.setenv('WIND_QUOTA_S', '5')
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter

    cache = WindCache(_make_url(tmp_path))
    quota = WindQuota(_make_url(tmp_path))
    counter = {'posts': 0}
    # 业务信封 ok=false + QUOTA_ERROR → 降级 None
    _patch_httpx(monkeypatch, {'ok': False, 'error': {'code': 'QUOTA_ERROR'}}, counter)

    ad = WindAdapter(cache=cache, quota=quota)
    result = ad.get_financial_data('600519')
    assert result == {}  # 映射降级值
    # 额度已消耗（失败不回滚），缓存未写
    assert quota.remaining()['S'] == 4
    assert cache.get('get_stock_fundamentals', '600519.SH', {'windcode': '600519.SH'}) is None


def test_adapter_quota_exhausted_no_http(tmp_path, monkeypatch):
    monkeypatch.setenv('WIND_API_KEY', 'fake-key')
    monkeypatch.setenv('WIND_QUOTA_B', '1')
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter

    cache = WindCache(_make_url(tmp_path))
    quota = WindQuota(_make_url(tmp_path))
    counter = {'posts': 0}
    _patch_httpx(monkeypatch, {'name': 'x'}, counter)

    ad = WindAdapter(cache=cache, quota=quota)
    # 先把 B 档耗尽（用不同标的避免缓存命中）
    ad.get_stock_info('600519')
    posts_after_first = counter['posts']
    # 第二个标的：额度耗尽 → 直接降级，不再发 HTTP
    result = ad.get_stock_info('000001')
    assert result == {}
    assert counter['posts'] == posts_after_first  # 无新 HTTP


def test_adapter_index_stocks_and_history_degrade(tmp_path, monkeypatch):
    monkeypatch.setenv('WIND_API_KEY', 'fake-key')
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter
    ad = WindAdapter(cache=WindCache(_make_url(tmp_path)), quota=WindQuota(_make_url(tmp_path)))
    assert ad.get_index_stocks('000300.SH') == []
    assert ad.get_stock_history('600519', '2026-01-01', '2026-05-01') is None


# ────────────────────── P1.5 加固：并发/超时/鉴权/熔断 ──────────────────────

def test_quota_concurrent_consume_no_overshoot(tmp_path, monkeypatch):
    """20 线程抢 S 档预算：总成功数不超预算，无超扣（验证 RLock 原子性）。"""
    import threading as _t
    monkeypatch.setenv('WIND_QUOTA_S', '7')
    from app.core.wind_budget import WindQuota
    q = WindQuota(database_url=_make_url(tmp_path))

    results = []
    res_lock = _t.Lock()
    barrier = _t.Barrier(20)

    def worker():
        barrier.wait()  # 尽量同时起跑，放大竞争
        ok = q.try_consume('S')
        with res_lock:
            results.append(ok)

    threads = [_t.Thread(target=worker) for _ in range(20)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    success = sum(1 for r in results if r)
    assert success == 7, f"应恰好消费 7 次，实际 {success}"
    assert results.count(False) == 13
    assert q.remaining()['S'] == 0


def _patch_httpx_raise(monkeypatch, exc, counter):
    """替换 httpx.Client，使 tools/call（第二次 post）抛指定异常。"""
    import app.adapters.wind_adapter as wa

    class _RaisingClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None, timeout=None):
            counter['posts'] += 1
            method = (json or {}).get('method')
            if method == 'initialize':
                class _R:
                    def raise_for_status(self_inner):
                        return None

                    def json(self_inner):
                        return {"jsonrpc": "2.0", "id": 1, "result": {}}
                return _R()
            raise exc

    monkeypatch.setattr(wa.httpx, 'Client', lambda *a, **k: _RaisingClient())


def test_adapter_timeout_returns_none_no_cache(tmp_path, monkeypatch):
    """httpx.TimeoutException → _call_wind 返回 None 且不写缓存。"""
    monkeypatch.setenv('WIND_API_KEY', 'fake-key')
    monkeypatch.setenv('WIND_QUOTA_B', '5')
    import app.adapters.wind_adapter as wa
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter

    cache = WindCache(_make_url(tmp_path))
    quota = WindQuota(_make_url(tmp_path))
    counter = {'posts': 0}
    _patch_httpx_raise(monkeypatch, wa.httpx.TimeoutException('timed out'), counter)

    ad = WindAdapter(cache=cache, quota=quota)
    result = ad.get_stock_info('600519')
    assert result == {}  # 映射降级值
    assert cache.get('get_stock_basicinfo', '600519.SH', {'windcode': '600519.SH'}) is None
    assert quota.remaining()['B'] == 4  # 失败仍消耗额度（不回滚）


def test_adapter_auth_error_envelope_no_cache(tmp_path, monkeypatch):
    """AUTH_ERROR 信封 → 返回 None 且不写缓存。"""
    monkeypatch.setenv('WIND_API_KEY', 'fake-key')
    monkeypatch.setenv('WIND_QUOTA_S', '5')
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter

    cache = WindCache(_make_url(tmp_path))
    quota = WindQuota(_make_url(tmp_path))
    counter = {'posts': 0}
    _patch_httpx(monkeypatch, {'ok': False, 'error': {'code': 'AUTH_ERROR'}}, counter)

    ad = WindAdapter(cache=cache, quota=quota)
    result = ad.get_financial_data('600519')
    assert result == {}
    assert cache.get('get_stock_fundamentals', '600519.SH', {'windcode': '600519.SH'}) is None
    assert quota.remaining()['S'] == 4


def test_adapter_circuit_breaker_cooldown_no_reconsume(tmp_path, monkeypatch):
    """首次失败后冷却窗内二次调用直接降级，且 quota 未再消费、无新 HTTP。"""
    monkeypatch.setenv('WIND_API_KEY', 'fake-key')
    monkeypatch.setenv('WIND_QUOTA_B', '10')
    monkeypatch.setenv('WIND_FAIL_COOLDOWN', '300')
    import app.adapters.wind_adapter as wa
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter

    cache = WindCache(_make_url(tmp_path))
    quota = WindQuota(_make_url(tmp_path))
    counter = {'posts': 0}
    _patch_httpx_raise(monkeypatch, wa.httpx.TimeoutException('timed out'), counter)

    ad = WindAdapter(cache=cache, quota=quota)

    # 首次失败：消耗 1 次额度 + 发 HTTP（initialize + tools/call）
    assert ad.get_stock_info('600519') == {}
    posts_after_first = counter['posts']
    assert quota.remaining()['B'] == 9

    # 冷却窗内二次：直接降级，不消费额度、不发 HTTP
    assert ad.get_stock_info('600519') == {}
    assert quota.remaining()['B'] == 9  # 额度未再消费
    assert counter['posts'] == posts_after_first  # 无新 HTTP


# ─────────────────────── P2c: SSE 响应解析 ───────────────────────

def _sse_resp(jsonrpc_dict, content_type='text/event-stream'):
    """构造一个 SSE 响应对象：body 为 `event: message\r\ndata: {json}`。"""
    import json as _json

    class _SseResp:
        def __init__(self, data, ct):
            self.headers = {'content-type': ct}
            self.text = 'event: message\r\ndata: ' + _json.dumps(data, ensure_ascii=False) + '\r\n\r\n'

        def raise_for_status(self):
            return None

        def json(self):
            # SSE body 非纯 JSON，模拟真实 httpx 行为：直接 json() 抛错
            raise ValueError('Expecting value: line 1 column 1 (char 0)')

    return _SseResp(jsonrpc_dict, content_type)


def _patch_httpx_sse(monkeypatch, text_payload, counter):
    """替换 httpx.Client，使 initialize 与 tools/call 均返回 SSE 响应。"""
    import json as _json
    import app.adapters.wind_adapter as wa

    init_data = {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26"}}
    call_data = {
        "jsonrpc": "2.0", "id": 2,
        "result": {"content": [{"type": "text", "text": _json.dumps(text_payload, ensure_ascii=False)}]},
    }
    init_resp = _sse_resp(init_data)
    call_resp = _sse_resp(call_data)

    def _client_factory(*a, **k):
        return _FakeClient(init_resp, call_resp, counter)

    monkeypatch.setattr(wa.httpx, 'Client', _client_factory)


def test_adapter_sse_response_parsed(tmp_path, monkeypatch):
    """P2c：Wind MCP 以 text/event-stream（SSE）返回，adapter 应正确解析出内层财务 dict。"""
    monkeypatch.setenv('WIND_API_KEY', 'fake-key')
    monkeypatch.setenv('WIND_QUOTA_S', '5')
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter

    cache = WindCache(_make_url(tmp_path))
    quota = WindQuota(_make_url(tmp_path))
    counter = {'posts': 0}
    payload = {'pe_ttm': 20.01, 'pb': 6.11, 'roe': 10.57}
    _patch_httpx_sse(monkeypatch, payload, counter)

    ad = WindAdapter(cache=cache, quota=quota)
    result = ad.get_financial_data('600519')

    # SSE 解析成功 → 拿到非空内层财务 dict
    assert result == payload
    assert result  # 非空
    assert quota.remaining()['S'] == 4  # 消费 1 次
    assert counter['posts'] == 2  # initialize + tools/call

    # 缓存命中：二次同参不消费额度、不发 HTTP
    result2 = ad.get_financial_data('600519')
    assert result2 == result
    assert quota.remaining()['S'] == 4
    assert counter['posts'] == 2


def test_adapter_plain_json_response_no_regression(tmp_path, monkeypatch):
    """P2c 回归：非 SSE 的纯 JSON 响应（无 content-type header）仍走 resp.json()，行为不变。"""
    monkeypatch.setenv('WIND_API_KEY', 'fake-key')
    monkeypatch.setenv('WIND_QUOTA_S', '5')
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter

    cache = WindCache(_make_url(tmp_path))
    quota = WindQuota(_make_url(tmp_path))
    counter = {'posts': 0}
    payload = {'pe_ttm': 4.89, 'pb': 0.45, 'roe': 2.83}
    _patch_httpx(monkeypatch, payload, counter)  # 复用原 _Resp（无 headers → fallback json()）

    ad = WindAdapter(cache=cache, quota=quota)
    result = ad.get_financial_data('600519')

    assert result == payload
    assert result  # 非空
    assert quota.remaining()['S'] == 4
    assert counter['posts'] == 2


# ─────────────────────── P2d: 业务失败信封不缓存 + 降级 ───────────────────────

def test_adapter_business_error_envelope_not_cached(tmp_path, monkeypatch):
    """P2d：内层业务 payload 为 {'data':None,'error':{...}} 时视为失败：
    返回 {}（空 → registry 判无效回落）、不写缓存、配额仍被消费（不回滚）。"""
    monkeypatch.setenv('WIND_API_KEY', 'fake-key')
    monkeypatch.setenv('WIND_QUOTA_S', '5')
    from app.core.wind_budget import WindCache, WindQuota
    from app.adapters.wind_adapter import WindAdapter

    cache = WindCache(_make_url(tmp_path))
    quota = WindQuota(_make_url(tmp_path))
    counter = {'posts': 0}
    err_envelope = {'data': None, 'error': {'code': 'invalid_param_name',
                                            'message': '缺少必填参数: question'}}
    _patch_httpx_sse(monkeypatch, err_envelope, counter)

    ad = WindAdapter(cache=cache, quota=quota)
    windcode = '000001.SZ'
    result = ad.get_financial_data('000001')

    # 1) 降级为空 dict（registry 判无效自动回落）
    assert result == {}
    # 2) 缓存未写入（污染防护）
    assert cache.get('get_stock_fundamentals', windcode, {'windcode': windcode}) is None
    # 3) 配额仍被消费一次（HTTP 已实际发出，不回滚）
    assert quota.remaining()['S'] == 4
    assert counter['posts'] == 2  # initialize + tools/call

    # 4) 持久 param 错误 → 进熔断冷却：二次调用不再消费额度、不发 HTTP
    result2 = ad.get_financial_data('000001')
    assert result2 == {}
    assert quota.remaining()['S'] == 4  # 未再扣
    assert counter['posts'] == 2  # 无新 HTTP


def test_is_business_error_classification():
    """P2d：_is_business_error 边界——失败信封识别为 True，正常数据为 False。"""
    from app.adapters.wind_adapter import WindAdapter
    f = WindAdapter._is_business_error
    assert f({'data': None, 'error': {'code': 'x'}}) is True   # data=None+error
    assert f({'data': [1, 2], 'error': {'code': 'x'}}) is True  # truthy error
    assert f({'data': None, 'error': None}) is False            # error 为 None → 无错误
    assert f({'data': [1, 2], 'error': None}) is False          # 正常成功
    assert f({'pe_ttm': 20.0, 'pb': 6.1}) is False              # 普通财务 dict
    assert f([1, 2, 3]) is False                                # 非 dict
