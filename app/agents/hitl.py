"""
Input: Agent分析结果 + 人工审批决策
Output: 审批后的最终决策 + EventBus approval_needed 事件流
Pos: app/agents/hitl.py - Human-in-the-Loop 审批机制
[R3 Q4 P2 2026-04-15 +08:00] 在 request_approval/submit_approval 时向 EventBus publish
  EVENT_APPROVAL_NEEDED, 让前端终端看见 [APPROVAL] 前缀的 reasoning 行。

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
import threading
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _publish_approval_event(action: str, task_id: str, decision: Dict[str, Any],
                            risk_level: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """[R3 Q4 P2] 向 EventBus 发布 approval 相关事件 (前缀 [APPROVAL] 走 reasoning 通道)。"""
    try:
        from app.core.event_bus import get_event_bus, EVENT_APPROVAL_NEEDED
        decision_summary = str(decision.get('action') or decision.get('recommendation') or decision)[:120]
        content = f'[APPROVAL] {action} task={task_id} risk={risk_level} — {decision_summary}'
        payload = {
            'event_type': 'reasoning',
            'data': {
                'agent': 'HITL审批官',
                'content': content,
                'approval_type': decision.get('approval_type', 'investment_decision'),
                'task_id': task_id,
                'risk_level': risk_level,
                'options': ['approve', 'reject', 'modify'],
            },
        }
        if extra:
            payload['data'].update(extra)
        get_event_bus().publish(EVENT_APPROVAL_NEEDED, payload)
    except Exception as e:
        logger.debug(f"[HITL] publish approval event 失败: {e}")


class HumanApprovalManager:
    """人工审批管理器"""

    def __init__(self):
        self._pending_approvals = {}  # task_id -> approval_request
        self._lock = threading.Lock()

    def request_approval(self, task_id: str, decision: Dict[str, Any],
                         risk_level: str = 'low', timeout: int = 300) -> Dict[str, Any]:
        """
        请求人工审批。
        - 低风险(low): 自动通过
        - 中风险(medium): 记录但自动通过
        - 高风险(high): 等待人工审批（最多timeout秒）
        """
        if risk_level == 'low':
            _publish_approval_event('auto_pass', task_id, decision, risk_level)
            return {**decision, 'approved': True, 'approval_type': 'auto_low_risk'}

        if risk_level == 'medium':
            logger.info(f"中风险决策自动通过(task={task_id}): {decision.get('action', 'N/A')}")
            _publish_approval_event('auto_pass', task_id, decision, risk_level)
            return {**decision, 'approved': True, 'approval_type': 'auto_medium_risk'}

        # 高风险：等待人工审批
        _publish_approval_event('pending', task_id, decision, risk_level)
        approval_request = {
            'task_id': task_id,
            'decision': decision,
            'risk_level': risk_level,
            'status': 'pending',  # pending / approved / rejected
            'created_at': time.time(),
            'human_feedback': None,
        }

        with self._lock:
            self._pending_approvals[task_id] = approval_request

        logger.info(f"高风险决策等待人工审批(task={task_id}): {decision.get('action', 'N/A')}")

        # 等待审批（轮询）
        start = time.time()
        while time.time() - start < timeout:
            with self._lock:
                current = self._pending_approvals.get(task_id, {})
                if current.get('status') in ('approved', 'rejected'):
                    result = {
                        **decision,
                        'approved': current['status'] == 'approved',
                        'approval_type': 'human',
                        'human_feedback': current.get('human_feedback', ''),
                    }
                    del self._pending_approvals[task_id]
                    return result
            time.sleep(1)

        # 超时自动通过（但标记）
        with self._lock:
            self._pending_approvals.pop(task_id, None)

        logger.warning(f"人工审批超时(task={task_id})，自动通过")
        return {**decision, 'approved': True, 'approval_type': 'timeout_auto'}

    def submit_approval(self, task_id: str, approved: bool, feedback: str = '') -> bool:
        """提交人工审批结果"""
        with self._lock:
            if task_id in self._pending_approvals:
                self._pending_approvals[task_id]['status'] = 'approved' if approved else 'rejected'
                self._pending_approvals[task_id]['human_feedback'] = feedback
                decision = self._pending_approvals[task_id].get('decision', {})
                risk_level = self._pending_approvals[task_id].get('risk_level', 'high')
                _publish_approval_event(
                    'approved' if approved else 'rejected',
                    task_id, decision, risk_level,
                    extra={'human_feedback': feedback[:200] if feedback else ''}
                )
                return True
        return False

    def get_pending_approvals(self) -> list:
        """获取所有待审批项"""
        with self._lock:
            return [
                {
                    'task_id': k,
                    'decision': v['decision'],
                    'risk_level': v['risk_level'],
                    'created_at': v['created_at'],
                }
                for k, v in self._pending_approvals.items()
                if v['status'] == 'pending'
            ]


# 全局单例
approval_manager = HumanApprovalManager()
