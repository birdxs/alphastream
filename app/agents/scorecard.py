"""
Input: Agent run state（final_decision / execution_log / degradations / 多角色报告）
Output: run.scorecard 四维指标 dict（无假行情）
Pos: app/agents/scorecard.py - G6 Run scorecard 纯计算

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# 用于 data_coverage 的核心报告槽位（存在且非空即覆盖）
_COVERAGE_SLOTS: Tuple[str, ...] = (
    "technical_report",
    "fundamental_report",
    "capital_flow_report",
    "sentiment_report",
    "bull_case",
    "bear_case",
)

# 多空/角色一致性可比对文本槽
_ROLE_TEXT_SLOTS: Tuple[str, ...] = (
    "bull_case",
    "bear_case",
    "technical_report",
    "fundamental_report",
    "sentiment_report",
)


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def _clamp01(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return max(0.0, min(1.0, float(x)))


def compute_data_coverage(state: Dict[str, Any]) -> float:
    """报告槽位覆盖率：有内容槽位 / 总槽位。"""
    if not state:
        return 0.0
    hits = sum(1 for k in _COVERAGE_SLOTS if _is_present(state.get(k)))
    return _clamp01(hits / float(len(_COVERAGE_SLOTS)))


def compute_tool_success_rate(state: Dict[str, Any]) -> float:
    """从 execution_log 统计工具/节点成功率；无日志时退化为 1.0（未知≠失败）。"""
    logs = state.get("execution_log") or []
    if not isinstance(logs, list) or not logs:
        # 无工具轨迹：不因缺失惩罚（避免假失败），由 degradations 体现风险
        return 1.0
    total = 0
    success = 0
    for entry in logs:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "").strip().lower()
        if not status:
            continue
        total += 1
        if status in ("success", "ok", "completed", "done", "fallback"):
            # fallback 仍算"完成"但会由 degradations/score 其他维体现
            success += 1
        elif status in ("failed", "error", "timeout", "cancelled"):
            pass
        else:
            # 未知 status 记入分母，不计成功
            pass
    if total == 0:
        return 1.0
    return _clamp01(success / float(total))


def _action_from_text(text: str) -> Optional[str]:
    t = (text or "").upper()
    if not t.strip():
        return None
    # 顺序：显式动作词优先
    if "BUY" in t or "买入" in t or "看多" in t or "做多" in t:
        return "BUY"
    if "SELL" in t or "卖出" in t or "看空" in t or "做空" in t:
        return "SELL"
    if "HOLD" in t or "持有" in t or "观望" in t:
        return "HOLD"
    return None


def compute_role_agreement(state: Dict[str, Any]) -> float:
    """多角色动作倾向一致性（0–1）。样本不足时返回 None 语义用 0.5 中性。"""
    if not state:
        return 0.5
    votes: List[str] = []
    for key in _ROLE_TEXT_SLOTS:
        act = _action_from_text(str(state.get(key) or ""))
        if act:
            votes.append(act)
    fd = state.get("final_decision") or {}
    if isinstance(fd, dict):
        fa = str(fd.get("action") or "").upper().strip()
        if fa in ("BUY", "SELL", "HOLD"):
            votes.append(fa)
    if len(votes) < 2:
        return 0.5
    # 众数占比
    counts: Dict[str, int] = {}
    for v in votes:
        counts[v] = counts.get(v, 0) + 1
    majority = max(counts.values())
    return _clamp01(majority / float(len(votes)))


def extract_confidence_cap(state: Dict[str, Any]) -> Optional[float]:
    """从 state / final_decision / degradations 取最紧 confidence_cap。"""
    caps: List[float] = []
    for raw in (state.get("confidence_cap"),):
        if raw is None:
            continue
        try:
            caps.append(float(raw))
        except (TypeError, ValueError):
            pass
    fd = state.get("final_decision")
    if isinstance(fd, dict) and fd.get("confidence_cap") is not None:
        try:
            caps.append(float(fd["confidence_cap"]))
        except (TypeError, ValueError):
            pass
    for d in state.get("degradations") or []:
        if not isinstance(d, dict):
            continue
        if d.get("confidence_cap") is None:
            continue
        try:
            caps.append(float(d["confidence_cap"]))
        except (TypeError, ValueError):
            pass
    if not caps:
        return None
    return _clamp01(min(caps))


def compute_run_scorecard(
    state: Dict[str, Any],
    *,
    task_id: str = "",
    stock_code: str = "",
) -> Dict[str, Any]:
    """G6：产出 run.scorecard 载荷（铁律 #1：无假行情数值）。"""
    state = state or {}
    data_coverage = compute_data_coverage(state)
    tool_success_rate = compute_tool_success_rate(state)
    role_agreement = compute_role_agreement(state)
    confidence_cap = extract_confidence_cap(state)

    scorecard: Dict[str, Any] = {
        "event_type": "run.scorecard",
        "data_coverage": round(data_coverage, 4),
        "tool_success_rate": round(tool_success_rate, 4),
        "role_agreement": round(role_agreement, 4),
        "confidence_cap": (
            round(confidence_cap, 4) if confidence_cap is not None else None
        ),
        # 证据指针（非假数）
        "evidence": {
            "coverage_slots": list(_COVERAGE_SLOTS),
            "coverage_hits": [
                k for k in _COVERAGE_SLOTS if _is_present(state.get(k))
            ],
            "execution_log_count": len(state.get("execution_log") or [])
            if isinstance(state.get("execution_log"), list)
            else 0,
            "degradation_count": len(state.get("degradations") or [])
            if isinstance(state.get("degradations"), list)
            else 0,
        },
    }
    code = stock_code or state.get("stock_code") or ""
    if code:
        scorecard["stock_code"] = str(code)
    if task_id:
        scorecard["task_id"] = str(task_id)
    return scorecard


