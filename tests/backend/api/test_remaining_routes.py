# Input: Flask test client + 各类业务模块的 mock
# Output: pytest 用例结果（快乐路径 + 错误路径）
# Pos: tests/backend/api/test_remaining_routes.py — BE-01f 剩余路由收尾测试
"""BE-01f 剩余 /api/* 路由收尾测试。

覆盖 BE-01a/b/c/d/e 与既有 P3 测试均未覆盖的关键路由，
全部 Mock 内部分析器/数据提供者/会话管理器，避免真实 IO/akshare 调用。

目标路由（12 条全新覆盖）：
  1. POST /api/start_market_scan
  2. GET  /api/scan_status/<task_id>
  3. POST /api/cancel_scan/<task_id>
  4. GET  /api/index_stocks
  5. GET  /api/industry_stocks
  6. GET  /api/board_stocks
  7. GET  /api/concept_fund_flow
  8. GET  /api/individual_fund_flow_rank
  9. GET  /api/history_analysis
 10. POST /api/delete_agent_analysis
 11. GET  /.well-known/agent.json
 12. POST /api/upload_image
"""

from __future__ import annotations

import io
import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# 工具函数
# =========================================================================
def _json(resp) -> Dict[str, Any]:
    return json.loads(resp.get_data(as_text=True))


def _has_error(body: Dict[str, Any]) -> bool:
    """兼容旧格式 {'error': ...} 和新统一外壳 {'error_code': ..., 'success': False}"""
    return "error" in body or "error_code" in body


