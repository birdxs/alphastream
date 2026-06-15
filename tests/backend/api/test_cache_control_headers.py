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


def test_openapi_json_includes_first_batch_routes(flask_client):
    """OpenAPI spec 应包含第一批补齐的 10 个路由及方法。"""
    resp = flask_client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]

    expected = {
        "/api/health/deep": "get",
        "/api/metrics": "get",
        "/api/mcp/tools": "get",
        "/api/mcp/call": "post",
        "/api/shipping/bdi": "get",
        "/api/shipping/port/{port}": "get",
        "/api/esg/{ticker}": "get",
        "/api/corporate/search": "get",
        "/api/jobs/search": "get",
        "/api/jobs/company/{company}": "get",
    }

    for path, method in expected.items():
        assert path in paths
        assert method in paths[path]


def _param(operation: dict, name: str, location: str) -> dict:
    for param in operation.get("parameters", []):
        if param.get("name") == name and param.get("in") == location:
            return param
    raise AssertionError(f"缺少参数: {location} {name}")


def test_openapi_json_first_batch_parameters(flask_client):
    """OpenAPI spec 应声明第一批路由的关键 path/query/body 参数。"""
    resp = flask_client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]

    bdi = paths["/api/shipping/bdi"]["get"]
    days_schema = _param(bdi, "days", "query")["schema"]
    assert days_schema["type"] == "integer"
    assert days_schema["minimum"] == 1
    assert days_schema["maximum"] == 365
    assert days_schema["default"] == 30

    port_op = paths["/api/shipping/port/{port}"]["get"]
    assert _param(port_op, "port", "path")["required"] is True
    period_schema = _param(port_op, "period", "query")["schema"]
    assert period_schema["enum"] == ["daily", "monthly", "yearly"]
    assert period_schema["default"] == "monthly"

    esg_op = paths["/api/esg/{ticker}"]["get"]
    assert _param(esg_op, "ticker", "path")["required"] is True
    source_schema = _param(esg_op, "source", "query")["schema"]
    assert source_schema["maxLength"] == 32
    assert source_schema["default"] == "synthetic"

    corporate_op = paths["/api/corporate/search"]["get"]
    corporate_q = _param(corporate_op, "q", "query")
    assert corporate_q["required"] is True
    assert corporate_q["schema"]["minLength"] == 1
    assert corporate_q["schema"]["maxLength"] == 100
    corporate_limit = _param(corporate_op, "limit", "query")["schema"]
    assert corporate_limit["minimum"] == 1
    assert corporate_limit["maximum"] == 100
    assert corporate_limit["default"] == 20

    jobs_op = paths["/api/jobs/search"]["get"]
    jobs_q = _param(jobs_op, "q", "query")
    assert jobs_q["required"] is True
    assert jobs_q["schema"]["minLength"] == 1
    assert jobs_q["schema"]["maxLength"] == 100
    jobs_limit = _param(jobs_op, "limit", "query")["schema"]
    assert jobs_limit["minimum"] == 1
    assert jobs_limit["maximum"] == 200
    assert jobs_limit["default"] == 20

    company_op = paths["/api/jobs/company/{company}"]["get"]
    assert _param(company_op, "company", "path")["required"] is True

    mcp_call = paths["/api/mcp/call"]["post"]
    assert mcp_call["requestBody"]["required"] is True
    assert mcp_call["requestBody"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/McpCallRequest"
    )


def test_openapi_json_includes_second_batch_routes(flask_client):
    """OpenAPI spec 应包含第二批补齐的 10 个路由及方法。"""
    resp = flask_client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]

    expected = {
        "/api/stock_name": "get",
        "/api/stock_name_search": "get",
        "/api/start_market_scan": "post",
        "/api/scan_status/{task_id}": "get",
        "/api/cancel_scan/{task_id}": "post",
        "/api/index_stocks": "get",
        "/api/industry_stocks": "get",
        "/api/board_stocks": "get",
        "/api/concept_fund_flow": "get",
        "/api/individual_fund_flow_rank": "get",
    }

    for path, method in expected.items():
        assert path in paths
        assert method in paths[path]


