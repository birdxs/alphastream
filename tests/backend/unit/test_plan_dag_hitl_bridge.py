"""
Input: plan_dag / skill_loader / write_proposal↔HITL bridge
Output: pytest assertions（离线、无服务）
Pos: tests/backend/unit/test_plan_dag_hitl_bridge.py — Sprint4+ 薄切片

[NEW-FILE:#20260724-S4B] 最小单元测试：Plan DAG + HITL 提案桥 + Skill stub
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _reset_stores():
    """每测重置进程内 store，避免交叉污染。"""
    from app.core.write_proposal import reset_write_proposal_store_for_tests
    from app.core.plan_dag import get_plan_dag_store
    from app.agents.hitl import approval_manager

    reset_write_proposal_store_for_tests()
    get_plan_dag_store().reset()
    with approval_manager._lock:
        approval_manager._pending_approvals.clear()
    yield
    reset_write_proposal_store_for_tests()
    get_plan_dag_store().reset()
    with approval_manager._lock:
        approval_manager._pending_approvals.clear()


class TestHitlProposalBridge:
    def test_propose_registers_in_hitl_pending(self):
        from app.core.write_proposal import get_write_proposal_store
        from app.agents.hitl import approval_manager

        store = get_write_proposal_store()
        res = store.create_proposal(
            action="add_holding",
            code="600519",
            name="贵州茅台",
            shares=100,
            reason="unit-test propose",
        )
        assert res["success"] is True
        assert res["executed"] is False
        aid = res["approval_id"]
        assert aid and aid.startswith("appr_")

        pending = approval_manager.get_pending_approvals()
        ids = {p["task_id"] for p in pending}
        assert aid in ids
        item = next(p for p in pending if p["task_id"] == aid)
        assert item.get("kind") == "portfolio_write_proposal"
        assert item.get("approval_id") == aid
        assert item.get("decision", {}).get("code") == "600519"

    def test_agent_submit_approval_decides_write_proposal(self):
        """/api/agent_submit_approval 语义：submit_approval → decide_approval。"""
        from app.core.write_proposal import get_write_proposal_store
        from app.agents.hitl import approval_manager

        store = get_write_proposal_store()
        res = store.create_proposal(action="add_holding", code="000001", shares=10)
        aid = res["approval_id"]
        pid = res["proposal_id"]

        ok = approval_manager.submit_approval(aid, approved=True, feedback="ok")
        assert ok is True

        ap = store.get_approval(aid)
        assert ap is not None
        assert ap["status"] == "approved"

        # 已不在 pending
        pending_ids = {p["task_id"] for p in approval_manager.get_pending_approvals()}
        assert aid not in pending_ids

        # apply 可通过
        applied = store.apply_proposal(proposal_id=pid, approval_id=aid)
        assert applied["success"] is True
        assert applied["executed"] is False
        assert applied.get("applied") is True
        assert applied.get("broker") is None
        assert applied.get("apply_mode") == "local_mark_only"

    def test_decide_tool_clears_hitl_pending(self):
        from app.core.write_proposal import get_write_proposal_store
        from app.agents.hitl import approval_manager

        store = get_write_proposal_store()
        res = store.create_proposal(action="remove_holding", code="600036")
        aid = res["approval_id"]
        assert any(p["task_id"] == aid for p in approval_manager.get_pending_approvals())

        d = store.decide_approval(aid, approved=False, feedback="no")
        assert d["success"] is True
        assert store.get_approval(aid)["status"] == "rejected"
        assert not any(
            p["task_id"] == aid for p in approval_manager.get_pending_approvals()
        )

    def test_submit_approval_write_proposal_only_path(self):
        """仅 store pending、无 HITL 登记时，submit 仍可桥接。"""
        from app.core.write_proposal import get_write_proposal_store
        from app.agents.hitl import approval_manager

        store = get_write_proposal_store()
        res = store.create_proposal(action="add_holding", code="688195", shares=5)
        aid = res["approval_id"]
        # 强制摘除 HITL 登记，模拟仅 store 路径
        with approval_manager._lock:
            approval_manager._pending_approvals.pop(aid, None)

        # get_pending 仍应从 write_proposal 合并
        pending = approval_manager.get_pending_approvals()
        assert any(p["task_id"] == aid for p in pending)

        ok = approval_manager.submit_approval(aid, approved=True, feedback="bridge")
        assert ok is True
        assert store.get_approval(aid)["status"] == "approved"


class TestPlanDag:
    def test_serial_create_and_status(self):
        from app.core.plan_dag import get_plan_dag_store

        store = get_plan_dag_store()
        res = store.create_plan(
            ["技术面", "基本面", "风险"],
            title="三步分析",
            stock_code="600519",
        )
        assert res["success"] is True
        plan = res["plan"]
        assert plan["status"] == "ready"
        assert len(plan["steps"]) == 3
        # 默认串行：s2 depends s1
        assert plan["steps"][1]["depends_on"] == [plan["steps"][0]["id"]]
        st = store.get_status(plan["plan_id"])
        assert st["success"] is True
        assert st["status"] == "ready"

    def test_depends_on_unknown_fails(self):
        from app.core.plan_dag import get_plan_dag_store

        store = get_plan_dag_store()
        res = store.create_plan(
            [
                {"id": "a", "name": "A"},
                {"id": "b", "name": "B", "depends_on": ["missing"]},
            ]
        )
        assert res["success"] is False
        assert res["error_code"] == "UNKNOWN_DEPEND"

    def test_cycle_detected(self):
        from app.core.plan_dag import get_plan_dag_store

        store = get_plan_dag_store()
        res = store.create_plan(
            [
                {"id": "a", "name": "A", "depends_on": ["b"]},
                {"id": "b", "name": "B", "depends_on": ["a"]},
            ]
        )
        assert res["success"] is False
        assert res["error_code"] == "CYCLE"

    def test_start_requires_deps_and_complete_flow(self):
        from app.core.plan_dag import get_plan_dag_store

        store = get_plan_dag_store()
        res = store.create_plan(
            [
                {"id": "a", "name": "A", "depends_on": []},
                {"id": "b", "name": "B", "depends_on": ["a"]},
            ]
        )
        pid = res["plan_id"]
        # b 不能先于 a
        bad = store.start_step(pid, "b")
        assert bad["success"] is False
        assert bad["error_code"] == "DEPENDS_NOT_MET"

        ok_a = store.start_step(pid, "a")
        assert ok_a["success"] is True
        assert ok_a["plan"]["status"] == "running"
        done_a = store.complete_step(pid, "a", result={"ok": True})
        assert done_a["success"] is True

        ok_b = store.start_step(pid, "b")
        assert ok_b["success"] is True
        done_b = store.complete_step(pid, "b", result={"ok": True})
        assert done_b["success"] is True
        assert done_b["plan"]["status"] == "completed"

    def test_tool_wrappers(self):
        from app.core.tools import create_analysis_plan, get_plan_status, execute_tool

        out = json.loads(
            create_analysis_plan.invoke(
                {"steps": json.dumps(["step1", "step2"]), "title": "t"}
            )
        )
        assert out["success"] is True
        plan_id = out["plan_id"]
        st = json.loads(get_plan_status.invoke({"plan_id": plan_id}))
        assert st["success"] is True
        assert st["plan_id"] == plan_id

        # execute_tool 分发
        out2 = json.loads(
            execute_tool(
                "create_analysis_plan",
                {"steps": '["x"]', "title": "via_exec"},
            )
        )
        assert out2["success"] is True


class TestSkillStub:
    def test_list_and_load_builtin(self):
        from app.core.skill_loader import get_skill_loader

        loader = get_skill_loader()
        skills = loader.list_skills()
        ids = {s["id"] for s in skills}
        assert "risk_checklist" in ids
        assert "portfolio_readonly" in ids
        assert "reflection_hint" in ids

        res = loader.load_skill("risk_checklist")
        assert res["success"] is True
        assert "system_hint" in res and "Skill: risk_checklist" in res["system_hint"]
        # 不得出现假价格数字作为行情
        assert "1174.06" not in res["system_hint"]

    def test_reflection_hint_uses_local_or_empty_message(self):
        from app.core.skill_loader import get_skill_loader

        loader = get_skill_loader()
        # 600519 仓库内通常有 reflections
        res = loader.load_skill("reflection_hint", stock_code="600519")
        assert res["success"] is True
        assert res["system_hint"]
        assert "adapters" in res["system_hint"] or "反思" in res["system_hint"] or "策略" in res["system_hint"]

        # 不存在标的：应说明暂无，不编造
        res2 = loader.load_skill("reflection_hint", stock_code="ZZZZZZ_NO_SUCH")
        assert res2["success"] is True
        assert "暂无" in res2["system_hint"]

    def test_unknown_skill(self):
        from app.core.skill_loader import get_skill_loader

        res = get_skill_loader().load_skill("not_a_real_skill_xyz")
        assert res["success"] is False
        assert res["error_code"] == "SKILL_NOT_FOUND"

    def test_tool_wrappers(self):
        from app.core.tools import load_agent_skill, list_agent_skills, execute_tool

        listed = json.loads(list_agent_skills.invoke({}))
        assert listed["success"] is True
        assert listed["count"] >= 3

        loaded = json.loads(
            load_agent_skill.invoke({"skill_id": "portfolio_readonly"})
        )
        assert loaded["success"] is True
        assert loaded["system_hint"]

        via = json.loads(
            execute_tool("load_agent_skill", {"skill_id": "analysis_plan"})
        )
        assert via["success"] is True

def test_list_analysis_plans_tool_readonly_summary():
    """list_analysis_plans：只读列出 plan 状态，不抓数。"""
    import json
    from app.core.plan_dag import get_plan_dag_store
    from app.core.tools import list_analysis_plans, create_analysis_plan

    store = get_plan_dag_store()
    store.reset()
    created = json.loads(
        create_analysis_plan.invoke(
            {
                "title": "list-tool-demo",
                "steps": '["技术面","基本面"]',
            }
        )
    )
    assert created.get("success") is True
    plan_id = created["plan_id"]

    raw = list_analysis_plans.invoke({"limit": 10})
    body = json.loads(raw)
    assert body.get("success") is True
    assert body.get("count", 0) >= 1
    plans = body.get("plans") or []
    hit = next((p for p in plans if p.get("plan_id") == plan_id), None)
    assert hit is not None
    assert hit.get("status")
    assert "steps_summary" in hit
    assert "pending" in hit["steps_summary"]
    assert "note" in body
    assert "不抓" in body["note"] or "只读" in body["note"]

