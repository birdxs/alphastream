# -*- coding: utf-8 -*-
# Input  : HumanApprovalManager + EventBus spy
# Output : pytest 用例，覆盖 approval 申请/批准/拒绝/进程重启风险暴露
# Pos    : tests/backend/integration/test_hitl.py - BE-02b HITL 集成测试
"""BE-02b HITL 测试

覆盖：
  - request_approval 发布 EVENT_APPROVAL_NEEDED
  - submit_approval(approved=True) -> 状态 approved 并解除阻塞
  - submit_approval(approved=False) -> 状态 rejected 并解除阻塞
  - H1 暴露：新建 HumanApprovalManager 实例后 _pending_approvals 丢失（内存字典风险）
"""
from __future__ import annotations

import threading
import time

import pytest

from app.agents.hitl import HumanApprovalManager


# =========================================================================
# B1. request_approval —— 发布事件 + 进入 pending
# =========================================================================
class TestRequestApprovalEvent:
    """B1: request_approval 应发布 EVENT_APPROVAL_NEEDED 并将 task 计入 pending"""

    def test_publishes_approval_needed_event(self, agent_event_recorder):
        mgr = HumanApprovalManager()
        decision = {"action": "BUY", "size": 100, "reasoning": "突破关键阻力"}

        # 启动后台线程调用 request_approval（阻塞 wait）
        t = threading.Thread(
            target=mgr.request_approval,
            args=("task-001", decision, "high"),
            kwargs={"timeout": 3.0},
            daemon=True,
        )
        t.start()

        # 等待事件发布
        time.sleep(0.2)

        # 断言事件已发布
        assert agent_event_recorder.has("approval.needed"), \
            f"未捕获 approval.needed 事件，实际事件: {agent_event_recorder.events}"

        payload_list = agent_event_recorder.filter("approval.needed")
        assert payload_list, "approval.needed 事件列表为空"
        payload = payload_list[0]
        # payload 结构（参见 hitl._publish_approval_event）
        # 业务故意把审批包成 reasoning 通道，前端按 [APPROVAL] 前缀识别
        assert payload.get("event_type") == "reasoning"
        data = payload.get("data", {})
        assert data.get("task_id") == "task-001"
        assert data.get("agent") == "HITL审批官"
        assert "[APPROVAL]" in data.get("content", "")
        assert "approve" in data.get("options", [])

        # pending 列表应含此任务
        pending = mgr.get_pending_approvals()
        assert any(p["task_id"] == "task-001" for p in pending)

        # 清理：让后台线程退出（超时自然结束）
        mgr.submit_approval("task-001", False, "test cleanup")
        t.join(timeout=2.0)


# =========================================================================
# B2. approve (submit_approval=True) —— 改变状态 + 解除阻塞
# =========================================================================
class TestApprove:
    """B2: submit_approval(True) 改变状态并解除 request_approval 阻塞"""

    def test_approve_unblocks_and_marks_approved(self):
        mgr = HumanApprovalManager()
        result_holder = {}

        def _wait():
            res = mgr.request_approval(
                "task-approve", {"action": "BUY"}, "high", timeout=5.0
            )
            result_holder["result"] = res

        t = threading.Thread(target=_wait, daemon=True)
        t.start()
        time.sleep(0.2)

        # 提交批准
        ok = mgr.submit_approval("task-approve", approved=True, feedback="放行")
        assert ok is True

        # 等待阻塞解除
        t.join(timeout=3.0)
        assert not t.is_alive(), "request_approval 未在 submit 后及时解除阻塞"

        res = result_holder.get("result")
        assert res is not None
        assert res.get("approved") is True
        # request_approval 返回字典含 approval_type='human' + human_feedback
        assert res.get("approval_type") == "human"
        assert res.get("human_feedback") == "放行"


