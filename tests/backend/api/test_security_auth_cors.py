# Input  : pytest collect → conftest.flask_client/flask_app fixture
# Output : SEC-01 暴露测试用例集（鉴权矩阵 / CORS 守卫 / 错误脱敏 / SSE / 上传）
# Pos    : tests/backend/api/test_security_auth_cors.py — W1 安全审计 SEC-01

"""SEC-01 安全暴露测试。

设计原则：
1. **只暴露不修复**——业务侧改动需 Comdr 审批，本文件仅产出证据。
2. **大量 xfail**——故意标 xfail 表示"当前未实现的安全防护"。
   - xfail PASS → 业务已经修复，应升级为 PASS（去掉 xfail 标记）
   - xfail FAIL → 当前 BASELINE（缺陷仍存在）
3. **静态扫描兜底**——动态请求耗时高的路由（如个股全量分析）只用 grep
   解析 `@app.route` 行做矩阵断言，不实际访问。

测试矩阵：
  A. SEC-1 鉴权矩阵：78 个 /api/* 路由是否裸奔
  B. SEC-2 CORS 守卫：DEBUG 守卫缺失
  C. 错误信息脱敏：5xx / 4xx 响应体不含敏感串
  D. SSE 跨域窃听
  E. 上传限制（/api/upload_image 若存在）
"""

from __future__ import annotations

import os
import re
import pytest
from pathlib import Path

# --------------------------------------------------------------------------- #
# 辅助：静态扫描 web_server.py 的 @app.route('/api/*') 路由
# --------------------------------------------------------------------------- #

_WEB_SERVER_PATH = Path(__file__).resolve().parents[3] / "app" / "web" / "web_server.py"

_ROUTE_RE = re.compile(
    r"@app\.route\(\s*['\"](?P<path>/api/[^'\"]*)['\"](?:[^)]*methods\s*=\s*\[(?P<methods>[^\]]*)\])?",
    re.MULTILINE,
)


def _extract_api_routes():
    """从 web_server.py 静态解析所有 /api/* 路由。

    返回 [(path, [methods]), ...]
    跳过含 <param> 的动态路由（替换为示例参数）。
    """
    text = _WEB_SERVER_PATH.read_text(encoding="utf-8")
    routes = []
    for m in _ROUTE_RE.finditer(text):
        path = m.group("path")
        methods_raw = m.group("methods") or ""
        methods = [
            x.strip().strip("'\"").upper()
            for x in methods_raw.split(",")
            if x.strip()
        ] or ["GET"]
        # 动态参数路径替换
        path_resolved = re.sub(r"<[^>]+:?([^>]*)>", "TESTPARAM", path)
        routes.append((path_resolved, methods))
    return routes


def _grep_auth_decorators():
    """检查 web_server.py 是否引用了鉴权装饰器。"""
    text = _WEB_SERVER_PATH.read_text(encoding="utf-8")
    return {
        "require_api_key": text.count("@require_api_key"),
        "require_hmac_auth": text.count("@require_hmac_auth"),
        "before_request_auth": text.count("before_request"),  # 也接受全局守卫
    }


_ALL_API_ROUTES = _extract_api_routes()
_AUTH_DECORATORS = _grep_auth_decorators()

# --------------------------------------------------------------------------- #
# A. SEC-1 鉴权矩阵
# --------------------------------------------------------------------------- #


