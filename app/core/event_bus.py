"""
Input: 事件名称 + 数据
Output: 事件广播到所有订阅者（含SSE桥接队列推送）
Pos: app/core/event_bus.py - Agent间事件通信总线 + SSE流式桥接

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
import queue
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Callable, Dict, List, Any, Optional, Tuple

_ASIA_SHANGHAI = timezone(timedelta(hours=8))
now_cn = lambda: datetime.now(_ASIA_SHANGHAI)

logger = logging.getLogger(__name__)


class EventBus:
    """简单的进程内事件总线"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._subscribers: Dict[str, List[Callable]] = {}
        self._sub_lock = threading.Lock()
        # 三元组: (queue, filter_events, created_at_monotonic)
        self._sse_bridges: List[Tuple[queue.Queue, Optional[List[str]], float]] = []
        self._bridge_lock = threading.Lock()
        self._SSE_BRIDGE_TTL = 30 * 60  # 30 分钟 TTL，防止连接泄漏
        self._initialized = True

    def subscribe(self, event_name: str, callback: Callable) -> None:
        """订阅事件"""
        with self._sub_lock:
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []
            self._subscribers[event_name].append(callback)
            logger.debug(f"订阅事件: {event_name}")

    def publish(self, event_name: str, data: Any = None, *, dual: bool = True) -> None:
        """发布事件。

        G3 dual=True：对角色/工具主题按 EVENT_ALIASES 双发等价别名；
        消费端用 event_dedupe_key / canonical_event_name 去重（不双计）。
        """
        topics = [event_name]
        if dual:
            try:
                aliases = EVENT_ALIASES.get(event_name) or EVENT_ALIASES.get(
                    canonical_event_name(event_name)
                )
            except Exception:
                aliases = None
            if aliases:
                topics = list(dict.fromkeys(aliases))

        for topic in topics:
            self._publish_one(topic, data)

    def _publish_one(self, event_name: str, data: Any = None) -> None:
        """单主题实际派发（handler + SSE bridge）。"""
        with self._sub_lock:
            subscribers = self._subscribers.get(event_name, []).copy()

        for callback in subscribers:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"事件处理失败({event_name}): {e}")

        # 推送到SSE桥接队列（同时清理 30min TTL 超时的桥接）
        now = time.monotonic()
        with self._bridge_lock:
            # 清理超过 TTL 的桥接队列（防止连接泄漏）
            self._sse_bridges = [
                (q, f, t) for q, f, t in self._sse_bridges
                if (now - t) < self._SSE_BRIDGE_TTL
            ]
            bridges = self._sse_bridges.copy()

        payload_data = data if data is not None else {}
        dedupe = ''
        canon = event_name
        try:
            canon = canonical_event_name(event_name)
            dedupe = event_dedupe_key(event_name, payload_data if isinstance(payload_data, dict) else {})
        except Exception:
            pass

        for bridge_queue, filter_events, _created_at in bridges:
            allowed = True
            if filter_events is not None:
                allowed = event_name in filter_events
                if not allowed:
                    try:
                        for a in EVENT_ALIASES.get(event_name, [event_name]):
                            if a in filter_events:
                                allowed = True
                                break
                    except Exception:
                        pass
            if not allowed:
                continue
            try:
                bridge_queue.put_nowait({
                    'event': event_name,
                    'data': data,
                    'timestamp': now_cn().strftime('%Y-%m-%d %H:%M:%S %z'),
                    'canonical': canon,
                    'dedupe_key': dedupe,
                })
            except queue.Full:
                logger.warning(f"SSE桥接队列已满，丢弃事件: {event_name}")

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """取消订阅"""
        with self._sub_lock:
            if event_name in self._subscribers:
                self._subscribers[event_name] = [
                    cb for cb in self._subscribers[event_name] if cb != callback
                ]

    def create_sse_bridge(self, filter_events: List[str] = None) -> queue.Queue:
        """创建SSE事件桥接队列

        返回一个Queue，订阅指定事件类型。
        SSE端点从此Queue中读取事件并推送给前端。

        Args:
            filter_events: 要订阅的事件类型列表，None表示全部

        Returns:
            queue.Queue 实例，调用方需在完成后调用 destroy_sse_bridge()
        """
        # [UI-Q4 2026-04-15 +08:00] maxsize 从 1000 → 10000, token级真实时流每秒10-50事件,
        #   一次深度分析可产生数千 token事件, 1000易被打满导致丢token
        bridge_queue = queue.Queue(maxsize=10000)
        with self._bridge_lock:
            self._sse_bridges.append((bridge_queue, filter_events, time.monotonic()))
        logger.debug(f"创建SSE桥接队列, filter={filter_events}")
        return bridge_queue

    def destroy_sse_bridge(self, bridge_queue: queue.Queue) -> None:
        """销毁SSE桥接队列，取消所有订阅"""
        with self._bridge_lock:
            self._sse_bridges = [
                (q, f, t) for q, f, t in self._sse_bridges if q is not bridge_queue
            ]
        logger.debug("销毁SSE桥接队列")


