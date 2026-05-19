"""
Input: HTTP GET 请求至 /health、/.well-known/agent-card.json、
       /.well-known/agent.json、/api/adapters/status、/api/registry/stats、
       /api/active_tasks。
Output: JSON 健康/元信息响应。
Pos: BE-01 后端路由全覆盖测试 - 健康与元信息域。

W2-BE01 后端路由测试 / 健康与元信息域。
覆盖：核心健康探针 + AgentCard 标准发现端点 + adapter/registry 状态 + 活跃任务。
注意：任务文档原列 `/api/agent/health` 与 `/api/health`，实际路由不存在，已按真实路由清单替换。
"""

from __future__ import annotations

import pytest


pytestmark = [pytest.mark.api, pytest.mark.unit]


@pytest.fixture(autouse=True)
def _mock_hc_one(monkeypatch):
    """阻止 /api/adapters/status 触发真实外网 adapter health_check（baostock socket 无超时上限）。
    _hc_one 替换为立即返回 ok=True 的 stub，保证路由/响应结构测试不被网络阻塞。
    """
    import app.web.web_server as ws
    monkeypatch.setattr(ws, "_hc_one", lambda cls_name, mod_path, timeout_s=5.0: {
        "ok": True, "msg": "mock", "latency_ms": 0
    })


# ---------------------------------------------------------------------------
# /health (核心健康探针)
# ---------------------------------------------------------------------------


def test_health_happy_returns_ok(flask_client):
    """快乐路径：/health 始终 200 + status=ok。"""
    resp = flask_client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body is not None
    assert body.get("status") == "ok"
    assert "ts" in body
    assert "uptime_s" in body
    assert body.get("version")


def test_health_method_not_allowed_post(flask_client):
    """入参校验：POST /health 应返回 405。"""
    resp = flask_client.post("/health")
    assert resp.status_code == 405


def test_health_response_no_stacktrace(flask_client):
    """响应脱敏：不得泄露 stacktrace/绝对路径。"""
    resp = flask_client.get("/health")
    body_text = resp.get_data(as_text=True)
    assert "Traceback" not in body_text
    assert "/Users/" not in body_text
    assert "/home/" not in body_text


def test_health_latency_under_500ms(flask_client):
    """性能：/health <500ms（CI 抖动容忍）。"""
    import time

    t0 = time.time()
    resp = flask_client.get("/health")
    dt = time.time() - t0
    assert resp.status_code == 200
    assert dt < 0.5, f"/health 延迟 {dt:.3f}s 超阈值"


# ---------------------------------------------------------------------------
# AgentCard 端点（A2A 标准发现）
# ---------------------------------------------------------------------------


def test_agent_card_well_known_returns_valid_card(flask_client):
    """A2A v1.0：/.well-known/agent-card.json 必填字段齐全。"""
    resp = flask_client.get("/.well-known/agent-card.json")
    assert resp.status_code == 200
    card = resp.get_json()
    assert card is not None
    for field in ("name", "description", "url", "version", "capabilities", "skills"):
        assert field in card, f"AgentCard 缺失必填字段 {field}"
    assert isinstance(card["skills"], list) and card["skills"], "skills 至少 1 个"
    assert card.get("_stub") is True, "当前为 stub 实现，标记必须保留"


def test_agent_card_legacy_alias_matches(flask_client):
    """向后兼容：/.well-known/agent.json 与新路径同构。"""
    new = flask_client.get("/.well-known/agent-card.json").get_json()
    legacy = flask_client.get("/.well-known/agent.json").get_json()
    assert new is not None and legacy is not None
    assert new["name"] == legacy["name"]
    assert new["skills"] == legacy["skills"]


def test_agent_card_skill_schema(flask_client):
    """A2A Skill schema：每个 skill 应有 id/name/description/tags。"""
    card = flask_client.get("/.well-known/agent-card.json").get_json()
    for skill in card["skills"]:
        for k in ("id", "name", "description", "tags"):
            assert k in skill, f"skill 缺少字段 {k}"
        assert isinstance(skill["tags"], list)


def test_agent_card_method_not_allowed(flask_client):
    """POST 到 well-known 应 405。"""
    resp = flask_client.post("/.well-known/agent-card.json", json={})
    assert resp.status_code == 405


# ---------------------------------------------------------------------------
# /api/adapters/status (适配器状态)
# ---------------------------------------------------------------------------


def test_adapters_status_happy(flask_client):
    """已有 test_health_endpoints 覆盖 schema，本处冒烟 + 脱敏。"""
    resp = flask_client.get("/api/adapters/status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body is not None


def test_adapters_status_no_stacktrace_leak(flask_client):
    resp = flask_client.get("/api/adapters/status")
    body_text = resp.get_data(as_text=True)
    assert "Traceback" not in body_text
    assert "/Users/" not in body_text


def test_adapters_status_method_405(flask_client):
    resp = flask_client.delete("/api/adapters/status")
    assert resp.status_code == 405


# ---------------------------------------------------------------------------
# /api/registry/stats (Registry 域分布)
# ---------------------------------------------------------------------------


def test_registry_stats_happy(flask_client):
    resp = flask_client.get("/api/registry/stats")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body is not None


def test_registry_stats_method_405(flask_client):
    resp = flask_client.put("/api/registry/stats")
    assert resp.status_code == 405


# ---------------------------------------------------------------------------
# /api/active_tasks
# ---------------------------------------------------------------------------


def test_active_tasks_happy(flask_client):
    resp = flask_client.get("/api/active_tasks")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body is not None
    assert "active_tasks" in body
    assert isinstance(body["active_tasks"], list)


def test_active_tasks_method_405(flask_client):
    resp = flask_client.post("/api/active_tasks", json={})
    assert resp.status_code == 405


# ---------------------------------------------------------------------------
# /api/agent_analysis_history (Agent 历史)
# ---------------------------------------------------------------------------


def test_agent_analysis_history_happy(flask_client):
    resp = flask_client.get("/api/agent_analysis_history")
    # 路由可能依赖外部存储；200 或 500 都不视为路由缺失
    assert resp.status_code in (200, 500)
    if resp.status_code == 500:
        body_text = resp.get_data(as_text=True)
        assert "Traceback" not in body_text


def test_agent_pending_approvals_happy(flask_client):
    resp = flask_client.get("/api/agent_pending_approvals")
    assert resp.status_code in (200, 500)
