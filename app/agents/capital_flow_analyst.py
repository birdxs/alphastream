"""
Input: StockAnalysisState (stock_code, market_type)
Output: StockAnalysisState (capital_flow_report已填充，含AI评分/主力动向/资金意图/工具调用记录)
Pos: 资金流向分析Agent，通过Function Calling让AI自主查询数据并评分分析，降级时使用硬编码模式
[C2 2026-04-15] fallback层接入 AdapterRegistry (a_stock_realtime / a_stock_kline),
  原 CapitalFlowAnalyzer 兜底 —— 双保险。
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _registry_fetch(domain: str, method: str, **kwargs) -> Optional[Any]:
    """模块级 AdapterRegistry 多源降级 fetch。失败返回None。"""
    try:
        from app.adapters.adapter_registry import AdapterRegistry
        return AdapterRegistry.default().call_with_fallback(domain, method, **kwargs)
    except Exception as e:
        logger.info(f"[CapitalFlowAnalyst] registry fetch {domain}.{method} 降级失败: {type(e).__name__}: {e}")
        return None


class CapitalFlowAnalystAgent:
    """资金流向分析师Agent - AI通过Function Calling自主获取数据并评分分析"""

    name = "资金流向分析师"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """执行资金流向分析（AI Agent模式，降级时使用硬编码模式）"""
        from app.core.ai_client import get_ai_client, chat_with_tools
        from app.core.tools import CAPITAL_FLOW_TOOLS_SCHEMA

        stock_code = state['stock_code']
        market_type = state.get('market_type', 'A')

        try:
            client = get_ai_client()
            if not client:
                return _fallback_analyze(state)

            system_prompt = (
                "你是资深资金分析师，具备查询股票资金流向数据的工具。"
                "请使用工具获取真实的资金流向数据后，基于数据给出专业的资金面分析和评分。"
                "评分标准：综合主力净流入/流出趋势、大单占比、北向资金动向、"
                "连续流入/流出天数等多维度，给出0-100分。"
                "80分以上=资金强力流入，60-80=温和流入，40-60=中性，40以下=资金流出。"
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"""请对股票 {stock_code}（市场：{market_type}）进行全面资金流向分析。

请先使用工具获取该股票的资金流向数据，然后基于真实数据给出专业分析。

请严格以如下JSON格式输出（不要添加任何markdown代码块标记）：
{{
    "score": 65,
    "main_force_trend": "净流入/净流出/平衡",
    "main_force_amount": "1.5亿",
    "big_order_ratio": 35.5,
    "retail_behavior": "跟进/离场/观望",
    "capital_intention": "建仓/出货/洗盘/试探",
    "consecutive_days": 3,
    "flow_data": {{
        "today_net_inflow": 15000,
        "5day_net_inflow": 50000,
        "10day_net_inflow": -20000
    }},
    "recommendation": "买入/持有/减仓/卖出",
    "ai_commentary": "详细的资金流向分析，包括主力动向、资金意图解读、大单与散户行为对比、短期资金面展望"
}}

