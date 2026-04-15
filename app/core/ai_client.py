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


def chat_with_tools(client, messages, tools_schema, tool_executor=None,
                    max_tool_rounds=3, temperature=0.7, max_tokens=4096):
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

    for round_idx in range(max_tool_rounds):
        # 调用AI（带工具定义）
        response, error = chat_completion(
            client, messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools_schema,
            tool_choice="auto"
        )

        if error:
            return None, tool_calls_log, error

        if not response or not response.choices:
            return None, tool_calls_log, "AI返回空响应"

        assistant_message = response.choices[0].message

        # 检查是否有工具调用
        if not assistant_message.tool_calls:
            # AI没有调用工具，返回最终文本
            final_content = assistant_message.content or ""
            logger.info(f"Function Calling完成，共{round_idx}轮工具调用，"
                        f"调用了{len(tool_calls_log)}个工具")
            return final_content, tool_calls_log, None

        # 将assistant消息（含tool_calls）追加到消息列表
        messages.append(assistant_message)

        # 执行每个工具调用
        for tc in assistant_message.tool_calls:
            tool_name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                arguments = {}
                logger.warning(f"工具 {tool_name} 参数解析失败: {tc.function.arguments}")

            logger.info(f"[Round {round_idx + 1}] 执行工具: {tool_name}({arguments})")

            # [UI-Q3 2026-04-15] publish tool_call_start 到 event_bus (SSE桥接)
            _tc_start_ts = time.time()
            try:
                from app.core.event_bus import get_event_bus, EVENT_TOOL_CALL_START
                _args_preview = arguments
                try:
                    _args_str = json.dumps(arguments, ensure_ascii=False)
                    if len(_args_str) > 200:
                        _args_preview = _args_str[:200] + '...'
                except Exception:
                    _args_preview = str(arguments)[:200]
                get_event_bus().publish(EVENT_TOOL_CALL_START, {
                    'event_type': 'tool_call_start',
                    'data': {
                        'tool_call_id': tc.id,
                        'tool_name': tool_name,
                        'arguments': _args_preview,
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

            # [UI-Q3 2026-04-15] publish tool_call_result 到 event_bus
            try:
                from app.core.event_bus import get_event_bus, EVENT_TOOL_CALL_RESULT
                _result_summary = result if isinstance(result, str) else str(result)
                if len(_result_summary) > 200:
                    _result_summary = _result_summary[:200] + '...'
                get_event_bus().publish(EVENT_TOOL_CALL_RESULT, {
                    'event_type': 'tool_call_result',
                    'data': {
                        'tool_call_id': tc.id,
                        'tool_name': tool_name,
                        'result_summary': _result_summary,
                        'duration_ms': int((time.time() - _tc_start_ts) * 1000),
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
                "tool_call_id": tc.id,
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
                           event_callback=None):
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
            # [UI-Q3 2026-04-15] 同时publish到event_bus, 让SSE桥接方式也能收到
            try:
                from app.core.event_bus import get_event_bus, EVENT_TOOL_CALL_START
                _args_preview = arguments
                try:
                    _args_str = json.dumps(arguments, ensure_ascii=False)
                    if len(_args_str) > 200:
                        _args_preview = _args_str[:200] + '...'
                except Exception:
                    _args_preview = str(arguments)[:200]
                get_event_bus().publish(EVENT_TOOL_CALL_START, {
                    'event_type': 'tool_call_start',
                    'data': {
                        'tool_call_id': tc_msg['id'],
                        'tool_name': tool_name,
                        'arguments': _args_preview,
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
            # [UI-Q3 2026-04-15] 同时publish到event_bus
            try:
                from app.core.event_bus import get_event_bus, EVENT_TOOL_CALL_RESULT
                _result_summary = result if isinstance(result, str) else str(result)
                if len(_result_summary) > 200:
                    _result_summary = _result_summary[:200] + '...'
                get_event_bus().publish(EVENT_TOOL_CALL_RESULT, {
                    'event_type': 'tool_call_result',
                    'data': {
                        'tool_call_id': tc_msg['id'],
                        'tool_name': tool_name,
                        'result_summary': _result_summary,
                        'duration_ms': int((time.time() - _tc_start_ts) * 1000),
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
