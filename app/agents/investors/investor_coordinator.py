# -*- coding: utf-8 -*-
"""
Input: StockAnalysisState (所有已完成的分析报告)
Output: Dict 包含 investor_consensus 字段 (AI综合研判 + 投票统计辅助)
Pos: app/agents/investors/investor_coordinator.py - 投资者人格协调器，AI驱动共识构建

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
import time
from typing import Dict, Any, List
from collections import Counter

logger = logging.getLogger(__name__)


class InvestorCoordinator:
    """投资者人格协调器

    职责：
    - 依次调用4个投资者人格Agent（巴菲特、芒格、林奇、达摩达兰）
    - 汇总各人格的建议
    - AI综合研判：权衡论据逻辑强度，而非简单投票计数
    - AI不可用时降级到基础投票机制
    - 返回综合建议
    """

    name = "投资者人格协调器"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """协调所有投资者人格Agent并汇总建议"""
        from .buffett import BuffettAgent
        from .munger import MungerAgent
        from .lynch import LynchAgent
        from .damodaran import DamodaranAgent

        stock_code = state.get('stock_code', '未知')
        results = {}
        execution_log = list(state.get('execution_log', []))

        # 依次调用4个投资者人格Agent
        agents = [
            ('buffett', BuffettAgent),
            ('munger', MungerAgent),
            ('lynch', LynchAgent),
            ('damodaran', DamodaranAgent),
        ]

        for key, agent_cls in agents:
            try:
                logger.info(f"[投资者协调器] 调用 {agent_cls.name}...")
                result = agent_cls.analyze(state)
                investor_key = f'investor_{key}'

                if investor_key in result:
                    results[investor_key] = result[investor_key]

                # 合并execution_log
                if 'execution_log' in result:
                    for entry in result['execution_log']:
                        if entry not in execution_log:
                            execution_log.append(entry)

            except Exception as e:
                logger.error(f"[投资者协调器] {agent_cls.name} 执行异常: {e}")
                results[f'investor_{key}'] = {
                    'analyst': agent_cls.name,
                    'recommendation': 'HOLD',
                    'confidence': '低',
                    'reasoning': f'执行异常: {str(e)}',
                    'error': str(e)
                }
                execution_log.append({
                    'agent': agent_cls.name,
                    'status': 'failed',
                    'error': str(e)
                })

        # AI驱动的共识构建
        consensus = _build_consensus(results, stock_code)

        execution_log.append({
            'agent': '投资者人格协调器',
            'status': 'success',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })

        # 将各投资者结果打包到State定义的investor_opinions字段中
        investor_opinions = {
            'buffett': results.get('investor_buffett', {}),
            'munger': results.get('investor_munger', {}),
            'lynch': results.get('investor_lynch', {}),
            'damodaran': results.get('investor_damodaran', {}),
        }

        return {
            'investor_opinions': investor_opinions,
            'investor_consensus': consensus,
            'progress': 80.0,
            'execution_log': execution_log
        }


def _compute_vote_stats(results: Dict[str, Any]) -> Dict[str, Any]:
    """纯统计投票结果（不做决策，仅作为AI参考数据）"""
    recommendations: List[str] = []
    individual_views: List[Dict[str, Any]] = []

    for key, result in results.items():
        if not key.startswith('investor_'):
            continue

        rec = result.get('recommendation', 'HOLD').upper()
        # 标准化推荐
        if rec not in ('BUY', 'SELL', 'HOLD'):
            rec = 'HOLD'

        recommendations.append(rec)
        individual_views.append({
            'analyst': result.get('analyst', key),
            'recommendation': rec,
            'confidence': result.get('confidence', '中'),
            'reasoning': result.get('reasoning', '无')[:200]
        })

    if not recommendations:
        return {
            'recommendations': [],
            'individual_views': [],
            'vote_count': {},
            'total_votes': 0,
            'majority_rec': 'HOLD',
            'majority_count': 0,
            'agreement_ratio': 0.0
        }

    vote_count = Counter(recommendations)
    total_votes = len(recommendations)
    majority_rec, majority_count = vote_count.most_common(1)[0]
    agreement_ratio = majority_count / total_votes

    return {
        'recommendations': recommendations,
        'individual_views': individual_views,
        'vote_count': dict(vote_count),
        'total_votes': total_votes,
        'majority_rec': majority_rec,
        'majority_count': majority_count,
        'agreement_ratio': round(agreement_ratio, 2)
    }


def _collect_investor_analyses(results: Dict[str, Any]) -> str:
    """收集所有投资者的完整分析文本，供AI综合研判"""
    rec_cn = {'BUY': '买入', 'SELL': '卖出', 'HOLD': '持有'}
    sections = []

    investor_labels = {
        'investor_buffett': '沃伦·巴菲特（价值投资：护城河、安全边际、长期持有）',
        'investor_munger': '查理·芒格（反向思维：多元思维模型、避免愚蠢、风险规避）',
        'investor_lynch': '彼得·林奇（成长投资：PEG估值、六大股票分类、实地调研）',
        'investor_damodaran': '阿斯沃斯·达摩达兰（量化估值：DCF、叙事+数字、风险溢价）',
    }

    for key, result in results.items():
        if not key.startswith('investor_'):
            continue

        label = investor_labels.get(key, key)
        rec = result.get('recommendation', 'HOLD').upper()
        rec_text = rec_cn.get(rec, rec)
        confidence = result.get('confidence', '中')
        reasoning = result.get('reasoning', '无分析')

        # 收集关键指标（如果有）
        key_metrics = result.get('key_metrics', {})
        metrics_text = ""
        if key_metrics:
            metrics_text = f"\n  关键指标: {json.dumps(key_metrics, ensure_ascii=False, default=str)}"

        sections.append(
            f"【{label}】\n"
            f"  建议: {rec_text} | 信心: {confidence}\n"
            f"  分析: {reasoning}{metrics_text}"
        )

    return "\n\n".join(sections)


def _build_consensus(results: Dict[str, Any], stock_code: str) -> Dict[str, Any]:
    """AI驱动的投资者共识构建

    先做基础投票统计作为参考，再交由AI综合研判。
    AI不可用时降级到基础投票机制。
    """
    from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

    # 1. 基础投票统计（作为参考数据，不作为最终决策）
    vote_stats = _compute_vote_stats(results)

    if not vote_stats['recommendations']:
        return {
            'stock_code': stock_code,
            'final_recommendation': 'HOLD',
            'consensus_confidence': '低',
            'consensus_reasoning': '无有效投资者分析结果',
            'vote_summary': {},
            'individual_views': [],
            'agreement_level': '无数据'
        }

    # 2. 收集所有投资者的完整分析
    investor_analyses = _collect_investor_analyses(results)

    # 3. AI综合研判
    client = get_ai_client()
    if client:
        vote_summary_text = json.dumps(vote_stats['vote_count'], ensure_ascii=False)
        prompt = f"""你是首席投资策略官。以下是4位顶级投资者对股票 {stock_code} 的独立分析：

