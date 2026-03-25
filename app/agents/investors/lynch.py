"""
Input: StockAnalysisState (所有已完成的分析报告)
Output: Dict 包含 investor_lynch 字段 (recommendation + reasoning)
Pos: app/agents/investors/lynch.py - 彼得·林奇风格投资者人格Agent

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class LynchAgent:
    """彼得·林奇风格投资分析Agent

    核心投资哲学：
    - PEG估值法：PE/盈利增长率，PEG < 1 为低估
    - 六大股票分类：缓慢成长、稳定成长、快速成长、周期、困境反转、隐蔽资产
    - 日常生活中发现投资机会（Buy what you know）
    - 关注盈利增长的可持续性
    - 重视实地调研和行业理解
    """

    name = "彼得林奇投资风格分析"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """以彼得·林奇投资哲学分析股票"""
        from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

        stock_code = state.get('stock_code', '未知')

        try:
            client = get_ai_client()
            if not client:
                return _error_result('AI客户端不可用', state)

            reports_summary = _compile_reports(state)

            prompt = f"""你是彼得·林奇（Peter Lynch），历史上最成功的共同基金经理之一，掌管富达麦哲伦基金期间年化回报29%。
请严格按照林奇的投资哲学对以下股票进行分析。

## 你的核心分析框架

1. **股票分类（六大类型，选择一个最匹配的）**：
   - 缓慢成长股（Slow Growers）：成熟大型公司，增长率低于GDP，高分红
   - 稳定成长股（Stalwarts）：大型优质公司，年增长10-12%，经济衰退时有防御性
   - 快速成长股（Fast Growers）：小型进取公司，年增长20-50%，最大回报潜力但风险也最大
   - 周期股（Cyclicals）：盈利随经济周期波动，时机判断是关键
   - 困境反转股（Turnarounds）：经历困难但有望复苏的公司
   - 隐蔽资产股（Asset Plays）：市场未充分认识到的隐性资产价值

2. **PEG估值法**：
   - PEG = PE / 年盈利增长率（%）
   - PEG < 1：低估，有吸引力
   - PEG = 1-2：合理
   - PEG > 2：高估
   - 根据已有基本面数据估算PEG

3. **两分钟故事（Two-Minute Drill）**：
   - 用2-3句话说清楚为什么看好（或不看好）这只股票
   - 如果说不清楚，就不应该买

4. **关键财务指标检查**：
   - 盈利增长率是否稳定？
   - 负债率是否健康？（特别关注银行和周期股）
   - 现金流是否充沛？
   - 存货和应收账款趋势？

5. **催化剂与时机**：
   - 什么事件/因素可能推动股价上涨？
   - 机构持股比例？（林奇偏好机构持股低的股票，意味着被忽视）

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
    "stock_category": "缓慢成长/稳定成长/快速成长/周期/困境反转/隐蔽资产",
    "peg_assessment": {{
        "estimated_pe": "估计值或已知值",
        "estimated_growth_rate": "估计年增长率%",
        "estimated_peg": "估计PEG值",
        "peg_verdict": "低估/合理/高估"
    }},
    "two_minute_story": "用2-3句话说清楚投资逻辑",
    "catalyst": "最可能的上涨催化剂",
    "lynch_score": "1-10分（10分最佳）",
    "key_concern": "最大的担忧"
}}"""

            response, error = chat_completion(
                client,
                [{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500
            )

            if error:
                return _error_result(f'AI分析失败: {error}', state)

            content = get_completion_content(response)
            if not content:
                return _error_result('AI未返回分析结果', state)

            analysis = _parse_json_response(content)

            return {
                'investor_lynch': {
                    'analyst': '彼得林奇风格',
                    'recommendation': analysis.get('recommendation', 'HOLD'),
                    'confidence': analysis.get('confidence', '中'),
                    'reasoning': analysis.get('reasoning', content[:500]),
                    'details': analysis,
                    'raw_response': content
                },
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '彼得林奇投资风格分析', 'status': 'success'}
                ]
            }

        except Exception as e:
            logger.error(f"彼得林奇风格分析失败: {e}")
            return _error_result(str(e), state)


def _error_result(error_msg: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """构建错误返回结果"""
    return {
        'investor_lynch': {
            'analyst': '彼得林奇风格',
            'recommendation': 'HOLD',
            'confidence': '低',
            'reasoning': f'分析失败: {error_msg}',
            'error': error_msg
        },
        'execution_log': state.get('execution_log', []) + [
            {'agent': '彼得林奇投资风格分析', 'status': 'failed', 'error': error_msg}
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
