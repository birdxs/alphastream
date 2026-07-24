"""
Input: scorecard 纯函数固定样例
Output: pytest 断言 data_coverage / tool_success_rate / role_agreement / confidence_cap / memo / reflection / memory
Pos: tests/backend/unit/test_agent_scorecard.py - G5+G6+G7+G8 unit

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
from __future__ import annotations

import json

import pytest

from app.agents.scorecard import (
    build_decision_memo,
    build_memory_prefetch_summary,
    compute_data_coverage,
    compute_role_agreement,
    compute_run_scorecard,
    compute_tool_success_rate,
    extract_confidence_cap,
    summarize_reflection_readonly,
)


def test_data_coverage_full_and_empty():
    empty = compute_data_coverage({})
    assert empty == 0.0
    full = {
        "technical_report": {"ma": 1},
        "fundamental_report": "ok",
        "capital_flow_report": {"net": 1},
        "sentiment_report": "中性",
        "bull_case": "看多",
        "bear_case": "看空",
    }
    assert compute_data_coverage(full) == 1.0
    half = {
        "technical_report": "x",
        "fundamental_report": "y",
        "capital_flow_report": None,
        "sentiment_report": "",
        "bull_case": None,
        "bear_case": "  ",
    }
    # 2/6
    assert abs(compute_data_coverage(half) - (2 / 6)) < 1e-6


def test_tool_success_rate_from_execution_log():
    state = {
        "execution_log": [
            {"status": "success"},
            {"status": "failed"},
            {"status": "ok"},
            {"status": "timeout"},
        ]
    }
    # 2 success / 4
    assert abs(compute_tool_success_rate(state) - 0.5) < 1e-6
    # 无日志 → 1.0（未知≠失败）
    assert compute_tool_success_rate({}) == 1.0


def test_role_agreement_majority_and_neutral():
    # bull/bear 对立 → 不应 1.0；含 final HOLD 多数可变化
    state = {
        "bull_case": "强烈看多 BUY",
        "bear_case": "建议 SELL 离场",
        "technical_report": "持有 HOLD",
        "final_decision": {"action": "HOLD"},
    }
    ra = compute_role_agreement(state)
    assert 0.0 <= ra <= 1.0
    # 全部一致 BUY
    state2 = {
        "bull_case": "BUY 买入",
        "technical_report": "买入 BUY",
        "final_decision": {"action": "BUY"},
    }
    assert abs(compute_role_agreement(state2) - 1.0) < 1e-6
    # 样本不足 → 0.5
    assert compute_role_agreement({"bull_case": "BUY"}) == 0.5


def test_confidence_cap_tightest():
    state = {
        "confidence_cap": 0.8,
        "final_decision": {"confidence_cap": 0.6},
        "degradations": [{"confidence_cap": 0.45, "message": "timeout"}],
    }
    assert extract_confidence_cap(state) == 0.45
    assert extract_confidence_cap({}) is None


def test_compute_run_scorecard_fixed_fixture():
    state = {
        "stock_code": "600519",
        "technical_report": {"ok": True},
        "fundamental_report": {"ok": True},
        "capital_flow_report": {"ok": True},
        "sentiment_report": "中性",
        "bull_case": "买入 BUY",
        "bear_case": "谨慎 HOLD",
        "execution_log": [
            {"status": "success"},
            {"status": "success"},
            {"status": "failed"},
        ],
        "degradations": [{"cause": "timeout", "message": "timeout", "confidence_cap": 0.5}],
        "confidence_cap": 0.5,
        "final_decision": {"action": "HOLD", "confidence": 0.7, "reasoning": "综合观望"},
    }
    sc = compute_run_scorecard(state, task_id="t1", stock_code="600519")
    assert sc["event_type"] == "run.scorecard"
    assert sc["task_id"] == "t1"
    assert sc["stock_code"] == "600519"
    assert sc["data_coverage"] == 1.0
    assert abs(sc["tool_success_rate"] - (2 / 3)) < 1e-3
    assert 0.0 <= sc["role_agreement"] <= 1.0
    assert sc["confidence_cap"] == 0.5
    assert "price" not in sc  # 无假行情
    assert "evidence" in sc
    assert sc["evidence"]["degradation_count"] == 1


def test_decision_memo_evidence_and_veto_no_fake_numbers():
    state = {
        "stock_code": "000001",
        "final_decision": {
            "action": "SELL",
            "confidence": 0.4,
            "reasoning": "风险偏高",
            "approved": False,
            "risk_level": "高",
        },
        "hitl": {"required": True, "approved": False, "reason": "用户拒绝"},
        "hitl_rejected": True,
        "technical_report": "偏空",
        "fundamental_report": None,
        "degradations": [{"cause": "network", "message": "上游断连"}],
        "scorecard": {
            "data_coverage": 0.5,
            "tool_success_rate": 1.0,
            "role_agreement": 0.5,
            "confidence_cap": 0.4,
        },
    }
    memo = build_decision_memo(state)
    assert memo["action"] == "SELL"
    assert memo["confidence"] == 0.4
    assert any("HITL" in r for r in memo["veto_reasons"])
    assert any("风险" in r or "高" in r for r in memo["veto_reasons"])
    slots = {e["slot"]: e["status"] for e in memo["evidence_pointers"]}
    assert slots["technical_report"] == "present"
    assert slots["fundamental_report"] == "missing"
    # 不合成价量
    assert "last_price" not in memo
    assert memo["disclaimer"]
    # G1 对齐：空 provenance → 空列表（不造假源）
    assert isinstance(memo.get("provenance"), list)
    assert memo["provenance"] == []


def test_decision_memo_includes_provenance_from_state_and_fd():
    """decision_memo.provenance 与 state/final_decision 摘要对齐（去重、无假行情）。"""
    state = {
        "stock_code": "600519",
        "final_decision": {
            "action": "BUY",
            "confidence": 0.7,
            "provenance": [
                {"source": "akshare", "tool": "kline", "digest": "abc12345"},
                {"source": "akshare", "tool": "kline", "digest": "abc12345"},  # 重复应去
            ],
        },
        "provenance": [
            {"source": "sina", "tool": "indices", "digest": "def67890"},
            {"source": "", "tool": ""},  # 空源跳过
        ],
        "technical_report": {"summary": "ok"},
        "fundamental_report": None,
        "hitl": {"required": False},
        "risk_assessment": {},
        "degradations": [],
        "scorecard": {
            "data_coverage": 0.5,
            "tool_success_rate": 1.0,
            "role_agreement": 0.8,
            "confidence_cap": 0.9,
        },
    }
    memo = build_decision_memo(state)
    assert memo["action"] == "BUY"
    prov = memo.get("provenance")
    assert isinstance(prov, list)
    assert len(prov) == 2
    sources = {p.get("source") for p in prov}
    assert sources == {"akshare", "sina"}
    for p in prov:
        assert p.get("source")
        assert "last_price" not in p
        assert "price" not in p


def test_decision_memo_provenance_items_are_structured_dicts():
    """provenance 数组元素必须是 dict 结构（source/tool/digest），非裸字符串。"""
    state = {
        "stock_code": "000001",
        "final_decision": {
            "action": "HOLD",
            "confidence": 0.5,
            "provenance": [
                {"source": "wind", "tool": "fundamentals", "digest": "w1nddead"},
                "legacy-string-should-skip",
                {"source": "akshare", "tool": "quote", "digest": "ak000001"},
                {"source": "", "tool": "skip"},
            ],
        },
        "provenance": [
            {"source": "sina", "tool": "news", "digest": "sn123456"},
            None,
            42,
        ],
        "technical_report": {"summary": "neutral"},
        "fundamental_report": None,
        "hitl": {"required": False},
        "risk_assessment": {},
        "degradations": [],
        "scorecard": {
            "data_coverage": 0.4,
            "tool_success_rate": 0.9,
            "role_agreement": 0.5,
            "confidence_cap": 0.5,
        },
    }
    memo = build_decision_memo(state)
    prov = memo.get("provenance")
    assert isinstance(prov, list)
    assert len(prov) >= 2
    for item in prov:
        assert isinstance(item, dict), f"expected dict, got {type(item)}: {item!r}"
        assert item.get("source"), f"missing source: {item!r}"
        # 空 source 的 tool-only 项应被 collector 丢弃；禁止假行情字段
        assert "last_price" not in item
        assert "price" not in item
        assert "pe" not in item
    sources = {p.get("source") for p in prov}
    assert "wind" in sources
    assert "akshare" in sources
    assert "sina" in sources
    # tool-only / 非 dict 不入库
    assert all(isinstance(p, dict) and p.get("source") for p in prov)


def test_reflection_summary_empty_is_none():
    assert summarize_reflection_readonly([]) is None
    assert summarize_reflection_readonly(None) is None  # type: ignore[arg-type]
    rs = summarize_reflection_readonly(
        [
            {
                "timestamp": "2026-07-01T00:00:00+08:00",
                "accuracy_score": 0.6,
                "lessons_learned": "注意仓位",
                "what_went_well": "情绪判断",
                "what_went_wrong": "忽略资金流",
            }
        ]
    )
    assert rs is not None
    assert rs["readonly"] is True
    assert rs["count"] == 1
    assert "生产" in (rs.get("note") or "") or "权重" in (rs.get("note") or "")
    assert rs["items"][0]["lessons"] == "注意仓位"


def test_memory_prefetch_empty_is_none():
    assert build_memory_prefetch_summary([], "") is None
    assert build_memory_prefetch_summary([], "   ") is None
    mem = build_memory_prefetch_summary(
        [
            {
                "timestamp": "2026-07-01",
                "decision": {"action": "BUY", "confidence": 0.6, "reasoning": "趋势向上"},
            }
        ],
        "近半年以震荡为主",
    )
    assert mem is not None
    assert mem["history_count"] == 1
    assert mem["recent"][0]["action"] == "BUY"
    assert mem["semantic_context"] == "近半年以震荡为主"


def test_publish_run_scorecard_event_smoke(monkeypatch):
    from app.core import event_bus as eb

    published = []

    class _Bus:
        def publish(self, event_type, payload):
            published.append((event_type, payload))

    monkeypatch.setattr(eb, "get_event_bus", lambda: _Bus())
    sc = compute_run_scorecard(
        {
            "technical_report": "x",
            "execution_log": [{"status": "success"}],
            "final_decision": {"action": "HOLD"},
        },
        task_id="tid",
        stock_code="600519",
    )
    out = eb.publish_run_scorecard(sc, task_id="tid", stock_code="600519")
    assert out["event_type"] == eb.EVENT_RUN_SCORECARD
    assert published and published[0][0] == eb.EVENT_RUN_SCORECARD
    assert published[0][1]["data_coverage"] is not None



def test_g12_degraded_fixture_no_fake_price_digits():
    """G12：agent.degraded + confidence_cap 夹具不得携带假价数字进入 scorecard memo。

    铁律 #1：降级态不把 point-in-time 假价写入可展示决策字段。
    """
    from app.core import event_bus as eb

    degradations = [
        {
            "level": "partial",
            "cause": "upstream_timeout",
            "message": "行情超时降级",
            "confidence_cap": 0.4,
            "source": "agent.degraded",
        }
    ]
    # 故意混入假价字段：scorecard/memo 路径应忽略，不把假价提升为事实
    final_decision = {
        "action": "HOLD",
        "confidence": 0.9,
        "price_targets": {
            "support": 1174.06,
            "target": 4384.17,
            "resistance": 4500.0,
        },
        "degradations": degradations,
        "confidence_cap": 0.4,
    }
    state = {
        "technical_report": None,
        "fundamental_report": None,
        "capital_flow_report": None,
        "sentiment_report": None,
        "bull_case": None,
        "bear_case": None,
        "execution_log": [{"status": "error", "tool": "get_stock_data"}],
        "final_decision": final_decision,
        "degradations": degradations,
    }
    sc = compute_run_scorecard(state, task_id="g12-tid", stock_code="600519")
    assert sc["confidence_cap"] is not None
    assert float(sc["confidence_cap"]) <= 0.4 + 1e-9
    # scorecard 本身不承载 price_targets
    assert "price_targets" not in sc
    assert "support" not in sc
    assert "target" not in sc
    memo = build_decision_memo(state, scorecard=sc)
    assert isinstance(memo, dict)
    # memo 不得承载 price_targets 假价；标志性假点位不得出现在 memo JSON
    assert "price_targets" not in memo or memo.get("price_targets") in (None, {}, [])
    memo_s = json.dumps(memo, ensure_ascii=False)
    for fake in ("1174.06", "4384.17", "4500"):
        assert fake not in memo_s
    # memo 可含 action；不得把假点位当必填字段输出
    memo_s = json.dumps(memo, ensure_ascii=False) if not isinstance(memo, str) else memo
    # 允许 action 文本；禁止夹具里的标志性假价原样落到 memo 必填价位键
    if isinstance(memo, dict):
        assert memo.get("price_targets") in (None, {}, [])
        for fake in (1174.06, 4384.17):
            # 价位数字不得以目标价字段出现
            pt = memo.get("price_targets") or {}
            assert fake not in (pt.values() if isinstance(pt, dict) else [])


def test_g12_event_bus_agent_degraded_payload_shape(monkeypatch):
    """agent.degraded 事件载荷含 confidence_cap，不含假行情价位。"""
    from app.core import event_bus as eb

    published = []

    class _Bus:
        def publish(self, event_type, payload):
            published.append((event_type, payload))
            return payload

    monkeypatch.setattr(eb, "get_event_bus", lambda: _Bus())
    out = eb.publish_agent_degraded(
        task_id="g12-tid",
        stock_code="600519",
        confidence_cap=0.4,
        cause="fixture",
        message="unit degrade",
    )
    assert isinstance(out, dict)
    assert out.get("confidence_cap") == 0.4
    assert "price" not in out
    assert "price_targets" not in out
    assert "1174.06" not in json.dumps(out)
    assert published, "should publish agent.degraded"
    et, pl = published[0]
    assert et == eb.EVENT_AGENT_DEGRADED
    assert pl.get("confidence_cap") == 0.4
