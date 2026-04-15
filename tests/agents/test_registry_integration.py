# -*- coding: utf-8 -*-
"""
Input: mock AdapterRegistry.call_with_fallback
Output: 验证4个specialist agent能通过Registry多源降级拿到数据
Pos: tests/agents/test_registry_integration.py [NEW-FILE:#20260415-22]

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

覆盖:
  1. BaseStockAgent.fetch 正确委派 call_with_fallback
  2. fundamental_analyst._registry_fetch xbrl_financials 优先
  3. technical_analyst._registry_fetch a_stock_kline 优先
  4. capital_flow_analyst._registry_fetch a_stock_realtime 优先
  5. sentiment_analyst._registry_fetch news 优先
  6. registry 失败时返回 None (不抛, 让analyzer兜底)
"""
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd


class TestBaseAgentRegistry(unittest.TestCase):
    """验证 BaseStockAgent 的 registry property 与 fetch 便捷方法。"""

    def test_fetch_delegates_to_call_with_fallback(self):
        from app.agents.base_agent import BaseStockAgent

        class _Dummy(BaseStockAgent):
            def analyze(self, state):
                return state

        with patch('app.core.ai_client.get_ai_client', return_value=None), \
             patch('app.core.ai_client.get_ai_model', return_value='x'), \
             patch('app.core.data_provider.get_data_provider', return_value=None):
            agent = _Dummy()

        mock_reg = MagicMock()
        mock_reg.call_with_fallback.return_value = pd.DataFrame({'close': [10, 11, 12]})
        agent._registry = mock_reg

        result = agent.fetch('a_stock_kline', 'get_stock_history', code='000001')
        mock_reg.call_with_fallback.assert_called_once_with(
            'a_stock_kline', 'get_stock_history', code='000001'
        )
        self.assertEqual(len(result), 3)

    def test_fetch_raises_when_registry_none(self):
        from app.agents.base_agent import BaseStockAgent

        class _Dummy(BaseStockAgent):
            def analyze(self, state):
                return state

        with patch('app.core.ai_client.get_ai_client', return_value=None), \
             patch('app.core.ai_client.get_ai_model', return_value='x'), \
             patch('app.core.data_provider.get_data_provider', return_value=None), \
             patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   side_effect=Exception('boom')):
            agent = _Dummy()
            with self.assertRaises(RuntimeError):
                agent.fetch('a_stock_kline', 'x')


class TestFundamentalRegistry(unittest.TestCase):
    def test_fundamental_registry_fetch_xbrl(self):
        from app.agents import fundamental_analyst as fa

        mock_reg = MagicMock()
        mock_reg.call_with_fallback.return_value = {'pe': 15.0, 'roe': 18.0}
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            out = fa._registry_fetch('xbrl_financials', 'get_financials', code='AAPL')
        self.assertEqual(out['pe'], 15.0)
        mock_reg.call_with_fallback.assert_called_once_with(
            'xbrl_financials', 'get_financials', code='AAPL'
        )

    def test_fundamental_registry_fetch_returns_none_on_failure(self):
        from app.agents import fundamental_analyst as fa

        mock_reg = MagicMock()
        mock_reg.call_with_fallback.side_effect = Exception('all sources failed')
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            out = fa._registry_fetch('xbrl_financials', 'get_financials', code='AAPL')
        self.assertIsNone(out)


class TestTechnicalRegistry(unittest.TestCase):
    def test_technical_registry_fetch_kline(self):
        from app.agents import technical_analyst as ta

        df = pd.DataFrame({'close': [100, 101, 102]})
        mock_reg = MagicMock()
        mock_reg.call_with_fallback.return_value = df
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            out = ta._registry_fetch('a_stock_kline', 'get_stock_history', code='000001')
        self.assertEqual(len(out), 3)
        mock_reg.call_with_fallback.assert_called_once()


class TestCapitalFlowRegistry(unittest.TestCase):
    def test_capital_flow_registry_fetch_realtime(self):
        from app.agents import capital_flow_analyst as cf

        mock_reg = MagicMock()
        mock_reg.call_with_fallback.return_value = {'today_net_inflow': 15000}
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            out = cf._registry_fetch('a_stock_realtime', 'get_individual_fund_flow',
                                     code='000001', market='sz')
        self.assertEqual(out['today_net_inflow'], 15000)
        call_kwargs = mock_reg.call_with_fallback.call_args
        self.assertEqual(call_kwargs.args[0], 'a_stock_realtime')


class TestSentimentRegistry(unittest.TestCase):
    def test_sentiment_registry_fetch_news(self):
        from app.agents import sentiment_analyst as sa

        mock_reg = MagicMock()
        mock_reg.call_with_fallback.return_value = [
            {'title': 'test news', 'date': '2026-04-15', 'content': 'xx'}
        ]
        with patch('app.adapters.adapter_registry.AdapterRegistry.default',
                   return_value=mock_reg):
            out = sa._registry_fetch('news', 'get_latest_news',
                                     code='000001', days=3, limit=20)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['title'], 'test news')


if __name__ == '__main__':
    unittest.main()
