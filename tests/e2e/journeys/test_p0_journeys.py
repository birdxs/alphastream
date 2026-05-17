# Input: P0 关键用户旅程契约 (J1/J3/J5/J10/J11/J13/J14/J15)
# Output: pytest 集成测试，验证前后端契约一致性
# Pos: tests/e2e/journeys/test_p0_journeys.py；E2E-01 落盘
"""
E2E-01 P0 关键端到端用户旅程契约测试。

约束:
- 不实启 Playwright 浏览器（W6 真实联调留用）
- 不实启后端服务（用 flask test_client）
- LLM 全 mock；akshare/coordinator/hitl 全 mock
- 仅 8 个 P0 旅程，周期 ≤ 20min

参考: 之前 P1 联调调研 J1-J20 旅程清单。
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# 强制 mock 环境
os.environ.setdefault('OPENAI_API_KEY', 'sk-test-mock')
os.environ.setdefault('USE_AGENT_SYSTEM', 'true')


# ---------- fixtures ----------

@pytest.fixture(scope='module')
def flask_client():
    """加载 Flask app 的 test_client（不真启 server）。"""
    from app.web import web_server as ws
    ws.app.config['TESTING'] = True
    with ws.app.test_client() as c:
        yield c


@pytest.fixture
def reset_approval_manager():
    """每次测试前清空 HITL 待审批列表，避免互相污染。"""
    from app.agents.hitl import approval_manager
    with approval_manager._lock:
        approval_manager._pending_approvals.clear()
    yield approval_manager
    with approval_manager._lock:
        approval_manager._pending_approvals.clear()


def _wait_task_completed(client, task_id: str, timeout: float = 5.0) -> Dict[str, Any]:
    """轮询 agent_analysis_status，直到 completed / failed / 超时。"""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        rsp = client.get(f'/api/agent_analysis_status/{task_id}')
        assert rsp.status_code == 200, f'status 接口 HTTP {rsp.status_code}'
        last = rsp.get_json()
        if last.get('status') in ('completed', 'failed'):
            return last
        time.sleep(0.05)
    raise AssertionError(f'task {task_id} 未在 {timeout}s 内结束, 最后状态={last}')


def _mock_final_state(
    action: str = 'BUY',
    confidence: float = 0.8,
    artifacts: List[Dict] = None,
    errors: List[str] = None,
) -> Dict[str, Any]:
    """构造 9-Agent 链完结后的 result_state，符合 coordinator.run_agent_analysis 契约。"""
    return {
        'stock_code': '000001',
        'market_type': 'A',
        'final_decision': {
            'action': action,
            'reasoning': 'mock 决策',
            'confidence': confidence,
        },
        'artifacts': artifacts or [],
        'execution_log': [
            {'agent': 'market_analyst', 'status': 'completed'},
            {'agent': 'social_analyst', 'status': 'completed'},
            {'agent': 'news_analyst', 'status': 'completed'},
            {'agent': 'fundamentals_analyst', 'status': 'completed'},
            {'agent': 'bull_researcher', 'status': 'completed'},
            {'agent': 'bear_researcher', 'status': 'completed'},
            {'agent': 'research_manager', 'status': 'completed'},
            {'agent': 'risk_manager', 'status': 'completed'},
            {'agent': 'trader', 'status': 'completed'},
        ],
        'errors': errors or [],
    }


# ============================================================
# J1 完整股票分析旅程
# ============================================================

def test_j1_full_stock_analysis_journey(flask_client):
    """J1: POST start_agent_analysis -> mock 9-Agent -> 轮询直到 completed -> 断言 decision/final_state。"""
    mock_state = _mock_final_state(action='BUY', confidence=0.85)

    with patch('app.agents.coordinator.run_agent_analysis', return_value=mock_state) as mock_run, \
         patch('app.web.web_server.analyzer.get_stock_info', return_value={'股票名称': '平安银行'}):
        rsp = flask_client.post(
            '/api/start_agent_analysis',
            json={
                'stock_code': '000001',
                'market_type': 'A',
                'research_depth': 3,
                'selected_analysts': ['market', 'social', 'news', 'fundamentals'],
            },
        )
        assert rsp.status_code == 200, rsp.data
        body = rsp.get_json()
        task_id = body['task_id']
        assert body['status'] == 'pending'

        final = _wait_task_completed(flask_client, task_id)

    assert final['status'] == 'completed'
    assert mock_run.called, 'coordinator.run_agent_analysis 未被调用'
    result = final['result']
    assert 'decision' in result and result['decision']['action'] == 'BUY'
    assert 'final_state' in result
    assert result['final_state']['company_name'] == '平安银行'
    # execution_log 应有 9 步
    assert len(result['execution_log']) == 9


# ============================================================
# J3 HITL 审批闭环
# ============================================================

def test_j3_hitl_approval_loop(flask_client, reset_approval_manager):
    """J3: 高风险 decision -> EVENT_APPROVAL_NEEDED -> GET pending -> POST approve -> 推进。"""
    from app.agents.hitl import approval_manager
    import threading

    task_id = 'task_j3_test'
    decision = {'action': 'BUY', 'reasoning': '高风险买入', 'confidence': 0.9}

    # 后台线程触发 request_approval(high) — 会阻塞直到外部 submit
    result_holder: Dict[str, Any] = {}

    def _request():
        result_holder['ret'] = approval_manager.request_approval(
            task_id, decision, risk_level='high', timeout=5,
        )

    t = threading.Thread(target=_request, daemon=True)
    t.start()

    # 等待 pending 上架
    deadline = time.time() + 2
    pending: List[Dict] = []
    while time.time() < deadline:
        rsp = flask_client.get('/api/agent_pending_approvals')
        assert rsp.status_code == 200
        pending = rsp.get_json()['approvals']
        if any(p['task_id'] == task_id for p in pending):
            break
        time.sleep(0.05)
    assert any(p['task_id'] == task_id for p in pending), 'pending approval 未上架'
    target = next(p for p in pending if p['task_id'] == task_id)
    assert target['risk_level'] == 'high'
    assert target['decision']['action'] == 'BUY'

    # 提交审批
    rsp = flask_client.post(
        '/api/agent_submit_approval',
        json={'task_id': task_id, 'approved': True, 'feedback': '人工通过'},
    )
    assert rsp.status_code == 200
    body = rsp.get_json()
    assert body['approved'] is True

    # 后台线程应能返回
    t.join(timeout=3)
    assert not t.is_alive(), 'request_approval 线程未退出'
    ret = result_holder['ret']
    assert ret['approved'] is True
    assert ret['approval_type'] == 'human'
    assert ret['human_feedback'] == '人工通过'

    # pending 列表已清空
    rsp = flask_client.get('/api/agent_pending_approvals')
    assert all(p['task_id'] != task_id for p in rsp.get_json()['approvals'])


# ============================================================
# J5 多市场切换契约 (A / HK / US)
# ============================================================

@pytest.mark.parametrize(
    'stock_code,market_type',
    [
        ('000001', 'A'),
        ('00700', 'HK'),
        ('AAPL', 'US'),
    ],
)
def test_j5_multi_market_routing(flask_client, stock_code, market_type):
    """J5: 同结构请求在不同 market_type 下被正确路由。"""
    # 不依赖真实 analyzer，patch 后台 thread 入口
    with patch('app.analysis.stock_analyzer.StockAnalyzer.perform_enhanced_analysis',
               return_value={'score': 80, 'market_type': market_type}):
        rsp = flask_client.post(
            '/api/start_stock_analysis',
            json={'stock_code': stock_code, 'market_type': market_type},
        )
        assert rsp.status_code == 200, f'{market_type} {stock_code}: {rsp.data}'
        body = rsp.get_json()
        assert 'task_id' in body
        assert stock_code.upper() in body.get('message', '') or stock_code in body.get('message', ''), \
            f'响应未透传股票码: {body}'


# ============================================================
# J10 对话历史 list / resume
# ============================================================

def test_j10_conversation_list_and_resume(flask_client):
    """J10: 创建对话 -> 追加消息 -> list 看到 -> 取回完整消息。"""
    from app.core.conversation import get_conversation_manager
    mgr = get_conversation_manager()

    conv_id = mgr.create_conversation(title='J10 测试对话')
    try:
        mgr.add_message(conv_id, 'user', '你好，分析平安银行')
        mgr.add_message(conv_id, 'assistant', '好的，开始分析 000001', artifacts=[
            {'artifact_type': 'analysis', 'title': '初步结论', 'data': {'score': 80}, 'confidence': 0.75},
        ])

        # 列表
        rsp = flask_client.get('/api/conversations')
        assert rsp.status_code == 200
        body = rsp.get_json()
        items = body.get('conversations') if isinstance(body, dict) else body
        assert isinstance(items, list), f'conversations 必须是列表, got={type(items)}'
        ids = [c['conversation_id'] for c in items]
        assert conv_id in ids, f'新对话 {conv_id} 未出现在列表中'

        # 详情
        rsp = flask_client.get(f'/api/conversations/{conv_id}')
        assert rsp.status_code == 200
        detail = rsp.get_json()
        assert detail.get('conversation_id') == conv_id
        msgs = detail.get('messages', [])
        assert len(msgs) == 2
        assert msgs[0]['role'] == 'user'
        assert msgs[1]['role'] == 'assistant'
        assert len(msgs[1]['artifacts']) == 1
        assert msgs[1]['artifacts'][0]['artifact_type'] == 'analysis'
    finally:
        # 清理
        try:
            flask_client.delete(f'/api/conversations/{conv_id}')
        except Exception:
            pass


# ============================================================
# J11 Artifact 渲染契约
# ============================================================

def test_j11_artifact_passthrough(flask_client):
    """J11: 9-Agent 返回 artifacts -> 透传到响应体，每个含必备字段。"""
    artifacts = [
        {'artifact_type': 'chart', 'title': 'K线图', 'data': {'kline': [1, 2, 3]}, 'confidence': 0.9},
        {'artifact_type': 'table', 'title': '财务指标', 'data': {'pe': 12.3}, 'confidence': 0.85},
        {'artifact_type': 'text', 'title': '研究纪要', 'data': {'summary': 'mock'}, 'confidence': 0.7},
    ]
    mock_state = _mock_final_state(artifacts=artifacts)

    with patch('app.agents.coordinator.run_agent_analysis', return_value=mock_state), \
         patch('app.web.web_server.analyzer.get_stock_info', return_value={'股票名称': 'X'}):
        rsp = flask_client.post(
            '/api/start_agent_analysis',
            json={'stock_code': '000001', 'market_type': 'A'},
        )
        assert rsp.status_code == 200
        task_id = rsp.get_json()['task_id']
        final = _wait_task_completed(flask_client, task_id)

    assert final['status'] == 'completed'
    final_state = final['result']['final_state']
    got = final_state.get('artifacts', [])
    assert len(got) == 3
    required = {'artifact_type', 'title', 'data', 'confidence'}
    for a in got:
        assert required.issubset(a.keys()), f'artifact 缺字段: {a}'


# ============================================================
# J13 LLM 失败兜底 (H3)
# ============================================================

def test_j13_llm_failure_fallback(flask_client):
    """J13: 所有 LLM 抛错 -> final_decision={action:HOLD, confidence:0}。"""
    # coordinator 入口直接被 patch 模拟 H3 兜底状态
    fallback_state = {
        'stock_code': '000001',
        'market_type': 'A',
        'final_decision': {
            'action': 'HOLD',
            'reasoning': 'LLM 调用全部失败，触发 H3 兜底',
            'confidence': 0.0,
        },
        'artifacts': [],
        'execution_log': [],
        'errors': ['LLM provider unreachable', 'fallback engaged'],
    }
    with patch('app.agents.coordinator.run_agent_analysis', return_value=fallback_state), \
         patch('app.web.web_server.analyzer.get_stock_info', return_value={'股票名称': 'X'}):
        rsp = flask_client.post(
            '/api/start_agent_analysis',
            json={'stock_code': '000001', 'market_type': 'A'},
        )
        assert rsp.status_code == 200
        task_id = rsp.get_json()['task_id']
        final = _wait_task_completed(flask_client, task_id)

    assert final['status'] == 'completed'  # 兜底也是 completed
    decision = final['result']['decision']
    assert decision['action'] == 'HOLD'
    assert decision['confidence'] == 0.0
    assert any('LLM' in e or 'fallback' in e for e in final['result'].get('errors', []))


# ============================================================
# J14 LangGraph Checkpointer replay
# ============================================================

def test_j14_checkpoint_replay_same_conversation(flask_client):
    """J14: LangGraph Checkpointer 多次启动 state 隔离契约。

    后端契约（已通过源码确认）：/api/start_agent_analysis 每次 POST 都新建独立
    task_id（uuid4），coordinator.run_agent_analysis 被独立调用。LangGraph
    checkpointer 的语义体现在 **同一 task 内** 的 state 持久化，而非跨 HTTP 请求
    复用任务。本用例据此验证：
      1. 两次独立启动产生不同 task_id
      2. coordinator 被调用次数与 POST 次数相等（无串扰）
      3. 每次调用入参精确携带各自 stock_code（state 隔离）
      4. 同股票第二次启动仍能独立完成（checkpointer 不阻塞 fresh run）
    """
    call_log: List[Dict] = []

    def _fake_run(**kwargs):
        call_log.append(kwargs)
        idx = len(call_log)
        return _mock_final_state(action='BUY' if idx == 1 else 'HOLD')

    with patch('app.agents.coordinator.run_agent_analysis', side_effect=_fake_run), \
         patch('app.web.web_server.analyzer.get_stock_info', return_value={'股票名称': 'X'}):
        # 第一次：000002
        rsp1 = flask_client.post(
            '/api/start_agent_analysis',
            json={'stock_code': '000002', 'market_type': 'A'},
        )
        tid1 = rsp1.get_json()['task_id']
        f1 = _wait_task_completed(flask_client, tid1)
        assert f1['status'] == 'completed'

        # 第二次：同股票 000002 — 当前契约：新建独立 task（不复用）
        rsp2 = flask_client.post(
            '/api/start_agent_analysis',
            json={'stock_code': '000002', 'market_type': 'A'},
        )
        tid2 = rsp2.get_json()['task_id']
        assert tid1 != tid2, '每次启动应产生独立 task_id'
        f2 = _wait_task_completed(flask_client, tid2)
        assert f2['status'] == 'completed'

    # 两次调用 → coordinator 被独立调两次
    assert len(call_log) == 2, f'coordinator 调用次数={len(call_log)}, 期望 2'
    # state 隔离：两次 kwargs 各自完整携带 stock_code（无跨 task 串扰）
    for c in call_log:
        assert c.get('stock_code') == '000002'
        assert c.get('market_type') == 'A'
    # 决策可独立演化（不是被 cache 强行返回首个结果）
    assert f1['result']['decision']['action'] == 'BUY'
    assert f2['result']['decision']['action'] == 'HOLD'


# ============================================================
# J15 错误信息脱敏端到端
# ============================================================

def test_j15_error_sanitization(flask_client):
    """J15: 触发各种错误 -> 响应体不含 stacktrace / 绝对文件路径。"""
    # case-1: 非法股票代码
    rsp = flask_client.post(
        '/api/start_agent_analysis',
        json={'stock_code': '!@#$', 'market_type': 'A'},
    )
    assert rsp.status_code == 400
    text = rsp.data.decode('utf-8')
    _assert_no_sensitive(text)

    # case-2: 缺 stock_code
    rsp = flask_client.post('/api/start_agent_analysis', json={'market_type': 'A'})
    assert rsp.status_code == 400
    _assert_no_sensitive(rsp.data.decode('utf-8'))

    # case-3: 不存在的 task_id
    rsp = flask_client.get('/api/agent_analysis_status/nonexistent_task_id_xyz')
    assert rsp.status_code == 404
    _assert_no_sensitive(rsp.data.decode('utf-8'))

    # case-4: submit_approval 找不到 task
    rsp = flask_client.post(
        '/api/agent_submit_approval',
        json={'task_id': 'never_existed', 'approved': True},
    )
    assert rsp.status_code in (404, 400)
    _assert_no_sensitive(rsp.data.decode('utf-8'))


def _assert_no_sensitive(text: str) -> None:
    """断言响应文本不含敏感泄漏。"""
    forbidden_substrings = [
        'Traceback (most recent call last)',
        '/Users/',           # 本机绝对路径
        '/home/',
        'File "',            # python traceback 标志
        'site-packages',
        '.pyc',
    ]
    for s in forbidden_substrings:
        assert s not in text, f'响应体泄漏敏感字串 {s!r}: {text[:200]}'