{investor_analyses}

基础投票统计：{vote_summary_text}

请综合评估所有投资者的分析，注意：
1. 不要简单投票计数，要权衡每个投资者论据的逻辑强度和数据支撑
2. 巴菲特侧重护城河和内在价值，芒格侧重风险和反向思维，林奇侧重PEG和成长，达摩达兰侧重DCF估值
3. 如果观点分歧，分析分歧的根本原因
4. 给出你作为首席策略官的最终综合判断

请以JSON格式输出（不要包含```json标记，直接输出JSON）：
{{
    "final_recommendation": "BUY/SELL/HOLD（三选一）",
    "consensus_confidence": "高/中/低",
    "agreement_level": "强共识/多数一致/建设性分歧",
    "consensus_reasoning": "200字以内的综合分析理由",
    "key_agreements": ["投资者们一致认同的要点"],
    "key_disagreements": ["主要分歧点及其原因"],
    "weight_analysis": "各投资者观点的权重分析（谁的分析更有说服力，为什么）",
    "risk_warnings": ["综合风险提醒"]
}}"""

        try:
            response, error = chat_completion(
                client,
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500
            )
            if not error:
                content = get_completion_content(response)
                if content:
                    ai_result = _parse_ai_consensus(content)
                    if ai_result:
                        # AI结果与投票统计合并
                        ai_result['stock_code'] = stock_code
                        ai_result['vote_summary'] = vote_stats['vote_count']
                        ai_result['total_votes'] = vote_stats['total_votes']
                        ai_result['agreement_ratio'] = vote_stats['agreement_ratio']
                        ai_result['individual_views'] = vote_stats['individual_views']
                        ai_result['ai_driven'] = True
                        logger.info(f"[投资者协调器] AI综合研判完成: {ai_result.get('final_recommendation')}")
                        return ai_result
            else:
                logger.warning(f"[投资者协调器] AI调用失败，降级到投票机制: {error}")
        except Exception as e:
            logger.warning(f"[投资者协调器] AI共识构建异常，降级到投票机制: {e}")

    # fallback: AI不可用，退回到基础投票机制
    logger.info("[投资者协调器] 使用降级投票机制构建共识")
    return _fallback_consensus(vote_stats, results, stock_code)


def _parse_ai_consensus(content: str) -> Dict[str, Any]:
    """解析AI返回的共识JSON，带容错处理"""
    try:
        # 清理可能的markdown代码块标记
        text = content.strip()
        if text.startswith('```'):
            # 移除 ```json 和 ``` 包裹
            lines = text.split('\n')
            lines = [l for l in lines if not l.strip().startswith('```')]
            text = '\n'.join(lines)

        result = json.loads(text)

        # 校验必需字段并标准化
        final_rec = result.get('final_recommendation', 'HOLD').upper()
        if final_rec not in ('BUY', 'SELL', 'HOLD'):
            final_rec = 'HOLD'

        confidence = result.get('consensus_confidence', '中')
        if confidence not in ('高', '中', '低'):
            confidence = '中'

        agreement = result.get('agreement_level', '多数一致')
        if agreement not in ('强共识', '多数一致', '建设性分歧'):
            agreement = '多数一致'

        return {
            'final_recommendation': final_rec,
            'consensus_confidence': confidence,
            'agreement_level': agreement,
            'consensus_reasoning': result.get('consensus_reasoning', ''),
            'key_agreements': result.get('key_agreements', []),
            'key_disagreements': result.get('key_disagreements', []),
            'weight_analysis': result.get('weight_analysis', ''),
            'risk_warnings': result.get('risk_warnings', []),
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"[投资者协调器] AI共识JSON解析失败: {e}")
        return None


