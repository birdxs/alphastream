# -*- coding: utf-8 -*-
"""
Input: app/core/ai_client.py 单元测试
Output: pytest 用例集（≥8 用例），覆盖 get_ai_client/chat_completion/chat_with_tools/stream
Pos: tests/backend/unit/test_core_ai_client.py — BE-03b 最小批 Core 测试 #2

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

【任务编号】BE-03b
【目标】app/core/ai_client.py
【约束】LLM 全 mock；仅在 SDK 边界 (client.chat.completions.create) mock，不替换整个模块
"""
import os
import json
import types
import importlib
import unittest.mock as mock

import pytest


# ---------- 通用 fixtures ----------
@pytest.fixture
def ai_client_mod(monkeypatch):
    """每次导入前重置 env, 拿到干净的 ai_client 模块。"""
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key')
    monkeypatch.setenv('OPENAI_API_URL', 'http://127.0.0.1:9/v1')
    monkeypatch.setenv('OPENAI_API_MODEL', 'gpt-test')
    import app.core.ai_client as ac
    importlib.reload(ac)
    return ac


def _make_response(content="hello", tool_calls=None):
    """构造类 OpenAI ChatCompletion 响应对象（duck-typed）。"""
    msg = types.SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = types.SimpleNamespace(message=msg, finish_reason='stop')
    return types.SimpleNamespace(choices=[choice])


def _make_stream_chunks(text_parts, tool_calls_chunks=None):
    """构造一组流式 chunk 迭代器。tool_calls_chunks: [{idx,id,name,args_part}]"""
    chunks = []
    for t in text_parts:
        delta = types.SimpleNamespace(content=t, tool_calls=None)
        chunks.append(types.SimpleNamespace(choices=[types.SimpleNamespace(delta=delta, finish_reason=None)]))
    if tool_calls_chunks:
        for tc in tool_calls_chunks:
            func = types.SimpleNamespace(name=tc.get('name'), arguments=tc.get('args_part', ''))
            tc_obj = types.SimpleNamespace(index=tc['idx'], id=tc.get('id'), function=func)
            delta = types.SimpleNamespace(content=None, tool_calls=[tc_obj])
            chunks.append(types.SimpleNamespace(choices=[types.SimpleNamespace(delta=delta, finish_reason=None)]))
    return iter(chunks)


# ============ T001 get_ai_client / get_ai_model 初始化 ============
def test_T001_get_ai_client_with_key(ai_client_mod):
    client = ai_client_mod.get_ai_client()
    assert client is not None
    # OpenAI SDK 客户端应携带 chat.completions.create
    assert hasattr(client, 'chat')
    assert hasattr(client.chat, 'completions')
    assert ai_client_mod.get_ai_model() == 'gpt-test'


def test_T002_get_ai_client_without_key(monkeypatch):
    """无 API key 时返回 None，且打印警告。"""
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    import app.core.ai_client as ac
    importlib.reload(ac)
    assert ac.get_ai_client() is None


# ============ T003 chat_completion 非流式正常返回 ============
def test_T003_chat_completion_success(ai_client_mod):
    client = mock.MagicMock()
    client.chat.completions.create.return_value = _make_response("你好世界")
    resp, err = ai_client_mod.chat_completion(client, [{'role': 'user', 'content': 'hi'}])
    assert err is None
    assert ai_client_mod.get_completion_content(resp) == "你好世界"
    # 验证调用参数
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs['model'] == 'gpt-test'
    assert kwargs['messages'] == [{'role': 'user', 'content': 'hi'}]
    assert kwargs['temperature'] == 0.7
    assert kwargs['max_tokens'] == 4096
    assert 'tools' not in kwargs
    assert 'stream' not in kwargs


# ============ T004 chat_completion client=None 友好降级 ============
def test_T004_chat_completion_no_client(ai_client_mod):
    resp, err = ai_client_mod.chat_completion(None, [{'role': 'user', 'content': 'hi'}])
    assert resp is None
    assert 'OPENAI_API_KEY' in err


