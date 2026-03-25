"""
Input: StockAnalysisState (所有已完成的分析报告)
Output: Dict 包含 investor_buffett 字段 (recommendation + reasoning)
Pos: app/agents/investors/buffett.py - 巴菲特风格投资者人格Agent

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BuffettAgent:
    """巴菲特风格投资分析Agent

    核心投资哲学：
    - 护城河（Moat）：企业持久竞争优势
    - 管理层质量：诚实、能干、为股东着想
    - 内在价值：安全边际 (Margin of Safety)
    - 长期持有：买入优质企业，长期陪伴成长
    - 能力圈：只投资自己理解的生意
    """

    name = "巴菲特投资风格分析"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """以巴菲特投资哲学分析股票"""
        from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

        stock_code = state.get('stock_code', '未知')

        try:
            client = get_ai_client()
            if not client:
                return _error_result('AI客户端不可用', state)

            reports_summary = _compile_reports(state)

            prompt = f"""你是沃伦·巴菲特（Warren Buffett），世界上最成功的价值投资者之一。
请严格按照巴菲特的投资哲学对以下股票进行分析。

## 你的核心投资原则

1. **护城河分析**：该企业是否拥有持久的竞争优势？品牌、专利、网络效应、转换成本、成本优势？护城河是在变宽还是变窄？
2. **管理层质量**：管理层是否诚实正直？是否理性配置资本？是否坦诚面对股东？薪酬是否合理？
3. **内在价值与安全边际**：基于自由现金流的内在价值估算是多少？当前价格相对内在价值有多少安全边际？你要求至少25%的安全边际。
4. **商业模式可理解性**：这个生意是否在你的能力圈之内？商业模式是否简单易懂、可预测？
5. **长期持有价值**：10年后这家企业会比今天更强大吗？它的盈利是否可持续增长？
6. **财务健康度**：ROE是否持续高于15%？负债率是否合理？自由现金流是否充沛？利润率趋势如何？

## 待分析股票

股票代码: {stock_code}

## 已有分析数据

{reports_summary}

## 输出要求

请以JSON格式输出你的分析结论（不要输出markdown代码块标记，直接输出JSON）：
{{
    "recommendation": "BUY/SELL/HOLD",
    "confidence": "高/中/低",
    "reasoning": "你的核心投资论据（200字以内）",
    "moat_analysis": "护城河评估（100字以内）",
    "intrinsic_value_assessment": "内在价值与安全边际评估（100字以内）",
    "management_quality": "管理层评价（80字以内）",
    "key_metrics": {{
        "roe_acceptable": true/false,
        "debt_acceptable": true/false,
        "fcf_positive": true/false,
        "moat_strength": "强/中/弱/无"
    }},
    "buffett_would_buy": true/false,
    "holding_period": "建议持有期限"
}}"""

            response, error = chat_completion(
                client,
                [{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=1500
            )

            if error:
                return _error_result(f'AI分析失败: {error}', state)

            content = get_completion_content(response)
            if not content:
                return _error_result('AI未返回分析结果', state)

            # 解析JSON结果
            analysis = _parse_json_response(content)

            return {
                'investor_buffett': {
                    'analyst': '巴菲特风格',
                    'recommendation': analysis.get('recommendation', 'HOLD'),
                    'confidence': analysis.get('confidence', '中'),
                    'reasoning': analysis.get('reasoning', content[:500]),
                    'details': analysis,
                    'raw_response': content
                },
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '巴菲特投资风格分析', 'status': 'success'}
                ]
            }

        except Exception as e:
            logger.error(f"巴菲特风格分析失败: {e}")
            return _error_result(str(e), state)


def _error_result(error_msg: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """构建错误返回结果"""
    return {
        'investor_buffett': {
            'analyst': '巴菲特风格',
            'recommendation': 'HOLD',
            'confidence': '低',
            'reasoning': f'分析失败: {error_msg}',
            'error': error_msg
        },
        'execution_log': state.get('execution_log', []) + [
            {'agent': '巴菲特投资风格分析', 'status': 'failed', 'error': error_msg}
        ]
    }


def _parse_json_response(content: str) -> Dict[str, Any]:
    """从AI响应中解析JSON"""
    try:
        # 尝试直接解析
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    # 尝试提取JSON块
    try:
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            return json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        pass
    return {'reasoning': content[:500]}


def _compile_reports(state: Dict[str, Any]) -> str:
    """汇总所有已完成的分析报告"""
    sections = []

    if state.get('technical_report'):
        sections.append(f"【技术分析】\n{_format_report(state['technical_report'])}")

    if state.get('fundamental_report'):
        sections.append(f"【基本面分析】\n{_format_report(state['fundamental_report'])}")

    if state.get('capital_flow_report'):
        sections.append(f"【资金流向】\n{_format_report(state['capital_flow_report'])}")

    if state.get('sentiment_report'):
        sections.append(f"【舆情分析】\n{_format_report(state['sentiment_report'])}")

    return "\n\n".join(sections) if sections else "暂无前置分析报告"


def _format_report(report: Any) -> str:
    """格式化单个报告为可读文本"""
    if report is None:
        return "无数据"
    if isinstance(report, dict):
        if 'ai_commentary' in report:
            return str(report['ai_commentary'])[:800]
        lines = []
        for k, v in list(report.items())[:12]:
            if k not in ('flow_data', 'news_items', 'financial_indicators'):
                lines.append(f"  {k}: {v}")
        return "\n".join(lines) if lines else "空报告"
    return str(report)[:500]
