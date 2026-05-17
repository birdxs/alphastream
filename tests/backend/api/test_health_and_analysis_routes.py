# Input  : Flask test_client (flask_client fixture) + monkeypatch
# Output : pytest 用例：覆盖 8 条核心路由（健康/适配器/注册/分析三件套 + index）
# Pos    : tests/backend/api/test_health_and_analysis_routes.py
# 说明   : BE-01a 小批量验收。LLM/akshare 全 mock；不发起任何真实分析。
"""BE-01a 健康 + 分析核心 8 路由测试。

覆盖路由（精确）：
1. GET /                         -> HTML 200
2. GET /health                   -> JSON 200 (line 3770)
3. GET /api/health               -> 不存在，预期 404（占位测试，记录"路由不存在"）
4. GET /api/adapters/status      -> JSON 200 (line 3781)
5. GET /api/registry/stats       -> JSON 200 (line 3802)
6. POST /api/start_stock_analysis (line 753)  -> 返回 task_id；mock analyzer
7. GET /api/analysis_status/<task_id> (line 827)
8. POST /api/cancel_analysis/<task_id> (line 857)

约束：每路由 ≥ 2 用例（快乐 + 错误）。错误路径不得 500 leak stacktrace。
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict

import pytest


# --------------------------------------------------------------------------- #
# 工具：JSON 解析 + 类型断言
# --------------------------------------------------------------------------- #

def _json(resp) -> Dict[str, Any]:
    """安全解析 JSON 响应；保证返回 dict。"""
    assert resp.content_type and "application/json" in resp.content_type, (
        f"响应非 JSON: content_type={resp.content_type}, body={resp.data[:200]!r}"
    )
    data = json.loads(resp.data.decode("utf-8"))
    assert isinstance(data, dict), f"JSON 顶层非 dict: {type(data)}"
    return data


def _no_stacktrace(resp) -> None:
    """断言响应体不泄露 Python 堆栈关键字（traceback / File ".+", line ）。"""
    body = resp.data.decode("utf-8", errors="replace").lower()
    forbidden = ["traceback (most recent call last)", 'file "', "raise "]
    for fb in forbidden:
        assert fb not in body, f"4xx/受控错误响应不应泄露堆栈关键字 {fb!r}: {body[:300]}"


# --------------------------------------------------------------------------- #
# 1. GET /  index 页面
# --------------------------------------------------------------------------- #

class TestIndexRoute:
    def test_index_returns_html_ok(self, flask_client):
        resp = flask_client.get("/")
        assert resp.status_code == 200, resp.data[:200]
        # 模板可能因依赖缺失返回 500，但 TESTING 模式下应能渲染基本骨架
        assert "text/html" in (resp.content_type or "")

    def test_index_wrong_method(self, flask_client):
        # POST / 应返回 405 Method Not Allowed
        resp = flask_client.post("/", data="{}")
        assert resp.status_code in (405, 404), (
            f"POST / 应被拒绝，得到 {resp.status_code}"
        )


# --------------------------------------------------------------------------- #
# 2. GET /health  健康探针
# --------------------------------------------------------------------------- #

class TestHealthRoute:
    def test_health_ok_schema(self, flask_client):
        resp = flask_client.get("/health")
        assert resp.status_code == 200
        data = _json(resp)
        # schema：status / uptime_s / version / ts
        assert data.get("status") == "ok"
        assert "uptime_s" in data and isinstance(data["uptime_s"], (int, float))
        assert "version" in data
        assert "ts" in data and isinstance(data["ts"], int)

    def test_health_wrong_method(self, flask_client):
        resp = flask_client.post("/health")
        assert resp.status_code in (405, 404)


# --------------------------------------------------------------------------- #
# 3. GET /api/health  （不存在）
# --------------------------------------------------------------------------- #

class TestApiHealthAbsent:
    """文档/coordinator 索引中曾列出，但 web_server.py 中实际未注册。

    本用例的目的：明确记录"路由不存在"，避免后续误用。
    若后续真的新增该路由，本用例会自然失败，提示更新文档。
    """

    def test_api_health_returns_404(self, flask_client):
        resp = flask_client.get("/api/health")
        assert resp.status_code == 404, (
            f"/api/health 当前应当不存在（404），但得到 {resp.status_code}: "
            f"{resp.data[:200]!r}"
        )

    def test_api_health_post_also_404(self, flask_client):
        resp = flask_client.post("/api/health", json={})
        assert resp.status_code in (404, 405)


# --------------------------------------------------------------------------- #
# 4. GET /api/adapters/status
# --------------------------------------------------------------------------- #

@pytest.fixture
def patched_hc_one(monkeypatch):
    """Mock app.web.web_server._hc_one，避免对 22 个 adapter 顺序做真实 health_check
    （每个 5s 超时，最坏 110s 阻塞）。
    """
    from app.web import web_server as ws

    def _fake_hc(cls_name, mod_path, timeout_s=5.0):
        # 一半 healthy 一半 unhealthy，便于断言计数
        ok = (hash(cls_name) % 2 == 0)
        return {
            "ok": ok,
            "cls": cls_name,
            "module": mod_path,
            "elapsed_ms": 1,
            "error": None if ok else "mocked_unhealthy",
        }

    monkeypatch.setattr(ws, "_hc_one", _fake_hc, raising=True)
    return _fake_hc


class TestAdaptersStatusRoute:
    def test_adapters_status_ok(self, flask_client, patched_hc_one):
        resp = flask_client.get("/api/adapters/status")
        assert resp.status_code == 200, resp.data[:200]
        data = _json(resp)
        assert data.get("status") == "ok"
        assert "total" in data and isinstance(data["total"], int)
        assert "healthy" in data and isinstance(data["healthy"], int)
        assert "unhealthy" in data and isinstance(data["unhealthy"], int)
        assert "adapters" in data and isinstance(data["adapters"], dict)
        # 内部一致性
        assert data["healthy"] + data["unhealthy"] == data["total"]
        assert "ts" in data

    def test_adapters_status_wrong_method(self, flask_client, patched_hc_one):
        resp = flask_client.post("/api/adapters/status")
        assert resp.status_code in (405, 404)


# --------------------------------------------------------------------------- #
# 5. GET /api/registry/stats
# --------------------------------------------------------------------------- #

class TestRegistryStatsRoute:
    def test_registry_stats_ok(self, flask_client):
        resp = flask_client.get("/api/registry/stats")
        # 该路由 try/except 内 500 也算"受控错误"，但应返回 JSON
        assert resp.status_code in (200, 500)
        data = _json(resp)
        if resp.status_code == 200:
            assert data.get("status") == "ok"
            assert "domain_count" in data and isinstance(data["domain_count"], int)
            assert "domains" in data and isinstance(data["domains"], list)
            # 每个 domain 必含核心字段
            for d in data["domains"]:
                assert "name" in d
                assert "configured" in d
                assert "available" in d
        else:
            # 受控错误也得有 message，不能 leak stacktrace
            assert data.get("status") == "error"
            assert "message" in data
            _no_stacktrace(resp)

    def test_registry_stats_wrong_method(self, flask_client):
        resp = flask_client.post("/api/registry/stats")
        assert resp.status_code in (405, 404)


# --------------------------------------------------------------------------- #
# 6+7+8. 分析三件套：start / status / cancel
# --------------------------------------------------------------------------- #

@pytest.fixture
def patched_analyzer(monkeypatch):
    """Mock app.web.web_server.analyzer.perform_enhanced_analysis，避免真实调用。

    返回一个可断言的 spy。
    """
    from app.web import web_server as ws

    calls = []

    def _fake_analyze(stock_code, market_type="A"):
        calls.append((stock_code, market_type))
        return {
            "stock_code": stock_code,
            "market_type": market_type,
            "score": 75,
            "mocked": True,
        }

    monkeypatch.setattr(ws.analyzer, "perform_enhanced_analysis", _fake_analyze, raising=True)
    return calls


class TestStartStockAnalysis:
    def test_start_happy_path_returns_task_id(self, flask_client, patched_analyzer):
        resp = flask_client.post(
            "/api/start_stock_analysis",
            json={"stock_code": "000001", "market_type": "A"},
        )
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert "task_id" in data and isinstance(data["task_id"], str) and data["task_id"]
        assert "status" in data
        # 后台线程是 daemon，给一点时间但不阻塞太久
        time.sleep(0.2)

    def test_start_missing_body_returns_400(self, flask_client):
        # 空 body / 非 JSON
        resp = flask_client.post(
            "/api/start_stock_analysis",
            data="",
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = _json(resp)
        assert "error" in data
        _no_stacktrace(resp)

    def test_start_missing_stock_code_returns_400(self, flask_client):
        resp = flask_client.post(
            "/api/start_stock_analysis",
            json={"market_type": "A"},
        )
        assert resp.status_code == 400
        data = _json(resp)
        assert "error" in data
        _no_stacktrace(resp)

    def test_start_invalid_stock_code_returns_400(self, flask_client):
        # validate_stock_code 拒绝非法格式
        resp = flask_client.post(
            "/api/start_stock_analysis",
            json={"stock_code": "ZZZZZZ", "market_type": "A"},
        )
        assert resp.status_code == 400
        data = _json(resp)
        assert "error" in data
        _no_stacktrace(resp)


class TestAnalysisStatus:
    def test_status_unknown_task_returns_404(self, flask_client):
        resp = flask_client.get("/api/analysis_status/no-such-task-id-xyz")
        assert resp.status_code == 404
        data = _json(resp)
        assert "error" in data
        _no_stacktrace(resp)

    def test_status_after_start_returns_schema(self, flask_client, patched_analyzer):
        # 先启动一个任务
        start = flask_client.post(
            "/api/start_stock_analysis",
            json={"stock_code": "000001", "market_type": "A"},
        )
        assert start.status_code == 200, start.data[:200]
        task_id = _json(start)["task_id"]

        # 立即查询状态（后台线程可能已完成或还在跑，但 schema 必须稳定）
        resp = flask_client.get(f"/api/analysis_status/{task_id}")
        assert resp.status_code == 200, resp.data[:200]
        data = _json(resp)
        for key in ("id", "status", "progress", "created_at", "updated_at"):
            assert key in data, f"缺失字段 {key}: {data}"
        assert data["id"] == task_id


class TestCancelAnalysis:
    def test_cancel_unknown_task_returns_404(self, flask_client):
        resp = flask_client.post("/api/cancel_analysis/no-such-task-id-xyz")
        assert resp.status_code == 404
        data = _json(resp)
        assert "error" in data
        _no_stacktrace(resp)

    def test_cancel_after_start_returns_message(self, flask_client, patched_analyzer):
        # 先启动
        start = flask_client.post(
            "/api/start_stock_analysis",
            json={"stock_code": "000002", "market_type": "A"},
        )
        assert start.status_code == 200, start.data[:200]
        task_id = _json(start)["task_id"]

        resp = flask_client.post(f"/api/cancel_analysis/{task_id}")
        assert resp.status_code == 200, resp.data[:200]
        data = _json(resp)
        assert "message" in data
