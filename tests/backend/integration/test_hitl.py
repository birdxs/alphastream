"""
Input: HITL 审批闸门 / 高风险判定 / 超时拒绝契约
Output: pytest 断言
Pos: tests/backend/integration/test_hitl.py — P0-5 确认面回归
一旦我被修改，请更新头部注释与所属文件夹 md。
"""
import threading
import time

import pytest

from app.agents.hitl import (
    HumanApprovalManager,
    approval_manager,
    build_approval_reason,
    should_request_hitl,
)
from app.core.event_bus import (
    EVENT_APPROVAL_NEEDED,
    EVENT_APPROVAL_RESOLVED,
    get_event_bus,
)


@pytest.fixture(autouse=True)
def _clear_pending():
    """隔离用例之间的 pending 状态。"""
    with approval_manager._lock:
        approval_manager._pending_approvals.clear()
    yield
    with approval_manager._lock:
        approval_manager._pending_approvals.clear()


class TestShouldRequestHitl:
    def test_high_overall_risk_triggers(self):
        assert should_request_hitl(
            {'action': 'HOLD', 'confidence': 0.2},
            {'overall_risk': '高'},
        ) is True

    def test_high_buy_confidence_triggers(self):
        assert should_request_hitl(
            {'action': 'BUY', 'confidence': 0.9},
            {},
        ) is True

    def test_low_risk_hold_skips(self):
        assert should_request_hitl(
            {'action': 'HOLD', 'confidence': 0.5, 'risk_level': '中'},
            {'overall_risk': '中'},
        ) is False

    def test_buy_below_threshold_skips(self):
        assert should_request_hitl(
            {'action': 'BUY', 'confidence': 0.5},
            {},
        ) is False

    def test_build_reason_contains_fields(self):
        reason = build_approval_reason(
            {'action': 'BUY', 'confidence': 0.9, 'rationale': '基本面强'},
            {'overall_risk': '高'},
        )
        assert '风险评估' in reason or '高' in reason
        assert 'BUY' in reason or '基本面' in reason


class TestHITLApproval:
    """HumanApprovalManager 核心：阻塞等待 / 提交 / 超时拒绝。"""

    def test_approve_flow(self):
        manager = HumanApprovalManager()
        decision = {'action': 'BUY', 'confidence': 0.9, 'reasoning': '看多'}
        result_box = []

        def requester():
            result_box.append(
                manager.request_approval('task-approve', decision, risk_level='high', timeout=5)
            )

        t = threading.Thread(target=requester)
        t.start()
        time.sleep(0.15)
        pending = manager.get_pending_approvals()
        assert any(p['task_id'] == 'task-approve' for p in pending)
        assert manager.submit_approval('task-approve', True, '人工确认买入')
        t.join(timeout=3)
        assert len(result_box) == 1
        assert result_box[0]['approved'] is True
        assert result_box[0]['approval_type'] == 'human'
        assert result_box[0]['human_feedback'] == '人工确认买入'
        assert manager.get_pending_approvals() == []

    def test_reject_flow(self):
        manager = HumanApprovalManager()
        decision = {'action': 'BUY', 'confidence': 0.95}
        result_box = []

        def requester():
            result_box.append(
                manager.request_approval('task-reject', decision, risk_level='high', timeout=5)
            )

        t = threading.Thread(target=requester)
        t.start()
        time.sleep(0.15)
        assert manager.submit_approval('task-reject', False, '风险过高拒绝')
        t.join(timeout=3)
        assert result_box[0]['approved'] is False
        assert result_box[0]['approval_type'] == 'human'
        assert result_box[0]['human_feedback'] == '风险过高拒绝'

    def test_timeout_rejects_high_risk(self):
        """高风险超时必须拒绝，禁止静默通过。"""
        manager = HumanApprovalManager()
        decision = {'action': 'BUY', 'confidence': 0.99, 'reasoning': 'aggressive'}
        result = manager.request_approval(
            'task-timeout', decision, risk_level='high', timeout=0.3
        )
        assert result['approved'] is False
        assert result['approval_type'] == 'timeout_reject'
        assert result.get('timeout') is True
        assert result.get('auto_approved') is False
        assert '超时' in (result.get('human_feedback') or '')

    def test_submit_missing_returns_false(self):
        manager = HumanApprovalManager()
        assert manager.submit_approval('no-such-task', True) is False

    def test_task_status_hook_called(self):
        manager = HumanApprovalManager()
        calls = []

        def hook(task_type, task_id, status, result=None, error=None):
            calls.append((task_type, task_id, status, result, error))

        manager.set_task_status_hook(hook)
        decision = {'action': 'BUY', 'confidence': 0.8}
        result_box = []

        def requester():
            result_box.append(
                manager.request_approval('task-hook', decision, risk_level='高', timeout=5)
            )

        t = threading.Thread(target=requester)
        t.start()
        time.sleep(0.15)
        statuses = [c[2] for c in calls]
        assert 'awaiting_approval' in statuses
        manager.submit_approval('task-hook', True, 'ok')
        t.join(timeout=3)
        statuses_after = [c[2] for c in calls]
        assert any(s in ('approved', 'rejected') for s in statuses_after)
        assert result_box[0]['approved'] is True