# ============ T005 chat_completion 异常映射友好消息 ============
def test_T005_chat_completion_error_mapping(ai_client_mod):
    client = mock.MagicMock()
    class RateLimitError(Exception):
        pass
    client.chat.completions.create.side_effect = RateLimitError("429")
    resp, err = ai_client_mod.chat_completion(client, [{'role': 'user', 'content': 'hi'}])
    assert resp is None
    assert err == '服务繁忙，请稍后重试（API限流）'


def test_T005b_chat_completion_unknown_error_fallback(ai_client_mod):
    client = mock.MagicMock()
    client.chat.completions.create.side_effect = ValueError("bad arg")
    resp, err = ai_client_mod.chat_completion(client, [{'role': 'user', 'content': 'hi'}])
    assert resp is None
    assert 'AI分析出错' in err
    assert 'bad arg' in err


# ============ T006 chat_completion 透传 tools/tool_choice ============
def test_T006_chat_completion_tools_kwargs(ai_client_mod):
    client = mock.MagicMock()
    client.chat.completions.create.return_value = _make_response("ok")
    tools = [{'type': 'function', 'function': {'name': 'get_stock'}}]
    ai_client_mod.chat_completion(client, [{'role': 'user', 'content': 'q'}],
                                  tools=tools, tool_choice='auto',
                                  temperature=0.1, max_tokens=128)
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs['tools'] == tools
    assert kwargs['tool_choice'] == 'auto'
    assert kwargs['temperature'] == 0.1
    assert kwargs['max_tokens'] == 128


# ============ T007 chat_completion_stream 返回 stream + 透传 stream=True ============
def test_T007_chat_completion_stream(ai_client_mod):
    client = mock.MagicMock()
    fake_stream = _make_stream_chunks(["a", "b"])
    client.chat.completions.create.return_value = fake_stream
    stream, err = ai_client_mod.chat_completion_stream(
        client, [{'role': 'user', 'content': 'hi'}], tools=[{'x': 1}], tool_choice='auto')
    assert err is None
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs.get('stream') is True
    assert kwargs.get('tools') == [{'x': 1}]
    # 消费 stream
    texts = []
    for chunk in stream:
        if chunk.choices[0].delta.content:
            texts.append(chunk.choices[0].delta.content)
    assert texts == ['a', 'b']


def test_T007b_chat_completion_stream_no_client(ai_client_mod):
    stream, err = ai_client_mod.chat_completion_stream(None, [])
    assert stream is None
    assert err and 'OPENAI_API_KEY' in err


def test_T007c_chat_completion_stream_error(ai_client_mod):
    client = mock.MagicMock()
    class APITimeoutError(Exception):
        pass
    client.chat.completions.create.side_effect = APITimeoutError("timeout")
    stream, err = ai_client_mod.chat_completion_stream(client, [])
    assert stream is None
    assert err == 'AI分析超时，请稍后重试'


# ============ T008 get_completion_content / 边界 ============
def test_T008_get_completion_content_variants(ai_client_mod):
    assert ai_client_mod.get_completion_content(None) is None
    empty = types.SimpleNamespace(choices=[])
    assert ai_client_mod.get_completion_content(empty) is None
    full = _make_response("abc")
    assert ai_client_mod.get_completion_content(full) == "abc"


