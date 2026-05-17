# Input  : Flask test_client (flask_client fixture) + monkeypatch + tmp_data_dir
# Output : pytest 用例：覆盖 7 条对话+MCP+A2A 路由
# Pos    : tests/backend/api/test_conversation_mcp_routes.py
"""BE-01d 对话 CRUD + MCP + A2A 路由测试。

实际存在路由（已 grep 确认 routes_raw.txt）：
1. GET    /api/conversations                              line 3096
2. GET    /api/conversations/<conversation_id>            line 3105
3. DELETE /api/conversations/<conversation_id>            line 3115
4. GET    /api/mcp/tools                                  line 2806
5. POST   /api/mcp/call                                   line 2815
6. POST   /a2a/v1                                         line 3180
7. GET    /.well-known/agent-card.json                    line 3168

未实际存在路由（保留 404 占位用例）：
- POST /api/conversations  -> 405（仅 GET），记录"路由不存在"

约束：每路由 ≥ 2 用例（快乐 + 错误）。LLM/akshare/外部 IO 全 mock。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

import pytest


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #

def _json(resp) -> Any:
    assert resp.content_type and "application/json" in resp.content_type, (
        f"响应非 JSON: content_type={resp.content_type}, body={resp.data[:200]!r}"
    )
    return json.loads(resp.data.decode("utf-8"))


def _no_stacktrace(resp) -> None:
    body = resp.data.decode("utf-8", errors="replace").lower()
    forbidden = ["traceback (most recent call last)", 'file "', "raise "]
    for fb in forbidden:
        assert fb not in body, f"响应不应泄露堆栈关键字 {fb!r}"


# --------------------------------------------------------------------------- #
# fixture: 重定向 CONVERSATION_DIR 到 tmp，并重置单例
# --------------------------------------------------------------------------- #

@pytest.fixture
def isolated_conv_dir(tmp_path, monkeypatch):
    """将 app.core.conversation.CONVERSATION_DIR 指向临时目录，重置单例。

    CONVERSATION_DIR 是模块级常量，且 _save/_load 在每次调用时读取该名字，
    monkeypatch 直接替换即可。
    """
    from app.core import conversation as conv_mod

    tmp_dir = tmp_path / "conversations"
    tmp_dir.mkdir()
    monkeypatch.setattr(conv_mod, "CONVERSATION_DIR", str(tmp_dir))
    # 重置全局 _manager，避免使用旧的（其 __init__ 仅 makedirs，不缓存路径）
    monkeypatch.setattr(conv_mod, "_manager", None)
    return tmp_dir


def _seed_conversation(tmp_dir, conv_id="conv_test1234567", title="测试对话",
                       messages=None, stock_codes=None):
    """直接落盘一个对话 JSON。"""
    payload = {
        "conversation_id": conv_id,
        "title": title,
        "created_at": "2026-05-17 10:00:00",
        "updated_at": "2026-05-17 10:30:00",
        "messages": messages or [],
        "stock_codes": stock_codes or [],
        "analysis_refs": [],
    }
    fpath = os.path.join(str(tmp_dir), f"{conv_id}.json")
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return conv_id, fpath


# =========================================================================== #
# 1. GET /api/conversations  对话列表
# =========================================================================== #

class TestListConversations:
    def test_list_empty_ok(self, flask_client, isolated_conv_dir):
        resp = flask_client.get("/api/conversations")
        assert resp.status_code == 200, resp.data[:200]
        data = _json(resp)
        assert isinstance(data, dict)
        assert "conversations" in data
        assert isinstance(data["conversations"], list)
        assert data["conversations"] == []

    def test_list_with_seeded_conversation(self, flask_client, isolated_conv_dir):
        _seed_conversation(isolated_conv_dir, conv_id="conv_aaaa00000001",
                           title="贵州茅台分析",
                           messages=[{"role": "user", "content": "分析600519",
                                      "message_id": "m1",
                                      "created_at": "2026-05-17 10:00:00"}],
                           stock_codes=["600519"])
        resp = flask_client.get("/api/conversations?limit=10")
        assert resp.status_code == 200
        data = _json(resp)
        assert len(data["conversations"]) == 1
        item = data["conversations"][0]
        assert item["conversation_id"] == "conv_aaaa00000001"
        assert item["title"] == "贵州茅台分析"
        assert item["message_count"] == 1
        assert item["stock_codes"] == ["600519"]

    def test_list_wrong_method_post_405(self, flask_client, isolated_conv_dir):
        # POST /api/conversations 不存在（只有 GET），应 405
        resp = flask_client.post("/api/conversations", json={"title": "x"})
        assert resp.status_code in (404, 405), f"POST 应被拒绝，得到 {resp.status_code}"


# =========================================================================== #
# 2. GET /api/conversations/<id>  对话详情
# =========================================================================== #

class TestGetConversation:
    def test_get_existing_conversation(self, flask_client, isolated_conv_dir):
        conv_id, _ = _seed_conversation(isolated_conv_dir, conv_id="conv_get0000test",
                                        title="测试详情")
        resp = flask_client.get(f"/api/conversations/{conv_id}")
        assert resp.status_code == 200, resp.data[:200]
        data = _json(resp)
        assert data["conversation_id"] == conv_id
        assert data["title"] == "测试详情"
        assert "messages" in data

    def test_get_nonexistent_404(self, flask_client, isolated_conv_dir):
        resp = flask_client.get("/api/conversations/conv_does_not_exist_999")
        assert resp.status_code == 404
        data = _json(resp)
        assert "error" in data
        _no_stacktrace(resp)


# =========================================================================== #
# 3. DELETE /api/conversations/<id>
# =========================================================================== #

class TestDeleteConversation:
    def test_delete_existing_ok(self, flask_client, isolated_conv_dir):
        conv_id, fpath = _seed_conversation(isolated_conv_dir, conv_id="conv_del000001")
        assert os.path.exists(fpath)

        resp = flask_client.delete(f"/api/conversations/{conv_id}")
        assert resp.status_code == 200, resp.data[:200]
        data = _json(resp)
        assert "message" in data
        # 文件应被实际删除
        assert not os.path.exists(fpath)

    def test_delete_nonexistent_404(self, flask_client, isolated_conv_dir):
        resp = flask_client.delete("/api/conversations/conv_no_such_one_999")
        assert resp.status_code == 404
        data = _json(resp)
        assert "error" in data
        _no_stacktrace(resp)


# =========================================================================== #
# 4. GET /api/mcp/tools  MCP工具列表
# =========================================================================== #

class TestMcpListTools:
    def test_list_tools_ok(self, flask_client):
        resp = flask_client.get("/api/mcp/tools")
        assert resp.status_code == 200, resp.data[:200]
        data = _json(resp)
        # MCP_SERVER_CONFIG schema
        assert isinstance(data, dict)
        assert data.get("name") == "stockanal-data-server"
        assert "tools" in data and isinstance(data["tools"], list)
        assert len(data["tools"]) >= 1
        # 工具有名字
        tool_names = [t["name"] for t in data["tools"]]
        assert "get_stock_history" in tool_names

    def test_list_tools_wrong_method(self, flask_client):
        resp = flask_client.post("/api/mcp/tools", json={})
        assert resp.status_code in (404, 405)


# =========================================================================== #
# 5. POST /api/mcp/call  MCP工具调用
# =========================================================================== #

class TestMcpCall:
    def test_call_unknown_tool_returns_error_field(self, flask_client):
        """未知工具应被 handle_mcp_tool_call 拦截，返回 {result: {error: ...}}"""
        resp = flask_client.post(
            "/api/mcp/call",
            json={"tool": "no_such_tool_xxx", "arguments": {}},
        )
        # 接口本身 200，但 result 内含 error
        assert resp.status_code == 200, resp.data[:200]
        data = _json(resp)
        assert "result" in data
        assert "error" in data["result"]
        assert "未知工具" in data["result"]["error"]

    def test_call_legal_tool_mocked(self, flask_client, monkeypatch):
        """合法 tool_name，mock handler 返回固定数据。"""
        # 直接 monkeypatch handlers dict 内的 handler 函数
        from app.mcp import stock_data_server as mcp_mod

        def fake_history(stock_code, days=120):
            return {"data": [{"date": "2026-05-16", "close": 1700.0}],
                    "total_rows": 1, "_mocked": True}

        monkeypatch.setattr(mcp_mod, "_handle_stock_history", fake_history)
        # 因为 handle_mcp_tool_call 内部 handlers dict 是函数局部，所以也要 patch
        # 调用映射构造：直接 patch handle_mcp_tool_call 更稳妥
        orig = mcp_mod.handle_mcp_tool_call

        def wrapped(tool_name, arguments):
            if tool_name == "get_stock_history":
                return fake_history(**arguments)
            return orig(tool_name, arguments)

        monkeypatch.setattr(mcp_mod, "handle_mcp_tool_call", wrapped)
        # web_server.py 在路由内 import，会引用到 patched 版本
        resp = flask_client.post(
            "/api/mcp/call",
            json={"tool": "get_stock_history", "arguments": {"stock_code": "600519", "days": 5}},
        )
        assert resp.status_code == 200, resp.data[:200]
        data = _json(resp)
        assert "result" in data
        assert data["result"].get("_mocked") is True
        assert data["result"]["total_rows"] == 1

    def test_call_missing_tool_field_400(self, flask_client):
        resp = flask_client.post("/api/mcp/call", json={"arguments": {}})
        assert resp.status_code == 400
        data = _json(resp)
        assert "error" in data
        _no_stacktrace(resp)

    def test_call_non_json_body_400(self, flask_client):
        resp = flask_client.post(
            "/api/mcp/call",
            data="not-json",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        _no_stacktrace(resp)


# =========================================================================== #
# 6. POST /a2a/v1  A2A JSON-RPC 端点
# =========================================================================== #

class TestA2AJsonRpc:
    def test_a2a_returns_jsonrpc_method_not_implemented(self, flask_client):
        """当前实现为 stub，必须返回 JSON-RPC 2.0 错误对象 + 501。"""
        resp = flask_client.post(
            "/a2a/v1",
            json={"jsonrpc": "2.0", "method": "message/send", "params": {}, "id": 42},
        )
        # spec: stub 返回 501
        assert resp.status_code == 501, resp.data[:200]
        data = _json(resp)
        assert data.get("jsonrpc") == "2.0"
        assert "error" in data
        assert data["error"]["code"] == -32601
        assert "Method not implemented" in data["error"]["message"]
        # id 透传
        assert data.get("id") == 42

    def test_a2a_no_body_still_jsonrpc_envelope(self, flask_client):
        """无 body 时 id 应为 None，仍需符合 JSON-RPC 信封。"""
        resp = flask_client.post("/a2a/v1", data="", content_type="application/json")
        assert resp.status_code == 501
        data = _json(resp)
        assert data.get("jsonrpc") == "2.0"
        assert data["error"]["code"] == -32601
        assert data.get("id") is None

    def test_a2a_wrong_method_get(self, flask_client):
        resp = flask_client.get("/a2a/v1")
        assert resp.status_code in (404, 405)


# =========================================================================== #
# 7. GET /.well-known/agent-card.json  A2A AgentCard 发现
# =========================================================================== #

class TestA2AAgentCard:
    def test_agent_card_schema(self, flask_client):
        resp = flask_client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200, resp.data[:200]
        data = _json(resp)
        # A2A v1.0 AgentCard 必需字段
        for k in ("name", "description", "url", "version", "capabilities",
                  "defaultInputModes", "defaultOutputModes", "skills"):
            assert k in data, f"AgentCard 缺少字段: {k}"
        assert isinstance(data["skills"], list) and len(data["skills"]) >= 1
        # url 应指向 /a2a/v1
        assert data["url"].endswith("/a2a/v1")
        # capabilities 字段
        assert "streaming" in data["capabilities"]
        # stub 标记
        assert data.get("_stub") is True

    def test_agent_card_wrong_method(self, flask_client):
        resp = flask_client.post("/.well-known/agent-card.json", json={})
        assert resp.status_code in (404, 405)