# =========================================================================
# B3. reject (submit_approval=False) —— 同上
# =========================================================================
class TestReject:
    """B3: submit_approval(False) 改变状态为 rejected 并解除阻塞"""

    def test_reject_unblocks_and_marks_rejected(self):
        mgr = HumanApprovalManager()
        result_holder = {}

        def _wait():
            res = mgr.request_approval(
                "task-reject", {"action": "SELL"}, "high", timeout=5.0
            )
            result_holder["result"] = res

        t = threading.Thread(target=_wait, daemon=True)
        t.start()
        time.sleep(0.2)

        ok = mgr.submit_approval("task-reject", approved=False, feedback="风险太大")
        assert ok is True

        t.join(timeout=3.0)
        assert not t.is_alive()

        res = result_holder.get("result")
        assert res is not None
        assert res.get("approved") is False
        assert res.get("approval_type") == "human"
        assert res.get("human_feedback") == "风险太大"

    def test_submit_for_unknown_task_returns_false(self):
        mgr = HumanApprovalManager()
        ok = mgr.submit_approval("nonexistent-task", approved=True)
        assert ok is False


# =========================================================================
# B4. H1 暴露 —— 进程重启后 _pending_approvals 全部丢失
# =========================================================================
class TestProcessRestartRisk:
    """H1 风险暴露：HumanApprovalManager 使用内存字典存储 pending approvals，
    一旦进程重启或对象重建，所有未决审批将丢失。这是生产环境的高危隐患。
    """

    def test_new_instance_loses_all_pending_approvals(self):
        """模拟"进程重启"：创建新实例后，原 _pending_approvals 完全不可见"""
        # === 旧实例 ===
        mgr_old = HumanApprovalManager()

        # 发起 2 个 pending（后台线程，不等待）
        threads = []
        for tid in ("restart-task-1", "restart-task-2"):
            t = threading.Thread(
                target=mgr_old.request_approval,
                args=(tid, {"action": "BUY"}, "high"),
                kwargs={"timeout": 10.0},
                daemon=True,
            )
            t.start()
            threads.append((tid, t))
        time.sleep(0.3)

        # 旧实例应能看到 2 个 pending
        pending_old = mgr_old.get_pending_approvals()
        assert len(pending_old) >= 2, \
            f"旧实例 pending 异常: {pending_old}"

        # === 模拟进程重启：新实例 ===
        mgr_new = HumanApprovalManager()

        # H1 关键断言：新实例 _pending_approvals 完全为空
        assert mgr_new._pending_approvals == {}, \
            "H1 风险被掩盖：新实例 _pending_approvals 不为空（不应发生）"
        assert len(mgr_new._pending_approvals) == 0, \
            "H1 风险：新实例应丢失所有 pending，但实际不为空"

        # 通过公开接口也应看不到旧任务
        pending_new = mgr_new.get_pending_approvals()
        assert pending_new == [], \
            f"H1 风险：新实例不应看到旧 pending，但看到了 {pending_new}"

        # 新实例对旧 task_id 提交，应返回 False（找不到）
        ok = mgr_new.submit_approval("restart-task-1", approved=True)
        assert ok is False, \
            "H1 风险被隐藏：新实例不应能处理旧 task，但 submit_approval 返回了 True"

        # 清理旧线程（超时退出）
        for tid, _ in threads:
            mgr_old.submit_approval(tid, False, "cleanup")
        for _, t in threads:
            t.join(timeout=2.0)

    def test_pending_state_not_shared_between_instances(self):
        """同一进程内两个实例的 _pending_approvals 互相独立（内存字典风险）"""
        mgr_a = HumanApprovalManager()
        mgr_b = HumanApprovalManager()

        t = threading.Thread(
            target=mgr_a.request_approval,
            args=("shared-task", {"action": "BUY"}, "high"),
            kwargs={"timeout": 3.0},
            daemon=True,
        )
        t.start()
        time.sleep(0.2)

        # mgr_a 看到，mgr_b 看不到 -> 字典非共享
        assert any(p["task_id"] == "shared-task" for p in mgr_a.get_pending_approvals())
        assert all(p["task_id"] != "shared-task" for p in mgr_b.get_pending_approvals())

        mgr_a.submit_approval("shared-task", False, "cleanup")
        t.join(timeout=2.0)
