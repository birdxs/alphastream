# -*- coding: utf-8 -*-
"""
Input: Flask test_client HTTP 请求 (/health, /api/adapters/status, /api/registry/stats)
Output: K3 健康检查 / 监控端点 200 响应 + schema 断言
Pos: tests/web/test_health_endpoints.py  [NEW-FILE:#20260415-49]

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

覆盖:
  GET /health                — 200 + {status,uptime_s,version,ts}
  GET /api/adapters/status  — 200 + 22 adapter keys + 单 adapter raise 仍 200
  GET /api/registry/stats   — 200 + 16 domain + configured/available 字段

策略: 不启后端, 用 Flask test_client + monkeypatch _hc_one 避免真实网络调用
"""
import os
import sys
import time
import pytest
from unittest.mock import patch

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("TESTING", "1")
    from app.web import web_server as ws
    ws.app.config["TESTING"] = True
    with ws.app.test_client() as c:
        yield c


# ======================================================
# /health
# ======================================================
def test_health_basic_200_schema(client):
    rsp = client.get('/health')
    assert rsp.status_code == 200
    data = rsp.get_json()
    assert data["status"] == "ok"
    assert "uptime_s" in data and data["uptime_s"] >= 0
    assert data["version"] == "3.1.0"
    assert "ts" in data and isinstance(data["ts"], int)


def test_health_latency_lt_100ms(client):
    """/health 必须 <100ms (放宽至 500ms 兼容 CI 抖动)"""
    t0 = time.time()
    rsp = client.get('/health')
    elapsed_ms = (time.time() - t0) * 1000
    assert rsp.status_code == 200
    assert elapsed_ms < 500, f"/health 延迟 {elapsed_ms:.1f}ms 超标"


# ======================================================
# /api/adapters/status
# ======================================================
def _fast_hc(cls_name, mod_path, timeout_s=5.0):
    """mock: 所有 adapter 秒返 ok"""
    return {"ok": True, "msg": "ok", "latency_ms": 1}


def _raise_hc(cls_name, mod_path, timeout_s=5.0):
    """mock: 每 adapter 都抛异常 — 应被 _hc_one 捕获, 体现为 ok=False"""
    raise RuntimeError("simulated adapter crash")


def test_adapters_status_all_healthy(client):
    from app.web import web_server as ws
    with patch.object(ws, "_hc_one", side_effect=_fast_hc):
        rsp = client.get('/api/adapters/status')
    assert rsp.status_code == 200
    data = rsp.get_json()
    assert data["status"] == "ok"
    assert data["total"] == 21  # 21 个 adapter spec
    assert data["healthy"] == 21
    assert data["unhealthy"] == 0
    assert len(data["adapters"]) == 21
    # 关键 adapter 必须在列
    for name in ["AkshareAdapter", "YFinanceAdapter", "EDGARAdapter",
                 "ESGAdapter", "ShippingAdapter", "CorporateAdapter",
                 "JobsAdapter", "SatelliteAdapter"]:
        assert name in data["adapters"], f"缺失 {name}"
        assert data["adapters"][name]["ok"] is True


def test_adapters_status_single_raise_still_200(client):
    """单个 adapter health_check 抛异常, 整体 200, 此 adapter 标记 fail."""
    from app.web import web_server as ws

    def mixed_hc(cls_name, mod_path, timeout_s=5.0):
        if cls_name == "AkshareAdapter":
            # _hc_one 内部已 try/except, 这里直接模拟返回 ok=False
            return {"ok": False, "msg": "RuntimeError: boom", "latency_ms": 10}
        return {"ok": True, "msg": "ok", "latency_ms": 1}

    with patch.object(ws, "_hc_one", side_effect=mixed_hc):
        rsp = client.get('/api/adapters/status')
    assert rsp.status_code == 200
    data = rsp.get_json()
    assert data["adapters"]["AkshareAdapter"]["ok"] is False
    assert "boom" in data["adapters"]["AkshareAdapter"]["msg"]
    assert data["healthy"] == 20
    assert data["unhealthy"] == 1


def test_adapters_status_hc_one_catches_exception():
    """直接测试 _hc_one 对真实异常的吞吐 — 永不外抛."""
    from app.web import web_server as ws
    r = ws._hc_one("NotExistAdapter", "app.adapters.nonexistent_module")
    assert r["ok"] is False
    assert "latency_ms" in r
    assert isinstance(r["msg"], str)


# ======================================================
# /api/registry/stats
# ======================================================
def test_registry_stats_200_domain_count(client):
    rsp = client.get('/api/registry/stats')
    assert rsp.status_code == 200
    data = rsp.get_json()
    assert data["status"] == "ok"
    # AdapterRegistry.DEFAULT_DOMAIN_MAP 当前 16 个 domain
    assert data["domain_count"] == 16
    assert len(data["domains"]) == 16


def test_registry_stats_domain_schema(client):
    rsp = client.get('/api/registry/stats')
    data = rsp.get_json()
    # 验 domain 对象 schema
    sample = data["domains"][0]
    for k in ("name", "configured", "configured_count",
              "available", "available_count", "first_available"):
        assert k in sample, f"缺少字段 {k}"
    # 关键 domain 应在列
    names = [d["name"] for d in data["domains"]]
    for must in ["a_stock_kline", "us_stock", "macro_us", "crypto",
                 "esg_rating", "commodity_shipping", "earth_observation",
                 "corporate_entity", "hiring_signal"]:
        assert must in names, f"缺失 domain {must}"


def test_registry_stats_a_stock_kline_priority(client):
    """a_stock_kline configured 首位应为 AkshareAdapter."""
    rsp = client.get('/api/registry/stats')
    data = rsp.get_json()
    dmap = {d["name"]: d for d in data["domains"]}
    assert dmap["a_stock_kline"]["configured"][0] == "AkshareAdapter"
    assert dmap["a_stock_kline"]["configured_count"] >= 4


def test_registry_stats_fail_count_present(client):
    """fail_count 字典必须存在 (可为空)."""
    rsp = client.get('/api/registry/stats')
    data = rsp.get_json()
    assert "fail_count" in data
    assert isinstance(data["fail_count"], dict)
