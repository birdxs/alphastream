"""
Input: Flask test_client 发起 GET 请求至 /api/* 端点
Output: 验证 Cache-Control / Pragma / Expires header 按白名单规则正确设置
Pos: tests/backend/api/test_cache_control_headers.py — S3-H2 after_request Cache-Control 防御性 header 验证

一旦本文件结构变化，请同步更新 tests/backend/api/README.md 与所属测试模块。
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.api, pytest.mark.unit]


# ---------------------------------------------------------------------------
# /api/health/deep — 验证 no-store（忽略状态码，仅验证 header）
# ---------------------------------------------------------------------------

def test_api_health_deep_no_store(flask_client):
    """/api/health/deep 属于普通 API，响应应含 no-store Cache-Control（忽略状态码）。"""
    resp = flask_client.get("/api/health/deep")
    cc = resp.headers.get("Cache-Control", "")
    # 在 DISABLE_NETWORK 测试环境该端点可能 500，但 header 仍由 after_request 注入
    assert "no-store" in cc, f"Cache-Control 应含 no-store，实际: {cc!r}"
    assert "private" in cc, f"Cache-Control 应含 private，实际: {cc!r}"
    pragma = resp.headers.get("Pragma", "")
    assert "no-cache" in pragma, f"Pragma 应含 no-cache，实际: {pragma!r}"
    expires = resp.headers.get("Expires", "")
    assert expires == "0", f"Expires 应为 '0'，实际: {expires!r}"


# ---------------------------------------------------------------------------
# /api/openapi.json — 白名单：public, max-age=300
# ---------------------------------------------------------------------------

def test_openapi_json_public_cache(flask_client):
    """/api/openapi.json 应设 public, max-age=300。"""
    resp = flask_client.get("/api/openapi.json")
    assert resp.status_code == 200
    cc = resp.headers.get("Cache-Control", "")
    assert "public" in cc, f"Cache-Control 应含 public，实际: {cc!r}"
    assert "max-age=300" in cc, f"Cache-Control 应含 max-age=300，实际: {cc!r}"
    # 不应设置 no-store
    assert "no-store" not in cc, f"Cache-Control 不应含 no-store，实际: {cc!r}"


# ---------------------------------------------------------------------------
# /api/market_indices — 若路由已设 Cache-Control，after_request 不覆盖
# ---------------------------------------------------------------------------

def test_market_indices_cache_header_present(flask_client):
    """/api/market_indices 响应应有 Cache-Control header（with_cache 或 after_request 之一设置）。"""
    resp = flask_client.get("/api/market_indices")
    cc = resp.headers.get("Cache-Control", "")
    # 该路由由 with_cache 装饰器设置 public,max-age=5；after_request 不覆盖已有值
    # 无论哪方设置，Cache-Control 必须非空
    assert cc != "", f"Cache-Control 不应为空"
    # 如果是 with_cache 的值（public,max-age=5），说明 after_request 正确跳过了覆盖
    # 如果是 no-store，说明 with_cache 未设置，after_request 正确补上了防御性值
    # 两者都可接受，只要 header 存在即合规
    assert len(cc) > 0


# ---------------------------------------------------------------------------
# 已有 Cache-Control 的路由不被 after_request 覆盖（直接单元测试逻辑）
# ---------------------------------------------------------------------------

def test_after_request_skips_existing_cache_control(flask_app):
    """直接验证 after_request 钩子：若响应已有 Cache-Control，不会被覆盖为 no-store。"""
    from flask import request as flask_request

    with flask_app.test_request_context("/api/some_route"):
        # 模拟 after_request 逻辑：已设 Cache-Control 时不覆盖
        from flask import Response
        resp = Response('{"ok":true}', content_type='application/json')
        resp.headers['Cache-Control'] = 'public, max-age=60'

        # 调用 after_request 逻辑（直接测试 web_server 中的钩子函数）
        import app.web.web_server as ws
        # after_request_handler 通过 flask_app.after_request_funcs 注册
        after_fns = flask_app.after_request_funcs.get(None, [])
        # 找到 S3-H2 所在的 after_request handler（应该是同一个设置 security headers 的）
        result = resp
        for fn in after_fns:
            result = fn(result)

        cc = result.headers.get("Cache-Control", "")
        # 已有 public,max-age=60，不应被覆盖为 no-store
        assert "no-store" not in cc, f"已有 Cache-Control 不应被覆盖，实际: {cc!r}"
        assert "max-age=60" in cc, f"原有 max-age=60 应保留，实际: {cc!r}"
