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
from openai import OpenAI
import httpx

logger = logging.getLogger(__name__)

# 友好错误消息映射
ERROR_MESSAGES = {
    'RateLimitError': '服务繁忙，请稍后重试（API限流）',
    'APITimeoutError': 'AI分析超时，请稍后重试',
    'APIConnectionError': '无法连接AI服务，请检查网络',
    'AuthenticationError': 'AI服务认证失败，请检查API密钥配置',
    'APIStatusError': 'AI服务暂时不可用，请稍后重试',
}


def get_ai_client():
    """获取配置好的OpenAI客户端（带超时和重试）"""
    api_key = os.getenv('OPENAI_API_KEY')
    base_url = os.getenv('OPENAI_API_URL', 'https://api.openai.com/v1')

    if not api_key:
        logger.warning("OPENAI_API_KEY 未配置，AI功能将不可用")
        return None

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(180.0, connect=10.0),
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
        friendly_msg = ERROR_MESSAGES.get(error_type, f'AI分析出错: {str(e)}')
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

    tool_calls_log = []
    model = get_ai_model()

    for round_idx in range(max_tool_rounds):
        # [UI-Q4 2026-04-15 +08:00] 真·stream=True 逐token publish EVENT_TOKEN_GENERATED
        #   替代原 chat_completion 的一次性返回, 让Comdr看到"所见即所得"逐字流
        _publish_llm_request(agent_name, model, messages)
        stream, error = chat_completion_stream(
            client, messages,
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
        pending_tool_calls = {}  # {index: {id,name,arguments}}
        try:
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                # 文本 token → 逐token publish
                if delta.content:
                    full_content += delta.content
                    try:
                        from app.core.event_bus import get_event_bus, EVENT_TOKEN_GENERATED
                        get_event_bus().publish(EVENT_TOKEN_GENERATED, {
                            'event_type': 'token',
                            'data': {
                                'content': delta.content,
                                'agent': agent_name or '',
                                'round': round_idx,
                            }
                        })
                    except Exception:
                        pass
                # 工具调用 delta 累积
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
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
        except Exception as e:
            error_type = type(e).__name__
            friendly_msg = ERROR_MESSAGES.get(error_type, f'AI流式读取出错: {str(e)}')
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
        messages.append({
            "role": "assistant",
            "content": full_content or None,
            "tool_calls": tool_calls_for_message
        })

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

            # [UI-Q3→UI-Q4] publish tool_call_start 到 event_bus (完整arguments, 零截断除非>10KB)
            _tc_start_ts = time.time()
            try:
                from app.core.event_bus import get_event_bus, EVENT_TOOL_CALL_START
                try:
                    _args_full = json.dumps(arguments, ensure_ascii=False)
                except Exception:
                    _args_full = str(arguments)
                get_event_bus().publish(EVENT_TOOL_CALL_START, {
                    'event_type': 'tool_call_start',
                    'data': {
                        'tool_call_id': tc_id,
                        'tool_name': tool_name,
                        'arguments': arguments,  # 结构化对象, 前端可决定如何显示
                        'arguments_raw': _truncate_large(_args_full),  # 完整原始
                        'agent': agent_name or '',
                    }
                })
            except Exception:
                pass

            # 执行工具
            try:
                result = tool_executor(tool_name, arguments)
            except Exception as e:
                result = f"工具执行异常: {str(e)}"
                logger.error(f"工具 {tool_name} 执行异常: {e}")

            # [UI-Q3→UI-Q4] publish tool_call_result 到 event_bus (完整结果, 零截断除非>10KB)
            try:
                from app.core.event_bus import get_event_bus, EVENT_TOOL_CALL_RESULT
                _result_str = result if isinstance(result, str) else str(result)
                get_event_bus().publish(EVENT_TOOL_CALL_RESULT, {
                    'event_type': 'tool_call_result',
                    'data': {
                        'tool_call_id': tc_id,
                        'tool_name': tool_name,
                        'result_summary': _truncate_large(_result_str),
                        'duration_ms': int((time.time() - _tc_start_ts) * 1000),
                        'agent': agent_name or '',
                    }
                })
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
        friendly_msg = ERROR_MESSAGES.get(error_type, f'AI分析出错: {str(e)}')
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

    tool_calls_log = []

    for round_idx in range(max_tool_rounds):
        # 流式调用AI（带工具定义）
        stream, error = chat_completion_stream(
            client, messages,
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
        pending_tool_calls = {}  # {index: {id, name, arguments}}

        try:
            for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # 处理文本内容
                if delta.content:
                    full_content += delta.content
                    if event_callback:
                        event_callback('token', {'content': delta.content})
                    # [UI-Q4 2026-04-15 +08:00] token-level publish 到 event_bus,
                    #   让 agent-analyze SSE bridge 能真实时转发到前端打字机终端
                    try:
                        from app.core.event_bus import get_event_bus, EVENT_TOKEN_GENERATED
                        get_event_bus().publish(EVENT_TOKEN_GENERATED, {
                            'event_type': 'token',
                            'data': {
                                'content': delta.content,
                                'agent': agent_name or '',
                                'round': round_idx,
                            }
                        })
                    except Exception:
                        # token publish 失败不中断 LLM 流(静默降级)
                        pass

                # 处理工具调用（流式中分chunk传递，需要累积）
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
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
        except Exception as e:
            error_type = type(e).__name__
            friendly_msg = ERROR_MESSAGES.get(error_type, f'AI流式读取出错: {str(e)}')
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

        assistant_msg = {
            "role": "assistant",
            "content": full_content or None,
            "tool_calls": tool_calls_for_message
        }
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
            if event_callback:
                event_callback('tool_call_start', {
                    'tool_call_id': tc_msg['id'],
                    'tool_name': tool_name,
                    'arguments': arguments
                })
            # [UI-Q3→UI-Q4] publish到event_bus, 完整arguments零截断
            try:
                from app.core.event_bus import get_event_bus, EVENT_TOOL_CALL_START
                try:
                    _args_full = json.dumps(arguments, ensure_ascii=False)
                except Exception:
                    _args_full = str(arguments)
                get_event_bus().publish(EVENT_TOOL_CALL_START, {
                    'event_type': 'tool_call_start',
                    'data': {
                        'tool_call_id': tc_msg['id'],
                        'tool_name': tool_name,
                        'arguments': arguments,
                        'arguments_raw': _truncate_large(_args_full),
                        'agent': agent_name or '',
                    }
                })
            except Exception:
                pass

            # 执行工具
            try:
                result = tool_executor(tool_name, arguments)
            except Exception as e:
                result = f"工具执行异常: {str(e)}"
                logger.error(f"工具 {tool_name} 执行异常: {e}")

            if event_callback:
                event_callback('tool_call_result', {
                    'tool_call_id': tc_msg['id'],
                    'tool_name': tool_name,
                    'result': result[:500] if isinstance(result, str) else str(result)[:500]
                })
            # [UI-Q3→UI-Q4] publish到event_bus, 完整result零截断(>10KB才标记)
            try:
                from app.core.event_bus import get_event_bus, EVENT_TOOL_CALL_RESULT
                _result_str = result if isinstance(result, str) else str(result)
                get_event_bus().publish(EVENT_TOOL_CALL_RESULT, {
                    'event_type': 'tool_call_result',
                    'data': {
                        'tool_call_id': tc_msg['id'],
                        'tool_name': tool_name,
                        'result_summary': _truncate_large(_result_str),
                        'duration_ms': int((time.time() - _tc_start_ts) * 1000),
                        'agent': agent_name or '',
                    }
                })
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
