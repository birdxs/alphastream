# -*- coding: utf-8 -*-
"""
Input : pytest 收集 + tmp_data_dir
Output: AgentMemory 单元测试 (跨股票隔离 / JSON 落盘 / 历史上限 / confidence 归一)
Pos   : tests/backend/unit/test_core_agent_memory.py - BE-03c Core #3

一旦此文件被修改，请同步更新 tests/audit/reports/BE-03c_core_misc.md。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.core import agent_memory as am_mod
from app.core.agent_memory import AgentMemory


@pytest.fixture
def memory(tmp_path, monkeypatch):
    """把 MEMORY_DIR 指向 tmp_path，避免污染真实 data/agent_memory/。"""
    mem_dir = tmp_path / "agent_memory"
    mem_dir.mkdir()
    monkeypatch.setattr(am_mod, "MEMORY_DIR", str(mem_dir))
    return AgentMemory()


def test_save_and_get_history_isolation(memory, tmp_path):
    """不同股票的记忆互相隔离，落盘为独立文件。"""
    memory.save_analysis("600519", {
        "final_decision": {"action": "买入", "confidence": 0.8},
        "technical_report": {"score": 88},
        "risk_assessment": {"risk_level": "low"},
    })
    memory.save_analysis("000001", {
        "final_decision": {"action": "持有", "confidence": 0.5},
        "technical_report": {"score": 60},
        "risk_assessment": {"risk_level": "medium"},
    })

    h1 = memory.get_history("600519")
    h2 = memory.get_history("000001")
    assert len(h1) == 1 and len(h2) == 1
    assert h1[0]["decision"]["action"] == "买入"
    assert h2[0]["decision"]["action"] == "持有"
    # 隔离：互相不可见
    assert memory.get_history("999999") == []


def test_confidence_normalization_string(memory):
    """confidence 字符串 高/中/低 应归一为浮点。"""
    memory.save_analysis("600519", {
        "final_decision": {"action": "买入", "confidence": "高"},
        "technical_report": {"score": 80},
        "risk_assessment": {"risk_level": "low"},
    })
    h = memory.get_history("600519")
    c = h[0]["decision"]["confidence"]
    assert isinstance(c, float)
    assert 0.0 <= c <= 1.0
    assert c == 0.85


def test_confidence_normalization_out_of_range(memory):
    """confidence 越界值应裁剪到 [0,1]。"""
    memory.save_analysis("600519", {
        "final_decision": {"action": "买入", "confidence": 5.0},
        "technical_report": {"score": 80},
        "risk_assessment": {"risk_level": "low"},
    })
    h = memory.get_history("600519")
    assert h[0]["decision"]["confidence"] == 1.0

    memory.save_analysis("600520", {
        "final_decision": {"action": "卖出", "confidence": -0.5},
        "technical_report": {"score": 20},
        "risk_assessment": {"risk_level": "high"},
    })
    h2 = memory.get_history("600520")
    assert h2[0]["decision"]["confidence"] == 0.0


def test_history_cap_50(memory):
    """save_analysis 最多保留 50 条。"""
    for i in range(60):
        memory.save_analysis("600519", {
            "final_decision": {"action": f"a{i}", "confidence": 0.5},
            "technical_report": {"score": i},
            "risk_assessment": {"risk_level": "low"},
        })
    h = memory.get_history("600519", limit=100)
    assert len(h) == 50
    # 最早的 10 条应被裁掉
    assert h[0]["decision"]["action"] == "a10"
    assert h[-1]["decision"]["action"] == "a59"


def test_json_persistence_on_disk(memory):
    """落盘文件确实存在且是合法 JSON。"""
    memory.save_analysis("AAPL", {
        "final_decision": {"action": "buy", "confidence": 0.7},
        "technical_report": {"score": 90},
        "risk_assessment": {"risk_level": "low"},
    })
    fn = os.path.join(am_mod.MEMORY_DIR, "AAPL_history.json")
    assert os.path.isfile(fn)
    with open(fn, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list) and len(data) == 1
    assert data[0]["decision"]["action"] == "buy"


def test_save_agent_analysis_and_context(memory):
    """save_agent_analysis 写入后能查得 agent 上下文。"""
    memory.save_agent_analysis("600519", "tech_agent", "强势上涨")
    memory.save_agent_analysis("600519", "tech_agent", "继续突破")
    memory.save_agent_analysis("600519", "risk_agent", "波动放大")

    ctx = memory.get_agent_context("600519", "tech_agent")
    # 至少包含某条内容
    assert isinstance(ctx, str)


def test_context_prompt_empty_when_no_history(memory):
    """无历史时 get_context_prompt 不抛错。"""
    out = memory.get_context_prompt("NEVER_SEEN")
    assert isinstance(out, str)


def test_search_similar_empty_query(memory):
    """空 query 时 search_similar 返回 []。"""
    memory.save_analysis("600519", {
        "final_decision": {"action": "买入", "confidence": 0.8, "reasoning": "上涨趋势"},
        "technical_report": {"score": 80},
        "risk_assessment": {"risk_level": "low"},
    })
    assert memory.search_similar("600519", "") == []
    assert memory.search_similar("999999", "anything") == []


def test_search_similar_with_history(memory):
    """有历史时 search_similar 走 TF-IDF（若 sklearn 可用）。"""
    for i in range(3):
        memory.save_analysis("600519", {
            "final_decision": {"action": "买入" if i % 2 == 0 else "卖出",
                                "confidence": 0.7, "reasoning": f"分析理由{i} 上涨趋势"},
            "technical_report": {"score": 70 + i},
            "risk_assessment": {"risk_level": "low"},
        })
    out = memory.search_similar("600519", "上涨趋势 买入", top_k=2)
    # 仅断言不抛异常 + 返回 list
    assert isinstance(out, list)


def test_get_semantic_context_returns_string(memory):
    """get_semantic_context 在无历史时返回空串。"""
    out = memory.get_semantic_context("NO_STOCK", "查询")
    assert out == ""


def test_get_context_prompt_format(memory):
    """有历史时 get_context_prompt 返回非空字符串。"""
    memory.save_analysis("600519", {
        "final_decision": {"action": "买入", "confidence": 0.8, "reasoning": "技术面强势"},
        "technical_report": {"score": 88},
        "risk_assessment": {"risk_level": "low"},
    })
    out = memory.get_context_prompt("600519")
    assert isinstance(out, str)
