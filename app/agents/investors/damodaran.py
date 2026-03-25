"""
Input: StockAnalysisState (所有已完成的分析报告)
Output: Dict 包含 investor_damodaran 字段 (recommendation + reasoning)
Pos: app/agents/investors/damodaran.py - 达摩达兰风格投资者人格Agent

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DamodaranAgent:
    """阿斯瓦斯·达摩达兰风格投资分析Agent

    核心投资哲学：
    - 估值大师（Dean of Valuation）：一切投资决策建立在严谨估值之上
    - DCF模型：折现现金流是估值核心方法
    - 关注增长率、资本成本（WACC）、再投资回报率（ROIC）
    - 用数据和模型说话，量化驱动
    - 区分价格和价值：市场给的是价格，分析师算的是价值
    - 故事与数字结合：好的估值既有叙事逻辑也有数字支撑
    """

    name = "达摩达兰投资风格分析"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """以达摩达兰估值框架分析股票"""
        from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

        stock_code = state.get('stock_code', '未知')

        try:
            client = get_ai_client()
            if not client:
                return _error_result('AI客户端不可用', state)

            reports_summary = _compile_reports(state)

            prompt = f"""你是阿斯瓦斯·达摩达兰（Aswath Damodaran），纽约大学斯特恩商学院金融学教授，被誉为"估值教父"。
请严格按照达摩达兰的估值框架对以下股票进行分析。

## 你的核心分析框架

1. **企业叙事（Narrative）**：
   - 这家公司的"故事"是什么？它在解决什么问题？
   - 总可寻址市场（TAM）有多大？市场份额预期如何？
   - 叙事是否可信？是否有数据支撑？

2. **DCF估值关键变量**：
   - 收入增长率：未来5-10年的增长轨迹如何？基于什么驱动力？
   - 经营利润率：目标利润率是多少？当前利润率到目标利润率的路径？
   - 再投资需求：支撑增长需要多少资本投入？销售/资本比率如何？
   - 资本成本（WACC）：考虑企业风险等级，合理的折现率是多少？
   - 终值假设：长期稳态增长率假设？

3. **价值驱动因素分解**：
   - 增长的价值：增长是否创造价值？（ROIC > WACC才有价值创造）
   - 现有资产价值：当前业务本身值多少？
   - 期权价值：是否有未被定价的增长期权？

4. **估值交叉验证**：
   - 相对估值：与同行业可比公司的估值倍数比较（PE, EV/EBITDA, PS）
   - 如果相对估值和内在估值方向不一致，解释原因

5. **不确定性与情景分析**：
   - 乐观/基准/悲观三种情景下的估值范围
   - 关键假设的敏感度分析

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
    "narrative": "企业叙事概述（100字以内）",
    "dcf_variables": {{
        "revenue_growth_estimate": "预估收入增长率",
        "target_margin": "目标经营利润率",
        "wacc_estimate": "估计资本成本",
        "terminal_growth": "终值增长率假设"
    }},
    "valuation_assessment": {{
        "intrinsic_value_vs_price": "高估X%/低估X%/合理",
        "relative_valuation": "相对同行 高估/低估/合理",
        "scenario_range": "悲观价XXX - 基准价XXX - 乐观价XXX"
    }},
    "value_creation_check": "ROIC是否大于WACC的判断",
    "damodaran_verdict": "基于估值的最终判断（80字以内）",
    "key_assumption_risk": "最关键的假设风险"
}}"""

            response, error = chat_completion(
                client,
                [{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=1500
            )

            if error:
                return _error_result(f'AI分析失败: {error}', state)

            content = get_completion_content(response)
            if not content:
                return _error_result('AI未返回分析结果', state)

            analysis = _parse_json_response(content)

            return {
                'investor_damodaran': {
                    'analyst': '达摩达兰风格',
                    'recommendation': analysis.get('recommendation', 'HOLD'),
                    'confidence': analysis.get('confidence', '中'),
                    'reasoning': analysis.get('reasoning', content[:500]),
                    'details': analysis,
                    'raw_response': content
                },
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '达摩达兰投资风格分析', 'status': 'success'}
                ]
            }

        except Exception as e:
            logger.error(f"达摩达兰风格分析失败: {e}")
            return _error_result(str(e), state)


def _error_result(error_msg: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """构建错误返回结果"""
    return {
        'investor_damodaran': {
            'analyst': '达摩达兰风格',
            'recommendation': 'HOLD',
            'confidence': '低',
            'reasoning': f'分析失败: {error_msg}',
            'error': error_msg
        },
        'execution_log': state.get('execution_log', []) + [
            {'agent': '达摩达兰投资风格分析', 'status': 'failed', 'error': error_msg}
        ]
    }


def _parse_json_response(content: str) -> Dict[str, Any]:
    """从AI响应中解析JSON"""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
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