# 事件名称常量
EVENT_ANALYSIS_STARTED = 'analysis.started'
EVENT_ANALYSIS_COMPLETED = 'analysis.completed'
EVENT_AGENT_STEP_DONE = 'agent.step.done'
EVENT_RISK_ALERT = 'risk.alert'
# HITL（P0-5）：bus 主名 approval.needed；payload.event_type / alias = approval_needed
EVENT_APPROVAL_NEEDED = 'approval.needed'
EVENT_APPROVAL_NEEDED_ALIAS = 'approval_needed'
EVENT_APPROVAL_RESOLVED = 'approval.resolved'
EVENT_APPROVAL_RESOLVED_ALIAS = 'approval_resolved'

# AI流式事件类型
EVENT_AGENT_STARTED = 'agent.started'
EVENT_AGENT_COMPLETED = 'agent.completed'
# G3 角色生命周期别名（与 agent.started/completed 双发不双计）
EVENT_AGENT_ROLE_STARTED = 'agent.role_started'
EVENT_AGENT_ROLE_FINISHED = 'agent.role_finished'
# 前端 timeline 常用 underscore 别名（canonical 仍为 agent.started / agent.completed）
EVENT_AGENT_PROGRESS = 'agent_progress'  # payload.event_type 字段名，非 bus 主题
# P0-4：总线主题（历史名）+ Sprint1 契约名 agent.tool_* 同构 payload
EVENT_TOOL_CALL_START = 'tool.call.start'
EVENT_TOOL_CALL_RESULT = 'tool.call.result'
EVENT_AGENT_TOOL_CALL = 'agent.tool_call'
EVENT_AGENT_TOOL_RESULT = 'agent.tool_result'
# P0-3：辩论轮次证据（bull/bear/summary 摘要，不落全文长文）
EVENT_AGENT_DEBATE_TURN = 'agent.debate_turn'
EVENT_TOKEN_GENERATED = 'token.generated'
EVENT_STREAM_DONE = 'stream.done'
EVENT_REASONING = 'reasoning'

# P0 降级可视化（零假值）：bus 主名 agent.degraded；payload.event_type 同名供 SSE 解包
EVENT_AGENT_DEGRADED = 'agent.degraded'
EVENT_AGENT_DEGRADED_ALIAS = 'agent_degraded'

# G6 Run scorecard（done 时四维指标；主名 run.scorecard）
EVENT_RUN_SCORECARD = 'run.scorecard'
EVENT_RUN_SCORECARD_ALIAS = 'run_scorecard'

# Plan DAG / 写仓提案（timeline 可选；失败不阻断）
EVENT_PLAN_CREATED = 'plan.created'
EVENT_PLAN_STEP = 'plan.step'
EVENT_WRITE_PROPOSAL = 'write_proposal'

