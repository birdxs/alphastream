"""
Input: mock 连续失败的 tool 调用
Output: block/warn/halt 与 execute_tool 挂接断言
Pos: tests/backend/unit/test_tool_guardrails.py — P0-1 工具护栏单测

[NEW-FILE:#20260723-P01]
"""
from __future__ import annotations

import json
import os

import pytest


@pytest.fixture
def block_at_3(monkeypatch):
    monkeypatch.setenv("TOOL_GUARD_EXACT_FAIL_WARN", "2")
    monkeypatch.setenv("TOOL_GUARD_EXACT_FAIL_BLOCK", "3")
    monkeypatch.setenv("TOOL_GUARD_SAME_TOOL_WARN", "10")
    monkeypatch.setenv("TOOL_GUARD_SAME_TOOL_HALT", "20")
    from app.core.tool_guardrails import ToolCallGuardrailController

    return ToolCallGuardrailController(
        exact_failure_warn_after=2,
        exact_failure_block_after=3,
        same_tool_failure_warn_after=10,
        same_tool_failure_halt_after=20,
        correlation_id="test-cid",
    )


class TestSignatureAndFailDetection:
    def test_args_normalization_order_independent(self):
        from app.core.tool_guardrails import ToolCallSignature

        a = ToolCallSignature.from_call("t", {"b": 1, "a": 2})
        b = ToolCallSignature.from_call("t", {"a": 2, "b": 1})
        assert a == b
        assert a.args_hash == b.args_hash

    def test_is_tool_result_failure_markers(self):
        from app.core.tool_guardrails import is_tool_result_failure

        assert is_tool_result_failure("获取数据失败: x") is True
        assert is_tool_result_failure("工具 get_stock_data 执行失败: timeout") is True
        assert is_tool_result_failure("", raised=False) is True
        assert is_tool_result_failure(None) is True
        assert is_tool_result_failure("价格最新收盘 100.5", raised=False) is False


class TestExactFailureBlock:
    def test_third_failure_then_block_fourth(self, block_at_3):
        from app.core.tool_guardrails import format_guardrail_result

        ctrl = block_at_3
        args = {"stock_code": "600519", "market_type": "A"}
        actions = []
        for _ in range(3):
            d = ctrl.before_call("get_stock_data", args)
            assert d.allows_execution
            after = ctrl.after_call(
                "get_stock_data", args, "获取数据失败: network", failed=True
            )
            actions.append(after.action)
        # 第 3 次 after 达 block 阈值
        assert actions[-1] == "block"
        # 第 4 次 before 拦截
        blocked = ctrl.before_call("get_stock_data", args)
        assert blocked.action == "block"
        assert blocked.should_halt_turn
        payload = json.loads(format_guardrail_result(blocked))
        assert payload["guardrail"] == "block"
        assert payload["code"] == "repeated_exact_failure_block"
        assert payload["data"] is None
        assert payload["degraded"] is True
        # 铁律 #1：无假金融数
        assert "price" not in payload
        assert "ma5" not in json.dumps(payload).lower()

    def test_warn_on_second_failure(self, block_at_3):
        ctrl = block_at_3
        args = {"stock_code": "000001"}
        ctrl.before_call("get_stock_data", args)
        a1 = ctrl.after_call("get_stock_data", args, "执行失败: e1", failed=True)
        assert a1.action == "allow"
        ctrl.before_call("get_stock_data", args)
        a2 = ctrl.after_call("get_stock_data", args, "执行失败: e2", failed=True)
        assert a2.action == "warn"
        assert a2.code == "repeated_exact_failure_warning"

    def test_success_resets_exact_count(self, block_at_3):
        ctrl = block_at_3
        args = {"stock_code": "600519"}
        for _ in range(2):
            ctrl.before_call("get_stock_data", args)
            ctrl.after_call("get_stock_data", args, "执行失败: x", failed=True)
        ctrl.before_call("get_stock_data", args)
        ok = ctrl.after_call(
            "get_stock_data", args, "date,close\n2026-01-01,100", failed=False
        )
        assert ok.action == "allow"
        # 再失败一次不应直接 block
        ctrl.before_call("get_stock_data", args)
        again = ctrl.after_call("get_stock_data", args, "执行失败: y", failed=True)
        assert again.action == "allow"
        assert again.count == 1

    def test_different_args_not_blocked_together(self, block_at_3):
        ctrl = block_at_3
        for code in ("600519", "600519", "600519"):
            args = {"stock_code": code}
            ctrl.before_call("get_stock_data", args)
            ctrl.after_call("get_stock_data", args, "执行失败: z", failed=True)
        # 不同参数独立计数
        other = {"stock_code": "000001"}
        d = ctrl.before_call("get_stock_data", other)
        assert d.allows_execution


