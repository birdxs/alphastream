# Input  : Flask test_client (flask_client fixture) + monkeypatch (analyzer mocks)
# Output : pytest 用例：覆盖约 10 条业务分析路由（ETF / 基本面 / 资金流 / 情景 / QA / 风险 / 指数 / 行业 / 行业比较 / 投资组合风险）
# Pos    : tests/backend/api/test_business_analysis_routes.py
# 说明   : BE-01e 小批量验收。LLM/akshare/外部 IO 全 mock；不发起任何真实分析。
"""BE-01e 业务分析路由测试（小批量 ~10 路由）。

覆盖路由（精确签名核对自 app/web/web_server.py）：
1.  POST /api/start_etf_analysis           (line 883)
2.  GET  /api/etf_analysis_status/<id>     (line 942)   ← 注：原任务列 etf_result 实际不存在，使用 etf_analysis_status
3.  POST /api/fundamental_analysis         (line 1839)
4.  POST /api/capital_flow                 (line 1933)
5.  POST /api/scenario_predict             (line 1959)
6.  POST /api/qa                           (line 1985)
7.  POST /api/risk_analysis                (line 2011)
8.  POST /api/portfolio_risk               (line 2036) ← 注：原任务列 portfolio_analysis 不存在，使用 portfolio_risk
9.  GET  /api/index_analysis               (line 2055)
10. GET  /api/industry_analysis            (line 2074)
11. GET  /api/industry_compare             (line 2128)

每路由 ≥ 2 用例（快乐路径 + 错误路径）。
错误路径覆盖：缺字段 + 非法 stock_code/period 值。
所有内部分析器全 mock，断言路由层正确转发参数。

缺陷登记：
- /api/portfolio_analysis 不存在 → 仓库实为 /api/portfolio_risk（参见 web_server.py:2036）
- /api/etf_result/<id>     不存在 → 仓库实为 /api/etf_analysis_status/<id>（参见 web_server.py:942）
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
    """断言响应体不泄露 Python 堆栈关键字。"""
    body = resp.data.decode("utf-8", errors="replace").lower()
    forbidden = ["traceback (most recent call last)", 'file "', "raise "]
    for fb in forbidden:
        assert fb not in body, f"4xx 错误响应不应泄露堆栈关键字 {fb!r}: {body[:300]}"


# --------------------------------------------------------------------------- #
# 公共 fixture：批量 mock 所有分析器（避免真实 IO/LLM）
# --------------------------------------------------------------------------- #

@pytest.fixture
def patched_analyzers(monkeypatch):
    """对路由层使用的分析器实例打桩，记录调用参数。

    分析器实例位于 app.web.web_server 模块全局：
      - fundamental_analyzer       (line 132)
      - capital_flow_analyzer      (line 133)
      - scenario_predictor         (line 134)
      - stock_qa                   (line 135)
      - risk_monitor               (line 136)
      - index_industry_analyzer    (line 137)
      - EtfAnalyzer (class)        (line 39, instantiated inside thread)
    """
    import app.web.web_server as ws

    calls: Dict[str, list] = {
        "fundamental": [],
        "capital_flow": [],
        "scenario": [],
        "qa": [],
        "risk_stock": [],
        "risk_portfolio": [],
        "index": [],
        "industry": [],
        "industry_compare": [],
        "etf": [],
    }

    # 1. fundamental_analyzer.calculate_fundamental_score(stock_code)
    def _fake_fund(stock_code):
        calls["fundamental"].append(stock_code)
        return {"stock_code": stock_code, "score": 80, "mocked": True}
    monkeypatch.setattr(
        ws.fundamental_analyzer, "calculate_fundamental_score", _fake_fund, raising=True
    )

    # 2. capital_flow_analyzer.calculate_capital_flow_score(stock_code, market_type)
    def _fake_cf(stock_code, market_type):
        calls["capital_flow"].append((stock_code, market_type))
        return {"stock_code": stock_code, "market_type": market_type, "flow_score": 60}
    monkeypatch.setattr(
        ws.capital_flow_analyzer, "calculate_capital_flow_score", _fake_cf, raising=True
    )

    # 3. scenario_predictor.generate_scenarios(stock_code, market_type, days)
    def _fake_scen(stock_code, market_type, days):
        calls["scenario"].append((stock_code, market_type, days))
        return {"stock_code": stock_code, "days": days, "scenarios": ["bull", "bear"]}
    monkeypatch.setattr(
        ws.scenario_predictor, "generate_scenarios", _fake_scen, raising=True
    )

    # 4. stock_qa.answer_question(stock_code, question, market_type)
    def _fake_qa(stock_code, question, market_type):
        calls["qa"].append((stock_code, question, market_type))
        return {"stock_code": stock_code, "answer": f"mocked answer for: {question}"}
    monkeypatch.setattr(ws.stock_qa, "answer_question", _fake_qa, raising=True)

    # 5a. risk_monitor.analyze_stock_risk(stock_code, market_type)
    def _fake_risk_stock(stock_code, market_type):
        calls["risk_stock"].append((stock_code, market_type))
        return {"stock_code": stock_code, "risk_level": "medium"}
    monkeypatch.setattr(
        ws.risk_monitor, "analyze_stock_risk", _fake_risk_stock, raising=True
    )

    # 5b. risk_monitor.analyze_portfolio_risk(portfolio)
    def _fake_risk_portfolio(portfolio):
        calls["risk_portfolio"].append(portfolio)
        return {"portfolio_size": len(portfolio), "overall_risk": "low"}
    monkeypatch.setattr(
        ws.risk_monitor, "analyze_portfolio_risk", _fake_risk_portfolio, raising=True
    )

    # 6. index_industry_analyzer.analyze_index(index_code, limit)
    def _fake_index(index_code, limit):
        calls["index"].append((index_code, limit))
        return {"index_code": index_code, "limit": limit, "trend": "up"}
    monkeypatch.setattr(
        ws.index_industry_analyzer, "analyze_index", _fake_index, raising=True
    )

    # 7. index_industry_analyzer.analyze_industry(industry, limit)
    def _fake_industry(industry, limit):
        calls["industry"].append((industry, limit))
        return {"industry": industry, "limit": limit, "trend": "flat"}
    monkeypatch.setattr(
        ws.index_industry_analyzer, "analyze_industry", _fake_industry, raising=True
    )

    # 8. index_industry_analyzer.compare_industries(limit)
    def _fake_compare(limit):
        calls["industry_compare"].append(limit)
        return {"limit": limit, "items": [{"industry": "AI", "score": 90}]}
    monkeypatch.setattr(
        ws.index_industry_analyzer, "compare_industries", _fake_compare, raising=True
    )

    # 9. EtfAnalyzer 类 → 假实例（线程内实例化，需打桩类本身）
    class _FakeEtfAnalyzer:
        def __init__(self, etf_code, stock_analyzer):
            calls["etf"].append(etf_code)
            self.etf_code = etf_code

        def run_analysis(self):
            return {"etf_code": self.etf_code, "score": 70, "mocked": True}

    monkeypatch.setattr(ws, "EtfAnalyzer", _FakeEtfAnalyzer, raising=True)

    return calls


# =========================================================================== #
# 1. POST /api/start_etf_analysis  (line 883)
# =========================================================================== #

class TestStartEtfAnalysis:
    def test_happy_returns_task_id(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/start_etf_analysis",
            json={"etf_code": "510300"},
        )
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert "task_id" in data and isinstance(data["task_id"], str) and data["task_id"]
        assert "status" in data
        # 给后台 daemon 线程极短时间，避免阻塞
        time.sleep(0.15)

    def test_missing_etf_code_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/start_etf_analysis",
            json={},
        )
        assert resp.status_code == 400
        data = _json(resp)
        assert "error" in data
        _no_stacktrace(resp)


# =========================================================================== #
# 2. GET /api/etf_analysis_status/<task_id>  (line 942)
#    （任务列 "etf_result" 不存在，使用 etf_analysis_status；记录为缺陷）
# =========================================================================== #

class TestEtfAnalysisStatus:
    def test_unknown_task_returns_404(self, flask_client):
        resp = flask_client.get("/api/etf_analysis_status/no-such-etf-task")
        assert resp.status_code == 404
        data = _json(resp)
        assert "error" in data
        _no_stacktrace(resp)

    def test_status_after_start_returns_schema(self, flask_client, patched_analyzers):
        # 先启动
        start = flask_client.post(
            "/api/start_etf_analysis",
            json={"etf_code": "510500"},
        )
        assert start.status_code == 200, start.data[:200]
        task_id = _json(start)["task_id"]

        resp = flask_client.get(f"/api/etf_analysis_status/{task_id}")
        assert resp.status_code == 200, resp.data[:200]
        data = _json(resp)
        for key in ("id", "status", "progress", "created_at", "updated_at"):
            assert key in data, f"缺失字段 {key}: {data}"
        assert data["id"] == task_id


# =========================================================================== #
# 3. POST /api/fundamental_analysis  (line 1839)
# =========================================================================== #

class TestFundamentalAnalysis:
    def test_happy_forwards_stock_code(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/fundamental_analysis",
            json={"stock_code": "000001"},
        )
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert data.get("score") == 80
        # 断言路由层正确转发参数
        assert patched_analyzers["fundamental"] == ["000001"]

    def test_missing_stock_code_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post("/api/fundamental_analysis", json={})
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)
        # 无下游调用
        assert patched_analyzers["fundamental"] == []

    def test_invalid_stock_code_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/fundamental_analysis",
            json={"stock_code": "ZZZZZZ"},
        )
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)


# =========================================================================== #
# 4. POST /api/capital_flow  (line 1933) — 与页面路由 /capital_flow 区分
# =========================================================================== #

class TestCapitalFlow:
    def test_happy_forwards_params(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/capital_flow",
            json={"stock_code": "000002", "market_type": "A"},
        )
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert data.get("flow_score") == 60
        assert patched_analyzers["capital_flow"] == [("000002", "A")]

    def test_missing_stock_code_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post("/api/capital_flow", json={})
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)

    def test_invalid_stock_code_with_market_returns_400(
        self, flask_client, patched_analyzers
    ):
        # 仅当 market_type 非空时才走 validate_stock_code
        resp = flask_client.post(
            "/api/capital_flow",
            json={"stock_code": "BADCODE", "market_type": "A"},
        )
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)


# =========================================================================== #
# 5. POST /api/scenario_predict  (line 1959)
# =========================================================================== #

class TestScenarioPredict:
    def test_happy_forwards_days(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/scenario_predict",
            json={"stock_code": "600519", "market_type": "A", "days": 90},
        )
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert data.get("days") == 90
        assert patched_analyzers["scenario"] == [("600519", "A", 90)]

    def test_default_days_60(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/scenario_predict",
            json={"stock_code": "600519"},
        )
        assert resp.status_code == 200
        # days 默认 60
        assert patched_analyzers["scenario"][-1][2] == 60

    def test_missing_stock_code_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post("/api/scenario_predict", json={})
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)

    def test_invalid_stock_code_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/scenario_predict",
            json={"stock_code": "@@@@@@", "market_type": "A"},
        )
        assert resp.status_code == 400
        _no_stacktrace(resp)


# =========================================================================== #
# 6. POST /api/qa  (line 1985)
# =========================================================================== #

class TestQa:
    def test_happy_forwards_params(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/qa",
            json={
                "stock_code": "000001",
                "question": "最近趋势如何？",
                "market_type": "A",
            },
        )
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert "answer" in data and "mocked answer" in data["answer"]
        assert patched_analyzers["qa"] == [("000001", "最近趋势如何？", "A")]

    def test_missing_question_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/qa",
            json={"stock_code": "000001"},
        )
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)

    def test_missing_stock_code_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/qa",
            json={"question": "随便问问"},
        )
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)


# =========================================================================== #
# 7. POST /api/risk_analysis  (line 2011)
# =========================================================================== #

class TestRiskAnalysis:
    def test_happy_forwards_params(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/risk_analysis",
            json={"stock_code": "000001", "market_type": "A"},
        )
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert data.get("risk_level") == "medium"
        assert patched_analyzers["risk_stock"] == [("000001", "A")]

    def test_missing_stock_code_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post("/api/risk_analysis", json={})
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)

    def test_invalid_stock_code_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post(
            "/api/risk_analysis",
            json={"stock_code": "INVALID!!!", "market_type": "A"},
        )
        assert resp.status_code == 400
        _no_stacktrace(resp)


# =========================================================================== #
# 8. POST /api/portfolio_risk  (line 2036)
#    （任务列 /api/portfolio_analysis 实际不存在，记录为缺陷）
# =========================================================================== #

class TestPortfolioRisk:
    def test_happy_forwards_portfolio(self, flask_client, patched_analyzers):
        portfolio = [
            {"stock_code": "000001", "weight": 0.4},
            {"stock_code": "600519", "weight": 0.6},
        ]
        resp = flask_client.post(
            "/api/portfolio_risk",
            json={"portfolio": portfolio},
        )
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert data.get("portfolio_size") == 2
        assert patched_analyzers["risk_portfolio"] == [portfolio]

    def test_empty_portfolio_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post("/api/portfolio_risk", json={"portfolio": []})
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)

    def test_missing_portfolio_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.post("/api/portfolio_risk", json={})
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)


# =========================================================================== #
# 9. GET /api/index_analysis  (line 2055)
# =========================================================================== #

class TestIndexAnalysis:
    def test_happy_forwards_limit(self, flask_client, patched_analyzers):
        resp = flask_client.get(
            "/api/index_analysis",
            query_string={"index_code": "000300", "limit": 50},
        )
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert data.get("index_code") == "000300"
        assert patched_analyzers["index"] == [("000300", 50)]

    def test_missing_index_code_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.get("/api/index_analysis")
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)

    def test_invalid_limit_returns_500_or_400(self, flask_client, patched_analyzers):
        # limit 非整数 → int() 抛 ValueError → except 兜底 500（不应泄露栈）
        resp = flask_client.get(
            "/api/index_analysis",
            query_string={"index_code": "000300", "limit": "not-a-number"},
        )
        # 接受 400/500 任一；只要不泄露堆栈
        assert resp.status_code in (400, 500)
        _no_stacktrace(resp)


# =========================================================================== #
# 10. GET /api/industry_analysis  (line 2074)
# =========================================================================== #

class TestIndustryAnalysis:
    def test_happy_forwards_params(self, flask_client, patched_analyzers):
        resp = flask_client.get(
            "/api/industry_analysis",
            query_string={"industry": "半导体", "limit": 20},
        )
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert data.get("industry") == "半导体"
        assert patched_analyzers["industry"] == [("半导体", 20)]

    def test_missing_industry_returns_400(self, flask_client, patched_analyzers):
        resp = flask_client.get("/api/industry_analysis")
        assert resp.status_code == 400
        assert "error" in _json(resp)
        _no_stacktrace(resp)


# =========================================================================== #
# 11. GET /api/industry_compare  (line 2128)
# =========================================================================== #

class TestIndustryCompare:
    def test_happy_default_limit(self, flask_client, patched_analyzers):
        resp = flask_client.get("/api/industry_compare")
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert "items" in data
        # 默认 limit=10
        assert patched_analyzers["industry_compare"] == [10]

    def test_happy_with_limit(self, flask_client, patched_analyzers):
        resp = flask_client.get(
            "/api/industry_compare",
            query_string={"limit": 25},
        )
        assert resp.status_code == 200
        assert patched_analyzers["industry_compare"][-1] == 25

    def test_invalid_limit_returns_500_or_400(self, flask_client, patched_analyzers):
        resp = flask_client.get(
            "/api/industry_compare",
            query_string={"limit": "abc"},
        )
        assert resp.status_code in (400, 500)
        _no_stacktrace(resp)