# G3 事件别名映射：bus 主题 → 等价规范主题列表（canonical 优先列在首位）
EVENT_ALIASES: Dict[str, List[str]] = {
    EVENT_AGENT_STARTED: [EVENT_AGENT_STARTED, EVENT_AGENT_ROLE_STARTED],
    EVENT_AGENT_ROLE_STARTED: [EVENT_AGENT_STARTED, EVENT_AGENT_ROLE_STARTED],
    EVENT_AGENT_COMPLETED: [EVENT_AGENT_COMPLETED, EVENT_AGENT_ROLE_FINISHED],
    EVENT_AGENT_ROLE_FINISHED: [EVENT_AGENT_COMPLETED, EVENT_AGENT_ROLE_FINISHED],
    EVENT_TOOL_CALL_START: [EVENT_TOOL_CALL_START, EVENT_AGENT_TOOL_CALL],
    EVENT_AGENT_TOOL_CALL: [EVENT_TOOL_CALL_START, EVENT_AGENT_TOOL_CALL],
    EVENT_TOOL_CALL_RESULT: [EVENT_TOOL_CALL_RESULT, EVENT_AGENT_TOOL_RESULT],
    EVENT_AGENT_TOOL_RESULT: [EVENT_TOOL_CALL_RESULT, EVENT_AGENT_TOOL_RESULT],
    EVENT_AGENT_DEGRADED: [EVENT_AGENT_DEGRADED, EVENT_AGENT_DEGRADED_ALIAS],
    EVENT_AGENT_DEGRADED_ALIAS: [EVENT_AGENT_DEGRADED, EVENT_AGENT_DEGRADED_ALIAS],
    EVENT_APPROVAL_NEEDED: [EVENT_APPROVAL_NEEDED, EVENT_APPROVAL_NEEDED_ALIAS],
    EVENT_APPROVAL_NEEDED_ALIAS: [EVENT_APPROVAL_NEEDED, EVENT_APPROVAL_NEEDED_ALIAS],
    EVENT_APPROVAL_RESOLVED: [EVENT_APPROVAL_RESOLVED, EVENT_APPROVAL_RESOLVED_ALIAS],
    EVENT_APPROVAL_RESOLVED_ALIAS: [EVENT_APPROVAL_RESOLVED, EVENT_APPROVAL_RESOLVED_ALIAS],
    EVENT_RUN_SCORECARD: [EVENT_RUN_SCORECARD, EVENT_RUN_SCORECARD_ALIAS],
    EVENT_RUN_SCORECARD_ALIAS: [EVENT_RUN_SCORECARD, EVENT_RUN_SCORECARD_ALIAS],
    EVENT_PLAN_CREATED: [EVENT_PLAN_CREATED],
    EVENT_PLAN_STEP: [EVENT_PLAN_STEP],
    EVENT_WRITE_PROPOSAL: [EVENT_WRITE_PROPOSAL],
}

# 别名 → 规范名（用于双计去重）
_CANONICAL_ALIAS_MAP = {
    EVENT_AGENT_ROLE_STARTED: EVENT_AGENT_STARTED,
    EVENT_AGENT_ROLE_FINISHED: EVENT_AGENT_COMPLETED,
    EVENT_AGENT_TOOL_CALL: EVENT_TOOL_CALL_START,
    EVENT_AGENT_TOOL_RESULT: EVENT_TOOL_CALL_RESULT,
    EVENT_AGENT_DEGRADED_ALIAS: EVENT_AGENT_DEGRADED,
    EVENT_APPROVAL_NEEDED_ALIAS: EVENT_APPROVAL_NEEDED,
    EVENT_APPROVAL_RESOLVED_ALIAS: EVENT_APPROVAL_RESOLVED,
    EVENT_RUN_SCORECARD_ALIAS: EVENT_RUN_SCORECARD,
    'agent_started': EVENT_AGENT_STARTED,
    'agent_completed': EVENT_AGENT_COMPLETED,
    'agent_role_started': EVENT_AGENT_STARTED,
    'agent_role_finished': EVENT_AGENT_COMPLETED,
    'role_started': EVENT_AGENT_STARTED,
    'role_finished': EVENT_AGENT_COMPLETED,
}


