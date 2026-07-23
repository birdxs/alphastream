# -*- coding: utf-8 -*-
"""
Input: 测试 EventBus 单例 / 订阅 / 发布 / SSE 桥接 / 异常隔离 / 慢消费者背压
Output: pytest 用例集
Pos: tests/backend/unit/test_core_event_bus.py - BE-03 W2-BE03 核心模块测试 - EventBus
"""
import threading
import time
import queue
import pytest

from app.core import event_bus as eb_mod
from app.core.event_bus import (
    EventBus,
    get_event_bus,
    EVENT_AGENT_STARTED,
    EVENT_AGENT_COMPLETED,
    EVENT_TOOL_CALL_START,
    EVENT_TOOL_CALL_RESULT,
    EVENT_TOKEN_GENERATED,
    EVENT_STREAM_DONE,
    EVENT_REASONING,
    EVENT_ANALYSIS_STARTED,
    EVENT_ANALYSIS_COMPLETED,
    EVENT_AGENT_STEP_DONE,
    EVENT_RISK_ALERT,
    EVENT_APPROVAL_NEEDED,
)


@pytest.fixture(autouse=True)
def _reset_eventbus_singleton():
    """每个用例独立的 EventBus 单例，避免订阅者污染"""
    EventBus._instance = None
    bus = EventBus()
    with bus._sub_lock:
        bus._subscribers.clear()
    with bus._bridge_lock:
        bus._sse_bridges.clear()
    yield bus
    with bus._sub_lock:
        bus._subscribers.clear()
    with bus._bridge_lock:
        bus._sse_bridges.clear()
    EventBus._instance = None


# ============ T001 单例 ============
def test_T001_singleton_identity():
    b1 = EventBus()
    b2 = EventBus()
    b3 = get_event_bus()
    assert b1 is b2 is b3


# ============ T002 事件常量存在且唯一（≥11 个）============
def test_T002_event_constants_present_and_unique():
    constants = [
        EVENT_ANALYSIS_STARTED,
        EVENT_ANALYSIS_COMPLETED,
        EVENT_AGENT_STEP_DONE,
        EVENT_RISK_ALERT,
        EVENT_APPROVAL_NEEDED,
        EVENT_AGENT_STARTED,
        EVENT_AGENT_COMPLETED,
        EVENT_TOOL_CALL_START,
        EVENT_TOOL_CALL_RESULT,
        EVENT_TOKEN_GENERATED,
        EVENT_STREAM_DONE,
        EVENT_REASONING,
    ]
    assert len(constants) >= 11
    assert len(set(constants)) == len(constants), "事件常量应当唯一不重复"
    for c in constants:
        assert isinstance(c, str) and len(c) > 0


# ============ T003 subscribe + publish 基本 ============
def test_T003_subscribe_and_publish_basic():
    bus = EventBus()
    received = []
    bus.subscribe('topic.test', lambda d: received.append(d))
    bus.publish('topic.test', {'k': 1})
    assert received == [{'k': 1}]


# ============ T004 多订阅者全广播 ============
def test_T004_multi_subscribers_broadcast():
    bus = EventBus()
    a, b, c = [], [], []
    bus.subscribe('multi', a.append)
    bus.subscribe('multi', b.append)
    bus.subscribe('multi', c.append)
    bus.publish('multi', 'X')
    assert a == ['X'] and b == ['X'] and c == ['X']


# ============ T005 异常隔离 ============
def test_T005_subscriber_exception_isolation():
    bus = EventBus()
    received = []

    def bad(d):
        raise RuntimeError("boom")

    bus.subscribe('iso', bad)
    bus.subscribe('iso', lambda d: received.append(d))
    bus.subscribe('iso', lambda d: received.append(d * 2))
    bus.publish('iso', 5)  # 不应抛
    assert 5 in received and 10 in received


# ============ T006 unsubscribe 取消订阅 ============
def test_T006_unsubscribe_removes_callback():
    bus = EventBus()
    received = []

    def cb(d):
        received.append(d)

    bus.subscribe('u', cb)
    bus.publish('u', 1)
    bus.unsubscribe('u', cb)
    bus.publish('u', 2)
    assert received == [1]


# ============ T007 publish 无订阅者静默 ============
def test_T007_publish_no_subscriber_silent():
    bus = EventBus()
    bus.publish('nobody.cares', {'x': 1})  # 不抛


