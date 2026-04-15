# -*- coding: utf-8 -*-
"""
Input: mock AdapterRegistry.call_with_fallback
Output: 验证4投资者人格 + 决策层/风险/策略层通过 Registry 多源降级拉取增强上下文
Pos: tests/agents/test_investors_registry.py [NEW-FILE:#20260415-29]

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

覆盖 (E3 扩展, 接续 C2 test_registry_integration):
  1. BuffettAgent._registry_fetch xbrl_financials 与 a_stock_kline 路径
  2. MungerAgent._registry_fetch xbrl_financials + news
  3. LynchAgent._registry_fetch a_stock_kline + corporate_entity
  4. DamodaranAgent._registry_fetch xbrl_financials + macro_us/macro_cn
  5. DecisionMaker._collect_decision_context 三域聚合 (news+social+esg)
  6. RiskManager._collect_alt_risk_context commodity_shipping + corporate_entity
  7. StrategyEvolver._collect_evolve_context hiring_signal + esg_rating
  8. 任一 domain registry 失败时返回None或空串, 不抛异常
"""
import unittest
from unittest.mock import patch, MagicMock


class TestBuffettRegistry(unittest.TestCase):
    def test_registry_fetch_xbrl_and_kline(self):
        from app.agents.investors import buffett as bf
        mock_reg = MagicMock()
        mock_reg.call_with_fallback.return_value = {'pe': 12.0, 'roe': 22.0}
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            out = bf._registry_fetch('xbrl_financials', 'get_financials', code='AAPL')
        self.assertEqual(out['pe'], 12.0)
        mock_reg.call_with_fallback.assert_called_once_with(
            'xbrl_financials', 'get_financials', code='AAPL'
        )

    def test_collect_context_handles_failure_gracefully(self):
        from app.agents.investors import buffett as bf
        mock_reg = MagicMock()
        mock_reg.call_with_fallback.side_effect = Exception('all sources failed')
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            ctx = bf._collect_registry_context('000001')
        self.assertEqual(ctx, "")


class TestMungerRegistry(unittest.TestCase):
    def test_registry_news_and_xbrl(self):
        from app.agents.investors import munger as mg
        mock_reg = MagicMock()
        mock_reg.call_with_fallback.side_effect = [
            {'pe': 10.0},
            [{'title': '丑闻调查', 'date': '2026-04-15'}]
        ]
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            ctx = mg._collect_registry_context('000001')
        self.assertIn('XBRL', ctx)
        self.assertIn('丑闻', ctx)
        self.assertEqual(mock_reg.call_with_fallback.call_count, 2)


class TestLynchRegistry(unittest.TestCase):
    def test_registry_kline_and_entity(self):
        from app.agents.investors import lynch as ly
        import pandas as pd
        mock_reg = MagicMock()
        mock_reg.call_with_fallback.side_effect = [
            pd.DataFrame({'close': [10.0, 11.0, 12.0]}),
            {'name': 'Apple Inc', 'jurisdiction': 'US'}
        ]
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            ctx = ly._collect_registry_context('AAPL')
        self.assertIn('K线', ctx)
        self.assertIn('企业实体', ctx)


class TestDamodaranRegistry(unittest.TestCase):
    def test_registry_xbrl_and_macro_us(self):
        from app.agents.investors import damodaran as dm
        mock_reg = MagicMock()
        mock_reg.call_with_fallback.side_effect = [
            {'fcf': 1000.0},
            {'gdp': 25000, 'cpi': 3.2}
        ]
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            ctx = dm._collect_registry_context('AAPL', market_type='US')
        self.assertIn('XBRL', ctx)
        self.assertIn('macro_us', ctx)
        call_args_list = mock_reg.call_with_fallback.call_args_list
        self.assertEqual(call_args_list[1].args[0], 'macro_us')

    def test_registry_uses_macro_cn_for_a_market(self):
        from app.agents.investors import damodaran as dm
        mock_reg = MagicMock()
        mock_reg.call_with_fallback.side_effect = [None, {'gdp_cn': 18000}]
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            ctx = dm._collect_registry_context('600000', market_type='A')
        self.assertIn('macro_cn', ctx)


class TestDecisionMakerRegistry(unittest.TestCase):
    def test_decision_aggregates_news_social_esg(self):
        from app.agents import decision_maker as dc
        mock_reg = MagicMock()
        mock_reg.call_with_fallback.side_effect = [
            [{'title': '业绩超预期', 'date': '2026-04-15'}],
            {'score': 0.62, 'trend': 'positive'},
            {'rating': 'AA', 'environment': 8.5}
        ]
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            ctx = dc._collect_decision_context('000001')
        self.assertIn('新闻', ctx)
        self.assertIn('社交舆情', ctx)
        self.assertIn('ESG', ctx)
        self.assertEqual(mock_reg.call_with_fallback.call_count, 3)

    def test_decision_all_fail_returns_empty(self):
        from app.agents import decision_maker as dc
        mock_reg = MagicMock()
        mock_reg.call_with_fallback.side_effect = Exception('x')
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            ctx = dc._collect_decision_context('000001')
        self.assertEqual(ctx, "")


class TestRiskManagerRegistry(unittest.TestCase):
    def test_risk_alt_shipping_and_entity(self):
        from app.agents import risk_manager as rm
        mock_reg = MagicMock()
        mock_reg.call_with_fallback.side_effect = [
            {'bdi': 1520, 'change_pct': -3.2},
            {'shareholders': ['A', 'B'], 'recent_change': '股权变更'}
        ]
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            ctx = rm._collect_alt_risk_context('000001')
        self.assertIn('BDI', ctx)
        self.assertIn('企业股权实体', ctx)


class TestStrategyEvolverRegistry(unittest.TestCase):
    def test_evolver_hiring_and_esg(self):
        from app.agents import strategy_evolver as se
        mock_reg = MagicMock()
        mock_reg.call_with_fallback.side_effect = [
            {'openings': 320, 'mom_growth': 0.15},
            {'rating': 'BBB', 'score': 75}
        ]
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            ctx = se._collect_evolve_context('000001')
        self.assertIn('招聘', ctx)
        self.assertIn('ESG', ctx)

    def test_evolver_partial_failure_still_returns_available(self):
        from app.agents import strategy_evolver as se
        mock_reg = MagicMock()
        # hiring 成功, esg 抛异常 → 函数级捕获只返回 hiring
        mock_reg.call_with_fallback.side_effect = [
            {'openings': 100},
            Exception('esg source down')
        ]
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            ctx = se._collect_evolve_context('000001')
        self.assertIn('招聘', ctx)
        self.assertNotIn('ESG', ctx)


if __name__ == '__main__':
    unittest.main()