def canonical_event_name(event_type: str) -> str:
    """将别名折叠为规范主题名（双计去重用）。role_started → agent.started。"""
    if not event_type:
        return event_type
    et = str(event_type).strip()
    if et in _CANONICAL_ALIAS_MAP:
        return _CANONICAL_ALIAS_MAP[et]
    if et in EVENT_ALIASES:
        return EVENT_ALIASES[et][0]
    return et


def event_dedupe_key(event_type: str, data: Optional[Dict[str, Any]] = None) -> str:
    """G3 去重键：canonical(event) + agent + task 标识。用于 SSE/前端「双发不双计」。"""
    data = data or {}
    canon = canonical_event_name(event_type)
    agent = (
        data.get('agent_name')
        or data.get('agent')
        or data.get('role')
        or ''
    )
    task = (
        data.get('task_id')
        or data.get('conversation_id')
        or data.get('thread_id')
        or ''
    )
    seq = data.get('seq') or data.get('step') or data.get('progress') or ''
    return f'{canon}|{agent}|{task}|{seq}'

# 机器可读 cause 枚举（任务契约 + inventory §1.6 兼容）
DEGRADATION_CAUSES = frozenset({
    'tool_timeout',
    'source_degraded',
    'guardrail_block',
    'network',
    'timeout',
    'upstream_empty',
    'quota',
    'auth',
    'parse',
    'tool_failure',
})

# cause → 建议 confidence 上界（铁律 #1：降级收紧置信，禁止假行情补洞）
_CAUSE_CONFIDENCE_CAP = {
    'guardrail_block': 0.35,
    'tool_timeout': 0.45,
    'timeout': 0.45,
    'network': 0.50,
    'source_degraded': 0.55,
    'upstream_empty': 0.50,
    'quota': 0.55,
    'auth': 0.40,
    'parse': 0.50,
    'tool_failure': 0.55,
}

_LEVEL_RANK = {'info': 0, 'warn': 1, 'critical': 2}


def confidence_cap_for_cause(cause: str) -> float:
    """按 cause 返回建议置信上界。"""
    return float(_CAUSE_CONFIDENCE_CAP.get(cause, 0.55))


def normalize_degradation_cause(cause: str) -> str:
    """归一化 cause 字符串；未知值落入 tool_failure（仍可审计，不造假数）。"""
    c = (cause or '').strip().lower()
    if c in DEGRADATION_CAUSES:
        return c
    aliases = {
        'guardrail': 'guardrail_block',
        'block': 'guardrail_block',
        'halt': 'guardrail_block',
        'timeout_error': 'tool_timeout',
        'timeouterror': 'tool_timeout',
        'empty': 'upstream_empty',
        'no_data': 'upstream_empty',
        'proxy': 'network',
        'connection': 'network',
        'connectionerror': 'network',
    }
    return aliases.get(c, 'tool_failure')


def infer_degradation_cause_from_text(text: str) -> str:
    """从工具失败/错误文案推断 cause（无金融数值，仅失败语义）。"""
    t = (text or '').lower()
    if not t.strip():
        return 'upstream_empty'
    if any(k in t for k in ('timeout', 'timed out', '超时')):
        return 'tool_timeout'
    if any(k in t for k in ('proxy', 'connection', 'network', 'remote disconnected', '连接', '网络')):
        return 'network'
    if any(k in t for k in ('quota', 'rate limit', '429', '配额')):
        return 'quota'
    if any(k in t for k in ('auth', '401', '403', 'unauthorized', '鉴权', '密钥')):
        return 'auth'
    if any(k in t for k in ('parse', 'json', 'decode', '解析')):
        return 'parse'
    if any(k in t for k in ('guardrail', '护栏', '拦截')):
        return 'guardrail_block'
    # empty/无数据优先于通用 degraded，避免 "empty response" 被误判为 source_degraded
    if any(k in t for k in ('empty', 'no data', 'no_data', '无数据', '暂无', 'unavailable', '不可用')):
        return 'upstream_empty'
    if any(k in t for k in ('degraded', '降级')):
        return 'source_degraded'
    return 'tool_failure'


