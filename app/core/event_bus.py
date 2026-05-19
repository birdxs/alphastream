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

    def publish(self, event_name: str, data: Any = None) -> None:
        """发布事件"""
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
        for bridge_queue, filter_events, _created_at in bridges:
            if filter_events is None or event_name in filter_events:
                try:
                    bridge_queue.put_nowait({
                        'event': event_name,
                        'data': data,
                        'timestamp': now_cn().strftime('%Y-%m-%d %H:%M:%S %z')
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
EVENT_APPROVAL_NEEDED = 'approval.needed'

# AI流式事件类型
EVENT_AGENT_STARTED = 'agent.started'
EVENT_AGENT_COMPLETED = 'agent.completed'
EVENT_TOOL_CALL_START = 'tool.call.start'
EVENT_TOOL_CALL_RESULT = 'tool.call.result'
EVENT_TOKEN_GENERATED = 'token.generated'
EVENT_STREAM_DONE = 'stream.done'
EVENT_REASONING = 'reasoning'


def get_event_bus() -> EventBus:
    return EventBus()
