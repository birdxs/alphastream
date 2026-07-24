"""
Input: plan_id / steps(name, depends_on) / status 转换命令
Output: 分析计划对象 + 状态机转换结果（串行 / depends_on 校验）
Pos: app/core/plan_dag.py — Sprint4+ 轻量 Plan DAG（进程内，非券商执行器）

[NEW-FILE:#20260724-S4B] 只做结构校验与状态流转；不替代 adapters / 不触发下单。

一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。
"""
from __future__ import annotations

import logging
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

_ASIA_SHANGHAI = timezone(timedelta(hours=8))


def now_cn() -> datetime:
    return datetime.now(_ASIA_SHANGHAI)


# pending -> running -> completed | failed | cancelled
# pending -> cancelled
ALLOWED_STEP_STATUS = frozenset(
    {"pending", "running", "completed", "failed", "cancelled"}
)
ALLOWED_PLAN_STATUS = frozenset(
    {"draft", "ready", "running", "completed", "failed", "cancelled"}
)

# 合法状态迁移
_PLAN_TRANSITIONS: Dict[str, Set[str]] = {
    "draft": {"ready", "cancelled"},
    "ready": {"running", "cancelled"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}

_STEP_TRANSITIONS: Dict[str, Set[str]] = {
    "pending": {"running", "cancelled"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


class PlanDagError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _validate_depends_on(steps: List[Dict[str, Any]]) -> None:
    """depends_on 必须引用既有 step id；禁止自环与未知 id。"""
    ids = [s["id"] for s in steps]
    id_set = set(ids)
    if len(ids) != len(id_set):
        raise PlanDagError("DUPLICATE_STEP_ID", "step id 重复")

    # 邻接：dep -> dependents 用于环检测（Kahn）
    indeg: Dict[str, int] = {i: 0 for i in ids}
    edges: Dict[str, List[str]] = {i: [] for i in ids}

    for s in steps:
        sid = s["id"]
        deps = s.get("depends_on") or []
        if not isinstance(deps, list):
            raise PlanDagError("INVALID_DEPENDS", f"step {sid}: depends_on 须为 list")
        for d in deps:
            if d not in id_set:
                raise PlanDagError(
                    "UNKNOWN_DEPEND",
                    f"step {sid} depends_on 未知 id: {d!r}",
                )
            if d == sid:
                raise PlanDagError("SELF_DEPEND", f"step {sid} 不可依赖自身")
            edges[d].append(sid)
            indeg[sid] += 1

    # 环检测
    queue = [i for i, g in indeg.items() if g == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for m in edges[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if seen != len(ids):
        raise PlanDagError("CYCLE", "depends_on 存在环，非法 DAG")


def _normalize_steps(raw_steps: List[Any]) -> List[Dict[str, Any]]:
    if not raw_steps:
        raise PlanDagError("EMPTY_STEPS", "至少需要 1 个 step")
    if len(raw_steps) > 32:
        raise PlanDagError("TOO_MANY_STEPS", "step 数量上限 32")

    steps: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_steps):
        if isinstance(item, str):
            name = item.strip()
            sid = f"s{idx + 1}"
            deps: List[str] = [f"s{idx}"] if idx > 0 else []  # 默认串行链
            steps.append(
                {
                    "id": sid,
                    "name": name or sid,
                    "depends_on": deps,
                    "status": "pending",
                    "result": None,
                    "error": None,
                }
            )
            continue
        if not isinstance(item, dict):
            raise PlanDagError("INVALID_STEP", f"step[{idx}] 须为 str 或 dict")
        name = str(item.get("name") or item.get("id") or f"step_{idx + 1}").strip()
        sid = str(item.get("id") or f"s{idx + 1}").strip()
        deps_raw = item.get("depends_on")
        if deps_raw is None:
            # 未声明时默认串行：依赖上一步
            deps = [steps[-1]["id"]] if steps else []
        else:
            deps = [str(d) for d in deps_raw]
        steps.append(
            {
                "id": sid,
                "name": name,
                "depends_on": deps,
                "status": "pending",
                "result": None,
                "error": None,
            }
        )
    _validate_depends_on(steps)
    return steps


def topological_order(steps: List[Dict[str, Any]]) -> List[str]:
    """稳定拓扑序（同层按 id 排序）。"""
    ids = [s["id"] for s in steps]
    id_set = set(ids)
    indeg = {i: 0 for i in ids}
    edges: Dict[str, List[str]] = {i: [] for i in ids}
    for s in steps:
        for d in s.get("depends_on") or []:
            if d in id_set:
                edges[d].append(s["id"])
                indeg[s["id"]] += 1
    ready = sorted([i for i, g in indeg.items() if g == 0])
    order: List[str] = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for m in sorted(edges[n]):
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
                ready.sort()
    return order


class PlanDagStore:
    """进程内分析计划 store（RLock）。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._plans: Dict[str, Dict[str, Any]] = {}

    def reset(self) -> None:
        with self._lock:
            self._plans.clear()

    def create_plan(
        self,
        steps: List[Any],
        *,
        title: str = "",
        conversation_id: str = "",
        stock_code: str = "",
        auto_ready: bool = True,
    ) -> Dict[str, Any]:
        try:
            norm = _normalize_steps(steps)
        except PlanDagError as e:
            return {
                "success": False,
                "error_code": e.code,
                "error": e.code,
                "message": e.message,
                "plan": None,
            }
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        created = now_cn().isoformat()
        status = "ready" if auto_ready else "draft"
        plan = {
            "plan_id": plan_id,
            "title": (title or "")[:200] or f"analysis_plan_{plan_id[-6:]}",
            "conversation_id": conversation_id or "",
            "stock_code": (stock_code or "").strip(),
            "status": status,
            "steps": norm,
            "topo_order": topological_order(norm),
            "created_at": created,
            "updated_at": created,
            "current_step_id": None,
            "disclaimer": (
                "轻量 Plan DAG：仅结构/状态机，不执行真实数据抓取或下单。"
            ),
        }
        with self._lock:
            self._plans[plan_id] = plan
        try:
            logger.info(
                "PLAN_CREATED plan_id=%s steps=%s status=%s",
                plan_id,
                len(norm),
                status,
            )
        except Exception:
            pass
        return {
            "success": True,
            "error_code": None,
            "message": "计划已创建",
            "plan": deepcopy(plan),
            "plan_id": plan_id,
        }

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            p = self._plans.get(plan_id)
            return deepcopy(p) if p else None

    def list_plans(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            items = sorted(
                self._plans.values(),
                key=lambda x: x.get("created_at") or "",
                reverse=True,
            )
            return [deepcopy(p) for p in items[: max(1, min(limit, 200))]]

    def _get_mut(self, plan_id: str) -> Dict[str, Any]:
        p = self._plans.get(plan_id)
        if not p:
            raise PlanDagError("PLAN_NOT_FOUND", f"未知 plan_id: {plan_id}")
        return p

    def transition_plan(self, plan_id: str, new_status: str) -> Dict[str, Any]:
        ns = (new_status or "").strip().lower()
        if ns not in ALLOWED_PLAN_STATUS:
            return {
                "success": False,
                "error_code": "INVALID_STATUS",
                "message": f"非法 plan status: {new_status!r}",
                "plan": None,
            }
        with self._lock:
            try:
                p = self._get_mut(plan_id)
            except PlanDagError as e:
                return {
                    "success": False,
                    "error_code": e.code,
                    "message": e.message,
                    "plan": None,
                }
            cur = p["status"]
            if ns == cur:
                return {
                    "success": True,
                    "error_code": None,
                    "message": "状态未变",
                    "plan": deepcopy(p),
                }
            allowed = _PLAN_TRANSITIONS.get(cur, set())
            if ns not in allowed:
                return {
                    "success": False,
                    "error_code": "INVALID_TRANSITION",
                    "message": f"plan 不允许 {cur} → {ns}",
                    "plan": deepcopy(p),
                }
            p["status"] = ns
            p["updated_at"] = now_cn().isoformat()
            return {
                "success": True,
                "error_code": None,
                "message": f"plan {cur} → {ns}",
                "plan": deepcopy(p),
            }

    def start_step(self, plan_id: str, step_id: str) -> Dict[str, Any]:
        """将 step 置 running：依赖须全部 completed；plan 自动 draft/ready→running。"""
        with self._lock:
            try:
                p = self._get_mut(plan_id)
            except PlanDagError as e:
                return {
                    "success": False,
                    "error_code": e.code,
                    "message": e.message,
                    "plan": None,
                }
            if p["status"] in ("completed", "failed", "cancelled"):
                return {
                    "success": False,
                    "error_code": "PLAN_TERMINAL",
                    "message": f"plan 已终态: {p['status']}",
                    "plan": deepcopy(p),
                }
            steps_by_id = {s["id"]: s for s in p["steps"]}
            step = steps_by_id.get(step_id)
            if not step:
                return {
                    "success": False,
                    "error_code": "STEP_NOT_FOUND",
                    "message": f"未知 step_id: {step_id}",
                    "plan": deepcopy(p),
                }
            for dep in step.get("depends_on") or []:
                ds = steps_by_id.get(dep)
                if not ds or ds.get("status") != "completed":
                    return {
                        "success": False,
                        "error_code": "DEPENDS_NOT_MET",
                        "message": f"依赖 {dep} 未 completed",
                        "plan": deepcopy(p),
                    }
            cur = step["status"]
            if "running" not in _STEP_TRANSITIONS.get(cur, set()) and cur != "running":
                return {
                    "success": False,
                    "error_code": "INVALID_STEP_TRANSITION",
                    "message": f"step 不允许 {cur} → running",
                    "plan": deepcopy(p),
                }
            # plan 升 running
            if p["status"] in ("draft", "ready"):
                p["status"] = "running"
            elif p["status"] not in ("running",):
                return {
                    "success": False,
                    "error_code": "INVALID_TRANSITION",
                    "message": f"plan 状态 {p['status']} 不可 start_step",
                    "plan": deepcopy(p),
                }
            step["status"] = "running"
            step["error"] = None
            p["current_step_id"] = step_id
            p["updated_at"] = now_cn().isoformat()
            return {
                "success": True,
                "error_code": None,
                "message": f"step {step_id} running",
                "plan": deepcopy(p),
            }

    def complete_step(
        self,
        plan_id: str,
        step_id: str,
        *,
        result: Any = None,
        failed: bool = False,
        error: str = "",
    ) -> Dict[str, Any]:
        with self._lock:
            try:
                p = self._get_mut(plan_id)
            except PlanDagError as e:
                return {
                    "success": False,
                    "error_code": e.code,
                    "message": e.message,
                    "plan": None,
                }
            steps_by_id = {s["id"]: s for s in p["steps"]}
            step = steps_by_id.get(step_id)
            if not step:
                return {
                    "success": False,
                    "error_code": "STEP_NOT_FOUND",
                    "message": f"未知 step_id: {step_id}",
                    "plan": deepcopy(p),
                }
            cur = step["status"]
            target = "failed" if failed else "completed"
            if target not in _STEP_TRANSITIONS.get(cur, set()):
                return {
                    "success": False,
                    "error_code": "INVALID_STEP_TRANSITION",
                    "message": f"step 不允许 {cur} → {target}",
                    "plan": deepcopy(p),
                }
            step["status"] = target
            step["result"] = result
            step["error"] = (error or "")[:500] if failed else None
            p["updated_at"] = now_cn().isoformat()

            if failed:
                p["status"] = "failed"
            else:
                # 全部 completed → plan completed
                if all(s.get("status") == "completed" for s in p["steps"]):
                    p["status"] = "completed"
                    p["current_step_id"] = None
                else:
                    p["status"] = "running"
            return {
                "success": True,
                "error_code": None,
                "message": f"step {step_id} → {target}",
                "plan": deepcopy(p),
            }

    def get_status(self, plan_id: str) -> Dict[str, Any]:
        plan = self.get_plan(plan_id)
        if not plan:
            return {
                "success": False,
                "error_code": "PLAN_NOT_FOUND",
                "message": f"未知 plan_id: {plan_id}",
                "status": None,
                "plan": None,
            }
        pending = [s["id"] for s in plan["steps"] if s.get("status") == "pending"]
        running = [s["id"] for s in plan["steps"] if s.get("status") == "running"]
        done = [s["id"] for s in plan["steps"] if s.get("status") == "completed"]
        return {
            "success": True,
            "error_code": None,
            "message": "ok",
            "plan_id": plan_id,
            "status": plan["status"],
            "current_step_id": plan.get("current_step_id"),
            "topo_order": plan.get("topo_order"),
            "steps_summary": {
                "pending": pending,
                "running": running,
                "completed": done,
                "failed": [s["id"] for s in plan["steps"] if s.get("status") == "failed"],
            },
            "plan": plan,
        }


_store: Optional[PlanDagStore] = None
_store_lock = threading.Lock()


def get_plan_dag_store() -> PlanDagStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = PlanDagStore()
        return _store