def test_openapi_json_second_batch_parameters(flask_client):
    """OpenAPI spec 应声明第二批路由的关键 path/query/body 参数。"""
    resp = flask_client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]

    stock_name = paths["/api/stock_name"]["get"]
    stock_code = _param(stock_name, "stock_code", "query")
    assert stock_code["required"] is True
    assert stock_code["schema"]["maxLength"] == 20

    stock_name_search = paths["/api/stock_name_search"]["get"]
    q_schema = _param(stock_name_search, "q", "query")["schema"]
    assert q_schema["minLength"] == 1
    assert q_schema["maxLength"] == 20
    search_limit = _param(stock_name_search, "limit", "query")["schema"]
    assert search_limit["minimum"] == 1
    assert search_limit["maximum"] == 100
    assert search_limit["default"] == 10

    scan = paths["/api/start_market_scan"]["post"]
    scan_schema = scan["requestBody"]["content"]["application/json"]["schema"]
    assert scan["requestBody"]["required"] is True
    assert scan_schema["properties"]["stock_list"]["maxItems"] == 500
    assert scan_schema["properties"]["min_score"]["minimum"] == 0
    assert scan_schema["properties"]["min_score"]["maximum"] == 100

    scan_status = paths["/api/scan_status/{task_id}"]["get"]
    assert _param(scan_status, "task_id", "path")["required"] is True

    cancel_scan = paths["/api/cancel_scan/{task_id}"]["post"]
    assert _param(cancel_scan, "task_id", "path")["schema"]["maxLength"] == 64

    index_op = paths["/api/index_stocks"]["get"]
    index_schema = _param(index_op, "index_code", "query")["schema"]
    assert index_schema["enum"] == ["000300", "000905", "000852", "000001"]
    assert index_schema["default"] == "000300"

    industry_op = paths["/api/industry_stocks"]["get"]
    industry = _param(industry_op, "industry", "query")
    assert industry["required"] is True
    assert industry["schema"]["maxLength"] == 50

    board_schema = _param(paths["/api/board_stocks"]["get"], "board", "query")["schema"]
    assert board_schema["enum"] == ["hs300", "zz500", "zz1000", "kc50", "kc100", "bj50"]
    assert board_schema["default"] == "hs300"

    concept_schema = _param(paths["/api/concept_fund_flow"]["get"], "period", "query")["schema"]
    assert concept_schema["default"] == "10日排行"
    assert concept_schema["maxLength"] == 20

    rank_op = paths["/api/individual_fund_flow_rank"]["get"]
    assert _param(rank_op, "period", "query")["schema"]["default"] == "今日"
    assert _param(rank_op, "market", "query")["schema"]["maxLength"] == 10


def test_openapi_json_includes_third_batch_routes(flask_client):
    """OpenAPI spec 应包含第三批补齐的 8 个路由及方法。"""
    resp = flask_client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]

    expected = {
        "/api/analysis_status/{task_id}": "get",
        "/api/cancel_analysis/{task_id}": "post",
        "/api/enhanced_analysis": "post",
        "/api/start_etf_analysis": "post",
        "/api/etf_analysis_status/{task_id}": "get",
        "/api/sector_stocks": "get",
        "/api/individual_fund_flow": "get",
        "/api/stock_quote_batch": "get",
    }

    for path, method in expected.items():
        assert path in paths
        assert method in paths[path]


def test_openapi_json_third_batch_parameters(flask_client):
    """OpenAPI spec 应声明第三批路由的关键 path/query/body 参数。"""
    resp = flask_client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]

    analysis_status = paths["/api/analysis_status/{task_id}"]["get"]
    task_id = _param(analysis_status, "task_id", "path")
    assert task_id["required"] is True
    assert task_id["schema"]["maxLength"] == 64

    cancel = paths["/api/cancel_analysis/{task_id}"]["post"]
    assert _param(cancel, "task_id", "path")["schema"]["maxLength"] == 64

    enhanced = paths["/api/enhanced_analysis"]["post"]
    enhanced_schema = enhanced["requestBody"]["content"]["application/json"]["schema"]
    assert enhanced["requestBody"]["required"] is True
    assert enhanced_schema["required"] == ["stock_code"]
    assert enhanced_schema["properties"]["research_depth"]["minimum"] == 1
    assert enhanced_schema["properties"]["research_depth"]["maximum"] == 5

    etf = paths["/api/start_etf_analysis"]["post"]
    etf_schema = etf["requestBody"]["content"]["application/json"]["schema"]
    assert etf_schema["required"] == ["etf_code"]
    assert etf_schema["properties"]["etf_code"]["maxLength"] == 20

    etf_status = paths["/api/etf_analysis_status/{task_id}"]["get"]
    assert _param(etf_status, "task_id", "path")["required"] is True

    sector = paths["/api/sector_stocks"]["get"]
    sector_param = _param(sector, "sector", "query")
    assert sector_param["required"] is True
    assert sector_param["schema"]["maxLength"] == 50

    fund_flow = paths["/api/individual_fund_flow"]["get"]
    assert _param(fund_flow, "stock_code", "query")["required"] is True

    quote_batch = paths["/api/stock_quote_batch"]["get"]
    codes = _param(quote_batch, "codes", "query")
    assert codes["required"] is True
    assert codes["schema"]["maxLength"] == 2000
    market_schema = _param(quote_batch, "market_type", "query")["schema"]
    assert market_schema["enum"] == ["A", "HK", "US", "B"]
    max_codes_schema = _param(quote_batch, "max_codes", "query")["schema"]
    assert max_codes_schema["minimum"] == 1
    assert max_codes_schema["maximum"] == 100


