"""
Input: 策略演进 Agent 单元测试 - StrategyEvolver
Output: 验证 evolve_strategy 快乐路径 / 落盘 / LLM 失败 / 历史不足早返
Pos: tests/backend/unit/test_agent_evolver.py - BE-02c2 子任务

[BE-02c2 2026-05-17 +08:00]
- 快乐路径：reflections -> 新策略并落盘 data/agent_strategies/<code>_strategy.json
- 落盘验证 + evolution_count+1
- LLM 失败 -> 保留当前策略，不改文件
- 反思中无 improvements/biases -> 早返 default_strategy
- 无 AI client -> 早返 current_strategy
- 非 JSON 输出 -> _safe_json_parse 兜底
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

import app.agents.strategy_evolver as evolver_mod
from app.agents.strategy_evolver import StrategyEvolver


@pytest.fixture
def isolated_strategy_dir(tmp_path, monkeypatch):
    d = tmp_path / "agent_strategies"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(evolver_mod, "STRATEGY_DIR", str(d))
    return str(d)


def _reflections_with_signals():
    return [
        {"reflection": {"improvements": ["关注宏观利率"], "biases_detected": ["over_confidence"]}},
        {"reflection": {"improvements": ["增加资金面权重"]}},
    ]


# ---------------------------------------------------------------- 1. 快乐路径 + 落盘
def test_evolver_happy_persist(isolated_strategy_dir):
    new_strategy_payload = json.dumps({
        "focus_areas": ["宏观", "资金流"],
        "risk_sensitivity": "high",
        "confidence_threshold": 0.7,
        "analysis_notes": ["警惕过度自信"],
        "weight_adjustments": {
            "technical": 0.25, "fundamental": 0.25,
            "sentiment": 0.2, "capital_flow": 0.3,
        },
    }, ensure_ascii=False)

    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(MagicMock(), None)), \
         patch("app.core.ai_client.get_completion_content",
               return_value=new_strategy_payload):
        ev = StrategyEvolver()
        out = ev.evolve_strategy("600519", _reflections_with_signals())

    assert out["focus_areas"] == ["宏观", "资金流"]
    assert out["evolution_count"] == 1
    assert "last_evolved" in out

    fp = os.path.join(isolated_strategy_dir, "600519_strategy.json")
    assert os.path.exists(fp), f"策略文件未创建: {fp}"
    with open(fp, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["focus_areas"] == ["宏观", "资金流"]


# ---------------------------------------------------------------- 2. LLM 失败 -> 保留当前
def test_evolver_llm_error_returns_current(isolated_strategy_dir):
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(None, "LLM 调用失败")):
        ev = StrategyEvolver()
        out = ev.evolve_strategy("600519", _reflections_with_signals())

    # 走的是 default_strategy 路径(无文件存在)
    assert out["evolution_count"] == 0
    assert "evolution_count" in out
    # 不应落盘
    fp = os.path.join(isolated_strategy_dir, "600519_strategy.json")
    assert not os.path.exists(fp)


# ---------------------------------------------------------------- 3. 无反思信号 -> 早返
def test_evolver_no_signals_early_return(isolated_strategy_dir):
    """reflections 为空 / 无 improvements 与 biases -> 直接返回 current_strategy 不调 LLM"""
    fake_get_client = MagicMock()
    with patch("app.core.ai_client.get_ai_client", fake_get_client):
        ev = StrategyEvolver()
        out = ev.evolve_strategy("600519", [{"reflection": {}}])  # 空 reflection dict

    # 应直接返回 default 策略且未调用 LLM
    assert out["evolution_count"] == 0
    assert out["risk_sensitivity"] == "medium"  # default
    fake_get_client.assert_not_called()


# ---------------------------------------------------------------- 4. 无 AI client -> 早返
def test_evolver_no_ai_client_early_return(isolated_strategy_dir):
    with patch("app.core.ai_client.get_ai_client", return_value=None):
        ev = StrategyEvolver()
        out = ev.evolve_strategy("600519", _reflections_with_signals())

    assert out["evolution_count"] == 0
    # 不落盘
    fp = os.path.join(isolated_strategy_dir, "600519_strategy.json")
    assert not os.path.exists(fp)


# ---------------------------------------------------------------- 5. 非 JSON -> safe_parse 失败保留
def test_evolver_non_json_safe_parse_keeps_current(isolated_strategy_dir):
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(MagicMock(), None)), \
         patch("app.core.ai_client.get_completion_content",
               return_value="完全不是 JSON 的纯文本"):
        ev = StrategyEvolver()
        out = ev.evolve_strategy("600519", _reflections_with_signals())

    assert out["evolution_count"] == 0
    fp = os.path.join(isolated_strategy_dir, "600519_strategy.json")
    assert not os.path.exists(fp)


# ---------------------------------------------------------------- 6. JSON 含 markdown fence
def test_evolver_safe_parse_handles_fence(isolated_strategy_dir):
    fenced = """```json
    {"focus_areas": ["x"], "risk_sensitivity": "low", "confidence_threshold": 0.5, "analysis_notes": [], "weight_adjustments": {"technical": 0.4, "fundamental": 0.2, "sentiment": 0.2, "capital_flow": 0.2}}
    ```"""
    with patch("app.core.ai_client.get_ai_client", return_value=MagicMock()), \
         patch("app.core.ai_client.chat_completion",
               return_value=(MagicMock(), None)), \
         patch("app.core.ai_client.get_completion_content", return_value=fenced):
        ev = StrategyEvolver()
        out = ev.evolve_strategy("600519", _reflections_with_signals())

    assert out["focus_areas"] == ["x"]
    assert out["evolution_count"] == 1


# ---------------------------------------------------------------- 7. get_active_strategy 默认
def test_get_active_strategy_returns_default(isolated_strategy_dir):
    ev = StrategyEvolver()
    s = ev.get_active_strategy("999999")
    assert s["evolution_count"] == 0
    assert s["risk_sensitivity"] == "medium"
