"""
Input: StockAnalysisState (stock_code, market_type, 前置分析结果)
Output: StockAnalysisState (risk_assessment已填充，含AI风险评分/等级/多维度风险分析/工具调用记录)
Pos: 风险管理Agent，通过Function Calling让AI自主获取数据并评估风险，降级时使用硬编码模式
[E3 2026-04-15] 接入 AdapterRegistry 另类风险源:
  - commodity_shipping (BDI异常→供应链风险) + corporate_entity (股权变动风险)
  - 失败降级为空, 不影响原AI function-calling 路径

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
        logger.info(f"[RiskManager] registry fetch {domain}.{method} 降级失败: {type(e).__name__}: {e}")
        return None


def _collect_alt_risk_context(stock_code: str) -> str:
    """拉取航运BDI异常 + 企业实体股权变动, 作为另类风险信号。"""
    parts = []
    shipping = _registry_fetch('commodity_shipping', 'get_bdi_index')
    if shipping:
        parts.append(f"【BDI航运指数】{str(shipping)[:250]}")
    entity = _registry_fetch('corporate_entity', 'search_entity', query=stock_code)
    if entity:
        parts.append(f"【企业股权实体】{str(entity)[:250]}")
    return "\n".join(parts)


class RiskManagerAgent:
    """风险管理Agent - AI通过Function Calling自主获取数据并评估风险"""

    name = "风险管理官"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """执行风险评估（AI Agent模式，降级时使用硬编码模式）"""
        from app.core.ai_client import get_ai_client, chat_with_tools
        from app.core.tools import RISK_TOOLS_SCHEMA, TECHNICAL_TOOLS_SCHEMA

        stock_code = state['stock_code']
        market_type = state.get('market_type', 'A')

        try:
            client = get_ai_client()
            if not client:
                return _fallback_analyze(state)

            # 构建系统提示，注入前置分析结果作为上下文
            system_prompt = _build_system_prompt(state)

            # 合并风险工具和技术工具schema，让AI可以查询更多维度数据
            tools_schema = RISK_TOOLS_SCHEMA + TECHNICAL_TOOLS_SCHEMA

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"""请对股票 {stock_code}（市场：{market_type}）进行全面风险评估。

请先使用工具获取该股票的风险数据和技术指标，然后基于真实数据给出专业的风险分析。

请严格以如下JSON格式输出（不要添加任何markdown代码块标记）：
{{
    "risk_score": 35,
    "risk_level": "低风险/中低风险/中等风险/中高风险/高风险",
    "volatility_risk": "低/中/高",
    "trend_risk": "低/中/高",
    "reversal_risk": "低/中/高",
    "volume_risk": "低/中/高",
    "max_drawdown_risk": "低/中/高",
    "risk_factors": [
        "风险因素1描述",
        "风险因素2描述"
    ],
    "stop_loss_suggestion": 95.0,
    "position_suggestion": "轻仓/半仓/重仓",
    "recommendation": "买入/持有/减仓/卖出",
    "ai_commentary": "详细的风险评估说明，包括各维度风险分析、止损建议、仓位管理建议"
}}

