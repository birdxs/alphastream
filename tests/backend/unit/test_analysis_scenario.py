# -*- coding: utf-8 -*-
# Input  : ScenarioPredictor + mock analyzer/chat_completion
# Output : pytest 用例 BE-06a 情景预测单元测试
# Pos    : tests/backend/unit/test_analysis_scenario.py
"""BE-06a ScenarioPredictor 单元测试

覆盖：
1. 实例化 + generate_scenarios 快乐路径（mock analyzer + LLM）
2. analyzer 异常 → 兜底返回 {}
3. LLM 失败 → 仅返回 _calculate_scenarios 结果
4. _calculate_scenarios 关键计算（乐观>当前>悲观）
5. _get_default_analysis 默认结构
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest


# -- helper ------------------------------------------------------------------
def _build_indicator_df(n=120, base_price=10.0):
    rng = np.random.default_rng(7)
    prices = base_price + np.cumsum(rng.normal(0, 0.05, n))
    df = pd.DataFrame({
        "close": prices,
        "MA5": prices,
        "MA20": prices,
        "MA60": prices,
        "RSI": 55.0,
        "MACD": 0.1,
        "Signal": 0.0,
        "BB_upper": prices * 1.05,
        "BB_middle": prices,
        "BB_lower": prices * 0.95,
        "Volatility": 2.0,
    })
    return df


@pytest.fixture
def mock_analyzer():
    m = MagicMock()
    m.get_stock_data.return_value = _build_indicator_df()
    m.calculate_indicators.side_effect = lambda df: df
    m.get_stock_info.return_value = {"股票名称": "测试股", "行业": "测试"}
    return m


@pytest.fixture
def predictor(mock_analyzer):
    with patch("app.analysis.scenario_predictor.get_ai_client", return_value=MagicMock()), \
         patch("app.analysis.scenario_predictor.get_ai_model", return_value="gpt-test"):
        from app.analysis.scenario_predictor import ScenarioPredictor
        return ScenarioPredictor(mock_analyzer, openai_api_key=None)


# ---------------------------------------------------------------- 1. 无 LLM 快乐路径
def test_generate_scenarios_no_llm(predictor):
    """无 openai_api_key → 仅返回 _calculate_scenarios 结果"""
    result = predictor.generate_scenarios("600519", market_type="A", days=30)
    assert "current_price" in result
    assert "optimistic" in result
    assert "neutral" in result
    assert "pessimistic" in result


# ---------------------------------------------------------------- 2. analyzer 异常 → {}
def test_generate_scenarios_analyzer_exception_returns_empty(predictor, mock_analyzer):
    mock_analyzer.get_stock_data.side_effect = Exception("data err")
    result = predictor.generate_scenarios("600519")
    assert result == {}


# ---------------------------------------------------------------- 3. LLM 成功路径
def test_generate_scenarios_with_llm_success(mock_analyzer):
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock()]
    fake_resp.choices[0].message.content = (
        '{"optimistic_analysis":"上涨","neutral_analysis":"震荡",'
        '"pessimistic_analysis":"下跌",'
        '"risk_factors":["r1","r2","r3","r4","r5"],'
        '"opportunity_factors":["o1","o2","o3","o4","o5"]}'
    )
    with patch("app.analysis.scenario_predictor.get_ai_client", return_value=MagicMock()), \
         patch("app.analysis.scenario_predictor.get_ai_model", return_value="gpt-test"), \
         patch("app.analysis.scenario_predictor.chat_completion",
               return_value=(fake_resp, None)):
        from app.analysis.scenario_predictor import ScenarioPredictor
        p = ScenarioPredictor(mock_analyzer, openai_api_key="key-test")
        result = p.generate_scenarios("600519", days=30)

    assert result.get("optimistic_analysis") == "上涨"
    assert len(result.get("risk_factors", [])) == 5


# ---------------------------------------------------------------- 4. LLM 失败 → 默认分析
def test_generate_scenarios_llm_failure_uses_default(mock_analyzer):
    with patch("app.analysis.scenario_predictor.get_ai_client", return_value=MagicMock()), \
         patch("app.analysis.scenario_predictor.get_ai_model", return_value="gpt-test"), \
         patch("app.analysis.scenario_predictor.chat_completion",
               return_value=(None, "API err")):
        from app.analysis.scenario_predictor import ScenarioPredictor
        p = ScenarioPredictor(mock_analyzer, openai_api_key="key-test")
        result = p.generate_scenarios("600519", days=30)

    # 失败时应包含 _get_default_analysis 的默认字段
    assert "optimistic_analysis" in result
    assert "risk_factors" in result
    assert len(result["risk_factors"]) == 5


# ---------------------------------------------------------------- 5. _calculate_scenarios 关键计算
def test_calculate_scenarios_price_ordering(predictor):
    df = _build_indicator_df(120, base_price=10.0)
    scenarios = predictor._calculate_scenarios(df, days=30)
    current = scenarios["current_price"]
    optimistic = scenarios["optimistic"]["target_price"]
    pessimistic = scenarios["pessimistic"]["target_price"]
    # 关键计算正确性：乐观目标价高于当前价；悲观低于当前价
    assert optimistic > current
    assert pessimistic < current
    # 涨跌幅符号正确
    assert scenarios["optimistic"]["change_percent"] > 0
    assert scenarios["pessimistic"]["change_percent"] < 0


# ---------------------------------------------------------------- 6. 默认结构
def test_get_default_analysis_structure(predictor):
    default = predictor._get_default_analysis()
    assert "optimistic_analysis" in default
    assert "neutral_analysis" in default
    assert "pessimistic_analysis" in default
    assert len(default["risk_factors"]) == 5
    assert len(default["opportunity_factors"]) == 5
