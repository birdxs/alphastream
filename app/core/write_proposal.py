"""
Input: 拟写仓提案字段 + approval_id 审批状态
Output: 提案对象 / 硬闸门响应（禁止假「已下单」）；无真实券商
Pos: app/core/write_proposal.py — Sprint4 写仓 harness（提案 + approval 闸门 + HITL pending 桥）

[NEW-FILE:#20260724-S4] 离线可测；不依赖联调/真券商。

一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ASIA_SHANGHAI = timezone(timedelta(hours=8))


def now_cn() -> datetime:
    return datetime.now(_ASIA_SHANGHAI)


# 允许的提案动作（本地模拟标签，非券商指令）
ALLOWED_ACTIONS = frozenset(
    {
        "add_holding",
        "remove_holding",
        "update_holding",
        "rebalance",
        "other",
    }
)

DISCLAIMER = (
    "本对象仅为写仓**提案**，不构成真实下单或持仓变更。"
    "无券商连通；executed=false 表示未发生外部写操作。"
)


class WriteProposalStore:
    """进程内提案 + 审批记录（RLock）。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # proposal_id -> dict
        self._proposals: Dict[str, Dict[str, Any]] = {}
        # approval_id -> dict
        self._approvals: Dict[str, Dict[str, Any]] = {}

    def reset(self) -> None:
        """测试用：清空。"""
        with self._lock:
            self._proposals.clear()
            self._approvals.clear()

    def _build_summary(
        self,
        action: str = "",
        code: str = "",
        shares: Any = None,
        weight: Any = None,
    ) -> str:
        """只读摘要（零假数）：动作 + 代码 + 可选 shares/weight，无价格。"""
        parts: List[str] = [str(action or "write").strip() or "write"]
        code_s = str(code or "").strip()
        if code_s:
            parts.append(code_s)
        if shares is not None:
            parts.append(f"×{shares}")
        if weight is not None:
            parts.append(f"w={weight}")
        return " ".join(parts)

    def _publish_write_proposal_event(
        self,
        *,
        proposal_id: str,
        approval_id: str,
        status: str,
        action: str = "",
        code: str = "",
        name: str = "",
        shares: Any = None,
        weight: Any = None,
        reason: str = "",
        conversation_id: str = "",
        summary: Optional[str] = None,
        apply_mode: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        timeline / SSE：EVENT_WRITE_PROPOSAL 生命周期事件。
        status: pending | approved | rejected | applied_local
        executed 恒 False（铁律#1：永不声明成交/已下单）。
        """
        try:
            from app.core.event_bus import get_event_bus, EVENT_WRITE_PROPOSAL

            status_s = str(status or "pending").strip().lower() or "pending"
            # 本地模拟 applied 对外契约用 applied_local（与 prop 内部 status=applied 区分语义）
            if status_s == "applied":
                status_s = "applied_local"
            summary_s = (summary or "").strip() or self._build_summary(
                action, code, shares, weight
            )
            payload: Dict[str, Any] = {
                "event_type": EVENT_WRITE_PROPOSAL,
                "kind": "portfolio_write_proposal",
                "proposal_id": proposal_id,
                "approval_id": approval_id,
                "task_id": approval_id,  # HITL task_id == approval_id
                "status": status_s,
                "action": action or None,
                "code": (code or None) or None,
                "name": (name or None) or None,
                "shares": shares,
                "weight": weight,
                "reason": (reason or "")[:500] or None,
                "conversation_id": conversation_id or "",
                "executed": False,  # 铁律#1：永不 true
                "apply_mode": apply_mode,
                "summary": summary_s,
                "message": message
                or f"写仓提案 {summary_s}（status={status_s}，未成交）".strip(),
            }
            get_event_bus().publish(EVENT_WRITE_PROPOSAL, payload)
        except Exception as e:
            try:
                logger.debug(
                    "WRITE_PROPOSAL event publish skipped proposal_id=%s status=%s: %s",
                    proposal_id,
                    status,
                    e,
                )
            except Exception:
                pass

    def create_proposal(
        self,
        action: str,
        code: str = "",
        *,
        name: str = "",
        shares: Optional[float] = None,
        weight: Optional[float] = None,
        reason: str = "",
        conversation_id: str = "",
        source: str = "agent_tool",
    ) -> Dict[str, Any]:
        """创建提案 + pending approval_id。永不标记已下单。"""
        act = (action or "").strip().lower()
        if act not in ALLOWED_ACTIONS:
            return {
                "success": False,
                "executed": False,
                "error_code": "INVALID_ACTION",
                "error": "INVALID_ACTION",
                "message": f"不支持的提案动作: {action!r}；允许: {sorted(ALLOWED_ACTIONS)}",
                "data": None,
                "broker": None,
                "disclaimer": DISCLAIMER,
            }

        code_s = (code or "").strip()
        if act in ("add_holding", "remove_holding", "update_holding") and not code_s:
            return {
                "success": False,
                "executed": False,
                "error_code": "INVALID_INPUT",
                "error": "INVALID_INPUT",
                "message": "该动作要求非空 stock code",
                "data": None,
                "broker": None,
                "disclaimer": DISCLAIMER,
            }

        proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
        approval_id = f"appr_{uuid.uuid4().hex[:12]}"
        created = now_cn().isoformat()

        proposal = {
            "proposal_id": proposal_id,
            "approval_id": approval_id,
            "action": act,
            "code": code_s,
            "name": (name or "").strip() if name and name.strip() != code_s else "",
            "shares": shares,
            "weight": weight,
            "reason": (reason or "")[:500],
            "conversation_id": conversation_id or "",
            "source": source,
            "status": "proposed",  # proposed | applied | cancelled
            "created_at": created,
            "applied_at": None,
            "broker": None,
            "executed": False,
            "disclaimer": DISCLAIMER,
        }
        approval = {
            "approval_id": approval_id,
            "proposal_id": proposal_id,
            "status": "pending",  # pending | approved | rejected
            "created_at": created,
            "decided_at": None,
            "feedback": "",
            "kind": "portfolio_write_proposal",
        }
        with self._lock:
            self._proposals[proposal_id] = proposal
            self._approvals[approval_id] = approval

        # HITL 桥接：登记到 approval_manager，使 pending 列表 / agent_submit_approval 可见
        # task_id 使用 approval_id，与 decide_portfolio_proposal_approval 同键
        try:
            from app.agents.hitl import approval_manager

            approval_manager.register_non_blocking_pending(
                approval_id,
                decision={
                    "action": act,
                    "code": code_s,
                    "name": proposal.get("name") or "",
                    "shares": shares,
                    "weight": weight,
                    "proposal_id": proposal_id,
                    "kind": "portfolio_write_proposal",
                },
                risk_level="high",
                reason=(reason or f"写仓提案 {act} {code_s}".strip())[:500],
                kind="portfolio_write_proposal",
                metadata={
                    "proposal_id": proposal_id,
                    "approval_id": approval_id,
                    "source": source,
                },
            )
        except Exception as e:
            try:
                logger.debug(
                    "WRITE_PROPOSAL HITL register skipped proposal_id=%s: %s",
                    proposal_id,
                    e,
                )
            except Exception:
                pass

        try:
            logger.info(
                "WRITE_PROPOSAL_CREATED proposal_id=%s approval_id=%s action=%s code=%s",
                proposal_id,
                approval_id,
                act,
                code_s or "-",
            )
        except Exception:
            pass

        # timeline / SSE / ApprovalCard：字段与 pending 审批对齐（kind/approval_id/proposal_id）
        self._publish_write_proposal_event(
            proposal_id=proposal_id,
            approval_id=approval_id,
            status="pending",
            action=act,
            code=code_s,
            name=proposal.get("name") or "",
            shares=shares,
            weight=weight,
            reason=reason or "",
            conversation_id=conversation_id or "",
            message=f"写仓提案 {self._build_summary(act, code_s, shares, weight)}（待审批，未成交）",
        )

        return {
            "success": True,
            "executed": False,
            "error_code": None,
            "message": (
                "已生成写仓提案（未执行）。需经 approval_id 审批后才可 "
                "apply_portfolio_proposal；当前无真实券商下单。"
                "该 approval 已桥接到 HITL pending（task_id=approval_id），"
                "可用 /api/agent_submit_approval 或 decide_portfolio_proposal_approval。"
            ),
            "proposal": deepcopy(proposal),
            "approval_id": approval_id,
            "proposal_id": proposal_id,
            "data": None,
            "broker": None,
            "disclaimer": DISCLAIMER,
        }

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            p = self._proposals.get(proposal_id)
            return deepcopy(p) if p else None

    def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            a = self._approvals.get(approval_id)
            return deepcopy(a) if a else None

    def decide_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
        feedback: str = "",
    ) -> Dict[str, Any]:
        """审批提案（不执行写仓）。成功后发布 write_proposal 终态事件（executed=false）。"""
        snapshot: Optional[Dict[str, Any]] = None
        with self._lock:
            ap = self._approvals.get(approval_id)
            if not ap:
                return {
                    "success": False,
                    "executed": False,
                    "error_code": "APPROVAL_NOT_FOUND",
                    "error": "APPROVAL_NOT_FOUND",
                    "message": f"未知 approval_id: {approval_id}",
                    "data": None,
                    "broker": None,
                }
            if ap["status"] != "pending":
                return {
                    "success": False,
                    "executed": False,
                    "error_code": "APPROVAL_ALREADY_DECIDED",
                    "error": "APPROVAL_ALREADY_DECIDED",
                    "message": f"审批已决: {ap['status']}",
                    "approval": deepcopy(ap),
                    "data": None,
                    "broker": None,
                }
            ap["status"] = "approved" if approved else "rejected"
            ap["decided_at"] = now_cn().isoformat()
            ap["feedback"] = (feedback or "")[:500]
            prop = self._proposals.get(ap.get("proposal_id") or "")
            snapshot = {
                "proposal_id": ap.get("proposal_id") or "",
                "approval_id": approval_id,
                "status": ap["status"],
                "action": (prop or {}).get("action") or "",
                "code": (prop or {}).get("code") or "",
                "name": (prop or {}).get("name") or "",
                "shares": (prop or {}).get("shares"),
                "weight": (prop or {}).get("weight"),
                "reason": (prop or {}).get("reason") or "",
                "conversation_id": (prop or {}).get("conversation_id") or "",
                "feedback": ap.get("feedback") or "",
            }
            result = {
                "success": True,
                "executed": False,
                "approval": deepcopy(ap),
                "message": (
                    "审批已记录为 approved；仍未下单，需显式 apply。"
                    if approved
                    else "审批已拒绝；提案不可 apply。"
                ),
                "data": None,
                "broker": None,
                "disclaimer": DISCLAIMER,
            }

        # 工具路径 decide 时，同步摘除 HITL pending（task_id=approval_id）
        try:
            from app.agents.hitl import approval_manager

            with approval_manager._lock:
                entry = approval_manager._pending_approvals.get(approval_id)
                if entry is not None and entry.get("status") == "pending":
                    entry["status"] = "approved" if approved else "rejected"
                    entry["human_feedback"] = (feedback or "")[:500]
                    if entry.get("non_blocking") or entry.get("kind") == "portfolio_write_proposal":
                        approval_manager._pending_approvals.pop(approval_id, None)
        except Exception as e:
            try:
                logger.debug(
                    "decide_approval HITL cleanup skipped approval_id=%s: %s",
                    approval_id,
                    e,
                )
            except Exception:
                pass

        # timeline：终态 event（approved | rejected），executed 恒 False
        if snapshot:
            st = "approved" if approved else "rejected"
            self._publish_write_proposal_event(
                proposal_id=str(snapshot.get("proposal_id") or ""),
                approval_id=approval_id,
                status=st,
                action=str(snapshot.get("action") or ""),
                code=str(snapshot.get("code") or ""),
                name=str(snapshot.get("name") or ""),
                shares=snapshot.get("shares"),
                weight=snapshot.get("weight"),
                reason=str(snapshot.get("reason") or ""),
                conversation_id=str(snapshot.get("conversation_id") or ""),
                message=(
                    f"写仓提案已{('通过' if approved else '拒绝')}（status={st}，未成交）"
                    + (
                        f"：{str(snapshot.get('feedback'))[:120]}"
                        if snapshot.get("feedback")
                        else ""
                    )
                ),
            )

        return result

    def apply_proposal(
        self,
        proposal_id: str,
        approval_id: str,
    ) -> Dict[str, Any]:
        """
        应用提案闸门：
        - 必须 approval_id 匹配且 status=approved
        - 成功仅标记本地提案 applied（模拟）
        - broker 恒为 None；禁止声明真实下单
        """
        with self._lock:
            prop = self._proposals.get(proposal_id)
            if not prop:
                return {
                    "success": False,
                    "executed": False,
                    "error_code": "PROPOSAL_NOT_FOUND",
                    "error": "PROPOSAL_NOT_FOUND",
                    "message": f"未知 proposal_id: {proposal_id}",
                    "data": None,
                    "broker": None,
                    "disclaimer": DISCLAIMER,
                }
            if prop["status"] == "applied":
                return {
                    "success": False,
                    "executed": False,
                    "error_code": "ALREADY_APPLIED",
                    "error": "ALREADY_APPLIED",
                    "message": "提案已标记 applied（本地模拟），禁止重复应用",
                    "proposal": deepcopy(prop),
                    "data": None,
                    "broker": None,
                    "disclaimer": DISCLAIMER,
                }
            if prop["status"] == "cancelled":
                return {
                    "success": False,
                    "executed": False,
                    "error_code": "PROPOSAL_CANCELLED",
                    "error": "PROPOSAL_CANCELLED",
                    "message": "提案已取消",
                    "data": None,
                    "broker": None,
                    "disclaimer": DISCLAIMER,
                }

            ap = self._approvals.get(approval_id)
            if not ap:
                return {
                    "success": False,
                    "executed": False,
                    "error_code": "APPROVAL_REQUIRED",
                    "error": "APPROVAL_REQUIRED",
                    "message": (
                        "缺少有效 approval_id。写仓 apply 必须先审批；"
                        "当前未执行任何写操作/下单。"
                    ),
                    "data": None,
                    "broker": None,
                    "disclaimer": DISCLAIMER,
                }
            if ap.get("proposal_id") != proposal_id:
                return {
                    "success": False,
                    "executed": False,
                    "error_code": "APPROVAL_MISMATCH",
                    "error": "APPROVAL_MISMATCH",
                    "message": "approval_id 与 proposal_id 不匹配",
                    "data": None,
                    "broker": None,
                    "disclaimer": DISCLAIMER,
                }
            if ap.get("status") != "approved":
                return {
                    "success": False,
                    "executed": False,
                    "error_code": "APPROVAL_REQUIRED",
                    "error": "APPROVAL_REQUIRED",
                    "message": (
                        f"审批状态为 {ap.get('status')!r}，需要 approved 才能 apply；"
                        "未执行写操作，无真实下单。"
                    ),
                    "approval_status": ap.get("status"),
                    "data": None,
                    "broker": None,
                    "disclaimer": DISCLAIMER,
                }

            # 本地模拟：仅标记 applied；executed 表示外部下单/改仓，恒 false（禁假「已下单」）
            prop["status"] = "applied"
            prop["applied_at"] = now_cn().isoformat()
            prop["executed"] = False
            prop["broker"] = None
            prop["apply_mode"] = "local_mark_only"
            prop["local_marked"] = True
            snap = deepcopy(prop)

            try:
                logger.info(
                    "WRITE_PROPOSAL_APPLIED_LOCAL proposal_id=%s approval_id=%s "
                    "(no broker, executed=false)",
                    proposal_id,
                    approval_id,
                )
            except Exception:
                pass

        # 锁外发布 timeline：status=applied_local，executed 恒 False（铁律#1）
        self._publish_write_proposal_event(
            proposal_id=proposal_id,
            approval_id=approval_id,
            status="applied_local",
            action=str(snap.get("action") or ""),
            code=str(snap.get("code") or ""),
            name=str(snap.get("name") or ""),
            shares=snap.get("shares"),
            weight=snap.get("weight"),
            reason=str(snap.get("reason") or ""),
            conversation_id=str(snap.get("conversation_id") or ""),
            apply_mode="local_mark_only",
            message=(
                "提案已本地标记 applied_local（模拟完成，非成交；"
                "executed=false，broker=null）"
            ),
        )

        return {
            "success": True,
            "executed": False,
            "applied": True,
            "local_marked": True,
            "apply_mode": "local_mark_only",
            "broker": None,
            "error_code": None,
            "message": (
                "提案已本地标记为 applied（模拟完成，非成交）。"
                "executed=false；broker=null；用户持仓 JSON 未自动改写。"
                "禁止将本响应解读为交易所成交或已下单。"
            ),
            "proposal": deepcopy(snap),
            "data": None,
            "disclaimer": DISCLAIMER,
        }

    def list_proposals(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            items = sorted(
                self._proposals.values(),
                key=lambda x: x.get("created_at") or "",
                reverse=True,
            )
            return [deepcopy(p) for p in items[: max(1, min(limit, 200))]]

    def list_pending_approvals(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出仍 pending 的审批（供 HITL get_pending 合并）。"""
        with self._lock:
            items = [
                deepcopy(a)
                for a in self._approvals.values()
                if a.get("status") == "pending"
            ]
            items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
            return items[: max(1, min(limit, 200))]


_store: Optional[WriteProposalStore] = None
_store_lock = threading.Lock()


def get_write_proposal_store() -> WriteProposalStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = WriteProposalStore()
        return _store


def reset_write_proposal_store_for_tests() -> WriteProposalStore:
    """测试隔离：重置单例内容。"""
    store = get_write_proposal_store()
    store.reset()
    return store


def propose_to_json(result: Dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False)