其中risk_score为0-100的风险分数（越高越危险），请基于获取到的真实数据综合评估。"""}
            ]

            content, tool_log, error = chat_with_tools(
                client, messages, tools_schema,
                max_tool_rounds=3, temperature=0.7
            )

            if error:
                logger.warning(f"风险评估AI调用失败: {error}，降级到硬编码模式")
                return _fallback_analyze(state)

            # 解析AI输出的结构化JSON
            result = _parse_ai_result(content)
            result['tool_calls'] = tool_log

            return {
                'risk_assessment': result,
                'progress': 70.0,
                'execution_log': [
                    {'agent': '风险管理官', 'status': 'success', 'mode': 'ai_agent', 'tools_used': len(tool_log)}
                ]
            }

        except Exception as e:
            logger.error(f"风险评估失败: {e}，降级到硬编码模式")
            try:
                return _fallback_analyze(state)
            except Exception as fallback_err:
                logger.error(f"风险评估降级也失败: {fallback_err}")
                return {
                    'risk_assessment': {'error': str(e)},
                    'execution_log': [
                        {'agent': '风险管理官', 'status': 'failed', 'error': str(e)}
                    ]
                }


def _build_system_prompt(state: Dict[str, Any]) -> str:
    """构建系统提示词，注入前置分析结果作为上下文"""
    base_prompt = (
        "你是资深风险管理官，具备查询股票风险数据和技术指标的工具。"
        "请使用工具获取真实数据后，基于数据进行多维度风险评估。"
        "风险评分标准：0-100分，越高越危险。"
        "0-20=低风险，20-40=中低风险，40-60=中等风险，60-80=中高风险，80-100=高风险。"
        "评估维度包括：波动率风险、趋势风险、反转风险、成交量异常风险、最大回撤风险。"
    )

    # 注入前置分析结果作为上下文参考
    context_parts = []

    technical_report = state.get('technical_report')
    if technical_report and isinstance(technical_report, dict) and 'error' not in technical_report:
        tech_summary = f"技术评分: {technical_report.get('score', 'N/A')}, 趋势: {technical_report.get('trend', 'N/A')}"
        context_parts.append(f"技术分析结果: {tech_summary}")

    fundamental_report = state.get('fundamental_report')
    if fundamental_report and isinstance(fundamental_report, dict) and 'error' not in fundamental_report:
        fund_summary = f"基本面评分: {fundamental_report.get('score', 'N/A')}"
        context_parts.append(f"基本面分析结果: {fund_summary}")

    capital_flow_report = state.get('capital_flow_report')
    if capital_flow_report and isinstance(capital_flow_report, dict) and 'error' not in capital_flow_report:
        cap_summary = f"资金面评分: {capital_flow_report.get('score', 'N/A')}"
        context_parts.append(f"资金流向分析结果: {cap_summary}")

    if context_parts:
        base_prompt += "\n\n【前置分析结果参考】\n" + "\n".join(context_parts)
        base_prompt += "\n请结合以上前置分析结果，综合评估该股票的整体风险水平。"

    # === Registry 另类风险源 (双保险) ===
    try:
        stock_code = state.get('stock_code', '')
        if stock_code:
            alt_ctx = _collect_alt_risk_context(stock_code)
            if alt_ctx:
                base_prompt += "\n\n【另类风险信号 (供应链/股权)】\n" + alt_ctx
    except Exception as e:
        logger.info(f"[RiskManager] 另类风险聚合失败, 跳过: {type(e).__name__}")

    return base_prompt


def _parse_ai_result(content: str) -> Dict[str, Any]:
    """解析AI输出的JSON结果，支持处理markdown代码块"""
    if not content:
        return {
            'risk_score': 50, 'risk_level': '中等风险',
            'ai_commentary': '未获取到AI分析结果', 'recommendation': '观望'
        }

    # 尝试从markdown代码块中提取JSON
    json_str = content
    code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', content, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1).strip()

    # 尝试直接解析JSON
    try:
        result = json.loads(json_str)
        if isinstance(result, dict):
            result.setdefault('risk_score', 50)
            result.setdefault('risk_level', '中等风险')
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
                result.setdefault('risk_score', 50)
                result.setdefault('risk_level', '中等风险')
                result.setdefault('ai_commentary', content)
                result.setdefault('recommendation', '观望')
                return result
        except json.JSONDecodeError:
            pass

    # JSON解析完全失败
    logger.warning("风险评估JSON解析失败，使用纯文本模式")
    return {
        'risk_score': 50,
        'risk_level': '中等风险',
        'ai_commentary': content,
        'recommendation': '观望',
        'parse_warning': 'AI输出非标准JSON，已降级为纯文本'
    }


def _fallback_analyze(state: Dict[str, Any]) -> Dict[str, Any]:
    """AI不可用时的降级分析（保留原硬编码逻辑）"""
    from app.analysis.risk_monitor import RiskMonitor
    from app.analysis.stock_analyzer import StockAnalyzer

    stock_code = state['stock_code']
    market_type = state.get('market_type', 'A')

    analyzer = StockAnalyzer()
    rm = RiskMonitor(analyzer)
    result = rm.analyze_stock_risk(stock_code, market_type)

    return {
        'risk_assessment': result or {'error': '风险评估未返回结果'},
        'progress': 70.0,
        'execution_log': [
            {'agent': '风险管理官', 'status': 'success' if result else 'partial', 'mode': 'fallback'}
        ]
    }