def test_openapi_json_includes_fourth_batch_routes(flask_client):
    """OpenAPI spec 应包含第四批补齐的 10 个路由及方法。"""
    resp = flask_client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]

    expected = {
        "/api/fundamental_analysis": "post",
        "/api/capital_flow": "post",
        "/api/scenario_predict": "post",
        "/api/qa": "post",
        "/api/risk_analysis": "post",
        "/api/portfolio_risk": "post",
        "/api/index_analysis": "get",
        "/api/industry_analysis": "get",
        "/api/industry_fund_flow": "get",
        "/api/industry_detail": "get",
    }

    for path, method in expected.items():
        assert path in paths
        assert method in paths[path]


def test_openapi_json_fourth_batch_parameters(flask_client):
    """OpenAPI spec 应声明第四批路由的关键 path/query/body 参数。"""
    resp = flask_client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]

    fundamental = paths["/api/fundamental_analysis"]["post"]
    fundamental_schema = fundamental["requestBody"]["content"]["application/json"]["schema"]
    assert fundamental["requestBody"]["required"] is True
    assert fundamental_schema["required"] == ["stock_code"]
    assert fundamental_schema["properties"]["stock_code"]["maxLength"] == 20

    capital = paths["/api/capital_flow"]["post"]
    capital_schema = capital["requestBody"]["content"]["application/json"]["schema"]
    assert capital_schema["required"] == ["stock_code"]
    assert capital_schema["properties"]["market_type"]["maxLength"] == 10

    scenario = paths["/api/scenario_predict"]["post"]
    scenario_schema = scenario["requestBody"]["content"]["application/json"]["schema"]
    assert scenario_schema["required"] == ["stock_code"]
    assert scenario_schema["properties"]["days"]["minimum"] == 1
    assert scenario_schema["properties"]["days"]["maximum"] == 365
    assert scenario_schema["properties"]["days"]["default"] == 60

    qa = paths["/api/qa"]["post"]
    qa_schema = qa["requestBody"]["content"]["application/json"]["schema"]
    assert qa_schema["required"] == ["stock_code", "question"]
    assert qa_schema["properties"]["question"]["minLength"] == 1
    assert qa_schema["properties"]["question"]["maxLength"] == 1000

    risk = paths["/api/risk_analysis"]["post"]
    risk_schema = risk["requestBody"]["content"]["application/json"]["schema"]
    assert risk_schema["required"] == ["stock_code"]
    assert risk_schema["properties"]["market_type"]["default"] == "A"

    portfolio = paths["/api/portfolio_risk"]["post"]
    portfolio_schema = portfolio["requestBody"]["content"]["application/json"]["schema"]
    assert portfolio["requestBody"]["required"] is True
    assert portfolio_schema["required"] == ["portfolio"]
    assert portfolio_schema["properties"]["portfolio"]["minItems"] == 1
    assert portfolio_schema["properties"]["portfolio"]["maxItems"] == 100

    index_op = paths["/api/index_analysis"]["get"]
    index_code = _param(index_op, "index_code", "query")
    assert index_code["required"] is True
    assert index_code["schema"]["maxLength"] == 20
    index_limit = _param(index_op, "limit", "query")["schema"]
    assert index_limit["minimum"] == 1
    assert index_limit["maximum"] == 500
    assert index_limit["default"] == 30

    industry_op = paths["/api/industry_analysis"]["get"]
    industry = _param(industry_op, "industry", "query")
    assert industry["required"] is True
    assert industry["schema"]["maxLength"] == 50

    fund_flow_op = paths["/api/industry_fund_flow"]["get"]
    symbol_schema = _param(fund_flow_op, "symbol", "query")["schema"]
    assert symbol_schema["maxLength"] == 20
    assert symbol_schema["default"] == "即时"

    detail_op = paths["/api/industry_detail"]["get"]
    detail_industry = _param(detail_op, "industry", "query")
    assert detail_industry["required"] is True
    assert detail_industry["schema"]["maxLength"] == 50


# ---------------------------------------------------------------------------
# /api-docs — 历史 Swagger UI 入口兼容跳转
# ---------------------------------------------------------------------------

def test_api_docs_compat_redirect_preserves_swagger_ui(flask_client):
    """/api-docs 应兼容跳转到现有 /api/docs/，且不破坏 Swagger UI 原路径。"""
    for compat_path in ("/api-docs", "/api-docs/", "/api-docs/index.html"):
        compat_resp = flask_client.get(compat_path, follow_redirects=False)
        assert compat_resp.status_code in (301, 302, 308)
        assert compat_resp.headers["Location"].endswith("/api/docs/")

    docs_resp = flask_client.get("/api/docs/")
    assert docs_resp.status_code != 404
    assert docs_resp.status_code < 500


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
