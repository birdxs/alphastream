"""
Input: HTTP GET /api/health/deep，可选 patch 模块级 _hd_check_* 函数
Output: JSON {status, uptime_s, version, checks, elapsed_ms}，HTTP 200（含 degraded）
Pos: S3-K Critical 修复专项测试 — health_deep TimeoutError 兜底验证

S3-K：/api/health/deep TimeoutError 兜底 [NEW-FILE:#20260520-S3K]
覆盖三条路径：
  1. 正常调用 → 200 + status in (ok, degraded)
  2. 单 check 抛 RuntimeError → 200 + degraded + error=True
  3. 单 check 超时（sleep > _DEEP_TIMEOUT） → 200 + timeout=True 或 ok=False
"""

from __future__ import annotations

import time

import pytest

pytestmark = [pytest.mark.api, pytest.mark.unit]


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _stub_heavy_checks(monkeypatch):
    """默认将所有耗时/网络 check 替换为即时 stub，隔离外部依赖。"""
    import app.web.web_server as ws

    monkeypatch.setattr(ws, '_hd_check_sqlite', lambda: {'ok': True, 'latency_ms': 0.1})
    monkeypatch.setattr(ws, '_hd_check_akshare', lambda: {'ok': True, 'skipped': True, 'reason': 'stub'})
    monkeypatch.setattr(ws, '_hd_check_llm', lambda: {'ok': True, 'skipped': True, 'reason': 'MOCK_LLM=1'})
    monkeypatch.setattr(ws, '_hd_check_market_cache', lambda: {'ok': True, 'age_s': 1.0, 'ttl_s': 30, 'has_data': True})


# ── S3-K1：正常情况返回 200 + 合法 status ────────────────────────────────────

def test_health_deep_returns_200_under_normal_conditions(flask_client):
    """正常情况下返回 HTTP 200，status 为 ok 或 degraded，checks 包含四个子项。"""
    r = flask_client.get('/api/health/deep')
    assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.data}'
    body = r.get_json()
    assert body.get('status') in ('ok', 'degraded'), f"Unexpected status: {body.get('status')}"
    assert 'checks' in body
    assert 'sqlite' in body['checks']
    assert 'elapsed_ms' in body


# ── S3-K2：单 check 抛异常 → 200 + degraded ─────────────────────────────────

def test_health_deep_returns_200_when_check_raises(flask_client, monkeypatch):
    """单个 check 函数抛 RuntimeError 时：HTTP 200 + status=degraded + error=True，不冒泡 500。"""
    import app.web.web_server as ws

    monkeypatch.setattr(ws, '_hd_check_sqlite', lambda: (_ for _ in ()).throw(RuntimeError('simulated sqlite error')))

    r = flask_client.get('/api/health/deep')
    assert r.status_code == 200, f'Expected 200 after exception, got {r.status_code}: {r.data}'
    body = r.get_json()
    assert body.get('status') == 'degraded', f"Expected degraded, got: {body.get('status')}"
    sqlite_check = body.get('checks', {}).get('sqlite', {})
    assert sqlite_check.get('error') is True or sqlite_check.get('ok') is False, (
        f'sqlite check should be error/failed, got: {sqlite_check}'
    )


# ── S3-K3：单 check 超时 → 200 + timeout 标记 ───────────────────────────────

def test_health_deep_returns_200_when_check_times_out(flask_client, monkeypatch):
    """单个 check 超时（sleep 远超 HEALTH_DEEP_TIMEOUT_S）：HTTP 200 + timeout=True 或 ok=False，不冒泡 500。"""
    import app.web.web_server as ws

    # 设置极短总超时 0.3s，确保 sleep(5) 的 check 一定超时
    monkeypatch.setenv('HEALTH_DEEP_TIMEOUT_S', '0.3')

    def _slow_akshare():
        time.sleep(5)  # 远超 0.3s
        return {'ok': True}

    monkeypatch.setattr(ws, '_hd_check_akshare', _slow_akshare)

    r = flask_client.get('/api/health/deep')
    assert r.status_code == 200, f'Expected 200 after timeout, got {r.status_code}: {r.data}'
    body = r.get_json()
    akshare = body.get('checks', {}).get('akshare', {})
    assert akshare.get('timeout') is True or akshare.get('ok') is False, (
        f'akshare check should be timeout/failed, got: {akshare}'
    )
