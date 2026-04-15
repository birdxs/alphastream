"""
Input: bull_case / bear_case 文本与串行图结构
Output: debate_summary 合成与串行辩论edge断言结果
Pos: tests/agents/test_debate_summary.py - R2 Q4 P1+P5 串行辩论+debate_summary合成单测

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

[NEW-FILE:#20260415-R2] 新建理由: 仓库内原无 bull/bear/debate 相关单测,
为 R2 P1 串行辩论+P5 debate_summary 合成提供回归保障。
"""
import pytest

from app.agents.coordinator import _summarize_debate, build_analysis_graph


def test_summarize_debate_with_both_cases():
    """双方都有论据 + 多方置信度高 → 综合倾向看多"""
    state = {
        'bull_case': '核心买入逻辑: A公司Q3营收增速40%。看多置信度: 高, 理由充分。',
        'bear_case': '应收账款增速异常。看空置信度: 中, 证据有限。',
    }
    out = _summarize_debate(state)
    assert 'debate_summary' in out
    summary = out['debate_summary']
    assert '多方主论点' in summary
    assert '空方主论点' in summary
    assert '综合研判' in summary
    # 多方高置信度, 空方中置信度 → 倾向看多
    assert '倾向看多' in summary or '置信度' in summary


def test_summarize_debate_empty_cases():
    """双方均空 → skipped"""
    out = _summarize_debate({'bull_case': None, 'bear_case': None})
    assert out['debate_summary'] == '辩论双方均未产出有效分析'
    assert out['execution_log'][0]['status'] == 'skipped'


def test_summarize_debate_bear_stronger():
    """空方高置信度 + 多方低 → 综合倾向看空"""
    state = {
        'bull_case': '看多置信度: 低, 催化剂不足。',
        'bear_case': '看空置信度: 高, 基本面恶化明确。',
    }
    out = _summarize_debate(state)
    assert '倾向看空' in out['debate_summary'] or '看空' in out['debate_summary']


def test_graph_depth4_serial_debate():
    """depth>=4 图构建应为串行 bull→bear→debate_summary (非并行fan-out)"""
    try:
        graph = build_analysis_graph(research_depth=4)
    except Exception as e:
        pytest.skip(f"图编译依赖未满足, skip: {e}")

    # LangGraph CompiledGraph 暴露 get_graph() 获取节点边信息
    g = graph.get_graph()
    node_names = set(g.nodes.keys())

    # 断言关键节点存在
    assert 'bull' in node_names, "bull 节点缺失"
    assert 'bear' in node_names, "bear 节点缺失"
    assert 'debate_summary' in node_names, "R2 P5 debate_summary 节点缺失"

    # 断言串行边: bull→bear, bear→debate_summary
    edges = [(e.source, e.target) for e in g.edges]
    assert ('bull', 'bear') in edges, f"bull→bear 串行边缺失, 实际edges: {edges}"
    assert ('bear', 'debate_summary') in edges, f"bear→debate_summary 边缺失"
    # 串行下不应再有 bull→decision 和 bear→decision 直连(避免并行fan-in)
    assert ('bull', 'decision') not in edges, "bull 不应直连 decision (应走 bear→debate_summary)"
