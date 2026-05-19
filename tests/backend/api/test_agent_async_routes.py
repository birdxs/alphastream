"""
Input: Flask 测试 client + mock_event_bus + 注入的 mock coordinator / approval_manager
Output: BE-01c 批次断言（启动 Agent 异步分析、状态/历史查询、HITL approve/reject 双路径）
Pos: tests/backend/api/test_agent_async_routes.py — 后端 API 验收层

[BE-01c 2026-05-17 +08:00] 覆盖 app/web/web_server.py 中：
  /api/start_agent_analysis (POST, line 2483)
  /api/agent_analysis_status/<task_id> (GET, line 2665)
  /api/agent_analysis_history (GET, line 2691)
  /api/agent_pending_approvals (GET, line 2751)
  /api/agent_submit_approval (POST, line 2762)
约束：LLM/akshare/外部 IO 全 mock；不真实调用 LangGraph。
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# --------------------------------------------------------------------------- #
# 共用工具：等待异步线程把任务文件写盘                                       #
# --------------------------------------------------------------------------- #

def _has_error(body: dict) -> bool:
    """兼容旧 {'error': ...} 与新统一外壳 {'error_code': ..., 'success': False}"""
    return "error" in body or "error_code" in body


def _wait_task_persisted(session_manager, task_id: str, timeout: float = 3.0):
    """轮询 session_manager.load_task 直到拿到非 None，或超时。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = session_manager.load_task(task_id)
        if task is not None:
            return task
        time.sleep(0.05)
    return None


# --------------------------------------------------------------------------- #
# 1. POST /api/start_agent_analysis                                            #
# --------------------------------------------------------------------------- #

