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
        # 文件 skill 热读（data/skills）
        assert "research_depth" in ids
        assert "hitl_checklist" in ids
        assert "tool_discipline" in ids  # 文件优先 / builtin 同名

        # 元数据契约：source / has_hint / path(仅文件)
        file_skills = [s for s in skills if s.get("source") == "data/skills"]
        assert len(file_skills) >= 3
        for s in file_skills:
            assert s.get("has_hint") is True or s.get("has_hint") is False
            assert s.get("path") and "/" not in str(s.get("path"))  # 仅文件名
            assert "1174.06" not in json.dumps(s, ensure_ascii=False)

        res = loader.load_skill("risk_checklist")
        assert res["success"] is True
        assert "system_hint" in res and "Skill: risk_checklist" in res["system_hint"]
        # 不得出现假价格数字作为行情
        assert "1174.06" not in res["system_hint"]

        # tool_discipline 可 load（文件优先）
        td = loader.load_skill("tool_discipline")
        assert td["success"] is True
        assert "system_hint" in td
        assert "1174.06" not in td["system_hint"]

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
        # 文件 skill 元数据在 tools 出口
        skill_ids = {s["id"] for s in listed["skills"]}
        assert "tool_discipline" in skill_ids
        assert "research_depth" in skill_ids
        assert "by_source" in listed
        assert listed["by_source"].get("data/skills", 0) >= 1
        # 元数据无密钥/假数
        blob = json.dumps(listed, ensure_ascii=False)
        assert "api_key" not in blob.lower()
        assert "1174.06" not in blob

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
    assert any(
        (isinstance(s, dict) and s.get("status") == "pending") or s == "pending"
        for s in (hit.get("steps_summary") or [])
    )
    assert "note" in body
    assert "不抓" in body["note"] or "只读" in body["note"]



def test_list_plans_conversation_and_status_filter():
    """list_plans 支持 conversation_id + status 过滤。"""
    from app.core.plan_dag import get_plan_dag_store

    store = get_plan_dag_store()
    store.reset()
    store.create_plan(
        steps=[{"step_id": "s1", "name": "A"}],
        conversation_id="conv_filter_a",
        title="A",
        auto_ready=True,
    )
    store.create_plan(
        steps=[{"step_id": "s1", "name": "B"}],
        conversation_id="conv_filter_b",
        title="B",
        auto_ready=False,
    )
    only_a = store.list_plans(limit=20, conversation_id="conv_filter_a")
    assert len(only_a) == 1
    assert only_a[0]["conversation_id"] == "conv_filter_a"
    drafts = store.list_plans(limit=20, status="draft")
    assert any(p["title"] == "B" for p in drafts)
    ready = store.list_plans(limit=20, status="ready", conversation_id="conv_filter_a")
    assert len(ready) == 1
    empty = store.list_plans(limit=20, conversation_id="no_such_conv")
    assert empty == []



def test_advance_plan_step_state_machine_and_event():
    """advance_step start→complete 发 plan.step 事件；不抓数。"""
    from app.core.event_bus import get_event_bus
    from app.core.plan_dag import get_plan_dag_store
    from app.core.tools import advance_plan_step, create_analysis_plan
    import json

    bus = get_event_bus()
    seen = []

    def _on_step(data):
        seen.append(("plan.step", data))

    def _on_created(data):
        seen.append(("plan.created", data))

    bus.subscribe("plan.step", _on_step)
    bus.subscribe("plan.created", _on_created)
    store = get_plan_dag_store()
    store.reset()
    raw = create_analysis_plan.invoke(
        {
            "steps": json.dumps(
                [
                    {"step_id": "s1", "name": "collect"},
                    {"step_id": "s2", "name": "decide", "depends_on": ["s1"]},
                ],
                ensure_ascii=False,
            ),
            "title": "adv",
            "conversation_id": "conv_adv",
            "auto_ready": True,
        }
    )
    data = json.loads(raw)
    assert data.get("success") is True
    plan_id = data["plan_id"]
    steps = data["plan"]["steps"]
    s1 = steps[0].get("id") or steps[0].get("step_id") or "s1"
    assert s1

    r1 = json.loads(
        advance_plan_step.invoke(
            {"plan_id": plan_id, "step_id": s1, "action": "start"}
        )
    )
    assert r1.get("success") is True
    assert r1["plan"]["steps"][0]["status"] == "running"

    r2 = json.loads(
        advance_plan_step.invoke(
            {"plan_id": plan_id, "step_id": s1, "action": "complete"}
        )
    )
    assert r2.get("success") is True
    assert r2["plan"]["steps"][0]["status"] == "completed"

    names = [n for n, _ in seen]
    assert "plan.created" in names
    assert "plan.step" in names
    assert any(
        isinstance(d, dict) and d.get("action") in ("start", "complete")
        for n, d in seen
        if n == "plan.step"
    )