class TestSameToolHalt:
    def test_same_tool_halt_threshold(self, monkeypatch):
        from app.core.tool_guardrails import ToolCallGuardrailController

        ctrl = ToolCallGuardrailController(
            exact_failure_warn_after=100,
            exact_failure_block_after=100,
            same_tool_failure_warn_after=2,
            same_tool_failure_halt_after=3,
        )
        for i in range(3):
            args = {"stock_code": f"code{i}"}  # 不同 args 走 same_tool 计数
            assert ctrl.before_call("get_stock_data", args).allows_execution
            after = ctrl.after_call(
                "get_stock_data", args, "获取数据失败", failed=True
            )
        assert after.action == "halt"
        blocked = ctrl.before_call("get_stock_data", {"stock_code": "x"})
        assert blocked.action == "halt"


class TestGuardedExecuteAndExecuteTool:
    def test_guarded_execute_blocks_after_n_failures(self, block_at_3):
        from app.core.tool_guardrails import guarded_execute, turn_guardrails

        calls = {"n": 0}

        def failing_executor(name, args):
            calls["n"] += 1
            return "工具 foo 执行失败: boom"

        with turn_guardrails(block_at_3, correlation_id="t1", reset=False):
            args = {"q": 1}
            for _ in range(3):
                out = guarded_execute("foo", args, failing_executor)
                assert "执行失败" in out or "boom" in out
            assert calls["n"] == 3
            blocked = guarded_execute("foo", args, failing_executor)
            payload = json.loads(blocked)
            assert payload["guardrail"] == "block"
            # 不再执行底层
            assert calls["n"] == 3

    def test_execute_tool_honors_turn_guardrails(self, monkeypatch):
        from app.core import tools as tools_mod
        from app.core.tool_guardrails import turn_guardrails, ToolCallGuardrailController

        calls = {"n": 0}

        def fake_raw(name, args):
            calls["n"] += 1
            return f"工具 {name} 执行失败: mock-down"

        monkeypatch.setattr(tools_mod, "_raw_execute_tool", fake_raw)
        ctrl = ToolCallGuardrailController(
            exact_failure_block_after=2,
            exact_failure_warn_after=1,
            same_tool_failure_halt_after=99,
            same_tool_failure_warn_after=99,
        )
        args = {"stock_code": "600519"}
        with turn_guardrails(ctrl, correlation_id="exec", reset=False):
            r1 = tools_mod.execute_tool("get_stock_data", args)
            assert "执行失败" in r1
            r2 = tools_mod.execute_tool("get_stock_data", args)
            assert "执行失败" in r2
            r3 = tools_mod.execute_tool("get_stock_data", args)
            data = json.loads(r3)
            assert data["guardrail"] == "block"
            assert data["data"] is None
            assert calls["n"] == 2  # 第 3 次未进底层

    def test_no_context_bypasses_guard_count(self, monkeypatch):
        from app.core import tools as tools_mod

        calls = {"n": 0}

        def fake_raw(name, args):
            calls["n"] += 1
            return "工具 x 执行失败: z"

        monkeypatch.setattr(tools_mod, "_raw_execute_tool", fake_raw)
        # 无 turn 上下文：每次直调
        for _ in range(5):
            tools_mod.execute_tool("get_stock_data", {"stock_code": "1"})
        assert calls["n"] == 5


class TestEnvThresholds:
    def test_load_from_env(self, monkeypatch):
        monkeypatch.setenv("TOOL_GUARD_EXACT_FAIL_BLOCK", "5")
        monkeypatch.setenv("TOOL_GUARD_EXACT_FAIL_WARN", "4")
        from app.core.tool_guardrails import load_guardrail_thresholds

        th = load_guardrail_thresholds()
        assert th["exact_failure_block_after"] == 5
        assert th["exact_failure_warn_after"] == 4
