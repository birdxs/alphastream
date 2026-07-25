"""
Input: 模型名 + 原始 messages/stream chunk
Output: 归一化的请求字段 + 统一的 (thinking_delta, content_delta, tool_call_delta, usage) 元组
Pos: app/core/llm_providers.py - LLM provider 适配器层，隔离 reasoning_content 多轮回传规则差异

[FIX-5 2026-05-18 +08:00] Reasoning 协议三方兼容层。
依据 RESEARCH-01 调研:
  - DeepSeek V4 / MiMo: 多轮 tool_call 必须回传 assistant.reasoning_content
  - DeepSeek R1 (legacy): 任何场景不能回传 reasoning_content (传了 400)
  - OpenAI o1/o3: API 屏蔽 reasoning_content, 支持 reasoning_effort
  - Generic: 兜底, 剥离所有 reasoning 字段

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _to_plain_jsonable(value: Any) -> Any:
    """把 OpenAI SDK / Pydantic 嵌套对象压成 json.dumps 可序列化结构。

    背景：stream chunk.usage.completion_tokens_details 常为
    openai.types.completion_usage.CompletionTokensDetails，原样塞进 SSE
    会触发 TypeError: Object of type CompletionTokensDetails is not JSON serializable，
    导致 /api/ai/chat 与 /api/ai/agent-analyze 流式连接被服务端中断（前端 network error）。
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _to_plain_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_jsonable(v) for v in value]
    # Pydantic v2
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _to_plain_jsonable(model_dump())
        except Exception:
            pass
    # Pydantic v1
    as_dict = getattr(value, "dict", None)
    if callable(as_dict):
        try:
            return _to_plain_jsonable(as_dict())
        except Exception:
            pass
    # 普通对象：只取公开属性
    if hasattr(value, "__dict__") and not isinstance(value, type):
        try:
            return {
                k: _to_plain_jsonable(v)
                for k, v in vars(value).items()
                if not str(k).startswith("_")
            }
        except Exception:
            pass
    return str(value)


