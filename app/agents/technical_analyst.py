"""
Input: StockAnalysisState (stock_code, market_type, 可选的历史反思上下文)
Output: StockAnalysisState (technical_report已填充，含AI评分/趋势/建议/工具调用记录)
Pos: 技术分析Agent，通过Function Calling让AI自主查询数据并评分分析，降级时使用硬编码模式
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)


class TechnicalAnalystAgent:
    """技术分析师Agent - AI通过Function Calling自主获取数据并评分分析"""

    name = "技术分析师"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """执行技术分析（AI Agent模式，降级时使用硬编码模式）"""
        from app.core.ai_client import get_ai_client, chat_with_tools
        from app.core.tools import TECHNICAL_TOOLS_SCHEMA

        stock_code = state['stock_code']
        market_type = state.get('market_type', 'A')

        try:
            client = get_ai_client()
            if not client:
                return _fallback_analyze(state)

            # 构建系统提示（含历史反思、自适应策略等上下文）
            system_prompt = _build_system_prompt(state)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"""请对股票 {stock_code}（市场：{market_type}）进行全面技术分析。

请先使用工具获取该股票的K线数据和技术指标，然后基于真实数据给出专业分析。

请严格以如下JSON格式输出（不要添加任何markdown代码块标记）：
{{
    "score": 75,
    "price": 100.50,
    "trend": "上涨/下跌/震荡",
    "rsi": 55.3,
    "macd_signal": "金叉/死叉/中性",
    "volume_status": "放量/缩量/正常",
    "support_level": 95.0,
    "resistance_level": 108.0,
    "recommendation": "买入/持有/减仓/卖出",
    "ai_commentary": "详细的技术分析说明，包括趋势判断、关键支撑阻力位、短期操作建议"
}}

其中score为0-100的技术评分，请基于获取到的真实数据综合评估。"""}
            ]

            content, tool_log, error = chat_with_tools(
                client, messages, TECHNICAL_TOOLS_SCHEMA,
                max_tool_rounds=3, temperature=0.7
            )

            if error:
                logger.warning(f"技术分析AI调用失败: {error}，降级到硬编码模式")
                return _fallback_analyze(state)

            # 解析AI输出的结构化JSON
            result = _parse_ai_result(content)
            result['tool_calls'] = tool_log

            return {
                'technical_report': result,
                'progress': 10.0,
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '技术分析师', 'status': 'success', 'mode': 'ai_agent', 'tools_used': len(tool_log)}
                ]
            }

        except Exception as e:
            logger.error(f"技术分析失败: {e}，降级到硬编码模式")
            try:
                return _fallback_analyze(state)
            except Exception as fallback_err:
                logger.error(f"技术分析降级也失败: {fallback_err}")
                return {
                    'technical_report': {'error': str(e)},
                    'execution_log': state.get('execution_log', []) + [
                        {'agent': '技术分析师', 'status': 'failed', 'error': str(e)}
                    ]
                }


def _build_system_prompt(state: Dict[str, Any]) -> str:
    """构建系统提示词，注入历史反思上下文和自适应策略"""
    stock_code = state['stock_code']

    base_prompt = (
        "你是资深技术分析师，具备查询股票K线数据和计算技术指标的工具。"
        "请使用工具获取真实数据后，基于数据给出专业的技术分析和评分。"
        "评分标准：综合趋势、动量、成交量、均线系统等多维度因素，给出0-100分。"
        "80分以上=强势，60-80=偏强，40-60=中性，40以下=偏弱。"
    )

    # 注入历史反思上下文（如果有）
    reflection_context = ""
    try:
        from app.agents.reflection import ReflectionAgent
        reflection_context = ReflectionAgent.get_reflection_prompt(stock_code)
    except (ImportError, Exception):
        pass

    if reflection_context:
        base_prompt += f"\n\n【历史分析反思】\n{reflection_context}"

    # 注入自适应策略（从state.messages获取，如果有）
    adaptive_context = state.get('adaptive_strategy', '')
    if adaptive_context:
        base_prompt += f"\n\n【自适应策略】\n{adaptive_context}"

    return base_prompt


def _parse_ai_result(content: str) -> Dict[str, Any]:
    """解析AI输出的JSON结果，支持处理markdown代码块"""
    if not content:
        return {'score': 50, 'ai_commentary': '未获取到AI分析结果', 'trend': '未知', 'recommendation': '观望'}

    # 尝试从markdown代码块中提取JSON
    json_str = content
    code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', content, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1).strip()

    # 尝试直接解析JSON
    try:
        result = json.loads(json_str)
        if isinstance(result, dict):
            # 确保必要字段存在
            result.setdefault('score', 50)
            result.setdefault('ai_commentary', content)
            result.setdefault('trend', '未知')
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
                result.setdefault('trend', '未知')
                result.setdefault('recommendation', '观望')
                return result
        except json.JSONDecodeError:
            pass

    # JSON解析完全失败，用纯文本作为ai_commentary
    logger.warning("技术分析JSON解析失败，使用纯文本模式")
    return {
        'score': 50,
        'ai_commentary': content,
        'trend': '未知',
        'recommendation': '观望',
        'parse_warning': 'AI输出非标准JSON，已降级为纯文本'
    }


def _fallback_analyze(state: Dict[str, Any]) -> Dict[str, Any]:
    """AI不可用时的降级分析（保留原硬编码逻辑）"""
    from app.analysis.stock_analyzer import StockAnalyzer
    from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

    stock_code = state['stock_code']
    market_type = state.get('market_type', 'A')

    analyzer = StockAnalyzer()
    result = analyzer.quick_analyze_stock(stock_code, market_type)

    if 'error' in result:
        return {
            'technical_report': {'error': result['error']},
            'execution_log': state.get('execution_log', []) + [
                {'agent': '技术分析师', 'status': 'failed', 'mode': 'fallback', 'error': result['error']}
            ]
        }

    # 尝试用AI增强注释（降级模式的AI注释，非Agent模式）
    client = get_ai_client()
    if client:
        reflection_context = ""
        try:
            from app.agents.reflection import ReflectionAgent
            reflection_context = ReflectionAgent.get_reflection_prompt(stock_code)
        except (ImportError, Exception):
            pass

        prompt = ""
        if reflection_context:
            prompt = reflection_context + "\n\n"
        prompt += f"""你是资深技术分析师。基于以下技术指标数据，给出专业分析：

股票代码: {stock_code}
评分: {result.get('score', 'N/A')}/100
价格: {result.get('price', 'N/A')}
趋势: {result.get('trend', 'N/A')}
RSI: {result.get('rsi', 'N/A')}
MACD信号: {result.get('macd_signal', 'N/A')}
成交量状态: {result.get('volume_status', 'N/A')}
建议: {result.get('recommendation', 'N/A')}

请给出：1. 趋势判断 2. 关键支撑/阻力位分析 3. 短期操作建议"""

        response, error = chat_completion(
            client,
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        if not error:
            result['ai_commentary'] = get_completion_content(response)

    return {
        'technical_report': result,
        'progress': 10.0,
        'execution_log': state.get('execution_log', []) + [
            {'agent': '技术分析师', 'status': 'success', 'mode': 'fallback'}
        ]
    }
