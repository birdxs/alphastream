"""
Input: 模拟节点完成 / 并发任务
Output: 验证 _ProgressTracker 单调推进、线程安全、跨任务隔离
Pos: tests/backend/unit/test_agent_progress.py - FIX-6 配套测试

[FIX-6 2026-05-18 +08:00] LangGraph 节点完成时回写 task.progress，
解决 Agent 任务卡 progress=5% 的问题。
"""
import threading
import time

import pytest

from app.agents.coordinator import (
    _ProgressTracker,
    set_progress_tracker,
    get_progress_tracker,
)
from app.core.event_bus import get_event_bus


class TestProgressTracker:
    def test_monotonic_advance(self):
        """7 节点串行 advance：progress 从 start=5 单调升至 end=95"""
        tracker = _ProgressTracker(task_id='t1', total_nodes=7, start=5, end=95)
        seq = []
        for i in range(7):
            p = tracker.advance(f'agent_{i}')
            seq.append(p)
        # 单调非降
        for a, b in zip(seq, seq[1:]):
            assert a <= b, f"progress 非单调: {seq}"
        # 起点 > 5（第一步已推进）
        assert seq[0] > 5
        # 终点 == 95
        assert seq[-1] == 95
        # 至少 5 个不同台阶
        assert len(set(seq)) >= 5

    def test_total_nodes_zero_safe(self):
        """total=0 也不会崩"""
        tracker = _ProgressTracker(task_id='t', total_nodes=0)
        p = tracker.advance('any')
        assert isinstance(p, int)

    def test_advance_publishes_event(self):
        """advance 时通过 EventBus 发布 task.progress_advance 事件"""
        received = []

        def listener(payload):
            received.append(payload)

        bus = get_event_bus()
        bus.subscribe('task.progress_advance', listener)
        try:
            tracker = _ProgressTracker(task_id='t-pub', total_nodes=5)
            tracker.advance('agent_X', current_step='step1')
            tracker.advance('agent_Y')
            time.sleep(0.05)  # 给同步广播一点时间
            assert len(received) >= 2
            assert all(r['task_id'] == 't-pub' for r in received)
            assert received[0]['agent_name'] == 'agent_X'
            assert received[0]['current_step'] == 'step1'
            # 第二条 current_step 自动生成
            assert 'agent_Y' in received[1]['current_step']
            # progress 字段单调
            assert received[1]['progress'] >= received[0]['progress']
        finally:
            bus.unsubscribe('task.progress_advance', listener)

    def test_concurrent_safety_single_tracker(self):
        """单 tracker 并发 advance: completed 计数精确无丢失"""
        tracker = _ProgressTracker(task_id='t-concur', total_nodes=100)
        N_THREADS = 10
        PER_THREAD = 10

        def worker():
            for _ in range(PER_THREAD):
                tracker.advance('w')

        threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert tracker.completed == N_THREADS * PER_THREAD

    def test_thread_local_isolation(self):
        """跨线程: 每个线程用 set_progress_tracker 注册的 tracker 互不污染"""
        results = {}
        barrier = threading.Barrier(2)

        def worker(name, task_id):
            tracker = _ProgressTracker(task_id=task_id, total_nodes=3)
            set_progress_tracker(tracker)
            barrier.wait()
            time.sleep(0.05)
            # 当前线程看到的应是自己的 tracker
            current = get_progress_tracker()
            results[name] = current.task_id if current else None
            set_progress_tracker(None)

        t1 = threading.Thread(target=worker, args=('A', 'task-A'))
        t2 = threading.Thread(target=worker, args=('B', 'task-B'))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert results == {'A': 'task-A', 'B': 'task-B'}

    def test_progress_clamped(self):
        """advance 调用次数超过 total_nodes 时 progress 不超 end"""
        tracker = _ProgressTracker(task_id='t-clamp', total_nodes=3, start=5, end=95)
        for _ in range(10):
            p = tracker.advance('a')
        assert p == 95

    def test_set_get_tracker(self):
        """set_progress_tracker / get_progress_tracker 配对"""
        t = _ProgressTracker(task_id='t-sg', total_nodes=2)
        set_progress_tracker(t)
        assert get_progress_tracker() is t
        set_progress_tracker(None)
        assert get_progress_tracker() is None


class TestIntegrationWithWrapWithEvents:
    """模拟 LangGraph 节点完成时通过 _wrap_with_events 推进 progress"""

    def test_wrap_advances_tracker(self):
        from app.agents.coordinator import _wrap_with_events

        # 注册 tracker
        tracker = _ProgressTracker(task_id='t-wrap', total_nodes=4)
        set_progress_tracker(tracker)
        try:
            def fake_agent(state):
                return {'foo': 'bar'}

            wrapped = _wrap_with_events(fake_agent, 'fake_agent_测试')
            state = {'stock_code': '000001', 'progress': 5}
            result = wrapped(state)

            # tracker 被推进 1 次
            assert tracker.completed == 1
            # result.progress 已被回写
            assert result.get('progress', 0) > 5
        finally:
            set_progress_tracker(None)

    def test_wrap_without_tracker_does_not_crash(self):
        """未注册 tracker 时, _wrap_with_events 走旧逻辑不报错"""
        from app.agents.coordinator import _wrap_with_events
        set_progress_tracker(None)

        def fake_agent(state):
            return {'progress': 20}

        wrapped = _wrap_with_events(fake_agent, 'no_tracker')
        result = wrapped({'stock_code': 'X'})
        # 旧路径走 result.get('progress', state.progress)
        assert result.get('progress') == 20