class ReasoningAdapter:
    """provider 适配器基类。子类实现请求归一化与流式解码的差异。"""

    name: str = "generic"
    supports_reasoning: bool = False
    reasoning_history_policy: str = "strip"  # "strip" | "keep" | "keep_for_tool"

    def normalize_request(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """归一化请求 messages 与 extra kwargs。

        Returns:
            (清洗后的 messages, 注入到 client 调用的额外字段)
        """
        clean_messages = self._apply_history_policy(messages)
        extra = self._build_extra_kwargs(**kwargs)
        return clean_messages, extra

    def _apply_history_policy(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """根据 reasoning_history_policy 处理历史 assistant 消息中的 reasoning_content。"""
        if self.reasoning_history_policy == "keep":
            return list(messages)

        cleaned: List[Dict[str, Any]] = []
        n = len(messages)
        # 找到最后一个 user/system 之后开始的 assistant + tool 序列(当前轮)
        # 当前轮的 reasoning_content 在 keep_for_tool 模式下应保留
        last_user_idx = -1
        for i in range(n - 1, -1, -1):
            if messages[i].get("role") in ("user", "system"):
                last_user_idx = i
                break

        for i, msg in enumerate(messages):
            if msg.get("role") != "assistant":
                cleaned.append(msg)
                continue

            new_msg = dict(msg)
            should_strip = True
            if self.reasoning_history_policy == "keep_for_tool":
                # 仅保留"当前轮"(last_user_idx 之后) 且带 tool_calls 的 assistant 消息的 reasoning_content
                if i > last_user_idx and new_msg.get("tool_calls"):
                    should_strip = False

            if should_strip:
                new_msg.pop("reasoning_content", None)
                new_msg.pop("reasoning_details", None)
            cleaned.append(new_msg)

        return cleaned

    def _build_extra_kwargs(self, **kwargs) -> Dict[str, Any]:
        return {}

    def parse_stream_chunk(self, chunk) -> Tuple[str, str, list, Optional[Dict[str, Any]]]:
        """解析流式 chunk，返回 (thinking_delta, content_delta, tool_call_deltas, usage)。"""
        thinking_delta = ""
        content_delta = ""
        tool_call_deltas: list = []
        usage = None

        try:
            if hasattr(chunk, "usage") and chunk.usage:
                u = chunk.usage
                usage = {
                    "prompt_tokens": getattr(u, "prompt_tokens", None),
                    "completion_tokens": getattr(u, "completion_tokens", None),
                    "total_tokens": getattr(u, "total_tokens", None),
                    # DeepSeek V4 prefix cache 字段透传
                    "prompt_cache_hit_tokens": getattr(u, "prompt_cache_hit_tokens", None),
                    "prompt_cache_miss_tokens": getattr(u, "prompt_cache_miss_tokens", None),
                    # OpenAI o1/reasoning token 字段（必须压成 plain dict，禁止 SDK 对象透传）
                    "completion_tokens_details": _to_plain_jsonable(
                        getattr(u, "completion_tokens_details", None)
                    ),
                    "prompt_tokens_details": _to_plain_jsonable(
                        getattr(u, "prompt_tokens_details", None)
                    ),
                }
        except Exception:
            pass

        try:
            if not chunk.choices:
                return thinking_delta, content_delta, tool_call_deltas, usage
            delta = chunk.choices[0].delta

            # 思考流: DeepSeek V4 / MiMo
            rc = getattr(delta, "reasoning_content", None)
            if rc:
                thinking_delta = rc

            # OpenRouter mimo: reasoning_details 数组
            rd = getattr(delta, "reasoning_details", None)
            if rd and not thinking_delta:
                try:
                    for item in rd:
                        text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
                        if text:
                            thinking_delta += text
                except Exception:
                    pass

            # 最终内容流
            if getattr(delta, "content", None):
                content_delta = delta.content

            # 工具调用 delta
            if getattr(delta, "tool_calls", None):
                tool_call_deltas = delta.tool_calls
        except Exception as e:
            logger.debug(f"parse_stream_chunk 异常: {e}")

        return thinking_delta, content_delta, tool_call_deltas, usage

    def assemble_assistant_message(
        self,
        content: str,
        reasoning_content: str,
        tool_calls: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """把累积的 content / reasoning_content / tool_calls 组装为 assistant message。

        provider 差异：DeepSeek V4 / MiMo 在多轮 tool_call 中必须把 reasoning_content
        写回 message，否则下一轮 400。
        """
        msg: Dict[str, Any] = {
            "role": "assistant",
            "content": content or None,
        }
        if tool_calls:
            msg["tool_calls"] = tool_calls
        # 仅当 provider 要求保留时才写入 reasoning_content
        if self.reasoning_history_policy in ("keep", "keep_for_tool") and reasoning_content:
            msg["reasoning_content"] = reasoning_content
        return msg

    def supports_cache(self) -> bool:
        return False


class DeepSeekV4Adapter(ReasoningAdapter):
    """DeepSeek V4 Pro / V4 Flash. thinking mode 默认开启，多轮含 tool 必须回传 reasoning_content。"""
    name = "deepseek-v4"
    supports_reasoning = True
    reasoning_history_policy = "keep_for_tool"

    def _build_extra_kwargs(self, **kwargs) -> Dict[str, Any]:
        extra: Dict[str, Any] = {}
        effort = kwargs.get("reasoning_effort")
        if effort:
            extra["reasoning_effort"] = effort
        return extra

    def supports_cache(self) -> bool:
        return True


class DeepSeekV3Adapter(ReasoningAdapter):
    """DeepSeek V3 / deepseek-chat. 非 reasoning, 普通 OpenAI 兼容。"""
    name = "deepseek-v3"
    supports_reasoning = False
    reasoning_history_policy = "strip"

    def supports_cache(self) -> bool:
        return True


class DeepSeekR1Adapter(ReasoningAdapter):
    """DeepSeek R1 / deepseek-reasoner (legacy). 任何场景禁止回传 reasoning_content。"""
    name = "deepseek-r1"
    supports_reasoning = True
    reasoning_history_policy = "strip"


class MimoAdapter(ReasoningAdapter):
    """Xiaomi MiMo-V2.5-Pro。与 DeepSeek V4 协议同源：多轮含 tool 必须回传。"""
    name = "mimo"
    supports_reasoning = True
    reasoning_history_policy = "keep_for_tool"


class OpenAIO1Adapter(ReasoningAdapter):
    """OpenAI o1 / o3. API 屏蔽 reasoning_content, 支持 reasoning_effort。"""
    name = "openai-o1"
    supports_reasoning = True
    reasoning_history_policy = "strip"

    def _build_extra_kwargs(self, **kwargs) -> Dict[str, Any]:
        extra: Dict[str, Any] = {}
        effort = kwargs.get("reasoning_effort")
        if effort:
            extra["reasoning_effort"] = effort
        return extra


class GenericOpenAIAdapter(ReasoningAdapter):
    """兜底：普通 OpenAI 兼容模型（gpt-4o, claude via proxy 等）。"""
    name = "generic"
    supports_reasoning = False
    reasoning_history_policy = "strip"


# === 路由 ===

_ADAPTER_PATTERNS = [
    (re.compile(r"^deepseek-v4", re.I), DeepSeekV4Adapter),
    (re.compile(r"^deepseek-v3", re.I), DeepSeekV3Adapter),
    (re.compile(r"^deepseek-chat", re.I), DeepSeekV3Adapter),
    (re.compile(r"^deepseek-r1", re.I), DeepSeekR1Adapter),
    (re.compile(r"^deepseek-reasoner", re.I), DeepSeekR1Adapter),
    (re.compile(r"^mimo", re.I), MimoAdapter),
    (re.compile(r"^o[13](-|$)", re.I), OpenAIO1Adapter),
]


def get_adapter(model_name: Optional[str]) -> ReasoningAdapter:
    """按模型名前缀匹配 adapter，未匹配返回 GenericOpenAIAdapter。"""
    if not model_name:
        return GenericOpenAIAdapter()
    for pattern, cls in _ADAPTER_PATTERNS:
        if pattern.match(model_name):
            return cls()
    return GenericOpenAIAdapter()
