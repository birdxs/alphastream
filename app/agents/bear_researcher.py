"""
Input: StockAnalysisState (所有已完成的分析报告) + 历史语义记忆
Output: StockAnalysisState (bear_case已填充) + 保存分析记忆
Pos: 看空研究员Agent，纯LLM驱动，从悲观角度寻找风险因素，带历史记忆注入
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BearResearcherAgent:
    """看空研究员Agent"""

    name = "看空研究员"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """从悲观角度质疑，寻找风险因素"""
        from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

        stock_code = state['stock_code']

        try:
            client = get_ai_client()
            if not client:
                # State定义bear_case为str类型，不能返回dict
                return {
                    'bear_case': 'AI客户端不可用，无法生成看空分析',
                    'execution_log': [
                        {'agent': '看空研究员', 'status': 'failed', 'error': 'AI客户端不可用'}
                    ]
                }

            # 汇总所有已有分析报告
            reports_summary = _compile_reports(state)

            # [R2 Q4 P1 2026-04-15] 串行辩论: 单独提取 bull_case 作为反驳对象
            bull_case_text = state.get('bull_case') or ''
            has_bull_case = bool(bull_case_text and not bull_case_text.startswith('AI'))

            # === 记忆注入（分析前） ===
            memory_context = ""
            try:
                from app.core.agent_memory import get_agent_memory
                memory = get_agent_memory()
                memory_context = memory.get_agent_context(stock_code, '看空研究员')
            except Exception:
                pass

            # [R2 Q4 P1 2026-04-15] 反驳式 prompt: 若 bull_case 已存在, 强制对多方具体论点逐条反驳
            rebuttal_section = ""
            if has_bull_case:
                rebuttal_section = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【必读·多方观点原文】(你必须针对以下具体论点逐条反驳)
{bull_case_text[:1200]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**反驳要求** (极重要):
- 你不是独立看空, 而是在与上述多方辩论
- 必须先识别多方的**3个最强论点**, 然后逐条给出反驳证据
- 反驳格式示例: "多方称XX利好, 但忽视了YY事实/数据, 因此该论点不成立"
- 禁止无视多方论点另起炉灶; 禁止笼统反对不给具体证据
"""

            prompt = f"""你是一位资深的看空研究员（Bear Researcher）。你的职责是从所有可用分析数据中，
找出潜在的风险因素和下跌信号。你要像一个严苛的审计师，质疑每一个乐观假设。

注意：你必须站在悲观角度分析，但分析必须基于事实和数据，不能凭空恐吓。

股票代码: {stock_code}

已有分析报告汇总:
{reports_summary}
{rebuttal_section}
请从以下维度给出看空论据：

1. **对多方观点的针对性反驳**（逐条回应多方最强论点，必须引用原文表述）
2. **核心风险因素**（最严重的2-3个风险）
3. **技术面危险信号**（趋势恶化、形态破位、指标背离）
4. **基本面隐患**（财务风险、增长放缓、估值泡沫）
5. **资金面警告**（主力出逃、资金流出、散户接盘）
6. **舆情/黑天鹅**（利空消息、政策风险、行业逆风）
7. **下行风险评估**（合理的下跌空间估算）
8. **看空置信度**（高/中/低，并说明理由）

请确保分析有据可依，标注数据来源。"""

            # 注入历史记忆到prompt
            if memory_context:
                prompt = f"【历史分析参考】\n{memory_context}\n\n" + prompt

            response, error = chat_completion(
                client,
                [{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=1500
            )

            if error:
                # State定义bear_case为str类型，不能返回dict
                return {
                    'bear_case': f'AI分析失败: {error}',
                    'execution_log': [
                        {'agent': '看空研究员', 'status': 'failed', 'error': str(error)}
                    ]
                }

            bear_analysis = get_completion_content(response)

            # State定义bear_case为str类型，直接返回分析文本
            bear_case_text = bear_analysis if isinstance(bear_analysis, str) else json.dumps(bear_analysis, ensure_ascii=False)

            # === 记忆保存（分析后） ===
            try:
                from app.core.agent_memory import get_agent_memory
                get_agent_memory().save_agent_analysis(stock_code, '看空研究员', bear_case_text[:300])
            except Exception:
                pass

            return {
                'bear_case': bear_case_text,
                'progress': 50.0,
                'execution_log': [
                    {'agent': '看空研究员', 'status': 'success'}
                ]
            }

        except Exception as e:
            logger.error(f"看空分析失败: {e}")
            # State定义bear_case为str类型，不能返回dict
            return {
                'bear_case': f'看空分析失败: {str(e)}',
                'execution_log': [
                    {'agent': '看空研究员', 'status': 'failed', 'error': str(e)}
                ]
            }


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

    # 也包含看多观点，以便看空方进行反驳
    if state.get('bull_case'):
        sections.append(f"【看多观点（需质疑）】\n{_format_report(state['bull_case'])}")

    return "\n\n".join(sections) if sections else "暂无前置分析报告"


def _format_report(report: Any) -> str:
    """格式化单个报告为可读文本"""
    if report is None:
        return "无数据"
    if isinstance(report, dict):
        if 'ai_commentary' in report:
            return report['ai_commentary'][:800]
        if 'analysis' in report:
            return report['analysis'][:800]
        lines = []
        for k, v in list(report.items())[:12]:
            if k not in ('flow_data', 'news_items', 'financial_indicators'):
                lines.append(f"  {k}: {v}")
        return "\n".join(lines) if lines else "空报告"
    return str(report)[:500]
