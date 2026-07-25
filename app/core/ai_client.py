# -*- coding: utf-8 -*-
"""
Input: AI API配置（环境变量）、工具定义schema、消息列表
Output: 统一的OpenAI客户端实例，带超时、重试、错误处理、Function Calling工具调用循环和流式输出
Pos: app/core/ai_client.py - 所有AI调用的统一入口，支持被动问答、主动工具调用、流式输出三种模式

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import os
import json
import time
import logging
import hashlib
from typing import Any, Dict, Optional
from openai import OpenAI
import httpx

logger = logging.getLogger(__name__)

# 友好错误消息映射（按异常类名；流式 httpx 超时类名也覆盖）
ERROR_MESSAGES = {
    'RateLimitError': '服务繁忙，请稍后重试（API限流）',
    'APITimeoutError': 'AI分析超时，请稍后重试',
    'APIConnectionError': '无法连接AI服务，请检查网络',
    'AuthenticationError': 'AI服务认证失败，请检查API密钥配置',
    'PermissionDeniedError': 'AI服务认证失败，请检查API密钥配置',
    'APIStatusError': 'AI服务暂时不可用，请稍后重试',
    # OneAPI/上游 5xx（OpenAI SDK InternalServerError 等）— 勿回落裸 str(exc) 露出 "Error code: 502"
    'InternalServerError': 'AI服务内部错误，请稍后重试',
    'BadRequestError': 'AI请求参数错误，请检查输入后重试',
    # 上游容量/过载（OpenAI/OneAPI 等常以 503 原文 "The model is currently overloaded" 回吐）
    'ModelOverloadedError': '模型繁忙，请稍后重试',
    # httpx 原生超时（流式 for chunk in stream 时可能直接冒泡，类名≠APITimeoutError）
    'ReadTimeout': 'AI分析超时，请稍后重试',
    'ConnectTimeout': '无法连接AI服务，请检查网络',
    'WriteTimeout': 'AI分析超时，请稍后重试',
    'PoolTimeout': '服务繁忙，请稍后重试（连接池耗尽）',
    'TimeoutException': 'AI分析超时，请稍后重试',
    'ConnectError': '无法连接AI服务，请检查网络',
    'RemoteProtocolError': '无法连接AI服务，请检查网络',
}


def _is_model_overloaded_message(msg_l: str) -> bool:
    """识别上游模型过载/容量不足类原文（含半截英文，禁止原样回前端）。"""
    if not msg_l:
        return False
    overloaded_tokens = (
        'overloaded',
        'model is currently',
        'currently unavailable',
        'capacity',
        'no available',
        'server is busy',
        'too many concurrent',
        'engine is currently',
        'high demand',
        'try again later',
        'service unavailable',
    )
    return any(tok in msg_l for tok in overloaded_tokens)


def map_ai_exception(exc: Exception, *, prefix: str = 'AI分析出错') -> str:
    """将 OpenAI/httpx 异常映射为前端可展示的友好文案。

    覆盖：类名表、status_code=429、模型过载/capacity、消息含 timeout/429、httpx.TimeoutException 子树。
    原始英文详情仅应由调用方 logger.error 保留，本函数不向用户透传半截上游原文。
    """
    if exc is None:
        return f'{prefix}: 未知错误'
    error_type = type(exc).__name__
    msg = str(exc) if exc is not None else ''
    msg_l = msg.lower()

    # 0) 上游模型过载 / 容量类（可能伪装成 503/InternalServerError/APIError，优先于通用 5xx）
    if _is_model_overloaded_message(msg_l) or 'overloaded' in error_type.lower():
        return ERROR_MESSAGES['ModelOverloadedError']

    # 1) status_code 优先（APIStatusError 等通用类名需按码细分）
    status = getattr(exc, 'status_code', None)
    if status is None and getattr(exc, 'response', None) is not None:
        status = getattr(exc.response, 'status_code', None)
    try:
        if status is not None and int(status) == 429:
            return ERROR_MESSAGES['RateLimitError']
        if status is not None and int(status) in (401, 403):
            return ERROR_MESSAGES['AuthenticationError']
        # 503 常伴随 overloaded 文案；未命中 0) 时仍走通用内部错误/不可用
        if status is not None and int(status) == 503:
            return ERROR_MESSAGES['ModelOverloadedError']
        # 上游 OneAPI/网关 5xx：统一友好文案，避免前端展示裸 Error code: 502 / timeout 噪声
        if status is not None and int(status) >= 500:
            if error_type in ERROR_MESSAGES:
                return ERROR_MESSAGES[error_type]
            return ERROR_MESSAGES['InternalServerError']
    except (TypeError, ValueError):
        pass

    # 2) 显式类名表
    if error_type in ERROR_MESSAGES:
        return ERROR_MESSAGES[error_type]

    # 3) httpx 超时基类（含未列名的子类）
    try:
        if isinstance(exc, httpx.TimeoutException):
            return ERROR_MESSAGES['APITimeoutError']
        if isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
            return ERROR_MESSAGES['APIConnectionError']
    except Exception:
        pass

    # 4) 类名/消息启发式
    type_l = error_type.lower()
    if 'ratelimit' in type_l or '429' in msg_l or 'rate limit' in msg_l or 'too many requests' in msg_l:
        return ERROR_MESSAGES['RateLimitError']
    if 'timeout' in type_l or 'timed out' in msg_l or 'timeout' in msg_l:
        return ERROR_MESSAGES['APITimeoutError']
    if 'auth' in type_l or 'unauthorized' in msg_l or 'invalid api key' in msg_l:
        return ERROR_MESSAGES['AuthenticationError']
    if 'connect' in type_l or 'connection' in type_l:
        return ERROR_MESSAGES['APIConnectionError']
    if 'error code: 502' in msg_l or 'error code: 503' in msg_l or 'error code: 504' in msg_l:
        if 'error code: 503' in msg_l:
            return ERROR_MESSAGES['ModelOverloadedError']
        return ERROR_MESSAGES['InternalServerError']
    if 'upstream request failed' in msg_l or 'upstream_error' in msg_l:
        return ERROR_MESSAGES['InternalServerError']

    # 5) 兜底：仍带 prefix，但截断过长/半截英文原文，避免 UI 出现 "The model is currently"
    if msg:
        # 若仍像英文上游原文（首字母大写长句），用通用文案，不直接透传
        if len(msg) > 12 and msg[:1].isupper() and any(c.isalpha() and c.isascii() for c in msg[:40]):
            ascii_ratio = sum(1 for c in msg[:80] if ord(c) < 128) / max(1, min(80, len(msg)))
            if ascii_ratio > 0.85 and not any('\u4e00' <= c <= '\u9fff' for c in msg):
                return ERROR_MESSAGES['APIStatusError']
        return f'{prefix}: {msg}'
    return f'{prefix}: {error_type}'


def get_ai_client():
    """获取配置好的OpenAI客户端（带超时和重试）。

    无 OPENAI_API_KEY 时返回 None（不抛），调用方降级/503。
    历史契约：chat_completion / web_server / BaseStockAgent / 单测 T002 均按 None 处理。
    """
    api_key = os.getenv('OPENAI_API_KEY', None)
    base_url = os.getenv('OPENAI_API_URL', 'https://api.openai.com/v1')

    if not api_key:
        logger.error("OPENAI_API_KEY 未设置，AI 功能不可用")
        return None

    _ai_http_timeout = float(os.getenv('AI_HTTP_TIMEOUT', '600'))
    _ai_http_connect = float(os.getenv('AI_HTTP_CONNECT_TIMEOUT', '15'))
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(_ai_http_timeout, connect=_ai_http_connect),  # 2026-05-18 拉富足：由 AI_HTTP_TIMEOUT/AI_HTTP_CONNECT_TIMEOUT 驱动
        max_retries=2,
    )
    return client


def get_ai_model():
    """获取配置的AI模型名称"""
    return os.getenv('OPENAI_API_MODEL', 'gpt-4o')


def chat_completion(client, messages, temperature=0.7, max_tokens=4096, tools=None, tool_choice=None):
    """统一的聊天完成调用，带错误处理"""
    if client is None:
        return None, "AI服务未配置，请设置OPENAI_API_KEY环境变量"

    model = get_ai_model()

    try:
        kwargs = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        if tools:
            kwargs['tools'] = tools
        if tool_choice:
            kwargs['tool_choice'] = tool_choice

        response = client.chat.completions.create(**kwargs)
        return response, None
    except Exception as e:
        error_type = type(e).__name__
        friendly_msg = map_ai_exception(e, prefix='AI分析出错')
        logger.error(f"AI调用失败 [{error_type}]: {str(e)}")
        return None, friendly_msg


def get_completion_content(response):
    """从响应中提取文本内容"""
    if response and response.choices:
        return response.choices[0].message.content
    return None


_TRUNC_MAX = 10240  # 10KB上限, 超过加 "...(truncated)" 后缀
_REASONING_EVENT = 'reasoning'
_LLM_REQUEST_EVENT = 'llm_request'


def _truncate_large(text: str) -> str:
    """[UI-Q4] 零截断策略: 默认不截断; 仅当超过10KB才截断并标记"""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ''
    if len(text) > _TRUNC_MAX:
        return text[:_TRUNC_MAX] + '\n...(truncated, total={}KB)'.format(len(text) // 1024)
    return text


def _args_digest(arguments):
    """P0-4：对工具参数做稳定 digest（sha256 前 12 位）。"""
    try:
        if isinstance(arguments, dict):
            raw = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
        else:
            raw = str(arguments)
    except Exception:
        raw = repr(arguments)
    return hashlib.sha256(raw.encode('utf-8', errors='replace')).hexdigest()[:12]


def _tool_call_start_payload(tool_call_id, tool_name, arguments, agent_name=None, source=None):
    """P0-4 契约：name / args_digest / source；G1 附 provenance 摘要（强制 normalize）。"""
    src = source or (agent_name or 'chat_with_tools')
    digest = _args_digest(arguments)
    try:
        from app.core.artifact_wrapper import build_provenance_entry, normalize_provenance_list
        provenance = normalize_provenance_list([
            build_provenance_entry(source=str(src), tool=str(tool_name or ''), digest=digest)
        ])
    except Exception:
        try:
            from app.core.artifact_wrapper import normalize_provenance_list as _npl
            provenance = _npl([{
                'source': str(src)[:200],
                'tool': str(tool_name or '')[:120],
                'digest': digest or '',
            }])
        except Exception:
            provenance = []
    return {
        'tool_call_id': tool_call_id,
        'name': tool_name,
        'tool_name': tool_name,
        'args_digest': digest,
        'arguments': arguments if isinstance(arguments, dict) else {},
        'source': src,
        'agent': agent_name or '',
        'provenance': provenance,
    }


def _tool_call_result_payload(tool_call_id, tool_name, result, duration_ms, agent_name=None, source=None, ok=None, error=None):
    """P0-4 契约：ok / error / duration_ms / result_summary；保留 result 兼容展开详情。"""
    result_str = result if isinstance(result, str) else str(result)
    summary = _truncate_large(result_str)
    inferred_ok = True
    inferred_error = None
    if error:
        inferred_ok = False
        inferred_error = error
    elif isinstance(result_str, str) and result_str.lstrip().startswith('{'):
        try:
            parsed = json.loads(result_str)
            if isinstance(parsed, dict):
                if parsed.get('guardrail') in ('block', 'halt') or parsed.get('error'):
                    inferred_ok = False
                    inferred_error = str(
                        parsed.get('message') or parsed.get('error') or parsed.get('guardrail')
                    )[:200]
        except Exception:
            pass
    if ok is not None:
        inferred_ok = bool(ok)
    src = source or (agent_name or 'chat_with_tools')
    # G1 provenance 摘要（digest 基于摘要文本，不含完整行情；强制 normalize）
    try:
        from app.core.artifact_wrapper import build_provenance_entry, normalize_provenance_list
        provenance = normalize_provenance_list([
            build_provenance_entry(
                source=str(src),
                tool=str(tool_name or ''),
                digest=_args_digest(summary) if summary else None,
            )
        ])
    except Exception:
        # 兜底仍强制走 normalize，避免 except 路径泄漏未清洗字段
        try:
            from app.core.artifact_wrapper import normalize_provenance_list as _npl
            provenance = _npl([{
                'source': str(src)[:200],
                'tool': str(tool_name or '')[:120],
            }])
        except Exception:
            provenance = []
    return {
        'tool_call_id': tool_call_id,
        'name': tool_name,
        'tool_name': tool_name,
        'ok': inferred_ok,
        'error': inferred_error,
        'duration_ms': int(duration_ms or 0),
        'result_summary': summary,
        'result': summary,
        'source': src,
        'agent': agent_name or '',
        'provenance': provenance,
    }


def _publish_tool_events(event_type_wire, bus_events, payload):
    """P0-4：同时发总线主题 + 兼容 SSE event_type（tool_call_start|tool_call_result）。"""
    try:
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        for bus_name in bus_events:
            try:
                bus.publish(bus_name, {
                    'event_type': event_type_wire,
                    'data': payload,
                })
            except Exception:
                pass
    except Exception:
        pass


def _publish_reasoning(agent_name, content):
    """[UI-Q4] publish reasoning 事件 (system prompt / LLM request 等) 到 event_bus"""
    try:
        from app.core.event_bus import get_event_bus
        get_event_bus().publish(_REASONING_EVENT, {
            'event_type': 'reasoning',
            'data': {
                'agent': agent_name or '',
                'content': _truncate_large(content),
            }
        })
    except Exception:
        pass


def _publish_llm_request(agent_name, model, messages):
    """[UI-Q4] 发LLM前publish llm_request, 让Comdr看到完整prompt工程"""
    try:
        import json as _json
        msgs_str = _json.dumps(messages, ensure_ascii=False, default=str)
        content = f'[LLM_REQ] model={model} messages={msgs_str}'
        from app.core.event_bus import get_event_bus
        get_event_bus().publish(_LLM_REQUEST_EVENT, {
            'event_type': 'reasoning',
            'data': {
                'agent': agent_name or '',
                'content': _truncate_large(content),
            }
        })
    except Exception:
        pass


def chat_with_tools(client, messages, tools_schema, tool_executor=None,
                    max_tool_rounds=3, temperature=0.7, max_tokens=4096,
                    agent_name=None):
    """
    带工具调用循环的AI对话（Function Calling）。

    AI可以主动决定调用哪些工具获取数据，而非被动接收预先塞入prompt的数据。
    支持多轮工具调用：AI调用工具 → 获取结果 → 继续推理 → 可能再调用工具 → 直到给出最终回答。

    Args:
        client: OpenAI客户端
        messages: 消息列表（会被就地修改，调用方如需保留原始列表请传入副本）
        tools_schema: OpenAI格式的工具定义列表（OPENAI_TOOLS_SCHEMA 或其子集）
        tool_executor: 工具执行函数，签名 (tool_name: str, arguments: dict) -> str
                       默认使用 tools.execute_tool
        max_tool_rounds: 最大工具调用轮次（防止无限循环），默认3轮
        temperature: 温度参数
        max_tokens: 最大token数

    Returns:
        tuple: (final_content, tool_calls_log, error)
            - final_content (str|None): AI最终的文本回复
            - tool_calls_log (list): 所有工具调用记录 [{tool_name, arguments, result}]
            - error (str|None): 错误信息，成功时为None
    """
    if client is None:
        return None, [], "AI服务未配置，请设置OPENAI_API_KEY环境变量"

    # 延迟导入，避免循环依赖
    if tool_executor is None:
        from app.core.tools import execute_tool
        tool_executor = execute_tool

    # P0-1：turn 级工具失败护栏（同签名连续失败 → block；与 FallbackManager 超时层解耦）
    from app.core.tool_guardrails import turn_guardrails

    with turn_guardrails(correlation_id=agent_name or "chat_with_tools"):
        return _chat_with_tools_body(
            client, messages, tools_schema, tool_executor,
            max_tool_rounds, temperature, max_tokens, agent_name,
        )


def _chat_with_tools_body(client, messages, tools_schema, tool_executor,
                          max_tool_rounds, temperature, max_tokens, agent_name):
    """chat_with_tools 主体（已在 turn_guardrails 上下文中）。"""
    tool_calls_log = []
    model = get_ai_model()

    # [FIX-5 2026-05-18] 引入 provider adapter 处理 reasoning_content 多轮兼容
    from app.core.llm_providers import get_adapter
    adapter = get_adapter(model)

    for round_idx in range(max_tool_rounds):
        # [UI-Q4 2026-04-15 +08:00] 真·stream=True 逐token publish EVENT_TOKEN_GENERATED
        #   替代原 chat_completion 的一次性返回, 让Comdr看到"所见即所得"逐字流
        # [FIX-5] 通过 adapter 清洗 history 中违规的 reasoning_content
        request_messages, _extra_kwargs = adapter.normalize_request(messages)
        _publish_llm_request(agent_name, model, request_messages)
        stream, error = chat_completion_stream(
            client, request_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools_schema,
            tool_choice="auto"
        )

        if error:
            return None, tool_calls_log, error
        if stream is None:
            return None, tool_calls_log, "AI返回空流"

        full_content = ""
        full_reasoning = ""  # [FIX-5] 累积 reasoning_content 流，多轮 tool_call 时需回传
        last_usage: Optional[Dict[str, Any]] = None
        pending_tool_calls = {}  # {index: {id,name,arguments}}
        try:
            for chunk in stream:
                # [FIX-5] 用 adapter 统一解码 thinking/content/tool_calls/usage
                thinking_delta, content_delta, tool_call_deltas, usage = adapter.parse_stream_chunk(chunk)
                if usage:
                    last_usage = usage

                # 思考流 → publish thinking event（前端折叠灰色显示）
                if thinking_delta:
                    full_reasoning += thinking_delta
                    try:
                        from app.core.event_bus import get_event_bus, EVENT_TOKEN_GENERATED
                        get_event_bus().publish(EVENT_TOKEN_GENERATED, {
                            'event_type': 'thinking',
                            'data': {
                                'content': thinking_delta,
                                'agent': agent_name or '',
                                'round': round_idx,
                            }
                        })
                    except Exception:
                        pass

                # 文本 token → 逐token publish
                if content_delta:
                    full_content += content_delta
                    try:
                        from app.core.event_bus import get_event_bus, EVENT_TOKEN_GENERATED
                        get_event_bus().publish(EVENT_TOKEN_GENERATED, {
                            'event_type': 'token',
                            'data': {
                                'content': content_delta,
                                'agent': agent_name or '',
                                'round': round_idx,
                            }
                        })
                    except Exception:
                        pass

                # 工具调用 delta 累积
                if tool_call_deltas:
                    for tc_delta in tool_call_deltas:
                        idx = tc_delta.index
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {'id': tc_delta.id or '', 'name': '', 'arguments': ''}
                        if tc_delta.id:
                            pending_tool_calls[idx]['id'] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                pending_tool_calls[idx]['name'] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                pending_tool_calls[idx]['arguments'] += tc_delta.function.arguments

            # [FIX-5] 流结束后发布 usage 事件（DeepSeek V4 prefix cache 计费观测）
            if last_usage:
                try:
                    from app.core.event_bus import get_event_bus, EVENT_TOKEN_GENERATED
                    get_event_bus().publish(EVENT_TOKEN_GENERATED, {
                        'event_type': 'usage',
                        'data': {
                            'usage': last_usage,
                            'agent': agent_name or '',
                            'round': round_idx,
                            'model': model,
                        }
                    })
                except Exception:
                    pass
        except Exception as e:
            error_type = type(e).__name__
            friendly_msg = map_ai_exception(e, prefix='AI流式读取出错')
            logger.error(f"AI流式读取失败 [{error_type}]: {str(e)}")
            return None, tool_calls_log, friendly_msg

        # 无工具调用 → 最终文本
        if not pending_tool_calls:
            # token流结束 → publish 一次 finish_reason=stop 的空token 便于前端 finalize
            try:
                from app.core.event_bus import get_event_bus, EVENT_TOKEN_GENERATED
                get_event_bus().publish(EVENT_TOKEN_GENERATED, {
                    'event_type': 'token',
                    'data': {
                        'content': '',
                        'agent': agent_name or '',
                        'round': round_idx,
                        'finish_reason': 'stop',
                    }
                })
            except Exception:
                pass
            logger.info(f"Function Calling完成，共{round_idx}轮工具调用，调用了{len(tool_calls_log)}个工具")
            return full_content, tool_calls_log, None

        # 构造 assistant 消息追加到messages
        tool_calls_for_message = []
        for idx in sorted(pending_tool_calls.keys()):
            tc_info = pending_tool_calls[idx]
            tool_calls_for_message.append({
                "id": tc_info['id'],
                "type": "function",
                "function": {"name": tc_info['name'], "arguments": tc_info['arguments']}
            })
        # [FIX-5] 用 adapter 组装 assistant message。
        # DeepSeek V4 / MiMo 在多轮含 tool_calls 时必须写回 reasoning_content，否则下一轮 400。
        assistant_msg = adapter.assemble_assistant_message(
            content=full_content,
            reasoning_content=full_reasoning,
            tool_calls=tool_calls_for_message,
        )
        messages.append(assistant_msg)

        # 执行每个工具调用 (tc 已是 dict 结构)
        for tc in tool_calls_for_message:
            tc_id = tc["id"]
            tool_name = tc["function"]["name"]
            raw_args = tc["function"]["arguments"]
            try:
                arguments = json.loads(raw_args)
            except json.JSONDecodeError:
                arguments = {}
                logger.warning(f"工具 {tool_name} 参数解析失败: {raw_args}")

            logger.info(f"[Round {round_idx + 1}] 执行工具: {tool_name}({arguments})")

            # P0-4 规范化 tool 事件（name/args_digest/ok/error/duration_ms/source）
            _tc_start_ts = time.time()
            _tool_err = None
            try:
                from app.core.event_bus import (
                    EVENT_TOOL_CALL_START, EVENT_AGENT_TOOL_CALL,
                    EVENT_TOOL_CALL_RESULT, EVENT_AGENT_TOOL_RESULT,
                )
                _start_payload = _tool_call_start_payload(
                    tc_id, tool_name, arguments, agent_name=agent_name,
                )
                _publish_tool_events(
                    'tool_call_start',
                    [EVENT_TOOL_CALL_START, EVENT_AGENT_TOOL_CALL],
                    _start_payload,
                )
            except Exception:
                pass

            # 执行工具
            try:
                result = tool_executor(tool_name, arguments)
            except Exception as e:
                result = f"工具执行异常: {str(e)}"
                _tool_err = str(e)
                logger.error(f"工具 {tool_name} 执行异常: {e}")

            try:
                from app.core.event_bus import (
                    EVENT_TOOL_CALL_RESULT, EVENT_AGENT_TOOL_RESULT,
                )
                _result_payload = _tool_call_result_payload(
                    tc_id, tool_name, result,
                    int((time.time() - _tc_start_ts) * 1000),
                    agent_name=agent_name,
                    ok=False if _tool_err else None,
                    error=_tool_err,
                )
                _publish_tool_events(
                    'tool_call_result',
                    [EVENT_TOOL_CALL_RESULT, EVENT_AGENT_TOOL_RESULT],
                    _result_payload,
                )
            except Exception:
                pass

            # 记录调用日志 (内存保留摘要500字避免 tool_calls_log 无限膨胀)
            tool_calls_log.append({
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result[:500] if isinstance(result, str) else str(result)[:500],
                "round": round_idx + 1
            })

            # 将工具结果追加为 tool role message (完整内容送回LLM)
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result if isinstance(result, str) else str(result)
            })

    # 达到最大轮次后，做一次不带工具的最终调用，让AI给出总结
    logger.warning(f"达到最大工具调用轮次({max_tool_rounds})，请求AI给出最终总结")
    response, error = chat_completion(
        client, messages,
        temperature=temperature,
        max_tokens=max_tokens
    )

    if error:
        return None, tool_calls_log, error

    final_content = get_completion_content(response) or ""
    return final_content, tool_calls_log, None


def chat_completion_stream(client, messages, temperature=0.7, max_tokens=4096, tools=None, tool_choice=None):
    """流式聊天完成调用，返回流式迭代器

    与chat_completion()参数一致，但增加stream=True。
    返回OpenAI流式响应迭代器，调用方需自行处理chunk。

    Returns:
        (stream_iterator, error) — stream为OpenAI stream对象，error为错误信息
    """
    if client is None:
        return None, "AI服务未配置，请设置OPENAI_API_KEY环境变量"

    model = get_ai_model()

    try:
        kwargs = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': True,
        }
        if tools:
            kwargs['tools'] = tools
        if tool_choice:
            kwargs['tool_choice'] = tool_choice

        stream = client.chat.completions.create(**kwargs)
        return stream, None
    except Exception as e:
        error_type = type(e).__name__
        friendly_msg = map_ai_exception(e, prefix='AI流式分析出错')
        logger.error(f"AI流式调用失败 [{error_type}]: {str(e)}")
        return None, friendly_msg


def chat_with_tools_stream(client, messages, tools_schema, tool_executor=None,
                           max_tool_rounds=3, temperature=0.7, max_tokens=4096,
                           event_callback=None, agent_name=None):
    """带工具调用循环的流式AI对话。

    与chat_with_tools()逻辑一致，但流式输出每个token和事件。
    通过event_callback推送事件给调用方（SSE端点会将其转发给前端）。

    Args:
        client: OpenAI客户端
        messages: 消息列表（会被就地修改，调用方如需保留原始列表请传入副本）
        tools_schema: OpenAI格式的工具定义列表
        tool_executor: 工具执行函数，签名 (tool_name: str, arguments: dict) -> str
                       默认使用 tools.execute_tool
        max_tool_rounds: 最大工具调用轮次（防止无限循环），默认3轮
        temperature: 温度参数
        max_tokens: 最大token数
        event_callback: 事件回调函数，签名 (event_type: str, data: dict) -> None
            event_type: 'token' | 'tool_call_start' | 'tool_call_result' | 'reasoning' | 'error' | 'done'

    Returns:
        tuple: (final_content, tool_calls_log, error)
            - final_content (str|None): AI最终的文本回复
            - tool_calls_log (list): 所有工具调用记录 [{tool_name, arguments, result, round}]
            - error (str|None): 错误信息，成功时为None
    """
    if client is None:
        return None, [], "AI服务未配置，请设置OPENAI_API_KEY环境变量"

    # 延迟导入，避免循环依赖
    if tool_executor is None:
        from app.core.tools import execute_tool
        tool_executor = execute_tool

    # P0-1：流式 FC 同样挂 turn 级失败护栏（/api/ai/chat 主路径）
    from app.core.tool_guardrails import turn_guardrails

    with turn_guardrails(correlation_id=agent_name or "chat_with_tools_stream"):
        return _chat_with_tools_stream_body(
            client, messages, tools_schema, tool_executor,
            max_tool_rounds, temperature, max_tokens, event_callback, agent_name,
        )


def _chat_with_tools_stream_body(
    client, messages, tools_schema, tool_executor,
    max_tool_rounds, temperature, max_tokens, event_callback, agent_name,
):
    """chat_with_tools_stream 主体（已在 turn_guardrails 上下文中）。"""
    tool_calls_log = []

    # [FIX-5 2026-05-18] 引入 provider adapter 处理 reasoning_content 多轮兼容
    from app.core.llm_providers import get_adapter
    model = get_ai_model()
    adapter = get_adapter(model)

    for round_idx in range(max_tool_rounds):
        # [FIX-5] 通过 adapter 清洗 history 中违规的 reasoning_content
        request_messages, _extra_kwargs = adapter.normalize_request(messages)
        # 流式调用AI（带工具定义）
        stream, error = chat_completion_stream(
            client, request_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools_schema,
            tool_choice="auto"
        )

        if error:
            if event_callback:
                event_callback('error', {'message': error})
            return None, tool_calls_log, error

        # 遍历stream chunk，累积内容和tool_calls
        full_content = ""
        full_reasoning = ""  # [FIX-5] 累积 reasoning_content 流
        last_usage = None
        pending_tool_calls = {}  # {index: {id, name, arguments}}

        try:
            for chunk in stream:
                # [FIX-5] 用 adapter 统一解码 thinking/content/tool_calls/usage
                thinking_delta, content_delta, tool_call_deltas, usage = adapter.parse_stream_chunk(chunk)
                if usage:
                    last_usage = usage

                # 思考流: 发布 thinking 事件供前端折叠灰色显示
                if thinking_delta:
                    full_reasoning += thinking_delta
                    if event_callback:
                        event_callback('thinking', {'content': thinking_delta})
                    try:
                        from app.core.event_bus import get_event_bus, EVENT_TOKEN_GENERATED
                        get_event_bus().publish(EVENT_TOKEN_GENERATED, {
                            'event_type': 'thinking',
                            'data': {
                                'content': thinking_delta,
                                'agent': agent_name or '',
                                'round': round_idx,
                            }
                        })
                    except Exception:
                        pass

                # 处理文本内容
                if content_delta:
                    full_content += content_delta
                    if event_callback:
                        event_callback('token', {'content': content_delta})
                    # [UI-Q4 2026-04-15 +08:00] token-level publish 到 event_bus,
                    #   让 agent-analyze SSE bridge 能真实时转发到前端打字机终端
                    try:
                        from app.core.event_bus import get_event_bus, EVENT_TOKEN_GENERATED
                        get_event_bus().publish(EVENT_TOKEN_GENERATED, {
                            'event_type': 'token',
                            'data': {
                                'content': content_delta,
                                'agent': agent_name or '',
                                'round': round_idx,
                            }
                        })
                    except Exception:
                        # token publish 失败不中断 LLM 流(静默降级)
                        pass

                # 处理工具调用（流式中分chunk传递，需要累积）
                if tool_call_deltas:
                    for tc_delta in tool_call_deltas:
                        idx = tc_delta.index
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {
                                'id': tc_delta.id or '',
                                'name': tc_delta.function.name if tc_delta.function and tc_delta.function.name else '',
                                'arguments': ''
                            }
                        if tc_delta.id:
                            pending_tool_calls[idx]['id'] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                pending_tool_calls[idx]['name'] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                pending_tool_calls[idx]['arguments'] += tc_delta.function.arguments

            # [FIX-5] 流结束发布 usage 事件 (DeepSeek V4 prefix cache 观测)
            if last_usage:
                try:
                    from app.core.event_bus import get_event_bus, EVENT_TOKEN_GENERATED
                    get_event_bus().publish(EVENT_TOKEN_GENERATED, {
                        'event_type': 'usage',
                        'data': {
                            'usage': last_usage,
                            'agent': agent_name or '',
                            'round': round_idx,
                            'model': model,
                        }
                    })
                except Exception:
                    pass
        except Exception as e:
            error_type = type(e).__name__
            friendly_msg = map_ai_exception(e, prefix='AI流式读取出错')
            logger.error(f"AI流式读取失败 [{error_type}]: {str(e)}")
            if event_callback:
                event_callback('error', {'message': friendly_msg})
            return None, tool_calls_log, friendly_msg

        # 检查是否有工具调用
        if not pending_tool_calls:
            # AI没有调用工具，返回最终文本
            logger.info(f"流式Function Calling完成，共{round_idx}轮工具调用，"
                        f"调用了{len(tool_calls_log)}个工具")
            if event_callback:
                event_callback('done', {'content': full_content})
            return full_content, tool_calls_log, None

        # 构造assistant消息（含tool_calls）追加到消息列表
        tool_calls_for_message = []
        for idx in sorted(pending_tool_calls.keys()):
            tc_info = pending_tool_calls[idx]
            tool_calls_for_message.append({
                "id": tc_info['id'],
                "type": "function",
                "function": {
                    "name": tc_info['name'],
                    "arguments": tc_info['arguments']
                }
            })

        # [FIX-5] 用 adapter 组装 assistant message
        # DeepSeek V4 / MiMo 在多轮含 tool_calls 时必须写回 reasoning_content
        assistant_msg = adapter.assemble_assistant_message(
            content=full_content,
            reasoning_content=full_reasoning,
            tool_calls=tool_calls_for_message,
        )
        messages.append(assistant_msg)

        # 执行每个工具调用
        for tc_msg in tool_calls_for_message:
            tool_name = tc_msg['function']['name']
            try:
                raw_args = tc_msg['function']['arguments']
                arguments = json.loads(raw_args)
            except json.JSONDecodeError:
                # 尝试提取第一个有效JSON对象（AI可能返回多个JSON连在一起）
                raw_args = tc_msg['function']['arguments']
                import re
                match = re.search(r'\{[^{}]*\}', raw_args)
                if match:
                    try:
                        arguments = json.loads(match.group(0))
                        logger.warning(f"工具 {tool_name} 参数修复：从多JSON中提取第一个")
                    except json.JSONDecodeError:
                        arguments = {}
                        logger.warning(f"工具 {tool_name} 参数解析彻底失败: {raw_args[:200]}")
                else:
                    arguments = {}
                    logger.warning(f"工具 {tool_name} 参数解析失败: {raw_args[:200]}")

            logger.info(f"[流式 Round {round_idx + 1}] 执行工具: {tool_name}({arguments})")

            _tc_start_ts = time.time()
            _tool_err = None
            _start_payload = _tool_call_start_payload(
                tc_msg['id'], tool_name, arguments, agent_name=agent_name,
            )
            if event_callback:
                event_callback('tool_call_start', _start_payload)
            # P0-4：总线历史主题 + agent.tool_call 契约主题
            try:
                from app.core.event_bus import (
                    EVENT_TOOL_CALL_START, EVENT_AGENT_TOOL_CALL,
                )
                _publish_tool_events(
                    'tool_call_start',
                    [EVENT_TOOL_CALL_START, EVENT_AGENT_TOOL_CALL],
                    _start_payload,
                )
            except Exception:
                pass

            # 执行工具
            try:
                result = tool_executor(tool_name, arguments)
            except Exception as e:
                result = f"工具执行异常: {str(e)}"
                _tool_err = str(e)
                logger.error(f"工具 {tool_name} 执行异常: {e}")

            duration_ms = int((time.time() - _tc_start_ts) * 1000)
            _result_payload = _tool_call_result_payload(
                tc_msg['id'], tool_name, result, duration_ms,
                agent_name=agent_name,
                ok=False if _tool_err else None,
                error=_tool_err,
            )
            if event_callback:
                event_callback('tool_call_result', _result_payload)
            try:
                from app.core.event_bus import (
                    EVENT_TOOL_CALL_RESULT, EVENT_AGENT_TOOL_RESULT,
                )
                _publish_tool_events(
                    'tool_call_result',
                    [EVENT_TOOL_CALL_RESULT, EVENT_AGENT_TOOL_RESULT],
                    _result_payload,
                )
            except Exception:
                pass

            # 记录调用日志
            tool_calls_log.append({
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result[:500] if isinstance(result, str) else str(result)[:500],
                "round": round_idx + 1
            })

            # 将工具结果追加为 tool role message
            messages.append({
                "role": "tool",
                "tool_call_id": tc_msg['id'],
                "content": result if isinstance(result, str) else str(result)
            })

    # 达到最大轮次后，做一次不带工具的非流式最终调用，让AI给出总结
    logger.warning(f"流式模式达到最大工具调用轮次({max_tool_rounds})，请求AI给出最终总结")
    response, error = chat_completion(
        client, messages,
        temperature=temperature,
        max_tokens=max_tokens
    )

    if error:
        if event_callback:
            event_callback('error', {'message': error})
        return None, tool_calls_log, error

    final_content = get_completion_content(response) or ""
    if event_callback:
        event_callback('done', {'content': final_content})
    return final_content, tool_calls_log, None