class TestStartAgentAnalysis:
    """启动 Agent 异步分析（line 2483）"""

    def test_start_agent_analysis_happy_path(self, flask_client, flask_app, monkeypatch):
        """快乐路径：合法股票代码 + mock 协调器 → 返回 task_id 与 running 状态。"""
        # 用 monkeypatch 替换协调器模块级函数，避免触发真实 LangGraph 编译
        fake_result = {
            'final_decision': {'action': 'hold', 'confidence': 0.7},
            'messages': [],
        }
        mock_run = MagicMock(return_value=fake_result)

        from app.web import web_server as ws
        import app.agents.coordinator as coord_mod
        monkeypatch.setattr(coord_mod, 'run_agent_analysis', mock_run)

        resp = flask_client.post(
            '/api/start_agent_analysis',
            json={'stock_code': '600519', 'market_type': 'A'},
        )

        assert resp.status_code == 200, resp.data
        body = resp.get_json()
        assert 'task_id' in body
        # 路由刚创建任务时返回的状态是 'pending'（异步线程稍后改 running→completed）
        assert body['status'] in {'pending', 'running'}
        task_id = body['task_id']

        # 异步线程应在短时间内把任务写盘并最终改为 completed
        task = _wait_task_persisted(ws.agent_session_manager, task_id, timeout=3.0)
        assert task is not None
        assert task['id'] == task_id
        # 状态可能尚在 running，也可能已经 completed —— 两者都允许
        assert task['status'] in {'pending', 'running', 'completed', 'failed'}

        # 协调器至少应被调用过一次（异步线程已 schedule）
        # 给后台线程一点时间
        for _ in range(20):
            if mock_run.called:
                break
            time.sleep(0.05)
        assert mock_run.called, "coordinator.run_agent_analysis 未被异步线程调用"

    def test_start_agent_analysis_invalid_stock_code(self, flask_client):
        """错误路径：非法股票代码 → 400。"""
        resp = flask_client.post(
            '/api/start_agent_analysis',
            json={'stock_code': 'BAD!!!', 'market_type': 'A'},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert _has_error(body)

    def test_start_agent_analysis_missing_stock_code(self, flask_client):
        """错误路径：缺失 stock_code → 400。"""
        resp = flask_client.post(
            '/api/start_agent_analysis',
            json={'market_type': 'A'},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert _has_error(body)


# --------------------------------------------------------------------------- #
# 2. GET /api/agent_analysis_status/<task_id>                                  #
# --------------------------------------------------------------------------- #

class TestAgentAnalysisStatus:
    """查询任务状态（line 2665）"""

    def test_status_happy_path_existing_task(self, flask_client, tmp_path, monkeypatch):
        """快乐路径：预写一份 task json → 返回 200 + 字段齐全。"""
        from app.web import web_server as ws

        task_id = f"test-{uuid.uuid4().hex[:8]}"
        task_data = {
            'id': task_id,
            'status': 'completed',
            'progress': 100,
            'created_at': '2026-05-17 10:00:00',
            'updated_at': '2026-05-17 10:05:00',
            'params': {'stock_code': '600519', 'market_type': 'A'},
            'result': {'final_decision': {'action': 'buy'}},
        }
        ws.agent_session_manager.save_task(task_data)

        try:
            resp = flask_client.get(f'/api/agent_analysis_status/{task_id}')
            assert resp.status_code == 200
            body = resp.get_json()
            assert body['id'] == task_id
            assert body['status'] == 'completed'
            assert body['progress'] == 100
            assert body['params']['stock_code'] == '600519'
        finally:
            ws.agent_session_manager.delete_task(task_id)

    def test_status_not_found(self, flask_client):
        """错误路径：不存在的 task_id → 404。"""
        resp = flask_client.get('/api/agent_analysis_status/nonexistent-task-xyz-999')
        assert resp.status_code == 404
        body = resp.get_json()
        assert _has_error(body)


# --------------------------------------------------------------------------- #
# 3. GET /api/agent_analysis_result/<task_id>  —— 路由不存在                  #
# --------------------------------------------------------------------------- #

class TestAgentAnalysisResult:
    """该路由在 web_server.py 中不存在；结果通过 status 接口的 `result` 字段返回。"""

    def test_result_route_does_not_exist(self, flask_client):
        """该路由未实现 → 404（Flask 默认 not registered）。"""
        resp = flask_client.get('/api/agent_analysis_result/whatever')
        # Flask 对未注册路由返回 404
        assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# 4. POST /api/agent_submit_approval — HITL approve / reject 双路径            #
# --------------------------------------------------------------------------- #

class TestAgentSubmitApproval:
    """HITL 审批（line 2762）"""

    def _seed_pending(self, task_id: str, decision: dict, risk_level: str = 'high'):
        """直接向 approval_manager._pending_approvals 注入一条 pending 请求。"""
        from app.agents.hitl import approval_manager
        with approval_manager._lock:
            approval_manager._pending_approvals[task_id] = {
                'task_id': task_id,
                'decision': decision,
                'risk_level': risk_level,
                'status': 'pending',
                'created_at': time.time(),
                'human_feedback': None,
            }

    def _cleanup(self, task_id: str):
        from app.agents.hitl import approval_manager
        with approval_manager._lock:
            approval_manager._pending_approvals.pop(task_id, None)

    def _spy_eventbus(self, monkeypatch):
        """在 EventBus 单例上挂一个 publish 间谍，返回捕获列表。"""
        from app.core.event_bus import EventBus
        captured = []
        bus = EventBus()
        original_publish = bus.publish

        def _spy(event_name, data=None):
            captured.append((event_name, data))
            return original_publish(event_name, data)

        monkeypatch.setattr(bus, 'publish', _spy)
        return captured

    def test_submit_approval_approved_path(self, flask_client, monkeypatch):
        """approve 路径：提交 approved=True → 200 + EventBus 推送 EVENT_APPROVAL_NEEDED。"""
        captured = self._spy_eventbus(monkeypatch)

        task_id = f"approve-{uuid.uuid4().hex[:8]}"
        decision = {'action': 'buy', 'stock_code': '600519', 'quantity': 100}
        self._seed_pending(task_id, decision, risk_level='high')

        try:
            resp = flask_client.post(
                '/api/agent_submit_approval',
                json={'task_id': task_id, 'approved': True, 'feedback': 'ok by trader'},
            )
            assert resp.status_code == 200
            body = resp.get_json()
            assert body['approved'] is True
            assert '审批已提交' in body.get('message', '')

            # 断言 captured 中有 EVENT_APPROVAL_NEEDED + 关联到本 task_id + 内容含 'approved'
            from app.core.event_bus import EVENT_APPROVAL_NEEDED
            target = [
                (name, data) for (name, data) in captured
                if name == EVENT_APPROVAL_NEEDED
            ]
            assert target, f"未捕获 {EVENT_APPROVAL_NEEDED} 事件，captured={[n for n,_ in captured]}"
            matched = []
            for _, data in target:
                if not isinstance(data, dict):
                    continue
                inner = data.get('data') if 'data' in data else data
                if isinstance(inner, dict) and inner.get('task_id') == task_id \
                        and 'approved' in (inner.get('content') or ''):
                    matched.append(data)
            assert matched, (
                f"approval 事件中未找到 task_id={task_id} 且 content 含 'approved'，target={target}"
            )
        finally:
            self._cleanup(task_id)

    def test_submit_approval_rejected_path(self, flask_client, monkeypatch):
        """reject 路径：提交 approved=False → 200 且 body.approved=False；事件 content 含 'rejected'。"""
        captured = self._spy_eventbus(monkeypatch)

        task_id = f"reject-{uuid.uuid4().hex[:8]}"
        decision = {'action': 'sell', 'stock_code': '600519', 'quantity': 200}
        self._seed_pending(task_id, decision, risk_level='high')

        try:
            resp = flask_client.post(
                '/api/agent_submit_approval',
                json={'task_id': task_id, 'approved': False, 'feedback': 'risk too high'},
            )
            assert resp.status_code == 200
            body = resp.get_json()
            assert body['approved'] is False

            from app.core.event_bus import EVENT_APPROVAL_NEEDED
            target = [
                (name, data) for (name, data) in captured
                if name == EVENT_APPROVAL_NEEDED
            ]
            # 至少有 approval.needed 事件（content 应含 rejected）
            matched_reject = []
            for _, data in target:
                if not isinstance(data, dict):
                    continue
                inner = data.get('data') if 'data' in data else data
                if isinstance(inner, dict) and inner.get('task_id') == task_id \
                        and 'rejected' in (inner.get('content') or ''):
                    matched_reject.append(data)
            assert matched_reject, (
                f"reject 路径未捕获 task_id={task_id} 含 'rejected' 的事件，target={target}"
            )
        finally:
            self._cleanup(task_id)

    def test_submit_approval_missing_task_id(self, flask_client):
        """错误路径：缺失 task_id → 400。"""
        resp = flask_client.post(
            '/api/agent_submit_approval',
            json={'approved': True},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert _has_error(body)

    def test_submit_approval_unknown_task(self, flask_client):
        """错误路径：未注册的 task_id → 404。"""
        resp = flask_client.post(
            '/api/agent_submit_approval',
            json={'task_id': 'never-existed-xyz', 'approved': True},
        )
        assert resp.status_code == 404
        body = resp.get_json()
        assert _has_error(body)


# --------------------------------------------------------------------------- #
# 5. GET /api/agent_pending_approvals                                          #
# --------------------------------------------------------------------------- #

class TestAgentPendingApprovals:
    """查看 pending 审批列表（line 2751）"""

    def test_pending_approvals_happy_path(self, flask_client):
        """快乐路径：注入 1 条 pending → 返回 200 且列表至少含 1 条。"""
        from app.agents.hitl import approval_manager

        task_id = f"pending-{uuid.uuid4().hex[:8]}"
        with approval_manager._lock:
            approval_manager._pending_approvals[task_id] = {
                'task_id': task_id,
                'decision': {'action': 'hold', 'stock_code': '000001'},
                'risk_level': 'high',
                'status': 'pending',
                'created_at': time.time(),
                'human_feedback': None,
            }

        try:
            resp = flask_client.get('/api/agent_pending_approvals')
            assert resp.status_code == 200
            body = resp.get_json()
            assert 'approvals' in body
            assert isinstance(body['approvals'], list)
            assert any(a.get('task_id') == task_id for a in body['approvals'])
        finally:
            with approval_manager._lock:
                approval_manager._pending_approvals.pop(task_id, None)

    def test_pending_approvals_empty_or_error_safe(self, flask_client):
        """错误/边界路径：无 pending 时也应 200 + 空列表（路由本身不抛 404）。"""
        from app.agents.hitl import approval_manager
        # 备份 + 清空
        with approval_manager._lock:
            backup = dict(approval_manager._pending_approvals)
            approval_manager._pending_approvals.clear()

        try:
            resp = flask_client.get('/api/agent_pending_approvals')
            assert resp.status_code == 200
            body = resp.get_json()
            assert body == {'approvals': []}
        finally:
            with approval_manager._lock:
                approval_manager._pending_approvals.update(backup)


# --------------------------------------------------------------------------- #
# 6. GET /api/agent_analysis_history                                           #
# --------------------------------------------------------------------------- #

class TestAgentAnalysisHistory:
    """历史任务列表（line 2691），仅返回 status in [TASK_COMPLETED, TASK_FAILED]。"""

    def test_history_happy_path_includes_completed(self, flask_client):
        from app.web import web_server as ws

        task_id_done = f"hist-done-{uuid.uuid4().hex[:8]}"
        task_id_fail = f"hist-fail-{uuid.uuid4().hex[:8]}"
        task_id_running = f"hist-run-{uuid.uuid4().hex[:8]}"

        ws.agent_session_manager.save_task({
            'id': task_id_done,
            'status': 'completed',
            'progress': 100,
            'created_at': '2026-05-17 10:00:00',
            'updated_at': '2026-05-17 10:05:00',
            'params': {'stock_code': '600000'},
        })
        ws.agent_session_manager.save_task({
            'id': task_id_fail,
            'status': 'failed',
            'progress': 50,
            'created_at': '2026-05-17 09:00:00',
            'updated_at': '2026-05-17 09:01:00',
            'params': {'stock_code': '600001'},
            'error': 'boom',
        })
        ws.agent_session_manager.save_task({
            'id': task_id_running,
            'status': 'running',
            'progress': 30,
            'created_at': '2026-05-17 11:00:00',
            'updated_at': '2026-05-17 11:00:30',
            'params': {'stock_code': '600002'},
        })

        try:
            resp = flask_client.get('/api/agent_analysis_history')
            assert resp.status_code == 200
            body = resp.get_json()
            assert 'history' in body
            ids = {t['id'] for t in body['history']}
            assert task_id_done in ids
            assert task_id_fail in ids
            # running 不应出现
            assert task_id_running not in ids
        finally:
            ws.agent_session_manager.delete_task(task_id_done)
            ws.agent_session_manager.delete_task(task_id_fail)
            ws.agent_session_manager.delete_task(task_id_running)

    def test_history_error_path_on_internal_failure(self, flask_client, monkeypatch):
        """错误路径：get_all_tasks 抛异常 → 500。"""
        from app.web import web_server as ws

        def _boom():
            raise RuntimeError("simulated IO failure")

        monkeypatch.setattr(ws.agent_session_manager, 'get_all_tasks', _boom)
        resp = flask_client.get('/api/agent_analysis_history')
        assert resp.status_code == 500
        body = resp.get_json()
        assert _has_error(body)


# --------------------------------------------------------------------------- #
# 7-8. agent_memory / agent_reflections —— 路由不存在                          #
# --------------------------------------------------------------------------- #

class TestAgentMemoryReflectionsAbsent:
    """这两条路由在 web_server.py 当前实现中不存在，记录为 N/A 并以 404 兜底断言。"""

    def test_agent_memory_route_absent(self, flask_client):
        resp = flask_client.get('/api/agent_memory/600519')
        assert resp.status_code == 404  # 未注册

    def test_agent_reflections_route_absent(self, flask_client):
        resp = flask_client.get('/api/agent_reflections/600519')
        assert resp.status_code == 404  # 未注册
