"""
Input: 拟写仓提案字段 + approval_id 审批状态
Output: 提案对象 / 硬闸门响应（禁止假「已下单」）；无真实券商
Pos: app/core/write_proposal.py — Sprint4 写仓 harness 骨架（提案 + approval 闸门）

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

        return {
            "success": True,
            "executed": False,
            "error_code": None,
            "message": (
                "已生成写仓提案（未执行）。需经 approval_id 审批后才可 "
                "apply_portfolio_proposal；当前无真实券商下单。"
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
        """审批提案（不执行写仓）。"""
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
            return {
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

            try:
                logger.info(
                    "WRITE_PROPOSAL_APPLIED_LOCAL proposal_id=%s approval_id=%s "
                    "(no broker, executed=false)",
                    proposal_id,
                    approval_id,
                )
            except Exception:
                pass

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
                "proposal": deepcopy(prop),
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