def publish_agent_degraded(
    *,
    cause: str,
    message: str,
    level: str = 'warn',
    source: str = '',
    task_id: str = '',
    stock_code: str = '',
    confidence_cap: float = None,
    correlation_id: str = '',
    extra: dict = None,
) -> dict:
    """发布 agent.degraded 并返回规范化 payload。

    契约（sprint0-inventory §1.6 + 任务 cause 枚举）：
    - level: info|warn|critical
    - cause: 机器可读枚举
    - message: 人类可读，禁止含假价
    - confidence_cap: 建议置信上界
    铁律 #1：仅描述降级因果，不填充任何伪造行情数值。
    """
    cause_n = normalize_degradation_cause(cause)
    level_n = level if level in _LEVEL_RANK else 'warn'
    cap = confidence_cap if confidence_cap is not None else confidence_cap_for_cause(cause_n)
    try:
        cap = float(cap)
    except (TypeError, ValueError):
        cap = confidence_cap_for_cause(cause_n)
    cap = max(0.0, min(1.0, cap))

    payload = {
        'event_type': EVENT_AGENT_DEGRADED,
        'level': level_n,
        'cause': cause_n,
        'message': (message or '数据源降级，未使用假行情填补。').strip()[:500],
        'confidence_cap': cap,
    }
    if source:
        payload['source'] = str(source)[:120]
    if task_id:
        payload['task_id'] = str(task_id)
    if stock_code:
        payload['stock_code'] = str(stock_code)
    if correlation_id:
        payload['correlation_id'] = str(correlation_id)
    if extra and isinstance(extra, dict):
        for k, v in extra.items():
            if k not in payload and k not in ('price', 'open', 'high', 'low', 'close', 'volume'):
                payload[k] = v

    try:
        get_event_bus().publish(EVENT_AGENT_DEGRADED, payload)
    except Exception as e:
        logger.debug('publish agent.degraded failed: %s', e)
    return payload


def publish_run_scorecard(
    scorecard: dict,
    *,
    task_id: str = '',
    stock_code: str = '',
    correlation_id: str = '',
) -> dict:
    """发布 G6 run.scorecard（done 时四维；不携带假行情字段）。

    scorecard 至少含 data_coverage / tool_success_rate / role_agreement / confidence_cap。
    """
    if not isinstance(scorecard, dict):
        scorecard = {}
    payload = {
        'event_type': EVENT_RUN_SCORECARD,
        'data_coverage': scorecard.get('data_coverage'),
        'tool_success_rate': scorecard.get('tool_success_rate'),
        'role_agreement': scorecard.get('role_agreement'),
        'confidence_cap': scorecard.get('confidence_cap'),
    }
    for k in ('evidence', 'task_id', 'stock_code', 'decision_memo',
              'reflection_summary', 'memory_context'):
        if scorecard.get(k) is not None and k not in payload:
            payload[k] = scorecard[k]
    if task_id:
        payload['task_id'] = str(task_id)
    elif scorecard.get('task_id'):
        payload['task_id'] = str(scorecard['task_id'])
    if stock_code:
        payload['stock_code'] = str(stock_code)
    elif scorecard.get('stock_code'):
        payload['stock_code'] = str(scorecard['stock_code'])
    if correlation_id:
        payload['correlation_id'] = str(correlation_id)
    try:
        get_event_bus().publish(EVENT_RUN_SCORECARD, payload)
    except Exception as e:
        logger.debug('publish run.scorecard failed: %s', e)
    return payload


def apply_confidence_cap(confidence, cap) -> float:
    """将 confidence 截断到 cap 上界；无效输入按 0.0 安全退化（非假行情）。"""
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        c = 0.0
    try:
        cap_f = float(cap)
    except (TypeError, ValueError):
        return max(0.0, min(1.0, c))
    return max(0.0, min(c, cap_f, 1.0))


def merge_confidence_cap(current, new_cap):
    """取更紧（更小）的 confidence 上界；均为 None 时返回 None。"""
    vals = []
    for v in (current, new_cap):
        if v is None:
            continue
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            continue
    if not vals:
        return None
    return max(0.0, min(vals))


def get_event_bus() -> EventBus:
    return EventBus()
