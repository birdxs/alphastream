"""
Input: 反思学习 Agent 单元测试 - ReflectionAgent
Output: 验证 reflect 快乐路径 / 落盘 JSON / fallback / 多次追加
Pos: tests/backend/unit/test_agent_reflection.py - BE-02c2 子任务

[BE-02c2 2026-05-17 +08:00]
- 快乐路径：传 final_state -> 返回 execution_log 且本地落盘
- 落盘文件：data/agent_reflections/<code>_reflections.json 被创建
- LLM 失败 -> reflection={'error':...} 仍然落盘
- 多次反思追加(不覆盖)：第二次调用后 data 长度 = 2
- get_past_reflections 读路径
"""
from __future__ import annotations

import sys as _sys
import types as _types
if "app.core.tools" not in _sys.modules:
    _stub = _types.ModuleType("app.core.tools")
    for _k in ("TECHNICAL_TOOLS_SCHEMA", "FUNDAMENTAL_TOOLS_SCHEMA",
              "CAPITAL_FLOW_TOOLS_SCHEMA", "SENTIMENT_TOOLS_SCHEMA",
              "RISK_TOOLS_SCHEMA", "STOCK_ANALYSIS_TOOLS_SCHEMA"):
        setattr(_stub, _k, [])
    _sys.modules["app.core.tools"] = _stub

import json
import os
from unittest.mock import patch, MagicMock

import pytest

import app.agents.reflection as reflection_mod
from app.agents.reflection import ReflectionAgent


@pytest.fixture
def isolated_reflection_dir(tmp_path, monkeypatch):
    d = tmp_path / "agent_reflections"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(reflection_mod, "REFLECTION_DIR", str(d))
    return str(d)


def _make_state():
    return {
        "stock_code": "600519",
        "final_decision": {
            "action": "BUY",
            "confidence": 0.8,
            "reasoning": "估值合理 + 趋势向上",
        },
        "errors": [],
    }


def _fake_memory():
    mem = MagicMock()
    mem.get_history.return_value = []
    return mem


# ---------------------------------------------------------------- 1. 快乐路径 + 落盘
def test_reflection_happy_and_persist(isolated_reflection_dir):
    state = _make_state()
    llm_payload = json.dumps({
        "consistency": "与历史一致",
        "information_gaps": ["macro_data"],
        "biases_detected": ["over_confidence"],
        "improvements": ["关注宏观利率"],
        "strategy_evolution": "增加宏观维度",
    }, ensure_ascii=False)

    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(MagicMock(), None)), \
         patch("app.core.ai_client.get_completion_content",
               return_value=llm_payload), \
         patch("app.core.agent_memory.get_agent_memory", return_value=_fake_memory()):
        out = ReflectionAgent.reflect(state)

    assert any(log.get("status") == "success" for log in out["execution_log"])

    # 落盘验证
    fp = os.path.join(isolated_reflection_dir, "600519_reflections.json")
    assert os.path.exists(fp), f"反思文件未创建: {fp}"
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list) and len(data) == 1
    assert data[0]["reflection"]["consistency"] == "与历史一致"


# ---------------------------------------------------------------- 2. LLM 失败 -> reflection={'error':...}
def test_reflection_llm_error_still_persists(isolated_reflection_dir):
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(None, "LLM 失败信息")), \
         patch("app.core.agent_memory.get_agent_memory", return_value=_fake_memory()):
        out = ReflectionAgent.reflect(state)

    assert "execution_log" in out
    fp = os.path.join(isolated_reflection_dir, "600519_reflections.json")
    assert os.path.exists(fp)
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)
    assert data[-1]["reflection"]["error"] == "LLM 失败信息"


# ---------------------------------------------------------------- 3. AI 服务不可用
def test_reflection_no_ai_client_skipped(isolated_reflection_dir):
    state = _make_state()
    with patch("app.core.ai_client.get_ai_client", return_value=None), \
         patch("app.core.agent_memory.get_agent_memory", return_value=_fake_memory()):
        out = ReflectionAgent.reflect(state)

    # 跳过状态
    assert any(log.get("status") == "skipped" for log in out["execution_log"])
    # 此分支不落盘
    fp = os.path.join(isolated_reflection_dir, "600519_reflections.json")
    assert not os.path.exists(fp)


# ---------------------------------------------------------------- 4. 多次追加（不覆盖）
def test_reflection_appends_multiple(isolated_reflection_dir):
    state = _make_state()
    payload = json.dumps({"consistency": "OK", "improvements": ["x"]}, ensure_ascii=False)

    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(MagicMock(), None)), \
         patch("app.core.ai_client.get_completion_content", return_value=payload), \
         patch("app.core.agent_memory.get_agent_memory", return_value=_fake_memory()):
        ReflectionAgent.reflect(state)
        ReflectionAgent.reflect(state)
        ReflectionAgent.reflect(state)

    fp = os.path.join(isolated_reflection_dir, "600519_reflections.json")
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 3, f"应追加 3 条, 实际 {len(data)}"


# ---------------------------------------------------------------- 5. get_past_reflections
def test_get_past_reflections_reads(isolated_reflection_dir):
    fp = os.path.join(isolated_reflection_dir, "600519_reflections.json")
    seed = [
        {"timestamp": "2026-05-17 10:00:00", "reflection": {"improvements": ["a", "b"]}},
        {"timestamp": "2026-05-17 11:00:00", "reflection": {"improvements": ["c"]}},
    ]
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(seed, f, ensure_ascii=False)

    out = ReflectionAgent.get_past_reflections("600519", limit=1)
    assert len(out) == 1
    assert out[0]["reflection"]["improvements"] == ["c"]
