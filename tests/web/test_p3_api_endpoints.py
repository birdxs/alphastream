# -*- coding: utf-8 -*-
"""
Input: Flask test_client HTTP请求 + mocked AdapterRegistry.call_with_fallback
Output: F3 P3 API端点 200/400/500 响应断言
Pos: tests/web/test_p3_api_endpoints.py  [NEW-FILE:#20260415-36]

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

覆盖端点 (10个):
  GET /api/shipping/bdi
  GET /api/shipping/port/<port>
  GET /api/esg/<ticker>
  GET /api/esg/climate/<cik>
  GET /api/corporate/search
  GET /api/corporate/<company_id>/network
  GET /api/jobs/search
  GET /api/jobs/company/<company>
  GET /api/satellite/search
  GET /api/alt_data/<ticker>

策略: 不真实启动Flask，用test_client + mock AdapterRegistry._p3_call_with_timeout
"""
import os
import sys
import json
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# 项目根加入sys.path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


@pytest.fixture(scope="module")
def client():
    """Flask test_client fixture."""
    os.environ.setdefault("TESTING", "1")
    from app.web import web_server as ws
    ws.app.config["TESTING"] = True
    with ws.app.test_client() as c:
        yield c


def _patch_call(return_value=None, side_effect=None):
    """替换 _p3_call_with_timeout 的 context manager 工厂."""
    from app.web import web_server as ws
    m = MagicMock()
    if side_effect is not None:
        m.side_effect = side_effect
    else:
        m.return_value = return_value
    return patch.object(ws, "_p3_call_with_timeout", m)


# ======================================================
# Shipping
# ======================================================
def test_shipping_bdi_happy(client):
    df = pd.DataFrame([{"date": "2026-04-14", "bdi": 1500}, {"date": "2026-04-15", "bdi": 1520}])
    with _patch_call(return_value=df):
        r = client.get("/api/shipping/bdi?days=10")
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["artifact"]["artifact_type"] == "shipping_bdi"
    assert data["artifact"]["data"]["count"] == 2


def test_shipping_bdi_invalid_days(client):
    r = client.get("/api/shipping/bdi?days=abc")
    assert r.status_code == 400
    assert r.get_json()["success"] is False


def test_shipping_bdi_out_of_range(client):
    r = client.get("/api/shipping/bdi?days=9999")
    assert r.status_code == 400


def test_shipping_bdi_upstream_error(client):
    with _patch_call(side_effect=Exception("upstream dead")):
        r = client.get("/api/shipping/bdi?days=30")
    assert r.status_code == 500
    assert "upstream dead" in r.get_json()["error"]


def test_shipping_port_happy(client):
    df = pd.DataFrame([{"month": "2026-03", "throughput": 12345}])
    with _patch_call(return_value=df):
        r = client.get("/api/shipping/port/shanghai?period=monthly")
    assert r.status_code == 200
    assert r.get_json()["artifact"]["artifact_type"] == "shipping_port"


def test_shipping_port_bad_period(client):
    r = client.get("/api/shipping/port/shanghai?period=weekly")
    assert r.status_code == 400


# ======================================================
# ESG
# ======================================================
def test_esg_score_happy(client):
    with _patch_call(return_value={"ticker": "AAPL", "score": 78, "grade": "A"}):
        r = client.get("/api/esg/AAPL")
    assert r.status_code == 200
    payload = r.get_json()
    assert payload["artifact"]["artifact_type"] == "esg_score"
    assert payload["artifact"]["data"]["score"] == 78


def test_esg_climate_happy(client):
    with _patch_call(return_value={"cik": "0000320193", "climate_items": []}):
        r = client.get("/api/esg/climate/0000320193")
    assert r.status_code == 200
    assert r.get_json()["artifact"]["artifact_type"] == "esg_climate"


def test_esg_score_upstream_fail(client):
    with _patch_call(side_effect=Exception("esg api down")):
        r = client.get("/api/esg/AAPL")
    assert r.status_code == 500


# ======================================================
# Corporate
# ======================================================
def test_corporate_search_happy(client):
    with _patch_call(return_value=[{"name": "Apple Inc"}, {"name": "Apple Bank"}]):
        r = client.get("/api/corporate/search?q=Apple")
    assert r.status_code == 200
    data = r.get_json()["artifact"]["data"]
    assert data["count"] == 2


def test_corporate_search_missing_q(client):
    r = client.get("/api/corporate/search")
    assert r.status_code == 400


def test_corporate_network_happy(client):
    with _patch_call(return_value={"nodes": [{"id": "c1"}], "edges": []}):
        r = client.get("/api/corporate/us_123/network")
    assert r.status_code == 200
    assert r.get_json()["artifact"]["artifact_type"] == "corporate_network"


# ======================================================
# Jobs
# ======================================================
def test_jobs_search_happy(client):
    df = pd.DataFrame([{"title": "Python Dev", "company": "X"}])
    with _patch_call(return_value=df):
        r = client.get("/api/jobs/search?q=python&limit=5")
    assert r.status_code == 200
    assert r.get_json()["artifact"]["data"]["count"] == 1


def test_jobs_search_bad_limit(client):
    r = client.get("/api/jobs/search?q=python&limit=xyz")
    assert r.status_code == 400


def test_jobs_company_happy(client):
    df = pd.DataFrame([{"title": "SWE"}])
    with _patch_call(return_value=df):
        r = client.get("/api/jobs/company/Tesla")
    assert r.status_code == 200


# ======================================================
# Satellite
# ======================================================
def test_satellite_search_happy(client):
    with _patch_call(return_value={"datasets": [{"id": "MODIS"}]}):
        r = client.get("/api/satellite/search?q=ndvi")
    assert r.status_code == 200


def test_satellite_search_missing_q(client):
    r = client.get("/api/satellite/search")
    assert r.status_code == 400


# ======================================================
# Alt Data aggregate
# ======================================================
def test_alt_data_happy(client):
    """4个域全部成功"""
    from app.web import web_server as ws

    def fake_call(domain, method, timeout=20, **kw):
        if domain == "commodity_shipping":
            return pd.DataFrame([{"date": "2026-04-15", "bdi": 1500}])
        if domain == "esg_rating":
            return {"ticker": kw.get("ticker"), "score": 80}
        if domain == "hiring_signal":
            return pd.DataFrame([{"title": "Eng"}])
        if domain == "corporate_entity":
            return [{"name": "Tesla Inc"}]
        raise ValueError(domain)

    with patch.object(ws, "_p3_call_with_timeout", side_effect=fake_call):
        r = client.get("/api/alt_data/TSLA")
    assert r.status_code == 200
    art = r.get_json()["artifact"]
    assert art["artifact_type"] == "alt_data_aggregate"
    assert art["metadata"]["coverage"] == "4/4"


def test_alt_data_all_fail(client):
    from app.web import web_server as ws

    def fake_call(domain, method, timeout=20, **kw):
        raise Exception(f"{domain} down")

    with patch.object(ws, "_p3_call_with_timeout", side_effect=fake_call):
        r = client.get("/api/alt_data/TSLA")
    assert r.status_code == 502
    body = r.get_json()
    assert body["success"] is False
    assert "details" in body


def test_alt_data_invalid_ticker(client):
    r = client.get("/api/alt_data/" + "X" * 30)
    assert r.status_code == 400
