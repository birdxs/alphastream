"""
Input: 高风险决策(decision dict) + task_id + risk_level
Output: 审批结果(approved/rejected/timeout) + 待审批列表 + EventBus 事件
Pos: app/agents/hitl.py - Human-in-the-Loop 审批闸门（P0-5 确认面一等公民）

契约要点（sprint0-inventory §1.5 / §6）：
- 仅高风险路径调用 request_approval；禁止静默通过高风险
- 事件主名 approval.needed；payload.event_type = approval_needed（兼容 alias）
- 超时对 high 默认拒绝（timeout_reject），timeout_auto 徽标 ≠ 已批准
- pending API 列出可提交项；submit 改变 status 并 publish approval.resolved

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, Optional

_ASIA_SHANGHAI = timezone(timedelta(hours=8))
now_cn = lambda: datetime.now(_ASIA_SHANGHAI)

logger = logging.getLogger(__name__)

# 高风险动作（买入侧）置信度阈值：≥ 则触发 HITL
_HITL_BUY_CONFIDENCE = float(os.getenv('HITL_BUY_CONFIDENCE_THRESHOLD', '0.75'))
# 默认审批超时（秒）
_HITL_DEFAULT_TIMEOUT = float(os.getenv('HITL_APPROVAL_TIMEOUT_S', '300'))


def _is_high_risk_level(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in ('high', '高', '很高', 'critical', '严重')


def should_request_hitl(
    decision: Optional[Dict[str, Any]],
    risk_assessment: Optional[Dict[str, Any]] = None,
) -> bool:
    """高风险判定（P0-5）。任一命中即闸门：

    1. risk_assessment.overall_risk / risk_level ∈ {高, high, ...}
    2. final_decision.risk_level 同上
    3. 动作 BUY/STRONG_BUY 且 confidence ≥ HITL_BUY_CONFIDENCE_THRESHOLD（默认 0.75）
    """
    decision = decision or {}
    risk_assessment = risk_assessment or {}

    if _is_high_risk_level(risk_assessment.get('overall_risk')):
        return True
    if _is_high_risk_level(risk_assessment.get('risk_level')):
        return True
    if _is_high_risk_level(decision.get('risk_level')):
        return True

    action = str(decision.get('action') or decision.get('recommendation') or '').upper()
    if action in ('BUY', 'STRONG_BUY', '买入', '强烈买入'):
        try:
            conf = float(decision.get('confidence') or 0)
        except (TypeError, ValueError):
            conf = 0.0
        if conf >= _HITL_BUY_CONFIDENCE:
            return True
    return False


def build_approval_reason(
    decision: Optional[Dict[str, Any]],
    risk_assessment: Optional[Dict[str, Any]] = None,
) -> str:
    """生成确认卡展示用理由（非假数据，仅合成已有字段说明）。"""
    decision = decision or {}
    risk_assessment = risk_assessment or {}
    parts = []
    ov = risk_assessment.get('overall_risk') or risk_assessment.get('risk_level')
    if ov:
        parts.append(f"风险评估={ov}")
    rl = decision.get('risk_level')
    if rl and str(rl) != str(ov):
        parts.append(f"决策风险级={rl}")
    action = decision.get('action') or decision.get('recommendation')
    if action:
        parts.append(f"动作={action}")
    conf = decision.get('confidence')
    if conf is not None:
        parts.append(f"置信度={conf}")
    rationale = decision.get('rationale') or decision.get('reasoning') or decision.get('summary')
    if rationale:
        parts.append(str(rationale)[:200])
    if not parts:
        return '高风险决策需人工确认'
    return '；'.join(parts)


def _publish_approval_event(
    event_type: str,
    task_id: str,
    decision: dict,
    risk_level: str = 'high',
    extra: Optional[Dict[str, Any]] = None,
    reason: str = '',
    timeout_seconds: Optional[float] = None,
) -> None:
    """发布审批事件到 EventBus（SSE 桥接自动转发）。

    Sprint0 契约：
    - bus 事件名：approval.needed / approval.resolved
    - payload.event_type：approval_needed / approval_resolved（前端 switch 用）
    """
    try:
        from app.core.event_bus import get_event_bus, EVENT_APPROVAL_NEEDED

        action = (decision or {}).get('action') or (decision or {}).get('recommendation') or ''
        try:
            conf = float((decision or {}).get('confidence') or 0)
        except (TypeError, ValueError):
            conf = 0.0

        if event_type in ('needed', 'approval_needed'):
            event_name = EVENT_APPROVAL_NEEDED  # 'approval.needed'
            payload_type = 'approval_needed'
            content = f"[APPROVAL] 等待人工确认: {action or '决策'} (风险={risk_level})"
        else:
            event_name = 'approval.resolved'
            payload_type = 'approval_resolved'
            content = f"[APPROVAL] 审批结果: {event_type} — {action or '决策'}"

        data = {
            # SSE 客户端在 event=info 时会读 data.event_type 再派发
            'event_type': payload_type,
            'type': payload_type,  # alias
            'task_id': task_id,
            'status': event_type if event_type not in ('needed', 'approval_needed') else 'pending',
            'risk_level': risk_level,
            'action_type': str(action) if action else '',
            'action': str(action) if action else '',
            'confidence': conf,
            'reason': reason or build_approval_reason(decision),
            'details': decision or {},
            'decision': decision or {},
            'timeout_seconds': timeout_seconds,
            # 兼容侧栏 [APPROVAL] 文案解析
            'data': {
                'content': content,
                'level': 'warn' if payload_type == 'approval_needed' else 'info',
                'task_id': task_id,
                'risk_level': risk_level,
                'action_type': str(action) if action else '',
                'status': event_type if event_type not in ('needed', 'approval_needed') else 'pending',
                'reason': reason or build_approval_reason(decision),
            },
            'content': content,
            'agent': '审批闸门',
        }
        if extra:
            data.update(extra)

        event_bus = get_event_bus()
        event_bus.publish(event_name, data)
        # alias：便于 filter 订阅 'approval_needed'
        if event_name == EVENT_APPROVAL_NEEDED:
            event_bus.publish('approval_needed', data)
    except Exception as e:
        logger.debug(f"发布审批事件失败(非致命): {e}")


class HumanApprovalManager:
    """人工审批管理器（进程内；H1 重启丢失风险已在 inventory 登记）"""

    def __init__(self):
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._task_status_hook: Optional[Callable[..., None]] = None

    def set_task_status_hook(self, hook: Optional[Callable[..., None]]) -> None:
        """可选：绑定 web 层 update_task_status，使 awaiting_approval 可被任务查询。"""
        self._task_status_hook = hook

    def _notify_task(self, task_id: str, status: str, result: Any = None, error: Any = None) -> None:
        hook = self._task_status_hook
        if not hook or not task_id:
            return
        try:
            hook('agent_analysis', task_id, status, result=result, error=error)
        except TypeError:
            try:
                hook(task_id, status, result=result)
            except Exception as e:
                logger.debug(f"task_status_hook 调用失败: {e}")
        except Exception as e:
            logger.debug(f"task_status_hook 调用失败: {e}")

    def request_approval(
        self,
        task_id: str,
        decision: dict,
        risk_level: str = 'high',
        timeout: Optional[float] = None,
        reason: str = '',
        risk_assessment: Optional[dict] = None,
    ) -> dict:
        """请求人工审批（阻塞等待）。

        高风险超时：**拒绝**（timeout_reject），禁止静默通过。
        """
        if timeout is None:
            timeout = _HITL_DEFAULT_TIMEOUT
        reason = reason or build_approval_reason(decision, risk_assessment)
        created_at = now_cn().isoformat()

        with self._lock:
            self._pending_approvals[task_id] = {
                'decision': decision or {},
                'risk_level': risk_level,
                'status': 'pending',
                'created_at': created_at,
                'reason': reason,
                'timeout_seconds': float(timeout),
                'risk_assessment': risk_assessment or {},
            }

        _publish_approval_event(
            'needed',
            task_id,
            decision or {},
            risk_level,
            reason=reason,
            timeout_seconds=float(timeout),
        )
        self._notify_task(
            task_id,
            'awaiting_approval',
            result={
                'awaiting_approval': True,
                'decision': decision or {},
                'risk_level': risk_level,
                'reason': reason,
            },
        )
        logger.info(
            f"等待人工审批: task={task_id}, risk={risk_level}, timeout={timeout}s, reason={reason[:80]}"
        )

        start = time.time()
        while time.time() - start < float(timeout):
            with self._lock:
                approval = self._pending_approvals.get(task_id, {})
                if approval.get('status') != 'pending':
                    result = {
                        **(decision or {}),
                        'approved': approval['status'] == 'approved',
                        'approval_type': 'human',
                        'human_feedback': approval.get('human_feedback', ''),
                        'approval_status': approval['status'],
                        'risk_level': risk_level,
                        'reason': reason,
                    }
                    self._pending_approvals.pop(task_id, None)
                    terminal = 'approved' if result['approved'] else 'rejected'
                    self._notify_task(
                        task_id,
                        terminal,
                        result=result if result['approved'] else None,
                        error=None if result['approved'] else (
                            f"人工拒绝: {result.get('human_feedback') or reason}"
                        ),
                    )
                    return result
            time.sleep(0.5)

        with self._lock:
            self._pending_approvals.pop(task_id, None)

        # P0-5：高风险超时拒绝，禁止 timeout_auto 静默通过
        high = _is_high_risk_level(risk_level) or should_request_hitl(decision, risk_assessment)
        if high:
            logger.warning(f"人工审批超时(task={task_id})，高风险默认拒绝（timeout_reject）")
            result = {
                **(decision or {}),
                'approved': False,
                'approval_type': 'timeout_reject',
                'approval_status': 'timeout_reject',
                'timeout': True,
                'auto_approved': False,
                'risk_level': risk_level,
                'reason': reason,
                'human_feedback': f'超时 {timeout}s 未确认，系统拒绝高风险动作',
            }
            _publish_approval_event(
                'timeout_reject',
                task_id,
                decision or {},
                risk_level,
                extra={'approval_type': 'timeout_reject'},
                reason=reason,
            )
            self._notify_task(
                task_id,
                'failed',
                error=result['human_feedback'],
                result=result,
            )
            return result

        # 非高风险（防御分支）：仍标记 timeout_auto，但不伪装为 human approve 无徽标
        logger.warning(f"人工审批超时(task={task_id})，非高风险 timeout_auto 通过并打徽标")
        result = {
            **(decision or {}),
            'approved': True,
            'approval_type': 'timeout_auto',
            'approval_status': 'timeout_auto',
            'timeout': True,
            'auto_approved': True,
            'risk_level': risk_level,
            'reason': reason,
        }
        _publish_approval_event(
            'timeout_auto',
            task_id,
            decision or {},
            risk_level,
            extra={'approval_type': 'timeout_auto'},
            reason=reason,
        )
        return result

    def submit_approval(self, task_id: str, approved: bool, feedback: str = '') -> bool:
        """提交人工审批结果"""
        with self._lock:
            if task_id not in self._pending_approvals:
                return False
            entry = self._pending_approvals[task_id]
            if entry.get('status') != 'pending':
                return False
            entry['status'] = 'approved' if approved else 'rejected'
            entry['human_feedback'] = feedback
            decision = entry.get('decision', {})
            risk_level = entry.get('risk_level', 'high')
            reason = entry.get('reason', '')
            _publish_approval_event(
                'approved' if approved else 'rejected',
                task_id,
                decision,
                risk_level,
                extra={
                    'human_feedback': (feedback or '')[:200],
                    'approval_type': 'human',
                },
                reason=reason,
            )
            return True

    def get_pending_approvals(self) -> list:
        """获取所有待审批项（确认卡字段）"""
        with self._lock:
            return [
                {
                    'task_id': k,
                    'decision': v.get('decision', {}),
                    'risk_level': v.get('risk_level', 'high'),
                    'created_at': v.get('created_at'),
                    'reason': v.get('reason') or build_approval_reason(v.get('decision')),
                    'action_type': (
                        (v.get('decision') or {}).get('action')
                        or (v.get('decision') or {}).get('recommendation')
                        or ''
                    ),
                    'confidence': (v.get('decision') or {}).get('confidence'),
                    'timeout_seconds': v.get('timeout_seconds', _HITL_DEFAULT_TIMEOUT),
                    'timeout': v.get('timeout_seconds', _HITL_DEFAULT_TIMEOUT),  # alias for API consumers
                    'status': 'pending',
                }
                for k, v in self._pending_approvals.items()
                if v.get('status') == 'pending'
            ]


# 全局单例
approval_manager = HumanApprovalManager()