def test_list_analysis_plans_filter_kwargs():
    """list_analysis_plans 工具接受 conversation_id / status。"""
    import json
    from app.core.plan_dag import get_plan_dag_store
    from app.core.tools import create_analysis_plan, list_analysis_plans

    store = get_plan_dag_store()
    store.reset()
    create_analysis_plan.invoke(
        {
            "steps": '[{"name":"x"}]',
            "title": "filt",
            "conversation_id": "conv_tool_filt",
            "auto_ready": True,
        }
    )
    raw = list_analysis_plans.invoke(
        {"limit": 10, "conversation_id": "conv_tool_filt", "status": "ready"}
    )
    data = json.loads(raw)
    assert data["success"] is True
    assert data["count"] >= 1
    assert all(p.get("conversation_id") == "conv_tool_filt" for p in data["plans"])


def test_write_proposal_event_fields_align_with_approval_card():
    """write_proposal EVENT 与 HITL pending 字段对齐：kind / approval_id / proposal_id / summary。"""
    from app.agents.hitl import approval_manager
    from app.core.event_bus import EVENT_WRITE_PROPOSAL, get_event_bus
    from app.core.write_proposal import (
        get_write_proposal_store,
        reset_write_proposal_store_for_tests,
    )

    bus = get_event_bus()
    seen = []

    def _on_wp(data):
        seen.append(data if isinstance(data, dict) else {})

    bus.subscribe(EVENT_WRITE_PROPOSAL, _on_wp)
    reset_write_proposal_store_for_tests()
    store = get_write_proposal_store()
    # 清理 HITL 残留
    try:
        with approval_manager._lock:  # type: ignore[attr-defined]
            approval_manager._pending_approvals.clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    result = store.create_proposal(
        action="add_holding",
        code="600519",
        name="贵州茅台",
        shares=100,
        reason="单元测试写仓提案字段对齐",
        conversation_id="conv_wp_align",
    )
    assert result.get("success") is True
    assert result.get("executed") is False
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    proposal_id = (
        result.get("proposal_id")
        or (data or {}).get("proposal_id")
    )
    approval_id = (
        result.get("approval_id")
        or (data or {}).get("approval_id")
    )
    assert proposal_id and str(proposal_id).startswith("prop_")
    assert approval_id and str(approval_id).startswith("appr_")

    # EventBus 载荷字段
    assert seen, "应发布 EVENT_WRITE_PROPOSAL"
    ev = seen[-1]
    # 允许总线再包一层 data
    if "data" in ev and isinstance(ev.get("data"), dict) and "proposal_id" not in ev:
        ev = ev["data"]
    assert ev.get("kind") == "portfolio_write_proposal"
    assert ev.get("proposal_id") == proposal_id
    assert ev.get("approval_id") == approval_id
    assert ev.get("status") == "pending"
    assert ev.get("executed") is False
    assert ev.get("summary")
    assert "add_holding" in str(ev.get("summary"))
    assert "600519" in str(ev.get("summary")) or ev.get("code") == "600519"
    assert "1174.06" not in json.dumps(ev, ensure_ascii=False)

    # HITL pending 列表字段与 event 对齐
    pending = approval_manager.get_pending_approvals()
    hit = next(
        (
            p
            for p in pending
            if p.get("approval_id") == approval_id
            or p.get("task_id") == approval_id
            or p.get("proposal_id") == proposal_id
        ),
        None,
    )
    assert hit is not None, f"pending 应含 approval_id={approval_id}, got={pending!r}"
    assert hit.get("kind") == "portfolio_write_proposal"
    assert hit.get("approval_id") == approval_id or hit.get("task_id") == approval_id
    assert hit.get("proposal_id") == proposal_id


def test_file_skills_from_data_dir():
    """data/skills 样例可被 list/load（无假数）。"""
    from app.core.skill_loader import SkillLoader
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    skills_dir = root / "data" / "skills"
    assert skills_dir.is_dir(), skills_dir
    loader = SkillLoader(skills_dir=skills_dir)
    items = loader.list_skills()
    ids = {x["id"] for x in items}
    assert "research_depth" in ids
    assert "hitl_checklist" in ids
    rd = loader.load_skill("research_depth")
    assert rd.get("success") is True
    rd_hint = rd.get("system_hint") or (rd.get("skill") or {}).get("system_hint") or ""
    assert "research_depth" in rd_hint
    hc = loader.load_skill("hitl_checklist")
    assert hc.get("success") is True
    hint = hc.get("system_hint") or (hc.get("skill") or {}).get("system_hint") or ""
    assert "审批" in hint or "HITL" in hint or "executed" in hint



def test_write_proposal_publishes_event():
    """create_proposal 发布 write_proposal 事件。"""
    from app.core.event_bus import get_event_bus, EVENT_WRITE_PROPOSAL
    from app.core.write_proposal import get_write_proposal_store

    bus = get_event_bus()
    seen = []

    def _on(data):
        seen.append((EVENT_WRITE_PROPOSAL, data))

    bus.subscribe(EVENT_WRITE_PROPOSAL, _on)
    store = get_write_proposal_store()
    store.reset()
    out = store.create_proposal(
        action="add_holding",
        code="600519",
        shares=100,
        reason="unit test proposal",
        conversation_id="conv_wp_evt",
    )
    assert out.get("success") is True
    assert out.get("executed") is False
    assert any(n == EVENT_WRITE_PROPOSAL or n == "write_proposal" for n, _ in seen)
    assert any(
        isinstance(d, dict) and d.get("executed") is False for _, d in seen
    )