class TestHITLEventBus:
    def test_request_publishes_approval_needed(self, agent_event_recorder):
        recorder = agent_event_recorder
        manager = HumanApprovalManager()
        decision = {'action': 'BUY', 'confidence': 0.85}
        done = threading.Event()

        def requester():
            manager.request_approval('task-evt', decision, risk_level='high', timeout=3)
            done.set()

        t = threading.Thread(target=requester)
        t.start()
        time.sleep(0.2)
        # agent_event_recorder: .events = List[Tuple[name, data]]；.filter(name)/.has(name)
        needed_payloads = list(recorder.filter(EVENT_APPROVAL_NEEDED)) + list(
            recorder.filter('approval_needed')
        )
        assert needed_payloads, f'expected approval.needed, names={recorder.names()}'
        payload = needed_payloads[0] if not isinstance(needed_payloads[0], tuple) else needed_payloads[0]
        if isinstance(payload, tuple):
            payload = payload[1] if len(payload) > 1 else {}
        assert isinstance(payload, dict)
        assert payload.get('event_type') in ('approval_needed', None) or payload.get('type') == 'approval_needed'
        assert payload.get('task_id') == 'task-evt'
        manager.submit_approval('task-evt', False, 'deny')
        t.join(timeout=3)
        done.wait(timeout=2)
        resolved_payloads = (
            list(recorder.filter(EVENT_APPROVAL_RESOLVED))
            + list(recorder.filter('approval_resolved'))
            + list(recorder.filter('approval.resolved'))
        )
        # resolved 至少应有一条，或任意 payload 标记终态
        assert resolved_payloads or any(
            isinstance(d, dict) and d.get('status') in ('rejected', 'approved', 'timeout_reject')
            for _, d in recorder.events
        )


class TestPendingApiShape:
    """进程内 approval_manager 与 list 形状（API 层另有 routes 测）。"""

    def test_global_manager_list_empty_initially(self):
        assert isinstance(approval_manager.get_pending_approvals(), list)

    def test_pending_payload_fields(self):
        manager = HumanApprovalManager()
        decision = {'action': 'STRONG_BUY', 'confidence': 0.99}
        result_box = []

        def requester():
            result_box.append(
                manager.request_approval(
                    'task-shape',
                    decision,
                    risk_level='高',
                    timeout=5,
                    reason='单测形状',
                )
            )

        t = threading.Thread(target=requester)
        t.start()
        time.sleep(0.15)
        pending = manager.get_pending_approvals()
        item = next(p for p in pending if p['task_id'] == 'task-shape')
        for key in ('task_id', 'decision', 'risk_level', 'status', 'created_at', 'timeout', 'reason'):
            assert key in item
        assert item['status'] == 'pending'
        assert item['reason'] == '单测形状'
        manager.submit_approval('task-shape', True)
        t.join(timeout=3)
