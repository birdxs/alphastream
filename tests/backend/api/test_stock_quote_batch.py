"""
Input: /api/stock_quote_batch 端点
Output: pytest 用例 — 覆盖参数校验、批量返回结构、错误兜底
Pos: tests/backend/api/test_stock_quote_batch.py — FIX-E5 新增
"""
import pandas as pd
import pytest


@pytest.fixture
def patch_analyzer(monkeypatch, flask_app):
    """劫持 analyzer.get_stock_data + _get_stock_name_safe，避免外部网络。"""
    from app.web import web_server as ws

    def fake_get(code, market_type, start_date, end_date):
        # 7 根 K，末两根 close=100/110 → change_pct=10%
        return pd.DataFrame({
            "open": [95, 96, 97, 98, 99, 100, 110],
            "close": [96, 97, 98, 99, 100, 100, 110],
            "high": [97, 98, 99, 100, 101, 101, 111],
            "low": [94, 95, 96, 97, 98, 99, 109],
        })

    monkeypatch.setattr(ws.analyzer, "get_stock_data", fake_get)
    monkeypatch.setattr(ws, "_get_stock_name_safe", lambda c, m='A': f"NAME-{c}")
    # 清空 flask_caching 缓存避免上一次测试残留
    try:
        ws.cache.clear()
    except Exception:
        pass
    return ws


def test_batch_missing_codes(flask_client):
    resp = flask_client.get("/api/stock_quote_batch")
    assert resp.status_code == 400
    assert "codes" in resp.get_json()["error"]


def test_batch_empty_codes(flask_client):
    resp = flask_client.get("/api/stock_quote_batch?codes=,,,")
    assert resp.status_code == 400


def test_batch_too_many_codes(flask_client):
    # [REAL-01 2026-05-18] 上限已提升到 100；发送 101 个代码触发 400
    codes = ",".join([str(600000 + i) for i in range(101)])
    resp = flask_client.get(f"/api/stock_quote_batch?codes={codes}")
    assert resp.status_code == 400


def test_batch_happy_path(flask_client, patch_analyzer):
    resp = flask_client.get("/api/stock_quote_batch?codes=600519,000001")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "results" in body and "errors" in body and "ts" in body
    codes_seen = {r["code"] for r in body["results"]}
    # validate_stock_code 会做 normalization；至少返回了 2 个结果
    assert len(body["results"]) == 2
    for r in body["results"]:
        assert "latest_price" in r
        assert "change_pct" in r
        assert r["latest_price"] == 110
        # (110-100)/100 = 10%
        assert abs(r["change_pct"] - 10.0) < 1e-6


def test_batch_partial_error_isolated(flask_client, monkeypatch, flask_app):
    """单只失败不应影响其他股票返回。"""
    from app.web import web_server as ws

    def fake_get(code, market_type, start_date, end_date):
        if "000001" in code:
            raise RuntimeError("simulated adapter failure")
        return pd.DataFrame({
            "open": [10, 11],
            "close": [10, 11],
            "high": [12, 12],
            "low": [9, 10],
        })

    monkeypatch.setattr(ws.analyzer, "get_stock_data", fake_get)
    monkeypatch.setattr(ws, "_get_stock_name_safe", lambda c, m='A': "Z")
    try:
        ws.cache.clear()
    except Exception:
        pass
    resp = flask_client.get("/api/stock_quote_batch?codes=600519,000001")
    assert resp.status_code == 200
    body = resp.get_json()
    # 一只成功 + 一只 error
    assert len(body["results"]) >= 1
    assert len(body["errors"]) >= 1