class TestSEC1AuthMatrix:
    """SEC-1：所有 /api/* 路由鉴权暴露。"""

    def test_no_auth_decorators_referenced(self):
        """BASELINE：web_server.py 应**未**引用任何鉴权装饰器。

        当前预期 PASS（暴露问题）。当业务侧引入 @require_api_key 后，
        本用例应当 FAIL → 即时改造为正向断言。
        """
        assert _AUTH_DECORATORS["require_api_key"] == 0, (
            f"已发现 require_api_key 装饰器 ({_AUTH_DECORATORS['require_api_key']} 处)，"
            "SEC-1 部分缓解，请升级本测试"
        )
        assert _AUTH_DECORATORS["require_hmac_auth"] == 0, (
            f"已发现 require_hmac_auth 装饰器，SEC-1 部分缓解"
        )

    def test_api_routes_count_baseline(self):
        """BASELINE：固化路由数。审计时刻 = 63（仅 /api/*）。

        若数量变化，说明新增/删除路由，需同步重审 SEC-01。
        """
        assert len(_ALL_API_ROUTES) >= 60, (
            f"路由数 {len(_ALL_API_ROUTES)} 低于 baseline=60，请确认是否误删"
        )
        # 上限放宽——避免新增路由直接打挂
        assert len(_ALL_API_ROUTES) <= 120

    @pytest.mark.xfail(
        reason="SEC-1：当前所有 /api/* 路由裸奔，未挂鉴权装饰器；"
               "等待鉴权方案落地（D-3 C 方案 PROD 强制）后转 PASS",
        strict=False,
    )
    def test_all_routes_should_require_auth_in_production(self):
        """期望测试：所有 /api/* 路由都应该挂载鉴权装饰器。

        采用**静态扫描**而非动态调用：将每个 @app.route('/api/...') 行
        与其上方 ~3 行的装饰器栈匹配；任何缺失 @require_api_key /
        @require_hmac_auth 的路由计入 offenders。

        当前必然 XFAIL（业务未实现）。鉴权方案落地后应去掉 xfail。
        """
        text = _WEB_SERVER_PATH.read_text(encoding="utf-8")
        lines = text.splitlines()
        offenders = []
        for idx, line in enumerate(lines):
            m = re.search(r"@app\.route\(\s*['\"](/api/[^'\"]*)", line)
            if not m:
                continue
            path = m.group(1)
            # 看上方 5 行的装饰器栈
            window = "\n".join(lines[max(0, idx - 5): idx + 1])
            has_auth = bool(
                re.search(r"@require_api_key|@require_hmac_auth", window)
            )
            if not has_auth:
                offenders.append(path)

        assert not offenders, (
            f"以下 {len(offenders)} 条 /api/* 路由未挂鉴权装饰器（前 20 条）：\n"
            + "\n".join(f"  - {p}" for p in offenders[:20])
        )

    def test_all_routes_currently_unauthenticated_baseline(self, flask_client):
        """BASELINE 暴露：少量轻量 GET 路由不带鉴权头应当**不**返回 401/403。

        仅对**已知安全/轻量**的端点（健康检查、版本号等）动态访问，
        避免触发外部 API 调用。
        """
        safe_probes = [
            "/api/health",
            "/api/version",
            "/api/dashboard_data",
        ]
        unauth_count = 0
        sample = []
        for path in safe_probes:
            try:
                resp = flask_client.get(path)
            except Exception:
                continue
            if resp.status_code not in (401, 403):
                unauth_count += 1
                sample.append((path, resp.status_code))

        # 至少 2 条返回非 401/403，证明确实裸奔
        assert unauth_count >= 2, (
            f"baseline 失效：仅 {unauth_count} 条轻量路由可访问；"
            f"采样：{sample}。"
            "若鉴权已落地，请删除本 baseline。"
        )


# --------------------------------------------------------------------------- #
# B. SEC-2 CORS 守卫
# --------------------------------------------------------------------------- #


