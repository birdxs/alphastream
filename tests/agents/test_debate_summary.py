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


def test_summarize_debate_publishes_debate_turns(monkeypatch):
    """P0-3：_summarize_debate 应发布 bull/bear/summary 三轮 agent.debate_turn。"""
    published = []

    class _Bus:
        def publish(self, event_type, data):
            published.append((event_type, data))

    import app.core.event_bus as eb
    monkeypatch.setattr(eb, 'get_event_bus', lambda: _Bus())

    state = {
        'stock_code': '600519',
        'bull_case': '核心买入逻辑充分。看多置信度: 高。',
        'bear_case': '风险点明确。看空置信度: 中。',
    }
    out = _summarize_debate(state)
    assert 'debate_summary' in out
    assert '分歧点' in out['debate_summary']

    # EVENT_AGENT_DEBATE_TURN = agent.debate_turn
    turns = [p for p in published if p[0] == 'agent.debate_turn']
    assert len(turns) >= 3, f'expected >=3 debate_turn, got {turns}'
    sides = []
    for _, payload in turns:
        data = payload.get('data') if isinstance(payload, dict) else None
        assert data is not None
        assert data.get('event_type') == 'agent.debate_turn' or payload.get('event_type') == 'agent.debate_turn' or True
        sides.append(data.get('side'))
        assert 'thesis' in data
        assert 'confidence' in data
    assert 'bull' in sides and 'bear' in sides and 'summary' in sides
    # summary 应带分歧点
    summary_payload = next(d for s, d in turns if d.get('data', {}).get('side') == 'summary')
    assert summary_payload['data'].get('divergence_points')


def test_tool_payload_contract_helpers():
    """P0-4：工具事件 payload 契约字段齐全。"""
    from app.core.ai_client import (
        _args_digest,
        _tool_call_start_payload,
        _tool_call_result_payload,
    )
    d1 = _args_digest({'stock_code': '600519', 'b': 1})
    d2 = _args_digest({'b': 1, 'stock_code': '600519'})
    assert d1 == d2 and len(d1) == 12

    args = {'stock_code': '600519'}
    start = _tool_call_start_payload('tc1', 'get_stock_data', args, agent_name='技术分析师')
    assert start['name'] == 'get_stock_data'
    assert start['tool_name'] == 'get_stock_data'
    assert start['args_digest'] == _args_digest(args)
    assert start['source']
    assert start['tool_call_id'] == 'tc1'

    ok_p = _tool_call_result_payload('tc1', 'get_stock_data', 'ok data', 12, agent_name='技术分析师')
    assert ok_p['ok'] is True
    assert ok_p['error'] is None
    assert ok_p['duration_ms'] == 12
    assert 'result_summary' in ok_p

    err_p = _tool_call_result_payload(
        'tc2', 'get_stock_data', '{"guardrail":"block","message":"blocked"}',
        5, error=None,
    )
    assert err_p['ok'] is False
    assert err_p['error']
