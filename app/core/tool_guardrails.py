"""
Input: 工具名 + 归一化参数 + 调用成败；env 阈值
Output: allow|warn|block|halt 决策与结构化护栏结果（无金融假数）
Pos: app/core/tool_guardrails.py — turn 级工具调用护栏（P0-1），挂 tools.execute_tool / FC 循环

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

[NEW-FILE:#20260723-P01] Dojo ToolCallGuardrailController 语义重写；不依赖 dojoagents。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Optional

logger = logging.getLogger(__name__)

# --- env 阈值（可配置；与 FallbackManager 超时无关，管的是 LLM 重复 call 层）---
def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return default


def load_guardrail_thresholds() -> Dict[str, int]:
    return {
        "exact_failure_warn_after": _env_int("TOOL_GUARD_EXACT_FAIL_WARN", 2),
        "exact_failure_block_after": _env_int("TOOL_GUARD_EXACT_FAIL_BLOCK", 3),
        "same_tool_failure_warn_after": _env_int("TOOL_GUARD_SAME_TOOL_WARN", 3),
        "same_tool_failure_halt_after": _env_int("TOOL_GUARD_SAME_TOOL_HALT", 8),
    }


# 读多写少类工具名（本仓 OpenAI tools）；成功同结果可触发 no-progress 警告（P0 仅计数，不造假数）
IDEMPOTENT_READ_TOOLS = frozenset(
    {
        "get_stock_data",
        "get_technical_indicators",
        "get_fundamental_data",
        "get_capital_flow",
        "get_stock_news",
        "search_web",
        "get_risk_assessment",
    }
)

# 结果串失败启发：execute_tool / 各 @tool 返回的中文失败前缀（不含任何假行情）
_FAILURE_MARKERS = (
    "执行失败",
    "获取数据失败",
    "工具执行异常",
    "未知工具",
    "分析失败",
    "查询失败",
    "未获取到",
    "error",
    "Error",
    "Exception",
    "Timeout",
    "超时",
)


@dataclass(frozen=True)
class ToolCallSignature:
    tool_name: str
    args_hash: str

    @classmethod
    def from_call(cls, tool_name: str, args: Optional[Mapping[str, Any]]) -> "ToolCallSignature":
        canonical = json.dumps(
            dict(args or {}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        args_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(tool_name=str(tool_name or ""), args_hash=args_hash)


@dataclass(frozen=True)
class ToolGuardrailDecision:
    """护栏决策。action: allow | warn | block | halt"""

    action: str = "allow"
    code: str = "allow"
    message: str = ""
    tool_name: str = ""
    count: int = 0
    signature: Optional[ToolCallSignature] = None
    correlation_id: str = ""

    @property
    def allows_execution(self) -> bool:
        return self.action in ("allow", "warn")

    @property
    def should_halt_turn(self) -> bool:
        """block/halt 均停止再执行该签名/进一步同一失败路径。"""
        return self.action in ("block", "halt")


class ToolCallGuardrailController:
    """Turn 级同签名失败风暴护栏。

    规则（after 记数，before 拦截）：
    - 同 tool + 归一化 args 连续失败 ≥ block 阈值 → block
    - 同 tool（任意 args）失败 ≥ halt 阈值 → halt
    - 中途 warn 不阻断执行，结果旁注给 LLM
    """

    def __init__(
        self,
        exact_failure_warn_after: Optional[int] = None,
        exact_failure_block_after: Optional[int] = None,
        same_tool_failure_warn_after: Optional[int] = None,
        same_tool_failure_halt_after: Optional[int] = None,
        correlation_id: str = "",
    ):
        th = load_guardrail_thresholds()
        self.exact_failure_warn_after = exact_failure_warn_after or th["exact_failure_warn_after"]
        self.exact_failure_block_after = exact_failure_block_after or th["exact_failure_block_after"]
        self.same_tool_failure_warn_after = (
            same_tool_failure_warn_after or th["same_tool_failure_warn_after"]
        )
        self.same_tool_failure_halt_after = (
            same_tool_failure_halt_after or th["same_tool_failure_halt_after"]
        )
        # 保证 block/halt ≥ warn
        if self.exact_failure_block_after < self.exact_failure_warn_after:
            self.exact_failure_block_after = self.exact_failure_warn_after
        if self.same_tool_failure_halt_after < self.same_tool_failure_warn_after:
            self.same_tool_failure_halt_after = self.same_tool_failure_warn_after

        self.correlation_id = correlation_id or ""
        self._exact_failure_counts: Dict[ToolCallSignature, int] = {}
        self._same_tool_failure_counts: Dict[str, int] = {}
        self._halt_decision: Optional[ToolGuardrailDecision] = None
        self._last_decision: Optional[ToolGuardrailDecision] = None

    def reset_for_turn(self, correlation_id: str = "") -> None:
        self._exact_failure_counts.clear()
        self._same_tool_failure_counts.clear()
        self._halt_decision = None
        self._last_decision = None
        if correlation_id:
            self.correlation_id = correlation_id

    @property
    def halt_decision(self) -> Optional[ToolGuardrailDecision]:
        return self._halt_decision

    def before_call(
        self, tool_name: str, args: Optional[Mapping[str, Any]]
    ) -> ToolGuardrailDecision:
        signature = ToolCallSignature.from_call(tool_name, args)

        if self._halt_decision is not None and self._halt_decision.action == "halt":
            d = ToolGuardrailDecision(
                action="halt",
                code=self._halt_decision.code or "turn_already_halted",
                message=self._halt_decision.message
                or "本 turn 已因工具失败风暴中止，拒绝继续执行工具。",
                tool_name=tool_name,
                count=self._halt_decision.count,
                signature=signature,
                correlation_id=self.correlation_id,
            )
            self._last_decision = d
            logger.warning(
                "tool_guardrail halt-skip tool=%s cid=%s code=%s",
                tool_name,
                self.correlation_id,
                d.code,
            )
            return d

        exact_count = self._exact_failure_counts.get(signature, 0)
        if exact_count >= self.exact_failure_block_after:
            d = ToolGuardrailDecision(
                action="block",
                code="repeated_exact_failure_block",
                message=(
                    f"护栏拦截 {tool_name}：相同参数已连续失败 {exact_count} 次。"
                    "请勿原样重试；改策略、换参数或向用户说明数据不可用（不得编造行情）。"
                ),
                tool_name=tool_name,
                count=exact_count,
                signature=signature,
                correlation_id=self.correlation_id,
            )
            self._halt_decision = d
            self._last_decision = d
            logger.warning(
                "tool_guardrail block tool=%s count=%s cid=%s sig=%s",
                tool_name,
                exact_count,
                self.correlation_id,
                signature.args_hash[:12],
            )
            return d

        same_count = self._same_tool_failure_counts.get(tool_name, 0)
        if same_count >= self.same_tool_failure_halt_after:
            d = ToolGuardrailDecision(
                action="halt",
                code="same_tool_failure_halt",
                message=(
                    f"护栏中止：工具 {tool_name} 本 turn 已失败 {same_count} 次。"
                    "停止继续调用该工具路径。"
                ),
                tool_name=tool_name,
                count=same_count,
                signature=signature,
                correlation_id=self.correlation_id,
            )
            self._halt_decision = d
            self._last_decision = d
            logger.warning(
                "tool_guardrail halt tool=%s count=%s cid=%s",
                tool_name,
                same_count,
                self.correlation_id,
            )
            return d

        d = ToolGuardrailDecision(
            tool_name=tool_name,
            signature=signature,
            correlation_id=self.correlation_id,
        )
        self._last_decision = d
        return d

    def after_call(
        self,
        tool_name: str,
        args: Optional[Mapping[str, Any]],
        result: Optional[str],
        failed: bool,
    ) -> ToolGuardrailDecision:
        signature = ToolCallSignature.from_call(tool_name, args)

        if failed:
            exact_count = self._exact_failure_counts.get(signature, 0) + 1
            self._exact_failure_counts[signature] = exact_count
            same_count = self._same_tool_failure_counts.get(tool_name, 0) + 1
            self._same_tool_failure_counts[tool_name] = same_count

            if same_count >= self.same_tool_failure_halt_after:
                d = ToolGuardrailDecision(
                    action="halt",
                    code="same_tool_failure_halt",
                    message=(
                        f"护栏中止：工具 {tool_name} 本 turn 已失败 {same_count} 次。"
                        "停止继续调用该工具路径；勿用假数据填补。"
                    ),
                    tool_name=tool_name,
                    count=same_count,
                    signature=signature,
                    correlation_id=self.correlation_id,
                )
                self._halt_decision = d
                self._last_decision = d
                return d

            if exact_count >= self.exact_failure_block_after:
                d = ToolGuardrailDecision(
                    action="block",
                    code="repeated_exact_failure_block",
                    message=(
                        f"护栏将拦截后续相同调用：{tool_name} 相同参数已失败 {exact_count} 次。"
                    ),
                    tool_name=tool_name,
                    count=exact_count,
                    signature=signature,
                    correlation_id=self.correlation_id,
                )
                self._halt_decision = d
                self._last_decision = d
                return d

            if exact_count >= self.exact_failure_warn_after:
                d = ToolGuardrailDecision(
                    action="warn",
                    code="repeated_exact_failure_warning",
                    message=(
                        f"{tool_name} 已用相同参数失败 {exact_count} 次，疑似死循环；"
                        "请改策略而非原样重试。"
                    ),
                    tool_name=tool_name,
                    count=exact_count,
                    signature=signature,
                    correlation_id=self.correlation_id,
                )
                self._last_decision = d
                return d

            if same_count >= self.same_tool_failure_warn_after:
                d = ToolGuardrailDecision(
                    action="warn",
                    code="same_tool_failure_warning",
                    message=(
                        f"{tool_name} 本 turn 已失败 {same_count} 次；"
                        "继续用工具但需先诊断，勿改用编造数据回答。"
                    ),
                    tool_name=tool_name,
                    count=same_count,
                    signature=signature,
                    correlation_id=self.correlation_id,
                )
                self._last_decision = d
                return d

            d = ToolGuardrailDecision(
                tool_name=tool_name,
                count=exact_count,
                signature=signature,
                correlation_id=self.correlation_id,
            )
            self._last_decision = d
            return d

        # 成功：清零该签名与该 tool 失败计数
        self._exact_failure_counts.pop(signature, None)
        self._same_tool_failure_counts.pop(tool_name, None)
        d = ToolGuardrailDecision(
            tool_name=tool_name,
            signature=signature,
            correlation_id=self.correlation_id,
        )
        self._last_decision = d
        return d


# --- ContextVar：按 turn/请求绑定控制器 ---
_current_guardrails: ContextVar[Optional[ToolCallGuardrailController]] = ContextVar(
    "stockanal_tool_guardrails", default=None
)


def get_turn_guardrails() -> Optional[ToolCallGuardrailController]:
    return _current_guardrails.get()


def set_turn_guardrails(controller: Optional[ToolCallGuardrailController]) -> None:
    _current_guardrails.set(controller)


@contextmanager
def turn_guardrails(
    controller: Optional[ToolCallGuardrailController] = None,
    *,
    correlation_id: str = "",
    reset: bool = True,
) -> Iterator[ToolCallGuardrailController]:
    """绑定 turn 级护栏；退出后恢复上一绑定。"""
    ctrl = controller or ToolCallGuardrailController(correlation_id=correlation_id)
    if reset:
        ctrl.reset_for_turn(correlation_id=correlation_id or ctrl.correlation_id)
    elif correlation_id:
        ctrl.correlation_id = correlation_id
    token = _current_guardrails.set(ctrl)
    try:
        yield ctrl
    finally:
        _current_guardrails.reset(token)


def is_tool_result_failure(result: Optional[str], *, raised: bool = False) -> bool:
    """判定工具结果是否为失败（无假数据语义；仅错误/空败路径）。"""
    if raised:
        return True
    if result is None:
        return True
    text = result if isinstance(result, str) else str(result)
    stripped = text.strip()
    if not stripped:
        return True
    # 结构化护栏结果本身不算「执行层新失败」记数，避免二次累加
    if '"guardrail"' in stripped and (
        '"block"' in stripped or '"halt"' in stripped or '"warn"' in stripped
    ):
        try:
            payload = json.loads(stripped)
            if isinstance(payload, dict) and payload.get("guardrail") in (
                "block",
                "halt",
                "warn",
            ):
                # block/halt 合成结果：不计为新一轮业务失败
                if payload.get("guardrail") in ("block", "halt"):
                    return False
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    low = stripped.lower()
    for marker in _FAILURE_MARKERS:
        if marker.lower() in low:
            return True
    return False


def format_guardrail_result(decision: ToolGuardrailDecision) -> str:
    """结构化护栏结果字符串（给 LLM / tool role）；严禁夹带假行情数值。"""
    payload = {
        "error": decision.message or "tool call blocked by guardrail",
        "guardrail": decision.action,  # block | warn | halt | allow
        "code": decision.code,
        "message": decision.message,
        "tool_name": decision.tool_name,
        "count": decision.count,
        "correlation_id": decision.correlation_id or "",
        # 明确告知模型：无数据，禁止补洞
        "data": None,
        "degraded": True,
    }
    return json.dumps(payload, ensure_ascii=False)


def append_guardrail_guidance(result: str, decision: ToolGuardrailDecision) -> str:
    if decision.action not in ("warn", "halt", "block") or not decision.message:
        return result or ""
    label = {
        "warn": "Tool loop warning",
        "block": "Tool loop blocked",
        "halt": "Tool loop hard stop",
    }.get(decision.action, "Tool guardrail")
    suffix = (
        f"\n\n[{label}: {decision.code}; count={decision.count}; {decision.message}]"
    )
    return (result or "") + suffix


def guarded_execute(
    tool_name: str,
    arguments: Optional[Mapping[str, Any]],
    executor,
    *,
    controller: Optional[ToolCallGuardrailController] = None,
) -> str:
    """统一 before → execute → after 护栏包装。

    executor: (tool_name, arguments) -> str  或 无 before 语义的底层调用 callable
    """
    ctrl = controller if controller is not None else get_turn_guardrails()
    args = dict(arguments or {})

    if ctrl is None:
        # 无 turn 上下文：直调，不累计（单测/脚本兼容）
        try:
            out = executor(tool_name, args)
            return out if isinstance(out, str) else str(out)
        except Exception as exc:
            logger.error("tool %s failed without guardrail context: %s", tool_name, exc)
            return f"工具 {tool_name} 执行失败: {exc}"

    decision = ctrl.before_call(tool_name, args)
    if not decision.allows_execution:
        # P0：护栏拦截 → agent.degraded（不造假金融数据）
        try:
            from app.core.event_bus import publish_agent_degraded
            publish_agent_degraded(
                cause='guardrail_block',
                message=(
                    decision.message
                    or f'工具 {tool_name} 被护栏拦截（{decision.action}），未执行取数'
                ),
                level='critical' if decision.action == 'halt' else 'warn',
                source=tool_name,
                correlation_id=getattr(ctrl, 'correlation_id', '') or '',
                extra={
                    'guardrail_action': decision.action,
                    'tool_name': tool_name,
                    'code': decision.code,
                },
            )
        except Exception:
            pass
        return format_guardrail_result(decision)

    raised = False
    result: str = ""
    try:
        out = executor(tool_name, args)
        result = out if isinstance(out, str) else str(out)
    except Exception as exc:
        raised = True
        result = f"工具 {tool_name} 执行失败: {exc}"
        logger.error("tool %s failed: %s", tool_name, exc)
        try:
            from app.core.event_bus import (
                infer_degradation_cause_from_text,
                publish_agent_degraded,
            )
            cause = infer_degradation_cause_from_text(str(exc))
            publish_agent_degraded(
                cause=cause,
                message=result[:500],
                level='warn',
                source=tool_name,
                correlation_id=getattr(ctrl, 'correlation_id', '') or '',
                extra={'tool_name': tool_name, 'raised': True},
            )
        except Exception:
            pass

    failed = is_tool_result_failure(result, raised=raised)
    after = ctrl.after_call(tool_name, args, result, failed=failed)
    if after.action == "warn":
        result = append_guardrail_guidance(result, after)
    elif after.action in ("block", "halt") and failed:
        # 本次已执行且失败达阈：附加 guidance，下次 before 会拦
        result = append_guardrail_guidance(result, after)
        try:
            from app.core.event_bus import (
                infer_degradation_cause_from_text,
                publish_agent_degraded,
            )
            cause = infer_degradation_cause_from_text(result)
            if cause == 'tool_failure' and raised is False:
                # 结果型失败优先 source_degraded（空/无数据），非阻断幻觉
                cause = 'source_degraded'
            publish_agent_degraded(
                cause=cause,
                message=(after.message or result)[:500],
                level='warn',
                source=tool_name,
                correlation_id=getattr(ctrl, 'correlation_id', '') or '',
                extra={
                    'guardrail_action': after.action,
                    'tool_name': tool_name,
                    'failed': True,
                },
            )
        except Exception:
            pass
    elif failed and after.action == "allow":
        # 单次失败但未达阈：仍可发 info 级降级提示（零假数）
        try:
            from app.core.event_bus import (
                infer_degradation_cause_from_text,
                publish_agent_degraded,
            )
            publish_agent_degraded(
                cause=infer_degradation_cause_from_text(result),
                message=result[:500],
                level='info',
                source=tool_name,
                correlation_id=getattr(ctrl, 'correlation_id', '') or '',
                extra={'tool_name': tool_name, 'failed': True, 'threshold_not_reached': True},
            )
        except Exception:
            pass
    return result