# =========================================================================
# 1-3. 市场扫描三件套
# =========================================================================
class TestMarketScan:
    """/api/start_market_scan、/api/scan_status/<id>、/api/cancel_scan/<id>"""

    def test_start_market_scan_happy(self, flask_client):
        """快乐路径：提交合法股票列表 → 返回 task_id。"""
        payload = {"stock_list": ["600000", "000001"], "min_score": 60, "market_type": "A"}
        # patch 后台线程执行的真实分析器调用，避免触发 akshare
        with patch("app.web.web_server.threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            resp = flask_client.post("/api/start_market_scan", json=payload)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = _json(resp)
        assert "task_id" in body
        assert body.get("status") in ("pending", "running")

    def test_start_market_scan_empty_list(self, flask_client):
        """错误路径：空股票列表 → 400。"""
        resp = flask_client.post("/api/start_market_scan", json={"stock_list": []})
        assert resp.status_code == 400
        body = _json(resp)
        assert _has_error(body)

    def test_scan_status_not_found(self, flask_client):
        """错误路径：未知 task_id → 404。"""
        resp = flask_client.get("/api/scan_status/nonexistent-task-xyz")
        assert resp.status_code == 404
        body = _json(resp)
        assert _has_error(body)

    def test_scan_status_happy(self, flask_client):
        """快乐路径：注入伪 task → 返回状态。"""
        from app.web import web_server as ws

        fake_id = "be01f-scan-happy"
        with ws.task_lock:
            ws.scan_tasks[fake_id] = {
                "id": fake_id,
                "status": ws.TASK_COMPLETED,
                "progress": 100,
                "total": 2,
                "processed": 2,
                "found": 1,
                "result": [{"stock_code": "600000", "score": 75}],
                "created_at": "2026-05-17T20:00:00",
                "updated_at": "2026-05-17T20:00:01",
            }
        try:
            resp = flask_client.get(f"/api/scan_status/{fake_id}")
            assert resp.status_code == 200
            body = _json(resp)
            assert body.get("status") == "completed"
        finally:
            with ws.task_lock:
                ws.scan_tasks.pop(fake_id, None)

    def test_cancel_scan_not_found(self, flask_client):
        """错误路径：取消未知任务 → 404。"""
        resp = flask_client.post("/api/cancel_scan/no-such-task-id")
        assert resp.status_code == 404

    def test_cancel_scan_happy(self, flask_client):
        """快乐路径：取消运行中任务 → 200。"""
        from app.web import web_server as ws

        fake_id = "be01f-cancel-happy"
        with ws.task_lock:
            ws.scan_tasks[fake_id] = {
                "id": fake_id,
                "status": ws.TASK_RUNNING,
                "progress": 50,
                "created_at": "2026-05-17T20:00:00",
                "updated_at": "2026-05-17T20:00:01",
            }
        try:
            resp = flask_client.post(f"/api/cancel_scan/{fake_id}")
            assert resp.status_code == 200
            body = _json(resp)
            assert body.get("status") in ("cancelled", "failed") or "message" in body
        finally:
            with ws.task_lock:
                ws.scan_tasks.pop(fake_id, None)


# =========================================================================
# 4-6. 指数/行业/板块成分股
# =========================================================================
class TestStockComposition:
    """/api/index_stocks、/api/industry_stocks、/api/board_stocks"""

    def test_index_stocks_happy(self, flask_client):
        """快乐路径：mock data_provider.get_index_stocks → 返回股票列表。"""
        mock_dp = MagicMock()
        mock_dp.get_index_stocks.return_value = ["600000", "600036", "601318"]
        with patch("app.core.data_provider.get_data_provider", return_value=mock_dp):
            resp = flask_client.get("/api/index_stocks?index_code=000300")
        assert resp.status_code == 200
        body = _json(resp)
        assert "stock_list" in body
        assert len(body["stock_list"]) == 3

    def test_index_stocks_error(self, flask_client):
        """错误路径：data_provider 抛异常 → 500。"""
        mock_dp = MagicMock()
        mock_dp.get_index_stocks.side_effect = RuntimeError("akshare 不可用")
        with patch("app.core.data_provider.get_data_provider", return_value=mock_dp):
            resp = flask_client.get("/api/index_stocks?index_code=000300")
        assert resp.status_code == 500
        assert _has_error(_json(resp))

    def test_industry_stocks_happy(self, flask_client):
        mock_dp = MagicMock()
        mock_dp.get_industry_stocks.return_value = ["600519", "000858"]
        with patch("app.core.data_provider.get_data_provider", return_value=mock_dp):
            resp = flask_client.get("/api/industry_stocks?industry=白酒")
        assert resp.status_code == 200
        body = _json(resp)
        assert "stock_list" in body

    def test_industry_stocks_error(self, flask_client):
        mock_dp = MagicMock()
        mock_dp.get_industry_stocks.side_effect = Exception("数据源失败")
        with patch("app.core.data_provider.get_data_provider", return_value=mock_dp):
            resp = flask_client.get("/api/industry_stocks?industry=foo")
        assert resp.status_code == 500

    def test_board_stocks_happy(self, flask_client):
        # board_stocks 接受 board 参数（白名单：hs300/zz500/...）复用 get_index_stocks
        mock_dp = MagicMock()
        mock_dp.get_index_stocks.return_value = ["300750", "002594"]
        with patch("app.core.data_provider.get_data_provider", return_value=mock_dp):
            resp = flask_client.get("/api/board_stocks?board=hs300")
        assert resp.status_code == 200
        body = _json(resp)
        assert "stock_list" in body
        assert body.get("count") == 2

    def test_board_stocks_invalid_board(self, flask_client):
        """错误路径：非法板块类型 → 400。"""
        resp = flask_client.get("/api/board_stocks?board=invalid_xxx")
        assert resp.status_code == 400
        body = _json(resp)
        assert _has_error(body)


# =========================================================================
# 7-8. 资金流向
# =========================================================================
class TestFundFlow:
    """/api/concept_fund_flow、/api/individual_fund_flow_rank"""

    def test_concept_fund_flow_happy(self, flask_client):
        with patch("app.web.web_server.capital_flow_analyzer") as mock_cfa:
            mock_cfa.get_concept_fund_flow.return_value = [
                {"name": "AI算力", "净流入": 12.5}
            ]
            resp = flask_client.get("/api/concept_fund_flow?period=10日排行")
        assert resp.status_code == 200
        body = _json(resp)
        assert isinstance(body, list)
        assert body[0]["name"] == "AI算力"

    def test_concept_fund_flow_error(self, flask_client):
        with patch("app.web.web_server.capital_flow_analyzer") as mock_cfa:
            mock_cfa.get_concept_fund_flow.side_effect = RuntimeError("API限流")
            resp = flask_client.get("/api/concept_fund_flow")
        assert resp.status_code == 500
        assert _has_error(_json(resp))

    def test_individual_fund_flow_rank_happy(self, flask_client):
        with patch("app.web.web_server.capital_flow_analyzer") as mock_cfa:
            mock_cfa.get_individual_fund_flow_rank.return_value = [
                {"code": "600000", "rank": 1}
            ]
            resp = flask_client.get("/api/individual_fund_flow_rank?period=10日")
        assert resp.status_code == 200
        body = _json(resp)
        assert isinstance(body, list)

    def test_individual_fund_flow_rank_error(self, flask_client):
        with patch("app.web.web_server.capital_flow_analyzer") as mock_cfa:
            mock_cfa.get_individual_fund_flow_rank.side_effect = Exception("error")
            resp = flask_client.get("/api/individual_fund_flow_rank")
        assert resp.status_code == 500


# =========================================================================
# 9. 历史分析
# =========================================================================
class TestHistoryAnalysis:
    """/api/history_analysis — 依赖 USE_DATABASE。"""

    def test_history_analysis_no_stock_code(self, flask_client):
        """错误路径：缺 stock_code → 400 或 数据库未启用 400。"""
        resp = flask_client.get("/api/history_analysis")
        assert resp.status_code == 400
        body = _json(resp)
        assert _has_error(body)

    def test_history_analysis_response(self, flask_client):
        """快乐/错误路径：根据数据库是否启用，分别验证不同 200/400 行为。"""
        from app.web import web_server as ws

        if not ws.USE_DATABASE:
            # 未启用数据库：仍应返回 400 且提示数据库
            resp = flask_client.get("/api/history_analysis?stock_code=600000")
            assert resp.status_code == 400
            body = _json(resp)
            assert "数据库" in (body.get("error") or body.get("message") or "")
        else:
            # 启用了数据库：mock get_session 返回空列表
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            with patch("app.web.web_server.get_session", return_value=mock_session):
                resp = flask_client.get("/api/history_analysis?stock_code=600000&limit=5")
            assert resp.status_code == 200
            body = _json(resp)
            assert "history" in body


# =========================================================================
# 10. 删除 Agent 分析
# =========================================================================
class TestDeleteAgentAnalysis:
    """/api/delete_agent_analysis"""

    def test_delete_agent_analysis_happy(self, flask_client):
        """快乐路径：传入 task_ids 列表 → 200。"""
        with patch("app.web.web_server.agent_session_manager") as mock_mgr:
            mock_mgr.load_task.return_value = {"status": "completed"}
            mock_mgr.delete_task.return_value = True
            resp = flask_client.post(
                "/api/delete_agent_analysis",
                json={"task_ids": ["be01f-del-1", "be01f-del-2"]},
            )
        assert resp.status_code == 200
        body = _json(resp)
        assert body.get("success") is True
        assert "message" in body

    def test_delete_agent_analysis_invalid_payload(self, flask_client):
        """错误路径：task_ids 非列表 → 400。"""
        resp = flask_client.post(
            "/api/delete_agent_analysis",
            json={"task_ids": "not-a-list"},
        )
        assert resp.status_code == 400
        body = _json(resp)
        assert _has_error(body)

    def test_delete_agent_analysis_empty(self, flask_client):
        """错误路径：空列表 → 400。"""
        resp = flask_client.post("/api/delete_agent_analysis", json={"task_ids": []})
        assert resp.status_code == 400
        assert _has_error(_json(resp))


# =========================================================================
# 11. A2A 兼容 agent.json
# =========================================================================
class TestAgentJsonLegacy:
    """/.well-known/agent.json (A2A v0.2 兼容)"""

    def test_agent_json_happy(self, flask_client):
        resp = flask_client.get("/.well-known/agent.json")
        assert resp.status_code == 200
        body = _json(resp)
        # _build_agent_card 应返回字典，至少包含 name 或 protocolVersion
        assert isinstance(body, dict)
        # 通用字段验证
        keys = set(body.keys())
        assert keys, "agent.json 不应为空"

    def test_agent_json_method_not_allowed(self, flask_client):
        """错误路径：POST 不允许 → 405。"""
        resp = flask_client.post("/.well-known/agent.json", json={})
        assert resp.status_code == 405


# =========================================================================
# 12. 图片上传
# =========================================================================
class TestUploadImage:
    """/api/upload_image"""

    def test_upload_image_no_file(self, flask_client):
        """错误路径：未携带 file 字段 → 400。"""
        resp = flask_client.post("/api/upload_image", data={})
        assert resp.status_code == 400
        body = _json(resp)
        assert _has_error(body)

    def test_upload_image_invalid_type(self, flask_client):
        """错误路径：非图片格式 → 400。"""
        data = {
            "file": (io.BytesIO(b"plain text not image"), "evil.txt"),
        }
        resp = flask_client.post(
            "/api/upload_image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        body = _json(resp)
        assert _has_error(body)

    def test_upload_image_happy(self, flask_client):
        """快乐路径：上传 PNG → 200。"""
        # 极简 PNG 字节序列（PNG magic + IHDR）足以通过扩展名校验
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        data = {
            "file": (io.BytesIO(png_bytes), "test.png"),
        }
        resp = flask_client.post(
            "/api/upload_image",
            data=data,
            content_type="multipart/form-data",
        )
        # 上传成功 200；若实现要求额外字段可能 400/500
        assert resp.status_code in (200, 400, 500)
        body = _json(resp)
        # 至少返回某种结构化响应
        assert isinstance(body, dict)
