"""
Input: I2阶段bug修复回归测试
Output: pytest断言结果
Pos: tests/agents/test_i2_regression.py - [NEW-FILE:#20260415-41]

[I2-2026-04-15] 回归测试覆盖 H2 真端到端验证发现的两个 minor bug:
  Bug#1 StrategyEvolver JSON 解析对 markdown fence/trailing comma/空字符串/非法JSON 容错
  Bug#2 capital_flow_analyzer 对 None/空DataFrame/美股symbol 不再 NoneType

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


# === Bug#1 StrategyEvolver JSON 容错 ===

class TestStrategyEvolverSafeJsonParse:
    """覆盖 _safe_json_parse 各种异常输入不抛异常。"""

    def test_markdown_fence_json(self):
        from app.agents.strategy_evolver import _safe_json_parse
        text = "```json\n{\"focus_areas\": [\"tech\"], \"risk_sensitivity\": \"medium\"}\n```"
        result = _safe_json_parse(text)
        assert result is not None
        assert result["focus_areas"] == ["tech"]

    def test_plain_fence_no_lang(self):
        from app.agents.strategy_evolver import _safe_json_parse
        text = "```\n{\"a\": 1}\n```"
        result = _safe_json_parse(text)
        assert result == {"a": 1}

    def test_trailing_comma(self):
        from app.agents.strategy_evolver import _safe_json_parse
        text = '{"focus_areas": ["a", "b",], "x": 1,}'
        result = _safe_json_parse(text)
        assert result is not None
        assert result["x"] == 1

    def test_empty_string_returns_none(self):
        from app.agents.strategy_evolver import _safe_json_parse
        assert _safe_json_parse("") is None
        assert _safe_json_parse(None) is None
        assert _safe_json_parse("   ") is None

    def test_invalid_json_returns_none(self):
        from app.agents.strategy_evolver import _safe_json_parse
        assert _safe_json_parse("not json at all {broken") is None

    def test_json_embedded_in_prose(self):
        from app.agents.strategy_evolver import _safe_json_parse
        text = "分析结果如下:\n{\"focus_areas\": [\"fundamental\"]}\n以上。"
        result = _safe_json_parse(text)
        assert result is not None
        assert "focus_areas" in result

    def test_evolve_strategy_no_exception_on_bad_llm(self):
        """evolve_strategy 遇到非法LLM输出应返回原策略而非抛异常。"""
        from app.agents.strategy_evolver import StrategyEvolver
        evolver = StrategyEvolver()
        reflections = [{"reflection": {"improvements": ["x"], "biases_detected": ["y"]}}]

        with patch('app.core.ai_client.get_ai_client') as mock_client, \
             patch('app.core.ai_client.chat_completion') as mock_chat, \
             patch('app.core.ai_client.get_completion_content') as mock_content:
            mock_client.return_value = MagicMock()
            mock_chat.return_value = (MagicMock(), None)
            mock_content.return_value = "not valid json {broken"

            # 不应抛异常
            result = evolver.evolve_strategy("TEST001", reflections)
            assert isinstance(result, dict)
            assert "focus_areas" in result


# === Bug#2 capital_flow_analyzer None/US guard ===

class TestCapitalFlowNoneGuard:
    """覆盖 get_individual_fund_flow 对 None/empty/US/HK 场景的 guard。"""

    def test_us_market_short_circuit(self):
        """美股应短路返回 mock, 不调用 akshare。"""
        from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
        analyzer = CapitalFlowAnalyzer()
        with patch('akshare.stock_individual_fund_flow') as mock_ak:
            result = analyzer.get_individual_fund_flow("AAPL", market_type="US")
            assert result is not None
            assert isinstance(result, dict)
            # 短路: akshare不应被调用
            mock_ak.assert_not_called()

    def test_hk_market_short_circuit(self):
        from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
        analyzer = CapitalFlowAnalyzer()
        with patch('akshare.stock_individual_fund_flow') as mock_ak:
            result = analyzer.get_individual_fund_flow("00700", market_type="HK")
            assert result is not None
            mock_ak.assert_not_called()

    def test_none_data_guarded(self):
        """akshare 返回 None 应走 mock 降级, 不抛 NoneType。"""
        from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
        analyzer = CapitalFlowAnalyzer()
        with patch('akshare.stock_individual_fund_flow', return_value=None):
            result = analyzer.get_individual_fund_flow("600000", market_type="A")
            assert result is not None
            assert isinstance(result, dict)

    def test_empty_dataframe_guarded(self):
        """akshare 返回空 DataFrame 应走 mock 降级。"""
        from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
        analyzer = CapitalFlowAnalyzer()
        # 清缓存避免命中历史
        analyzer.data_cache = {}
        with patch('akshare.stock_individual_fund_flow', return_value=pd.DataFrame()):
            result = analyzer.get_individual_fund_flow("600001", market_type="A")
            assert result is not None
            assert isinstance(result, dict)

    def test_aapl_full_flow_no_exception(self):
        """端到端: AAPL + US 走完不抛 NoneType。"""
        from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
        analyzer = CapitalFlowAnalyzer()
        # 无 patch, 依赖短路逻辑生效
        result = analyzer.get_individual_fund_flow("AAPL", market_type="US")
        assert result is not None
        assert isinstance(result, dict)
