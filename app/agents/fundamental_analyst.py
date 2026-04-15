"""
Input: StockAnalysisState (stock_code, market_type)
Output: StockAnalysisState (fundamental_report已填充，含AI评分/财务健康度/成长性/工具调用记录)
Pos: 基本面分析Agent，通过Function Calling让AI自主查询数据并评分分析，降级时使用硬编码模式
[C2 2026-04-15] fallback层接入 AdapterRegistry (xbrl_financials / us_stock / a_stock_kline),
  原analyzer调用作为降级兜底 —— 双保险不破坏现有路径。
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _registry_fetch(domain: str, method: str, **kwargs) -> Optional[Any]:
    """模块级 AdapterRegistry 多源降级 fetch (静态Agent使用)。失败返回None, 不抛。"""
    try:
        from app.adapters.adapter_registry import AdapterRegistry
        return AdapterRegistry.default().call_with_fallback(domain, method, **kwargs)
    except Exception as e:
        logger.info(f"[FundamentalAnalyst] registry fetch {domain}.{method} 降级失败: {type(e).__name__}: {e}")
        return None


class FundamentalAnalystAgent:
    """基本面分析师Agent - AI通过Function Calling自主获取数据并评分分析"""

    name = "基本面分析师"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """执行基本面分析（AI Agent模式，降级时使用硬编码模式）"""
        from app.core.ai_client import get_ai_client, chat_with_tools
        from app.core.tools import FUNDAMENTAL_TOOLS_SCHEMA

        stock_code = state['stock_code']
        market_type = state.get('market_type', 'A')

        try:
            client = get_ai_client()
            if not client:
                return _fallback_analyze(state)

            system_prompt = (
                "你是资深基本面分析师，具备查询股票财务数据的工具。"
                "请使用工具获取真实的基本面数据后，基于数据给出专业的基本面分析和评分。"
                "评分标准：综合盈利能力(ROE/净利润率)、偿债能力(资产负债率)、"
                "成长性(营收/利润增速)、估值水平(PE/PB)等多维度，给出0-100分。"
                "80分以上=优秀，60-80=良好，40-60=一般，40以下=较差。"
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"""请对股票 {stock_code}（市场：{market_type}）进行全面基本面分析。

请先使用工具获取该股票的基本面数据，然后基于真实数据给出专业分析。

请严格以如下JSON格式输出（不要添加任何markdown代码块标记）：
{{
    "score": 70,
    "financial_health": "健康/一般/较差",
    "profitability": "强/中等/弱",
    "growth_potential": "高/中/低",
    "valuation": "低估/合理/高估",
    "financial_indicators": {{
        "pe_ratio": 15.5,
        "pb_ratio": 2.1,
        "roe": 18.5,
        "debt_ratio": 45.0,
        "revenue_growth": 12.3,
        "profit_growth": 8.5
    }},
    "growth_data": {{
        "revenue_trend": "上升/平稳/下降",
        "profit_trend": "上升/平稳/下降"
    }},
    "recommendation": "买入/持有/减仓/卖出",
    "ai_commentary": "详细的基本面分析，包括财务健康度、成长性、估值合理性、关键风险提示"
}}

其中score为0-100的基本面评分，请基于获取到的真实数据综合评估。"""}
            ]

            content, tool_log, error = chat_with_tools(
                client, messages, FUNDAMENTAL_TOOLS_SCHEMA,
                max_tool_rounds=2, temperature=0.7
            )

            if error:
                logger.warning(f"基本面分析AI调用失败: {error}，降级到硬编码模式")
                return _fallback_analyze(state)

            # 解析AI输出的结构化JSON
            result = _parse_ai_result(content)
            result['tool_calls'] = tool_log

            return {
                'fundamental_report': result,
                'progress': 25.0,
                'execution_log': [
                    {'agent': '基本面分析师', 'status': 'success', 'mode': 'ai_agent', 'tools_used': len(tool_log)}
                ]
            }

        except Exception as e:
            logger.error(f"基本面分析失败: {e}，降级到硬编码模式")
            try:
                return _fallback_analyze(state)
            except Exception as fallback_err:
                logger.error(f"基本面分析降级也失败: {fallback_err}")
                return {
                    'fundamental_report': {'error': str(e)},
                    'execution_log': [
                        {'agent': '基本面分析师', 'status': 'failed', 'error': str(e)}
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
    logger.warning("基本面分析JSON解析失败，使用纯文本模式")
    return {
        'score': 50,
        'ai_commentary': content,
        'recommendation': '观望',
        'parse_warning': 'AI输出非标准JSON，已降级为纯文本'
    }


def _fallback_analyze(state: Dict[str, Any]) -> Dict[str, Any]:
    """AI不可用时的降级分析（保留原硬编码逻辑）"""
    from app.analysis.fundamental_analyzer import FundamentalAnalyzer
    from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

    stock_code = state['stock_code']

    analyzer = FundamentalAnalyzer()
    market_type = state.get('market_type', 'A')

    # [C2] 优先走 AdapterRegistry 多源 (xbrl_financials / us_stock), 失败才回退 analyzer
    financial_data = None
    if market_type == 'US':
        financial_data = _registry_fetch('xbrl_financials', 'get_financials', code=stock_code) \
                         or _registry_fetch('us_stock', 'get_financials', code=stock_code)
    if financial_data is None:
        financial_data = analyzer.get_financial_indicators(stock_code)

    # 获取成长性数据 (registry优先 → analyzer兜底)
    growth_data = _registry_fetch('a_stock_kline', 'get_growth_data', code=stock_code)
    if growth_data is None:
        growth_data = analyzer.get_growth_data(stock_code)

    # 计算基本面评分
    score_result = analyzer.calculate_fundamental_score(stock_code)

    result = {
        'financial_indicators': financial_data,
        'growth_data': growth_data,
        'score': score_result
    }

    # 检查是否有错误
    if isinstance(score_result, dict) and 'error' in score_result:
        return {
            'fundamental_report': {'error': score_result['error']},
            'execution_log': [
                {'agent': '基本面分析师', 'status': 'failed', 'mode': 'fallback', 'error': score_result['error']}
            ]
        }

    # 尝试用AI增强注释
    client = get_ai_client()
    if client:
        prompt = f"""你是资深基本面分析师。基于以下财务数据，给出专业分析：

股票代码: {stock_code}

财务指标摘要:
{_summarize_data(financial_data)}

成长性数据摘要:
{_summarize_data(growth_data)}

基本面评分:
{_summarize_data(score_result)}

请给出：
1. 财务健康度评估（偿债能力、盈利能力、运营效率）
2. 成长性分析（营收/利润增长趋势、可持续性）
3. 估值合理性判断（当前估值水平、相对行业位置）
4. 关键财务风险提示"""

        response, error = chat_completion(
            client,
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1200
        )
        if not error:
            result['ai_commentary'] = get_completion_content(response)

    return {
        'fundamental_report': result,
        'progress': 25.0,
        'execution_log': [
            {'agent': '基本面分析师', 'status': 'success', 'mode': 'fallback'}
        ]
    }


def _summarize_data(data: Any) -> str:
    """将数据摘要为字符串，用于AI prompt"""
    if data is None:
        return "无数据"
    if isinstance(data, dict):
        lines = []
        for k, v in list(data.items())[:15]:
            lines.append(f"  {k}: {v}")
        return "\n".join(lines) if lines else "空字典"
    return str(data)[:500]