其中score为0-100的资金面评分，请基于获取到的真实数据综合评估。"""}
            ]

            content, tool_log, error = chat_with_tools(
                client, messages, CAPITAL_FLOW_TOOLS_SCHEMA,
                max_tool_rounds=2, temperature=0.7,
                agent_name='资金流向分析师'  # [UI-Q4]
            )

            if error:
                logger.warning(f"资金流向分析AI调用失败: {error}，降级到硬编码模式")
                return _fallback_analyze(state)

            # 解析AI输出的结构化JSON
            result = _parse_ai_result(content)
            result['tool_calls'] = tool_log

            return {
                'capital_flow_report': result,
                'progress': 25.0,
                'execution_log': [
                    {'agent': '资金流向分析师', 'status': 'success', 'mode': 'ai_agent', 'tools_used': len(tool_log)}
                ]
            }

        except Exception as e:
            logger.error(f"资金流向分析失败: {e}，降级到硬编码模式")
            try:
                return _fallback_analyze(state)
            except Exception as fallback_err:
                logger.error(f"资金流向分析降级也失败: {fallback_err}")
                return {
                    'capital_flow_report': {'error': str(e)},
                    'execution_log': [
                        {'agent': '资金流向分析师', 'status': 'failed', 'error': str(e)}
                    ]
                }


def _parse_ai_result(content: str) -> Dict[str, Any]:
    """解析AI输出的JSON结果，支持处理markdown代码块"""
    if not content:
        return {'score': 50, 'ai_commentary': '未获取到AI分析结果', 'recommendation': '观望'}

    # 尝试从markdown代码块中提取JSON
    json_str = content
    code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', content, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1).strip()

    # 尝试直接解析JSON
    try:
        result = json.loads(json_str)
        if isinstance(result, dict):
            result.setdefault('score', 50)
            result.setdefault('ai_commentary', content)
            result.setdefault('recommendation', '观望')
            return result
    except json.JSONDecodeError:
        pass

    # 尝试从内容中提取JSON对象
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
    if json_match:
        try:
            result = json.loads(json_match.group(0))
            if isinstance(result, dict):
                result.setdefault('score', 50)
                result.setdefault('ai_commentary', content)
                result.setdefault('recommendation', '观望')
                return result
        except json.JSONDecodeError:
            pass

    # JSON解析完全失败
    logger.warning("资金流向分析JSON解析失败，使用纯文本模式")
    return {
        'score': 50,
        'ai_commentary': content,
        'recommendation': '观望',
        'parse_warning': 'AI输出非标准JSON，已降级为纯文本'
    }


def _fallback_analyze(state: Dict[str, Any]) -> Dict[str, Any]:
    """AI不可用时的降级分析（保留原硬编码逻辑）"""
    from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
    from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

    stock_code = state['stock_code']
    market_type = state.get('market_type', 'A')

    analyzer = CapitalFlowAnalyzer()

    # akshare资金流向接口需要 'sh'/'sz' 格式的market参数
    flow_market = market_type
    if market_type == 'A':
        flow_market = 'sh' if stock_code.startswith('6') else 'sz'

    # [C2] 优先走 AdapterRegistry 实时行情多源 (efinance/akshare/opencli), 失败兜底 analyzer
    flow_data = _registry_fetch('a_stock_realtime', 'get_individual_fund_flow',
                                code=stock_code, market=flow_market)
    if flow_data is None:
        # 尝试 a_stock_kline 域获取 (某些适配器在kline域暴露资金流)
        flow_data = _registry_fetch('a_stock_kline', 'get_individual_fund_flow',
                                    code=stock_code, market=flow_market)
    if flow_data is None:
        # 获取个股资金流向 (原路径兜底)
        flow_data = analyzer.get_individual_fund_flow(stock_code, flow_market)

    # 计算资金流向评分
    score_result = analyzer.calculate_capital_flow_score(stock_code, flow_market)

    result = {
        'flow_data': flow_data,
        'score': score_result
    }

    # 检查是否有错误
    if isinstance(score_result, dict) and 'error' in score_result:
        return {
            'capital_flow_report': {'error': score_result['error']},
            'execution_log': [
                {'agent': '资金流向分析师', 'status': 'failed', 'mode': 'fallback', 'error': score_result['error']}
            ]
        }

    # 尝试用AI增强注释
    client = get_ai_client()
    if client:
        flow_summary = _format_flow_data(flow_data)
        score_summary = _format_score_data(score_result)

        prompt = f"""你是资深资金分析师。基于以下资金流向数据，给出专业分析：

股票代码: {stock_code}

资金流向数据:
{flow_summary}

资金评分:
{score_summary}

请给出：
1. 主力资金动向判断（净流入/流出趋势、力度）
2. 资金意图解读（建仓/出货/洗盘/试探）
3. 大单与散户行为对比分析
4. 短期资金面展望与操作建议"""

        response, error = chat_completion(
            client,
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1200
        )
        if not error:
            result['ai_commentary'] = get_completion_content(response)

    return {
        'capital_flow_report': result,
        'progress': 25.0,
        'execution_log': [
            {'agent': '资金流向分析师', 'status': 'success', 'mode': 'fallback'}
        ]
    }


def _format_flow_data(data: Any) -> str:
    """格式化资金流向数据为可读字符串"""
    if data is None:
        return "无数据"
    if isinstance(data, dict):
        lines = []
        for k, v in list(data.items())[:15]:
            lines.append(f"  {k}: {v}")
        return "\n".join(lines) if lines else "空数据"
    if isinstance(data, list):
        return str(data[:5])
    return str(data)[:500]


def _format_score_data(data: Any) -> str:
    """格式化评分数据为可读字符串"""
    if data is None:
        return "无数据"
    if isinstance(data, dict):
        lines = []
        for k, v in list(data.items())[:10]:
            lines.append(f"  {k}: {v}")
        return "\n".join(lines) if lines else "空数据"
    return str(data)[:300]
