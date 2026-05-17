# -*- coding: utf-8 -*-
# Input  : InvestorCoordinator + 4 投资者 mock 输入
# Output : pytest 用例，覆盖编排、投票统计、AI 共识、降级共识
# Pos    : tests/backend/integration/test_investor_coordinator.py - BE-02b 投资者协调器集成测试
"""BE-02b 投资者协调器测试

覆盖：
  - InvestorCoordinator.analyze 4 人格并行/串行编排
  - _compute_vote_stats 投票统计多场景
  - _build_consensus AI 共识（mock LLM）
  - _fallback_consensus 降级共识（LLM 抛错）
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

import app.agents.investors.investor_coordinator as ic_mod
from app.agents.investors.investor_coordinator import (
    InvestorCoordinator,
    _compute_vote_stats,
    _build_consensus,
    _fallback_consensus,
)


# ---------- 公共工具 -----------------------------------------------------------
def _mk_view(name: str, rec: str, conf: float = 0.7, reasoning: str = "理由 X") -> dict:
    """构造单个投资者结果字典"""
    return {
        "analyst": name,
        "recommendation": rec,
        "confidence": conf,
        "reasoning": reasoning,
        "key_metrics": {"PE": 12.3},
    }


def _mk_results_all(rec_map: dict) -> dict:
    """根据 rec_map 构造 4 投资者 results 字典

    rec_map: {'buffett': 'BUY', 'munger': 'SELL', ...}
    """
    name_map = {
        "buffett": "巴菲特",
        "munger": "芒格",
        "lynch": "林奇",
        "damodaran": "达摩达兰",
    }
    return {
        f"investor_{k}": _mk_view(name_map[k], v)
        for k, v in rec_map.items()
    }


# =========================================================================
# A1. InvestorCoordinator.analyze —— 4 人格编排
# =========================================================================
class TestInvestorCoordinatorAnalyze:
    """A1: analyze() 应调用所有 4 个投资者 analyze 方法并返回 consensus 字段"""

    def test_analyze_invokes_all_four_investors_and_returns_consensus(
        self, minimal_state, patched_ai_client
    ):
        # 准备：mock 4 个投资者 analyze
        fake_buf = MagicMock(return_value={
            "investor_buffett": _mk_view("巴菲特", "BUY"),
            "execution_log": [{"agent": "巴菲特", "status": "success"}],
        })
        fake_mun = MagicMock(return_value={
            "investor_munger": _mk_view("芒格", "BUY"),
            "execution_log": [],
        })
        fake_lyn = MagicMock(return_value={
            "investor_lynch": _mk_view("林奇", "HOLD"),
            "execution_log": [],
        })
        fake_dam = MagicMock(return_value={
            "investor_damodaran": _mk_view("达摩达兰", "BUY"),
            "execution_log": [],
        })

        # 通过 patch 类的 analyze 替换
        with patch("app.agents.investors.buffett.BuffettAgent.analyze", fake_buf), \
             patch("app.agents.investors.munger.MungerAgent.analyze", fake_mun), \
             patch("app.agents.investors.lynch.LynchAgent.analyze", fake_lyn), \
             patch("app.agents.investors.damodaran.DamodaranAgent.analyze", fake_dam), \
             patch("app.core.ai_client.get_ai_client", return_value=None):
            # ai_client=None 时走 _fallback_consensus，避免依赖外部 LLM
            out = InvestorCoordinator.analyze(minimal_state)

        # 4 人格都被调用
        assert fake_buf.called, "BuffettAgent.analyze 未被调用"
        assert fake_mun.called, "MungerAgent.analyze 未被调用"
        assert fake_lyn.called, "LynchAgent.analyze 未被调用"
        assert fake_dam.called, "DamodaranAgent.analyze 未被调用"

        # 返回 state 包含 consensus / opinions
        assert "investor_consensus" in out, "缺少 investor_consensus 键"
        assert "investor_opinions" in out, "缺少 investor_opinions 键"
        opinions = out["investor_opinions"]
        assert set(opinions.keys()) >= {"buffett", "munger", "lynch", "damodaran"}

        consensus = out["investor_consensus"]
        assert consensus["final_recommendation"] in ("BUY", "SELL", "HOLD")
        assert "consensus_reasoning" in consensus
        # 3 BUY + 1 HOLD => 多数 BUY
        assert consensus["final_recommendation"] == "BUY"

    def test_analyze_handles_single_investor_exception(self, minimal_state):
        """单个投资者抛错时，协调器应记录失败并继续，不中断整个流程"""
        fake_buf = MagicMock(side_effect=RuntimeError("buffett boom"))
        fake_mun = MagicMock(return_value={"investor_munger": _mk_view("芒格", "BUY")})
        fake_lyn = MagicMock(return_value={"investor_lynch": _mk_view("林奇", "BUY")})
        fake_dam = MagicMock(return_value={"investor_damodaran": _mk_view("达摩达兰", "BUY")})

        with patch("app.agents.investors.buffett.BuffettAgent.analyze", fake_buf), \
             patch("app.agents.investors.munger.MungerAgent.analyze", fake_mun), \
             patch("app.agents.investors.lynch.LynchAgent.analyze", fake_lyn), \
             patch("app.agents.investors.damodaran.DamodaranAgent.analyze", fake_dam), \
             patch("app.core.ai_client.get_ai_client", return_value=None):
            out = InvestorCoordinator.analyze(minimal_state)

        assert "investor_consensus" in out
        # buffett 失败被兜底为 HOLD
        opinions = out["investor_opinions"]
        assert opinions["buffett"].get("recommendation") == "HOLD"
        # 异常被记录
        assert "error" in opinions["buffett"]


# =========================================================================
# A2. _compute_vote_stats —— 投票统计多场景
# =========================================================================
class TestComputeVoteStats:
    """A2: 多场景投票统计"""

    def test_all_buy(self):
        results = _mk_results_all(
            {"buffett": "BUY", "munger": "BUY", "lynch": "BUY", "damodaran": "BUY"}
        )
        stats = _compute_vote_stats(results)
        assert stats["total_votes"] == 4
        assert stats["majority_rec"] == "BUY"
        assert stats["majority_count"] == 4
        assert stats["agreement_ratio"] == 1.0
        assert stats["vote_count"] == {"BUY": 4}

    def test_two_buy_two_sell(self):
        results = _mk_results_all(
            {"buffett": "BUY", "munger": "BUY", "lynch": "SELL", "damodaran": "SELL"}
        )
        stats = _compute_vote_stats(results)
        assert stats["total_votes"] == 4
        assert stats["majority_count"] == 2
        # tie -> Counter 取第一个 most_common 元素
        assert stats["majority_rec"] in ("BUY", "SELL")
        assert stats["agreement_ratio"] == 0.5

    def test_all_hold(self):
        results = _mk_results_all(
            {"buffett": "HOLD", "munger": "HOLD", "lynch": "HOLD", "damodaran": "HOLD"}
        )
        stats = _compute_vote_stats(results)
        assert stats["majority_rec"] == "HOLD"
        assert stats["agreement_ratio"] == 1.0

    def test_empty_results(self):
        stats = _compute_vote_stats({})
        assert stats["total_votes"] == 0
        assert stats["majority_rec"] == "HOLD"
        assert stats["agreement_ratio"] == 0.0
        assert stats["recommendations"] == []

    def test_ignores_non_investor_keys(self):
        results = _mk_results_all({"buffett": "BUY", "munger": "BUY"})
        results["other_garbage"] = {"recommendation": "SELL"}
        stats = _compute_vote_stats(results)
        assert stats["total_votes"] == 2  # 仅 investor_ 前缀计入

    def test_normalizes_invalid_recommendation_to_hold(self):
        results = {
            "investor_buffett": _mk_view("巴菲特", "MAYBE"),  # 非法
            "investor_munger": _mk_view("芒格", "BUY"),
        }
        stats = _compute_vote_stats(results)
        # MAYBE 应被标准化为 HOLD
        assert "HOLD" in stats["vote_count"]


# =========================================================================
# A3. _build_consensus —— AI 共识（mock LLM）
# =========================================================================
class TestBuildConsensusAI:
    """A3: AI 共识构建（LLM mock 返回固定 JSON）"""

    def test_ai_returns_fixed_consensus(self):
        results = _mk_results_all(
            {"buffett": "BUY", "munger": "BUY", "lynch": "BUY", "damodaran": "HOLD"}
        )
        ai_response_json = (
            '{"final_recommendation": "BUY", '
            '"consensus_confidence": "高", '
            '"agreement_level": "强共识", '
            '"consensus_reasoning": "三票BUY一票HOLD，护城河+成长共振", '
            '"key_agreements": ["护城河深"], '
            '"key_disagreements": ["短期估值"], '
            '"weight_analysis": "巴菲特+林奇权重高", '
            '"risk_warnings": ["利率风险"]}'
        )

        fake_client = MagicMock(name="fake_ai_client")
        fake_resp = MagicMock(name="fake_resp")
        with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
             patch("app.core.ai_client.chat_completion", return_value=(fake_resp, None)), \
             patch("app.core.ai_client.get_completion_content", return_value=ai_response_json):
            consensus = _build_consensus(results, "000001")

        # 字段完整性
        assert consensus["final_recommendation"] == "BUY"
        assert consensus["consensus_confidence"] == "高"
        assert consensus["agreement_level"] == "强共识"
        assert "护城河" in consensus["consensus_reasoning"]
        assert consensus["stock_code"] == "000001"
        assert consensus["ai_driven"] is True
        assert "vote_summary" in consensus
        assert "individual_views" in consensus
        assert isinstance(consensus["key_agreements"], list)
        assert isinstance(consensus["risk_warnings"], list)

    def test_empty_results_returns_default_hold(self):
        """空 results 应返回默认 HOLD（无需调 AI）"""
        consensus = _build_consensus({}, "000001")
        assert consensus["final_recommendation"] == "HOLD"
        assert consensus["consensus_confidence"] == "低"
        assert consensus["stock_code"] == "000001"


# =========================================================================
# A4. _fallback_consensus —— 降级共识（LLM 抛错）
# =========================================================================
class TestFallbackConsensus:
    """A4: AI 不可用 / 抛错时走降级路径"""

    def test_fallback_majority_buy(self):
        results = _mk_results_all(
            {"buffett": "BUY", "munger": "BUY", "lynch": "BUY", "damodaran": "SELL"}
        )
        vote_stats = _compute_vote_stats(results)
        consensus = _fallback_consensus(vote_stats, results, "000001")

        assert consensus["final_recommendation"] == "BUY"
        # 3/4 = 0.75 -> 强共识
        assert consensus["agreement_level"] == "强共识"
        assert consensus["consensus_confidence"] == "高"
        assert consensus["ai_driven"] is False
        assert consensus["stock_code"] == "000001"
        # 多数即 BUY
        assert consensus["vote_summary"].get("BUY") == 3

    def test_fallback_strong_consensus_label(self):
        results = _mk_results_all(
            {"buffett": "HOLD", "munger": "HOLD", "lynch": "HOLD", "damodaran": "HOLD"}
        )
        vote_stats = _compute_vote_stats(results)
        consensus = _fallback_consensus(vote_stats, results, "600519")
        assert consensus["agreement_level"] == "强共识"
        assert consensus["final_recommendation"] == "HOLD"

    def test_fallback_disagreement_low_confidence(self):
        """4 票分散 - 2BUY+1SELL+1HOLD, agreement_ratio=0.5 -> 多数一致"""
        results = _mk_results_all(
            {"buffett": "BUY", "munger": "BUY", "lynch": "SELL", "damodaran": "HOLD"}
        )
        vote_stats = _compute_vote_stats(results)
        consensus = _fallback_consensus(vote_stats, results, "000001")
        # 0.5 >= 0.5 -> 多数一致
        assert consensus["agreement_level"] in ("多数一致", "意见分歧")

    def test_build_consensus_falls_back_when_llm_raises(self):
        """当 LLM chat_completion 抛异常时，_build_consensus 应降级"""
        results = _mk_results_all(
            {"buffett": "SELL", "munger": "SELL", "lynch": "SELL", "damodaran": "BUY"}
        )

        fake_client = MagicMock(name="fake_ai_client")
        with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
             patch("app.core.ai_client.chat_completion", side_effect=RuntimeError("LLM down")):
            consensus = _build_consensus(results, "000001")

        # 走降级路径，断言降级结果与投票多数一致 (SELL)
        assert consensus["ai_driven"] is False
        assert consensus["final_recommendation"] == "SELL"
        # 3 SELL + 1 BUY -> agreement_ratio = 0.75 -> 强共识
        assert consensus["agreement_level"] == "强共识"

    def test_build_consensus_falls_back_when_llm_returns_error(self):
        """当 chat_completion 返回 (None, error_msg) 时也降级"""
        results = _mk_results_all(
            {"buffett": "BUY", "munger": "HOLD", "lynch": "BUY", "damodaran": "BUY"}
        )

        fake_client = MagicMock(name="fake_ai_client")
        with patch("app.core.ai_client.get_ai_client", return_value=fake_client), \
             patch("app.core.ai_client.chat_completion", return_value=(None, "api error")):
            consensus = _build_consensus(results, "000001")

        assert consensus["ai_driven"] is False
        # 3 BUY + 1 HOLD -> 多数 BUY
        assert consensus["final_recommendation"] == "BUY"