# ============ T008 SSE 桥接 - 基本 ============
def test_T008_sse_bridge_basic():
    bus = EventBus()
    q = bus.create_sse_bridge(['t1', 't2'])
    assert isinstance(q, queue.Queue)

    bus.publish('t1', {'a': 1})
    bus.publish('t2', {'b': 2})
    bus.publish('t3', {'c': 3})  # 不在过滤列表

    item1 = q.get(timeout=1.0)
    item2 = q.get(timeout=1.0)
    assert item1['event'] == 't1' and item1['data'] == {'a': 1}
    assert item2['event'] == 't2' and item2['data'] == {'b': 2}
    with pytest.raises(queue.Empty):
        q.get(timeout=0.2)

    bus.destroy_sse_bridge(q)


# ============ T009 SSE 桥接 - destroy 后不再投递 ============
def test_T009_sse_bridge_destroy_stops_delivery():
    bus = EventBus()
    q = bus.create_sse_bridge(['x'])
    bus.publish('x', 1)
    _ = q.get(timeout=1.0)
    bus.destroy_sse_bridge(q)
    bus.publish('x', 2)
    with pytest.raises(queue.Empty):
        q.get(timeout=0.2)


# ============ T010 SSE 桥接 - 30min TTL 自动清理（防泄漏） ============
def test_T010_sse_bridge_30min_ttl_autocleanup():
    """工作区改动：超过 30 分钟未销毁的桥接队列在下次 publish 时被自动清理"""
    bus = EventBus()
    q = bus.create_sse_bridge(['ttl'])

    # 篡改 created_at 为 31 分钟前
    with bus._bridge_lock:
        assert len(bus._sse_bridges) == 1
        bq, fe, _t = bus._sse_bridges[0]
        bus._sse_bridges[0] = (bq, fe, time.monotonic() - 31 * 60)

    # 触发一次 publish → 触发自动清理
    bus.publish('ttl', 'evt')

    with bus._bridge_lock:
        assert len(bus._sse_bridges) == 0, "30min TTL 超时桥接应被自动清理"


# ============ T011 SSE 桥接 - maxsize=10000 背压（已修复 H5） ============
def test_T011_sse_bridge_maxsize_10000_backpressure():
    """工作区已将 maxsize 从 1000 改为 10000；超出后 put_nowait 应 queue.Full 被吞掉。"""
    bus = EventBus()
    q = bus.create_sse_bridge(['bp'])
    assert q.maxsize == 10000, "SSE 桥接队列应有 maxsize=10000 防泄漏"

    # 注入 10001 条；第 10001 条会被吞掉（queue.Full）
    for i in range(10001):
        bus.publish('bp', {'i': i})

    # 队列大小不超过 10000
    assert q.qsize() <= 10000, f"qsize={q.qsize()} 应被 maxsize 限制"


# ============ T012 慢消费者背压 - 暴露 H5（在 maxsize 内仍会无限堆积） ============
def test_T012_slow_consumer_within_maxsize_H5():
    """[H5] 已知缺陷：在 maxsize=10000 内，不消费的队列仍会堆积；
    本测试明确暴露：当事件率高且消费慢时，仍能堆满至 10000 条。
    若未来加入 drop_oldest 策略可缓解。"""
    bus = EventBus()
    q = bus.create_sse_bridge(['slow'])
    N = 5000
    for i in range(N):
        bus.publish('slow', {'i': i})
    qsize = q.qsize()
    assert qsize == N, f"H5: 慢消费者堆积全部 {N} 条事件至队列（无主动丢弃策略）"
    # 标记为已知 xfail（H5 未完全修复 - 仅 maxsize 兜底，无 drop_oldest）
    if qsize == N and N < 10000:
        pytest.xfail("[H5] 慢消费者无丢弃策略：仅 maxsize 兜底，5000 条全部入队")


