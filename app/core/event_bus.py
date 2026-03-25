"""
Input: 事件名称 + 数据
Output: 事件广播到所有订阅者
Pos: app/core/event_bus.py - Agent间事件通信总线

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
import threading
from typing import Callable, Dict, List, Any

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

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """取消订阅"""
        with self._sub_lock:
            if event_name in self._subscribers:
                self._subscribers[event_name] = [
                    cb for cb in self._subscribers[event_name] if cb != callback
                ]


# 事件名称常量
EVENT_ANALYSIS_STARTED = 'analysis.started'
EVENT_ANALYSIS_COMPLETED = 'analysis.completed'
EVENT_AGENT_STEP_DONE = 'agent.step.done'
EVENT_RISK_ALERT = 'risk.alert'
EVENT_APPROVAL_NEEDED = 'approval.needed'


def get_event_bus() -> EventBus:
    return EventBus()