def build_decision_memo(
    state: Dict[str, Any],
    *,
    scorecard: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """G5：终局决策备忘 — action、否决/风险理由、evidence 指针（无假价）。"""
    state = state or {}
    fd = state.get("final_decision") if isinstance(state.get("final_decision"), dict) else {}
    risk = state.get("risk_assessment") if isinstance(state.get("risk_assessment"), dict) else {}
    hitl = state.get("hitl") if isinstance(state.get("hitl"), dict) else {}
    sc = scorecard or state.get("scorecard") or {}

    action = str(fd.get("action") or "HOLD").upper()
    if action not in ("BUY", "SELL", "HOLD"):
        action = "HOLD"

    # 否决/风险理由（文本证据，非数字造假）
    veto_reasons: List[str] = []
    if state.get("hitl_rejected") or fd.get("approved") is False:
        reason = (
            hitl.get("reason")
            or fd.get("human_feedback")
            or fd.get("reasoning")
            or "HITL 拒绝/未通过"
        )
        veto_reasons.append(f"HITL: {str(reason)[:300]}")
    risk_level = (
        fd.get("risk_level")
        or risk.get("overall_risk")
        or risk.get("risk_level")
        or ""
    )
    if str(risk_level) in ("高", "high", "HIGH", "中高"):
        veto_reasons.append(f"风险等级: {risk_level}")
    for d in (state.get("degradations") or [])[:5]:
        if isinstance(d, dict) and d.get("message"):
            veto_reasons.append(
                f"降级[{d.get('cause') or '?'}]: {str(d.get('message'))[:160]}"
            )

    evidence_pointers: List[Dict[str, str]] = []
    for key, label in (
        ("technical_report", "技术面"),
        ("fundamental_report", "基本面"),
        ("capital_flow_report", "资金流"),
        ("sentiment_report", "情绪面"),
        ("bull_case", "多方"),
        ("bear_case", "空方"),
        ("debate_summary", "辩论摘要"),
        ("risk_assessment", "风险评估"),
    ):
        if _is_present(state.get(key)):
            evidence_pointers.append({"slot": key, "label": label, "status": "present"})
        else:
            # 缺失显式标注，不造内容
            evidence_pointers.append({"slot": key, "label": label, "status": "missing"})

    conf = fd.get("confidence")
    try:
        conf_f = float(conf) if conf is not None else None
    except (TypeError, ValueError):
        conf_f = None

    memo: Dict[str, Any] = {
        "action": action,
        "confidence": conf_f,
        "confidence_cap": sc.get("confidence_cap")
        if isinstance(sc, dict)
        else state.get("confidence_cap"),
        "risk_level": risk_level or None,
        "reasoning": (str(fd.get("reasoning") or "")[:1200] or None),
        "veto_reasons": veto_reasons,
        "risk_reasons": veto_reasons,  # 别名，便于前端
        "evidence_pointers": evidence_pointers,
        "scorecard": {
            "data_coverage": sc.get("data_coverage") if isinstance(sc, dict) else None,
            "tool_success_rate": sc.get("tool_success_rate") if isinstance(sc, dict) else None,
            "role_agreement": sc.get("role_agreement") if isinstance(sc, dict) else None,
            "confidence_cap": sc.get("confidence_cap") if isinstance(sc, dict) else None,
        }
        if isinstance(sc, dict)
        else None,
        "hitl": {
            "required": bool(hitl.get("required")),
            "approved": hitl.get("approved"),
            "approval_type": hitl.get("approval_type"),
        }
        if hitl
        else None,
        "disclaimer": "本研究结论仅供参考，不构成投资建议；证据缺失处不补假数。",
        "stock_code": state.get("stock_code"),
    }
    # 价格目标仅透传上游已有字段，不合成
    # G12 / 铁律 #1：降级态（degradations 或 confidence_cap < 1）不透传价位数字，避免假价误导
    degraded = bool(state.get("degradations")) or (
        isinstance(sc, dict)
        and sc.get("confidence_cap") is not None
        and float(sc["confidence_cap"]) < 1.0 - 1e-12
    ) or (
        state.get("confidence_cap") is not None
        and float(state["confidence_cap"]) < 1.0 - 1e-12
    )
    if isinstance(fd.get("price_targets"), dict) and not degraded:
        memo["price_targets"] = fd["price_targets"]
    if fd.get("position_suggestion") is not None:
        memo["position_suggestion"] = fd.get("position_suggestion")
    return memo


def summarize_reflection_readonly(
    reflections: List[Dict[str, Any]],
    *,
    limit: int = 3,
) -> Optional[Dict[str, Any]]:
    """G7：只读反思摘要；禁止写生产权重。空历史返回 None（不造假）。"""
    if not reflections or not isinstance(reflections, list):
        return None
    items: List[Dict[str, Any]] = []
    for r in reflections[: max(1, limit)]:
        if not isinstance(r, dict):
            continue
        items.append(
            {
                "timestamp": r.get("timestamp"),
                "accuracy_score": r.get("accuracy_score"),
                "lessons": (str(r.get("lessons_learned") or "")[:400] or None),
                "what_went_well": (str(r.get("what_went_well") or "")[:240] or None),
                "what_went_wrong": (str(r.get("what_went_wrong") or "")[:240] or None),
                "prediction_summary": (str(r.get("prediction_summary") or "")[:200] or None),
            }
        )
    if not items:
        return None
    return {
        "count": len(items),
        "items": items,
        "readonly": True,
        "note": "只读摘要；不写入生产策略权重。",
    }


def build_memory_prefetch_summary(
    history: List[Dict[str, Any]],
    semantic_context: str = "",
    *,
    limit: int = 5,
) -> Optional[Dict[str, Any]]:
    """G8：同标的历史摘要预取；空历史返回 None（不造假）。"""
    hist = history if isinstance(history, list) else []
    sem = (semantic_context or "").strip()
    if not hist and not sem:
        return None
    recent: List[Dict[str, Any]] = []
    for h in hist[: max(1, limit)]:
        if not isinstance(h, dict):
            continue
        decision = h.get("decision") if isinstance(h.get("decision"), dict) else {}
        recent.append(
            {
                "timestamp": h.get("timestamp"),
                "action": decision.get("action"),
                "confidence": decision.get("confidence"),
                "reasoning": (str(decision.get("reasoning") or "")[:200] or None),
            }
        )
    out: Dict[str, Any] = {
        "history_count": len(hist),
        "recent": recent,
        "semantic_context": sem or None,
        "empty": False,
    }
    return out