def _fallback_consensus(vote_stats: Dict[str, Any], results: Dict[str, Any], stock_code: str) -> Dict[str, Any]:
    """AI不可用时的降级投票机制（原有逻辑）"""
    majority_rec = vote_stats['majority_rec']
    agreement_ratio = vote_stats['agreement_ratio']
    vote_count = vote_stats['vote_count']
    individual_views = vote_stats['individual_views']

    # 共识度判定（原有阈值逻辑，作为降级方案）
    if agreement_ratio >= 0.75:
        consensus_confidence = '高'
        agreement_level = '强共识'
    elif agreement_ratio >= 0.5:
        consensus_confidence = '中'
        agreement_level = '多数一致'
    else:
        consensus_confidence = '低'
        agreement_level = '意见分歧'

    # 构建共识推理文本
    consensus_reasoning = _build_consensus_reasoning(
        individual_views, majority_rec, agreement_level, Counter(vote_stats['vote_count'])
    )

    return {
        'stock_code': stock_code,
        'final_recommendation': majority_rec,
        'consensus_confidence': consensus_confidence,
        'consensus_reasoning': consensus_reasoning,
        'vote_summary': vote_count,
        'total_votes': vote_stats['total_votes'],
        'agreement_ratio': agreement_ratio,
        'agreement_level': agreement_level,
        'individual_views': individual_views,
        'ai_driven': False
    }


def _build_consensus_reasoning(
    views: List[Dict[str, Any]],
    majority_rec: str,
    agreement_level: str,
    vote_count: Counter
) -> str:
    """构建共识推理文本（降级模式使用）"""
    rec_cn = {'BUY': '买入', 'SELL': '卖出', 'HOLD': '持有'}

    lines = [f"投资者人格共识分析（{agreement_level}，基础投票模式）："]
    lines.append(f"多数建议：{rec_cn.get(majority_rec, majority_rec)}")
    lines.append(f"投票分布：{', '.join(f'{rec_cn.get(r, r)}={c}票' for r, c in vote_count.items())}")
    lines.append("")

    for view in views:
        rec_text = rec_cn.get(view['recommendation'], view['recommendation'])
        lines.append(
            f"- {view['analyst']}：{rec_text}（信心{view['confidence']}）"
            f"—— {view['reasoning'][:100]}"
        )

    return "\n".join(lines)
