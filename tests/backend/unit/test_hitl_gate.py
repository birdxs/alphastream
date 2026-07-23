"""
P0-5 HITL 确认面闸门最小单测（离线，无网络/无服务）。
覆盖：高风险判定、pending 列表、submit 改状态、超时拒绝高风险、事件 payload 契约。
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List

import pytest


def test_should_request_hitl_high_risk_level():
    from app.agents.hitl import should_request_hitl

    assert should_request_hitl({"action": "HOLD", "risk_level": "高"}) is True
    assert should_request_hitl({"action": "HOLD", "risk_level": "high"}) is True
    assert should_request_hitl(
        {"action": "HOLD"},
        {"overall_risk": "高"},
    ) is True
    assert should_request_hitl({"action": "HOLD", "risk_level": "低", "confidence": 0.1}) is False


def test_should_request_hitl_buy_high_confidence():
    from app.agents.hitl import should_request_hitl

    assert should_request_hitl({"action": "BUY", "confidence": 0.9}) is True
    assert should_request_hitl({"action": "BUY", "confidence": 0.1}) is False
    assert should_request_hitl({"action": "STRONG_BUY", "confidence": 0.8}) is True


def test_pending_and_submit_changes_status(monkeypatch):
    from app.agents import hitl as hitl_mod

    # 避免 EventBus 依赖噪声
    monkeypatch.setattr(hitl_mod, "_publish_approval_event", lambda *a, **k: None)

    mgr = hitl_mod.HumanApprovalManager()
    statuses: List[str] = []

    def hook(task_type, task_id, status, progress=None, result=None, error=None):
        statuses.append(status)

    mgr.set_task_status_hook(hook)

    decision = {"action": "BUY", "confidence": 0.9, "risk_level": "高"}

    def approver():
        # 等待进入 pending
        for _ in range(50):
            if mgr.get_pending_approvals():
                break
            time.sleep(0.02)
        ok = mgr.submit_approval("t-hitl-1", True, "单测批准")
        assert ok is True

    th = threading.Thread(target=approver, daemon=True)
    th.start()
    result = mgr.request_approval(
        "t-hitl-1",
        decision,
        risk_level="高",
        timeout=5,
        reason="单测高风险",
    )
    th.join(timeout=3)

    assert result.get("approved") is True
    assert result.get("approval_type") == "human"
    assert "awaiting_approval" in statuses
    assert mgr.get_pending_approvals() == []


def test_submit_reject_not_silent_pass(monkeypatch):
    from app.agents import hitl as hitl_mod

    monkeypatch.setattr(hitl_mod, "_publish_approval_event", lambda *a, **k: None)
    mgr = hitl_mod.HumanApprovalManager()
    decision = {"action": "BUY", "confidence": 0.95, "risk_level": "高"}

    def rejector():
        for _ in range(50):
            if mgr.get_pending_approvals():
                break
            time.sleep(0.02)
        assert mgr.submit_approval("t-hitl-2", False, "单测拒绝") is True

    th = threading.Thread(target=rejector, daemon=True)
    th.start()
    result = mgr.request_approval("t-hitl-2", decision, risk_level="高", timeout=5)
    th.join(timeout=3)

    assert result.get("approved") is False
    assert result.get("approval_type") == "human"
    assert result.get("approval_status") == "rejected"


def test_high_risk_timeout_rejects(monkeypatch):
    from app.agents import hitl as hitl_mod

    events: List[str] = []

    def capture(event_type, task_id, decision, risk_level="high", extra=None, reason="", timeout_seconds=None):
        events.append(event_type)

    monkeypatch.setattr(hitl_mod, "_publish_approval_event", capture)
    mgr = hitl_mod.HumanApprovalManager()
    decision = {"action": "BUY", "confidence": 0.99, "risk_level": "高"}

    # 极短超时，无人提交
    result = mgr.request_approval("t-hitl-3", decision, risk_level="高", timeout=0.3)
    assert result.get("approved") is False
    assert result.get("approval_type") == "timeout_reject"
    assert "timeout_reject" in events
    # timeout_auto 不得伪装为通过高风险
    assert result.get("approval_type") != "timeout_auto"


def test_get_pending_fields_for_confirmation_card(monkeypatch):
    from app.agents import hitl as hitl_mod

    monkeypatch.setattr(hitl_mod, "_publish_approval_event", lambda *a, **k: None)
    mgr = hitl_mod.HumanApprovalManager()
    decision = {"action": "BUY", "confidence": 0.88, "risk_level": "高", "reasoning": "波动大"}
    box = {"fields": None, "result": None}

    def requester():
        box["result"] = mgr.request_approval(
            "t-hitl-4", decision, risk_level="高", timeout=3, reason="波动大需确认"
        )

    th = threading.Thread(target=requester, daemon=True)
    th.start()
    for _ in range(100):
        pending = mgr.get_pending_approvals()
        if pending:
            box["fields"] = pending[0]
            break
        time.sleep(0.02)
    assert box["fields"] is not None, "pending 未出现"
    fields = box["fields"]
    for key in ("task_id", "decision", "risk_level", "reason", "action_type", "status"):
        assert key in fields
    assert fields["task_id"] == "t-hitl-4"
    assert fields["action_type"] == "BUY"
    assert fields["status"] == "pending"
    assert fields["reason"]
    # 提交拒绝后 request_approval 返回
    assert mgr.submit_approval("t-hitl-4", False, "看完字段") is True
    th.join(timeout=3)
    assert box["result"] is not None
    assert box["result"].get("approved") is False


def test_approval_event_payload_has_event_type():
    """事件契约：payload.event_type = approval_needed，且可挂 EventBus。"""
    from app.agents import hitl as hitl_mod
    from app.core.event_bus import get_event_bus, EVENT_APPROVAL_NEEDED

    bus = get_event_bus()
    seen: List[Dict[str, Any]] = []

    def handler(data):
        if isinstance(data, dict):
            seen.append(data)

    bus.subscribe(EVENT_APPROVAL_NEEDED, handler)
    bus.subscribe("approval_needed", handler)

    mgr = hitl_mod.HumanApprovalManager()

    def approve():
        for _ in range(50):
            if mgr.get_pending_approvals():
                break
            time.sleep(0.02)
        mgr.submit_approval("t-hitl-5", True, "ok")

    th = threading.Thread(target=approve, daemon=True)
    th.start()
    mgr.request_approval(
        "t-hitl-5",
        {"action": "BUY", "confidence": 0.9, "risk_level": "高"},
        risk_level="高",
        timeout=3,
    )
    th.join(timeout=3)

    assert seen, "应发布 approval.needed / approval_needed 事件"
    payload = seen[0]
    assert payload.get("event_type") in ("approval_needed", "approval_resolved") or payload.get("type")
    assert payload.get("task_id") == "t-hitl-5"