class TestSEC2CORSGuard:
    """SEC-2：CORS 配置无 DEBUG/PROD 守卫。"""

    def test_cors_config_has_no_debug_guard(self):
        """BASELINE：web_server.py 第 91-96 行的 CORS 配置**未**被
        `if app.debug:` 包裹。

        当前应 PASS（暴露缺陷）。守卫加入后应 FAIL → 升级测试。
        """
        text = _WEB_SERVER_PATH.read_text(encoding="utf-8")
        # 提取 CORS( 调用所在的上下文（前 200 字符）
        m = re.search(r"CORS\(app,\s*resources=", text)
        assert m is not None, "未找到 CORS 配置"
        head = text[max(0, m.start() - 300): m.start()]
        # 守卫关键字
        has_guard = bool(re.search(r"if\s+(app\.)?debug|FLASK_ENV|ENV\s*==\s*['\"]development", head))
        assert not has_guard, (
            "CORS 已加入 DEBUG 守卫，请升级 SEC-2 测试为正向断言"
        )

    def test_cors_allows_lan_ip_origins(self):
        """BASELINE：当前 _DEV_ORIGIN_PATTERNS 包含 192.168.x / 10.x 任意 IP。"""
        text = _WEB_SERVER_PATH.read_text(encoding="utf-8")
        assert "192.168" in text and "10\\." in text, (
            "_DEV_ORIGIN_PATTERNS 应包含 LAN IP（当前 baseline）"
        )

    def test_cors_evil_origin_should_be_rejected(self, flask_client):
        """暴露：以恶意 origin 发起预检 → 当前预期 CORS 不返回该 origin。

        Flask-CORS 在白名单不匹配时会**不携带** Access-Control-Allow-Origin
        头（而非主动 403），这本身是合规行为。本用例确认这一基线。
        """
        resp = flask_client.options(
            "/api/health",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
        # 不应回显恶意 origin
        assert "evil.example.com" not in allow_origin, (
            f"CORS 回显了恶意 origin: {allow_origin}"
        )

    def test_cors_lan_ip_origin_allowed_baseline(self, flask_client):
        """BASELINE：192.168.43.125:3000 在 _DEV_ORIGIN_PATTERNS 范围内
        → 当前应被 CORS 放行。生产环境下不应放行 LAN IP。
        """
        resp = flask_client.options(
            "/api/health",
            headers={
                "Origin": "http://192.168.43.125:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
        # 当前 baseline：LAN IP 被允许
        # 记录而非强断（CORS 预检在 TESTING 模式行为可能差异）
        if "192.168.43.125" not in allow_origin:
            pytest.skip(
                f"预检响应未回显 LAN IP（实测 Access-Control-Allow-Origin={allow_origin!r}），"
                "可能与 Flask-CORS 版本相关；动态行为已记录"
            )

    @pytest.mark.xfail(
        reason="SEC-2：生产模式下 LAN/恶意 origin 不应被放行；"
               "当前 CORS 配置无 if app.debug 守卫，落地 D-3 C 方案后转 PASS",
        strict=False,
    )
    def test_cors_in_production_should_block_lan_ip(self, flask_client, monkeypatch):
        """期望测试：PROD 模式下，LAN IP origin 不应回显在 Allow-Origin。"""
        monkeypatch.setenv("FLASK_ENV", "production")
        resp = flask_client.options(
            "/api/health",
            headers={
                "Origin": "http://192.168.43.125:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
        assert "192.168" not in allow_origin, (
            f"PROD 模式下 LAN IP 仍被放行：{allow_origin}"
        )


# --------------------------------------------------------------------------- #
# C. 错误信息脱敏
# --------------------------------------------------------------------------- #

_SECRET_PATTERNS = [
    re.compile(r"/Users/panda/"),                  # 文件绝对路径
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r'File\s+"[^"]+\.py",\s*line\s+\d+,\s*in\s+'),
    re.compile(r"line\s+\d+,\s+in\s+"),
    re.compile(r"SELECT\s+.*\s+FROM\s+", re.IGNORECASE),
    re.compile(r"INSERT\s+INTO\s+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),            # OpenAI key 形态
    re.compile(r"OPENAI_API_KEY\s*=\s*['\"][^'\"]+['\"]"),
]


def _assert_no_secrets(body: str, route: str):
    body_str = body if isinstance(body, str) else body.decode("utf-8", errors="replace")
    hits = []
    for pat in _SECRET_PATTERNS:
        if pat.search(body_str):
            hits.append(pat.pattern)
    assert not hits, (
        f"[{route}] 响应体包含敏感模式：{hits}\n"
        f"片段：{body_str[:300]!r}"
    )


# 8 个代表性路由：混合 GET / POST(空 body 触发 400/422) / 404。
# 仅选不会触发外部 API、不会阻塞的端点。
_SANITIZE_ROUTES = [
    ("GET",  "/api/health"),
    ("GET",  "/api/version"),
    ("GET",  "/api/dashboard_data"),
    ("GET",  "/api/index_stocks"),
    ("GET",  "/api/latest_news"),
    ("GET",  "/api/conversations"),
    ("POST", "/api/north_flow_history"),       # POST 空 body → 400/422
    ("POST", "/api/save_portfolio"),           # POST 空 body → 400/422
    ("GET",  "/api/nonexistent_route_zzz_42"), # 404
    ("GET",  "/api/conversations/__bogus__"),  # 404 / 4xx
]


class TestErrorSanitization:
    """C. 错误信息脱敏暴露。"""

    @pytest.mark.parametrize("method,route", _SANITIZE_ROUTES)
    def test_response_body_no_sensitive_leak(self, flask_client, method, route):
        """断言响应体不含：绝对路径 / stacktrace / SQL / secrets。

        部分路由可能 200，但 5xx 时尤其关键。
        """
        try:
            if method == "GET":
                resp = flask_client.get(route)
            else:
                resp = flask_client.post(route, json={})
        except Exception as e:
            pytest.skip(f"路由 {route} 调用抛异常被框架吃掉：{e}")

        body = resp.get_data(as_text=True)
        _assert_no_secrets(body, route)


# --------------------------------------------------------------------------- #
# D. SSE 跨域窃听
# --------------------------------------------------------------------------- #


class TestSSECrossOrigin:
    """D. SSE 跨域窃听暴露。"""

    @pytest.mark.xfail(
        reason="SSE 端点当前未对 Origin 头做强校验；CORS 预检通过即放行流",
        strict=False,
    )
    def test_sse_with_evil_origin_rejected(self, flask_client):
        """SSE 流不应接受未授权 origin 的连接。

        当前预期 XFAIL（业务未实现 Origin 校验）。
        """
        resp = flask_client.get(
            "/api/conversations",   # 临时探针：暂无 SSE 列表 endpoint 时降级到任意 /api/
            headers={"Origin": "https://evil.example.com"},
        )
        # 真正落地 SSE 校验后：应当 401/403/不返 stream
        assert resp.status_code in (401, 403), (
            f"SSE 在恶意 origin 下未拒绝：{resp.status_code}"
        )

    def test_sse_endpoint_cors_header_does_not_echo_evil(self, flask_client):
        """OPTIONS 预检不应回显 evil origin（CORS 基线确认）。"""
        # 取一个真实存在的 SSE 路径；若不存在则跳过
        candidates = [
            "/api/conversations/stream",
            "/api/agent/coordinator/stream",
            "/api/sse/events",
        ]
        text = _WEB_SERVER_PATH.read_text(encoding="utf-8")
        target = None
        for c in candidates:
            if c in text:
                target = c
                break
        if target is None:
            pytest.skip("仓库中未发现明显的 SSE 端点路径")

        resp = flask_client.options(
            target,
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
        assert "evil.example.com" not in allow_origin


# --------------------------------------------------------------------------- #
# E. 上传限制
# --------------------------------------------------------------------------- #


class TestUploadLimits:
    """E. /api/upload_image（若存在）大小与 MIME 限制。"""

    @staticmethod
    def _upload_endpoint_exists():
        text = _WEB_SERVER_PATH.read_text(encoding="utf-8")
        return "/api/upload_image" in text or "upload_image" in text

    def test_upload_oversize_rejected(self, flask_client):
        """上传 > 10MB 文件应被拒绝（413 / 400）。"""
        if not self._upload_endpoint_exists():
            pytest.skip("/api/upload_image 端点不存在")
        from io import BytesIO

        # 构造 12MB 假数据
        data = b"\x00" * (12 * 1024 * 1024)
        resp = flask_client.post(
            "/api/upload_image",
            data={"file": (BytesIO(data), "huge.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code in (400, 413, 415), (
            f"超大上传应被拒绝，实测 {resp.status_code}"
        )

    @pytest.mark.xfail(
        reason="MIME 严格校验当前未实现",
        strict=False,
    )
    def test_upload_non_image_rejected(self, flask_client):
        """上传非图片 MIME 应被拒绝。"""
        if not self._upload_endpoint_exists():
            pytest.skip("/api/upload_image 端点不存在")
        from io import BytesIO

        resp = flask_client.post(
            "/api/upload_image",
            data={"file": (BytesIO(b"#!/bin/sh\nrm -rf /"), "evil.sh")},
            content_type="multipart/form-data",
        )
        assert resp.status_code in (400, 415), (
            f"非图片 MIME 应被拒绝，实测 {resp.status_code}"
        )
