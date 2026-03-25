"""
Input: StockAnalysisState (所有已完成的分析报告)
Output: Dict 包含 investor_munger 字段 (recommendation + reasoning)
Pos: app/agents/investors/munger.py - 芒格风格投资者人格Agent

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class MungerAgent:
    """查理·芒格风格投资分析Agent

    核心投资哲学：
    - 反向思维（Inversion）：先想怎么会失败，再考虑能否成功
    - 多元思维模型（Mental Models）：跨学科思维解决问题
    - 避免愚蠢比追求聪明更重要
    - 以合理价格买入优质企业，而非以低价买入平庸企业
    - 检查清单法（Checklist）：系统性排除风险
    """

    name = "芒格投资风格分析"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """以芒格投资哲学分析股票"""
        from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

        stock_code = state.get('stock_code', '未知')

        try:
            client = get_ai_client()
            if not client:
                return _error_result('AI客户端不可用', state)

            reports_summary = _compile_reports(state)

            prompt = f"""你是查理·芒格（Charlie Munger），沃伦·巴菲特的长期合作伙伴，以逆向思维和多元思维模型闻名。
请严格按照芒格的投资哲学对以下股票进行分析。

## 你的核心分析框架

1. **反向思维（Inversion）**：
   - 这笔投资怎么可能失败？列出最可能的3个失败场景。
   - 什么情况下会永久性亏损？
   - "告诉我我会死在哪里，我就不去那里。"

2. **多元思维模型检验**：
   - 心理学视角：市场对该股是否存在偏见？锚定效应？从众心理？
   - 经济学视角：供需关系、规模效应、竞争格局如何？
   - 数学/概率视角：期望值分析，赔率是否有利？
   - 生物学/进化视角：企业是否在适应环境变化？

3. **愚蠢行为检查清单**：
   - 是否追高？是否被故事驱动而非数据？
   - 管理层是否有不诚实记录？
   - 是否存在激励机制扭曲（incentive misalignment）？
   - 是否存在"虚假精确"（用精确数字掩盖不确定性）？

4. **企业质量评估**：
   - 这是一流企业还是二流企业？
   - "以合理价格买入伟大公司远好于以低价买入平庸公司"
   - 企业文化和组织能力如何？

5. **能力圈与诚实评估**：
   - 你是否真正理解这门生意？
   - 不理解就承认，不装懂。

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
    "inversion_analysis": "反向思维分析——最大的3个风险（150字以内）",
    "mental_models_check": "多元思维模型评估要点（150字以内）",
    "stupidity_checklist": {{
        "chasing_high": true/false,
        "story_driven": true/false,
        "management_dishonesty": true/false,
        "incentive_misalignment": true/false
    }},
    "quality_grade": "A/B/C/D/F",
    "munger_would_approve": true/false,
    "key_warning": "最需要注意的一点"
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

            analysis = _parse_json_response(content)

            return {
                'investor_munger': {
                    'analyst': '芒格风格',
                    'recommendation': analysis.get('recommendation', 'HOLD'),
                    'confidence': analysis.get('confidence', '中'),
                    'reasoning': analysis.get('reasoning', content[:500]),
                    'details': analysis,
                    'raw_response': content
                },
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '芒格投资风格分析', 'status': 'success'}
                ]
            }

        except Exception as e:
            logger.error(f"芒格风格分析失败: {e}")
            return _error_result(str(e), state)


def _error_result(error_msg: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """构建错误返回结果"""
    return {
        'investor_munger': {
            'analyst': '芒格风格',
            'recommendation': 'HOLD',
            'confidence': '低',
            'reasoning': f'分析失败: {error_msg}',
            'error': error_msg
        },
        'execution_log': state.get('execution_log', []) + [
            {'agent': '芒格投资风格分析', 'status': 'failed', 'error': error_msg}
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