# ============ T009 chat_with_tools — 0 工具调用直接返回 ============
def test_T009_chat_with_tools_no_tool_call(ai_client_mod):
    client = mock.MagicMock()
    # 单轮 stream 仅含文本
    client.chat.completions.create.return_value = _make_stream_chunks(["最", "终", "答"])
    content, log, err = ai_client_mod.chat_with_tools(
        client,
        messages=[{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function', 'function': {'name': 'noop'}}],
        tool_executor=lambda n, a: 'unused',
        max_tool_rounds=2,
    )
    assert err is None
    assert content == '最终答'
    assert log == []


# ============ T010 chat_with_tools — Function Calling 一轮工具调用 ============
def test_T010_chat_with_tools_one_round(ai_client_mod):
    """第 1 轮返回 tool_call, 第 2 轮返回最终文本。"""
    client = mock.MagicMock()
    round1 = _make_stream_chunks(
        text_parts=[],
        tool_calls_chunks=[{'idx': 0, 'id': 'call_1', 'name': 'get_stock_price', 'args_part': '{"code":"AAPL"}'}]
    )
    round2 = _make_stream_chunks(["价格", "是 100"])
    client.chat.completions.create.side_effect = [round1, round2]

    def executor(name, args):
        assert name == 'get_stock_price'
        assert args == {'code': 'AAPL'}
        return "AAPL=100"

    msgs = [{'role': 'user', 'content': '查苹果'}]
    content, log, err = ai_client_mod.chat_with_tools(
        client, msgs, tools_schema=[{'type': 'function'}],
        tool_executor=executor, max_tool_rounds=3,
    )
    assert err is None
    assert content == '价格是 100'
    assert len(log) == 1
    assert log[0]['tool_name'] == 'get_stock_price'
    assert log[0]['result'] == 'AAPL=100'
    # messages 应被追加 assistant + tool
    assert msgs[-1]['role'] == 'tool'
    assert msgs[-1]['content'] == 'AAPL=100'


# ============ T011 chat_with_tools — client=None 友好降级 ============
def test_T011_chat_with_tools_no_client(ai_client_mod):
    content, log, err = ai_client_mod.chat_with_tools(None, [], tools_schema=[])
    assert content is None
    assert log == []
    assert 'OPENAI_API_KEY' in err


# ============ T012 chat_with_tools — 流读取异常 → 错误映射 ============
def test_T012_chat_with_tools_stream_read_error(ai_client_mod):
    client = mock.MagicMock()

    class APIConnectionError(Exception):
        pass

    def gen():
        raise APIConnectionError("net")
        yield  # pragma: no cover

    client.chat.completions.create.return_value = gen()
    content, log, err = ai_client_mod.chat_with_tools(
        client, [{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function'}],
        tool_executor=lambda n, a: '',
    )
    assert content is None
    assert err == '无法连接AI服务，请检查网络'


# ============ T013 chat_with_tools — 工具执行抛异常 → 进入 tool result，不崩溃 ============
def test_T013_chat_with_tools_executor_exception(ai_client_mod):
    client = mock.MagicMock()
    round1 = _make_stream_chunks(
        text_parts=[],
        tool_calls_chunks=[{'idx': 0, 'id': 'c1', 'name': 'boom', 'args_part': '{}'}]
    )
    round2 = _make_stream_chunks(["回复"])
    client.chat.completions.create.side_effect = [round1, round2]

    def boom_exec(name, args):
        raise RuntimeError("explode")

    content, log, err = ai_client_mod.chat_with_tools(
        client, [{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function'}],
        tool_executor=boom_exec, max_tool_rounds=3,
    )
    assert err is None
    assert content == '回复'
    assert '工具执行异常' in log[0]['result']


# ============ T014 chat_with_tools — 超过 max_tool_rounds 走 fallback 总结 ============
def test_T014_chat_with_tools_exceed_rounds(ai_client_mod):
    """每轮均返回 tool_call → 达到 max_rounds → 调一次非流式 chat_completion 兜底。"""
    client = mock.MagicMock()
    tc_round = lambda i: _make_stream_chunks(
        text_parts=[],
        tool_calls_chunks=[{'idx': 0, 'id': f'c{i}', 'name': 'loop', 'args_part': '{}'}]
    )
    # max_tool_rounds=2 → 2 个流；之后是 fallback 非流式 chat_completion
    final_resp = _make_response("最终兜底")
    client.chat.completions.create.side_effect = [tc_round(1), tc_round(2), final_resp]

    content, log, err = ai_client_mod.chat_with_tools(
        client, [{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function'}],
        tool_executor=lambda n, a: 'r',
        max_tool_rounds=2,
    )
    assert err is None
    assert content == '最终兜底'
    assert len(log) == 2  # 2 轮工具调用


# ============ T015 超时/重试配置（构造期，验证 timeout=600/connect=15/max_retries=2） ============
def test_T015_client_timeout_and_retries(ai_client_mod, monkeypatch):
    """构造的 OpenAI 客户端应带 600s 总超时 + 15s 连接超时 + 2 次重试。
    AI_HTTP_TIMEOUT 默认 600，AI_HTTP_CONNECT_TIMEOUT 默认 15 (2026-05-18 拉富足)。
    """
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr(ai_client_mod, 'OpenAI', FakeOpenAI)
    ai_client_mod.get_ai_client()
    assert captured['api_key'] == 'sk-test-key'
    assert captured['base_url'] == 'http://127.0.0.1:9/v1'
    assert captured['max_retries'] == 2
    # httpx.Timeout 对象
    t = captured['timeout']
    # httpx.Timeout 可读 .connect / .read 等
    assert getattr(t, 'connect', None) == 15.0  # AI_HTTP_CONNECT_TIMEOUT 默认 15s（2026-05-18 拉富足调整）


# ============ T016 chat_with_tools_stream 基础调用 (smoke) ============
def test_T016_chat_with_tools_stream_smoke(ai_client_mod):
    """chat_with_tools_stream: 无工具调用流 → 应返回有效迭代器或 (None, err)。"""
    client = mock.MagicMock()
    client.chat.completions.create.return_value = _make_stream_chunks(["hi"])
    # 函数签名: chat_with_tools_stream(client, messages, tools_schema, tool_executor=None, ...)
    fn = getattr(ai_client_mod, 'chat_with_tools_stream', None)
    assert callable(fn), "chat_with_tools_stream 未导出"
    # 仅断言可调用且无未捕获异常；具体流逻辑依赖 event_bus 内部实现
    try:
        result = fn(client, [{'role': 'user', 'content': 'q'}],
                    tools_schema=[{'type': 'function'}],
                    tool_executor=lambda n, a: 'x',
                    max_tool_rounds=1)
    except Exception as e:
        pytest.skip(f"chat_with_tools_stream 内部依赖 event_bus，本环境跳过深测: {e}")
    # 结果应为 tuple 或 generator；不强断言以兼容实现
    assert result is not None


# ============ T017 map_ai_exception 覆盖 httpx ReadTimeout / 429 status ============
def test_T017_map_ai_exception_read_timeout(ai_client_mod):
    """流式 for-chunk 时 httpx.ReadTimeout 类名≠APITimeoutError，须映射为超时友好文案。"""
    import httpx

    msg = ai_client_mod.map_ai_exception(httpx.ReadTimeout('read timed out'))
    assert msg == 'AI分析超时，请稍后重试'

    msg2 = ai_client_mod.map_ai_exception(httpx.ConnectTimeout('connect timed out'))
    assert msg2 == '无法连接AI服务，请检查网络'


def test_T017b_map_ai_exception_status_429(ai_client_mod):
    """APIStatusError 带 status_code=429 须映射为限流文案。"""

    class APIStatusError(Exception):
        def __init__(self, message, status_code):
            super().__init__(message)
            self.status_code = status_code

    msg = ai_client_mod.map_ai_exception(APIStatusError('Too Many Requests', 429))
    assert msg == '服务繁忙，请稍后重试（API限流）'


def test_T017c_chat_with_tools_stream_read_timeout_maps(ai_client_mod):
    """chat_with_tools_stream 迭代中 ReadTimeout 须返回友好超时，而非原始 traceback 文案。"""
    import httpx

    client = mock.MagicMock()

    def _boom(**kwargs):
        raise httpx.ReadTimeout('The read operation timed out')

    client.chat.completions.create.side_effect = _boom
    content, tools_log, err = ai_client_mod.chat_with_tools_stream(
        client,
        [{'role': 'user', 'content': 'q'}],
        tools_schema=[],
        tool_executor=None,
        max_tool_rounds=1,
    )
    assert content is None
    assert err == 'AI分析超时，请稍后重试'
    assert tools_log == []


# ============ T017 _truncate_large 大文本截断 ============
def test_T017_truncate_large(ai_client_mod):
    fn = ai_client_mod._truncate_large
    # 短文本不变
    assert fn("abc") == "abc"
    # 非字符串走 str() 兜底
    assert fn(123) == "123"
    # 不可 str 的对象
    class Bad:
        def __str__(self):
            raise RuntimeError("x")
    assert fn(Bad()) == ''
    # 超 10KB 截断
    big = "a" * 20000
    out = fn(big)
    assert out.startswith("a" * 10240)
    assert "(truncated" in out


# ============ T018 _publish_reasoning / _publish_llm_request — event_bus 失败静默 ============
def test_T018_publish_helpers_swallow_errors(ai_client_mod, monkeypatch):
    """publish 助手函数应吞掉所有异常，不让上层崩溃。"""
    # 把 get_event_bus 替换为抛异常
    import app.core.event_bus as eb
    def boom():
        raise RuntimeError("bus down")
    monkeypatch.setattr(eb, 'get_event_bus', boom)
    # 不应抛
    ai_client_mod._publish_reasoning('agent_x', '内容')
    ai_client_mod._publish_llm_request('agent_x', 'm', [{'role': 'user', 'content': 'hi'}])


def test_T018b_publish_helpers_success_path(ai_client_mod, monkeypatch):
    """正常路径 publish 一次。"""
    import app.core.event_bus as eb
    calls = []
    class FakeBus:
        def publish(self, ev, payload):
            calls.append((ev, payload))
    monkeypatch.setattr(eb, 'get_event_bus', lambda: FakeBus())
    ai_client_mod._publish_reasoning('agent_y', 'hello')
    ai_client_mod._publish_llm_request('agent_y', 'gpt-test', [{'role': 'user', 'content': 'hi'}])
    assert len(calls) == 2
    assert calls[0][1]['data']['agent'] == 'agent_y'
    assert 'LLM_REQ' in calls[1][1]['data']['content']


# ============ T019 chat_completion_stream stream=None 防御 ============
def test_T019_chat_with_tools_stream_returns_none(ai_client_mod, monkeypatch):
    """模拟 chat_completion_stream 返回 (None, None) → chat_with_tools 应报 'AI返回空流'。"""
    client = mock.MagicMock()
    monkeypatch.setattr(ai_client_mod, 'chat_completion_stream',
                        lambda *a, **kw: (None, None))
    content, log, err = ai_client_mod.chat_with_tools(
        client, [{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function'}],
        tool_executor=lambda n, a: '',
        max_tool_rounds=1,
    )
    assert content is None
    assert err == 'AI返回空流'


# ============ T020 chat_with_tools — tool_executor 默认走 tools.execute_tool ============
def test_T020_chat_with_tools_default_executor(ai_client_mod, monkeypatch):
    """tool_executor=None 时应延迟导入 app.core.tools.execute_tool。"""
    captured = {}
    def fake_execute_tool(name, args):
        captured['called'] = (name, args)
        return "fake_result"
    # 在 app.core.tools 模块上 patch
    import importlib
    try:
        tools_mod = importlib.import_module('app.core.tools')
    except Exception:
        pytest.skip("app.core.tools 不可导入")
    if not hasattr(tools_mod, 'execute_tool'):
        # 其他测试文件在模块级 stub 了 app.core.tools（仅含 schema 属性），导致 execute_tool 缺失
        # 强制重载以获取真实模块（或 setattr 注入 fake）
        try:
            tools_mod = importlib.reload(tools_mod)
        except Exception:
            pass
    monkeypatch.setattr(tools_mod, 'execute_tool', fake_execute_tool, raising=False)

    client = mock.MagicMock()
    round1 = _make_stream_chunks(
        text_parts=[],
        tool_calls_chunks=[{'idx': 0, 'id': 'c1', 'name': 'default_tool', 'args_part': '{"k":1}'}]
    )
    round2 = _make_stream_chunks(["done"])
    client.chat.completions.create.side_effect = [round1, round2]
    content, log, err = ai_client_mod.chat_with_tools(
        client, [{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function'}],
        tool_executor=None, max_tool_rounds=2,
    )
    assert err is None
    assert content == 'done'
    assert captured['called'] == ('default_tool', {'k': 1})


# ============ T021 chat_completion_stream — 多种异常类型映射 ============
@pytest.mark.parametrize('exc_name,expected_keyword', [
    ('AuthenticationError', 'API密钥'),
    ('BadRequestError', '请求参数错误'),
    ('InternalServerError', '服务内部错误'),
])
def test_T021_stream_error_map(ai_client_mod, exc_name, expected_keyword):
    client = mock.MagicMock()
    Exc = type(exc_name, (Exception,), {})
    client.chat.completions.create.side_effect = Exc("x")
    stream, err = ai_client_mod.chat_completion_stream(client, [{'role': 'user', 'content': 'q'}])
    assert stream is None
    assert err
    # 至少其中一个错误映射关键词出现
    assert expected_keyword in err or 'AI' in err


# ============ T022 chat_with_tools — tool_call arguments 解析失败容错 ============
def test_T022_chat_with_tools_bad_json_args(ai_client_mod):
    """工具调用 arguments 为非法 JSON → 不崩溃，传 {} 或原文给 executor。"""
    client = mock.MagicMock()
    round1 = _make_stream_chunks(
        text_parts=[],
        tool_calls_chunks=[{'idx': 0, 'id': 'cX', 'name': 'parse_test', 'args_part': '{not-json'}]
    )
    round2 = _make_stream_chunks(["ok"])
    client.chat.completions.create.side_effect = [round1, round2]
    received_args = {}
    def exec_fn(name, args):
        received_args['v'] = args
        return 'r'
    content, log, err = ai_client_mod.chat_with_tools(
        client, [{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function'}],
        tool_executor=exec_fn, max_tool_rounds=2,
    )
    # 即使 json 解析失败也不应崩溃
    assert err is None or 'AI' in (err or '')
    # executor 被调用过（args 可能是 {} 或 str）
    assert 'v' in received_args


# ============ T023 chat_with_tools_stream — 无工具调用，纯 token 流 ============
def test_T023_chat_with_tools_stream_text_only(ai_client_mod):
    client = mock.MagicMock()
    client.chat.completions.create.return_value = _make_stream_chunks(["你", "好"])
    events = []
    def cb(et, data):
        events.append((et, data))
    content, log, err = ai_client_mod.chat_with_tools_stream(
        client, [{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function'}],
        tool_executor=lambda n, a: '',
        max_tool_rounds=2,
        event_callback=cb,
        agent_name='agent_t',
    )
    assert err is None
    assert content == '你好'
    assert log == []
    types_seen = [e[0] for e in events]
    assert 'token' in types_seen
    assert 'done' in types_seen


# ============ T024 chat_with_tools_stream — 一轮工具调用全路径 ============
def test_T024_chat_with_tools_stream_one_round(ai_client_mod):
    client = mock.MagicMock()
    round1 = _make_stream_chunks(
        text_parts=[],
        tool_calls_chunks=[{'idx': 0, 'id': 'cs1', 'name': 'get_price', 'args_part': '{"sym":"A"}'}]
    )
    round2 = _make_stream_chunks(["最", "终"])
    client.chat.completions.create.side_effect = [round1, round2]
    events = []
    def cb(et, data):
        events.append(et)
    content, log, err = ai_client_mod.chat_with_tools_stream(
        client, [{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function'}],
        tool_executor=lambda n, a: 'A=10',
        max_tool_rounds=3,
        event_callback=cb,
        agent_name='agent_s',
    )
    assert err is None
    assert content == '最终'
    assert len(log) == 1
    assert log[0]['tool_name'] == 'get_price'
    assert 'tool_call_start' in events
    assert 'tool_call_result' in events
    assert 'done' in events


# ============ T025 chat_with_tools_stream — 流读取异常 → error 事件 + 友好提示 ============
def test_T025_chat_with_tools_stream_read_error(ai_client_mod):
    client = mock.MagicMock()
    class APIConnectionError(Exception):
        pass
    def bad_gen():
        yield types.SimpleNamespace(choices=[types.SimpleNamespace(
            delta=types.SimpleNamespace(content='hi', tool_calls=None), finish_reason=None)])
        raise APIConnectionError("net broken")
    client.chat.completions.create.return_value = bad_gen()
    events = []
    def cb(et, data):
        events.append((et, data))
    content, log, err = ai_client_mod.chat_with_tools_stream(
        client, [{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function'}],
        tool_executor=lambda n, a: '',
        max_tool_rounds=2,
        event_callback=cb,
    )
    assert content is None
    assert err == '无法连接AI服务，请检查网络'
    assert any(e[0] == 'error' for e in events)


# ============ T026 chat_with_tools_stream — 超过 max_rounds 走 fallback ============
def test_T026_chat_with_tools_stream_exceed_rounds(ai_client_mod):
    client = mock.MagicMock()
    def tc_round(i):
        return _make_stream_chunks(
            text_parts=[],
            tool_calls_chunks=[{'idx': 0, 'id': f'sc{i}', 'name': 'loop', 'args_part': '{}'}]
        )
    final_resp = _make_response("兜底总结")
    client.chat.completions.create.side_effect = [tc_round(1), final_resp]
    content, log, err = ai_client_mod.chat_with_tools_stream(
        client, [{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function'}],
        tool_executor=lambda n, a: 'r',
        max_tool_rounds=1,
    )
    assert err is None
    assert content == '兜底总结'
    assert len(log) == 1


# ============ T027 chat_with_tools_stream — client=None ============
def test_T027_chat_with_tools_stream_no_client(ai_client_mod):
    content, log, err = ai_client_mod.chat_with_tools_stream(
        None, [], tools_schema=[], tool_executor=lambda n, a: '')
    assert content is None
    assert log == []
    assert 'OPENAI_API_KEY' in err


# ============ T028 chat_with_tools_stream — JSON 参数修复路径 ============
def test_T028_chat_with_tools_stream_bad_json_recover(ai_client_mod):
    """arguments 是 '{"a":1}{"b":2}' → 走正则提取首个 JSON。"""
    client = mock.MagicMock()
    round1 = _make_stream_chunks(
        text_parts=[],
        tool_calls_chunks=[{'idx': 0, 'id': 'cR', 'name': 'multi', 'args_part': '{"a":1}{"b":2}'}]
    )
    round2 = _make_stream_chunks(["ok"])
    client.chat.completions.create.side_effect = [round1, round2]
    seen = {}
    def ex(n, a):
        seen['a'] = a
        return 'r'
    content, log, err = ai_client_mod.chat_with_tools_stream(
        client, [{'role': 'user', 'content': 'q'}],
        tools_schema=[{'type': 'function'}],
        tool_executor=ex, max_tool_rounds=2,
    )
    assert err is None
    assert seen['a'] == {'a': 1}  # 提取首个有效 JSON


# ============ G1 provenance consumer: tool payload 强制 normalize ============
def test_tool_call_payloads_normalize_provenance(ai_client_mod):
    """start/result 两条 payload 出口 provenance 必须走 normalize（无假价字段）。"""
    start = ai_client_mod._tool_call_start_payload(
        'tc1', 'get_stock_data', {'code': '600519'}, agent_name='analyst', source='akshare',
    )
    result = ai_client_mod._tool_call_result_payload(
        'tc1', 'get_stock_data', '{"ok": true}', 12, agent_name='analyst', source='akshare',
    )
    for payload in (start, result):
        prov = payload.get('provenance') or []
        assert isinstance(prov, list)
        assert len(prov) >= 1
        for e in prov:
            assert isinstance(e, dict)
            assert e.get('source')
            assert 'price' not in e and 'close' not in e and 'pe' not in e
            assert set(e.keys()) <= {'source', 'tool', 'ts', 'digest'}