# ============ T013 并发发布线程安全 ============
def test_T013_concurrent_publish_thread_safety():
    bus = EventBus()
    received = []
    received_lock = threading.Lock()

    def on_evt(d):
        with received_lock:
            received.append(d)

    bus.subscribe('concur', on_evt)

    def worker(start, count):
        for i in range(start, start + count):
            bus.publish('concur', i)

    threads = [threading.Thread(target=worker, args=(i * 100, 100)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(received) == 800
    assert set(received) == set(range(800))


# ============ T014 publish 顺序：异常 + 正常订阅者交替 ============
def test_T014_exception_followed_by_normal_subscribers():
    bus = EventBus()
    log = []

    def boom1(d):
        raise ValueError("x")

    def boom2(d):
        raise RuntimeError("y")

    bus.subscribe('e', lambda d: log.append('a'))
    bus.subscribe('e', boom1)
    bus.subscribe('e', lambda d: log.append('b'))
    bus.subscribe('e', boom2)
    bus.subscribe('e', lambda d: log.append('c'))
    bus.publish('e', None)
    assert log == ['a', 'b', 'c']


# ============ T015 topic 隔离 ============
def test_T015_topic_isolation():
    bus = EventBus()
    t1, t2 = [], []
    bus.subscribe('alpha', t1.append)
    bus.subscribe('beta', t2.append)
    bus.publish('alpha', 1)
    bus.publish('beta', 2)
    assert t1 == [1] and t2 == [2]


# ============ T016 SSE filter_events=None 接收所有事件 ============
def test_T016_sse_bridge_filter_none_receives_all():
    bus = EventBus()
    q = bus.create_sse_bridge(None)  # 全订阅
    bus.publish('a', 1)
    bus.publish('b', 2)
    items = [q.get(timeout=1.0) for _ in range(2)]
    events = {it['event'] for it in items}
    assert events == {'a', 'b'}
    bus.destroy_sse_bridge(q)


# ---------------------------------------------------------------------------
# P0-2 降级可视化：结构化 degradation + confidence 上界帽
# ---------------------------------------------------------------------------

class TestAgentDegraded:
    def test_publish_agent_degraded_payload_and_bus(self, _reset_eventbus_singleton):
        bus = _reset_eventbus_singleton
        seen = []
        bus.subscribe(eb_mod.EVENT_AGENT_DEGRADED, lambda p: seen.append(p))

        payload = eb_mod.publish_agent_degraded(
            cause='tool_timeout',
            message='upstream timeout after 5s',
            level='warn',
            source='get_stock_data',
            task_id='t1',
            stock_code='600519',
        )
        assert payload['event_type'] == 'agent.degraded'
        assert payload['cause'] == 'tool_timeout'
        assert payload['confidence_cap'] == eb_mod.confidence_cap_for_cause('tool_timeout')
        assert payload['source'] == 'get_stock_data'
        assert payload['stock_code'] == '600519'
        assert len(seen) == 1
        assert seen[0]['cause'] == 'tool_timeout'
        assert 'price' not in seen[0]  # 铁律 #1：无假行情字段

    def test_normalize_unknown_cause_falls_to_tool_failure(self):
        assert eb_mod.normalize_degradation_cause('totally_unknown_xyz') == 'tool_failure'
        assert eb_mod.normalize_degradation_cause('guardrail') == 'guardrail_block'
        assert eb_mod.normalize_degradation_cause('timeout_error') == 'tool_timeout'

    def test_apply_and_merge_confidence_cap(self):
        assert eb_mod.apply_confidence_cap(0.9, 0.4) == 0.4
        assert eb_mod.apply_confidence_cap(0.2, 0.4) == 0.2
        # 无效 confidence 安全退化为 0.0 再与 cap 取 min
        assert eb_mod.apply_confidence_cap(None, 0.5) == 0.0
        assert eb_mod.merge_confidence_cap(0.7, 0.3) == 0.3
        assert eb_mod.merge_confidence_cap(None, None) is None
        assert eb_mod.merge_confidence_cap(0.2, None) == 0.2

    def test_infer_degradation_cause_from_text(self):
        assert eb_mod.infer_degradation_cause_from_text('ReadTimeout on adapter') == 'tool_timeout'
        assert eb_mod.infer_degradation_cause_from_text('ProxyError connection reset') == 'network'
        assert eb_mod.infer_degradation_cause_from_text('empty response from upstream') == 'upstream_empty'


# --- G3 event alias + dedupe ---
def test_canonical_event_name_role_aliases():
    from app.core.event_bus import (
        canonical_event_name,
        event_dedupe_key,
        EVENT_AGENT_STARTED,
        EVENT_AGENT_ROLE_STARTED,
        EVENT_AGENT_COMPLETED,
        EVENT_AGENT_ROLE_FINISHED,
    )
    assert canonical_event_name(EVENT_AGENT_ROLE_STARTED) == EVENT_AGENT_STARTED
    assert canonical_event_name(EVENT_AGENT_ROLE_FINISHED) == EVENT_AGENT_COMPLETED
    assert canonical_event_name('agent_started') == EVENT_AGENT_STARTED
    k1 = event_dedupe_key(EVENT_AGENT_STARTED, {'agent_name': 'market', 'task_id': 't1'})
    k2 = event_dedupe_key(EVENT_AGENT_ROLE_STARTED, {'agent_name': 'market', 'task_id': 't1'})
    assert k1 == k2


def test_publish_dual_role_aliases(monkeypatch):
    from app.core import event_bus as eb
    bus = eb.EventBus()
    seen = []
    bus.subscribe(eb.EVENT_AGENT_STARTED, lambda d: seen.append(('started', d)))
    bus.subscribe(eb.EVENT_AGENT_ROLE_STARTED, lambda d: seen.append(('role_started', d)))
    bus.publish(eb.EVENT_AGENT_STARTED, {'agent_name': 'x', 'task_id': '1'})
    kinds = {k for k, _ in seen}
    assert 'started' in kinds
    assert 'role_started' in kinds
