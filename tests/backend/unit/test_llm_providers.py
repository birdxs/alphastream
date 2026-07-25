"""
Input: 模型名 / messages / mock stream chunk
Output: 验证 adapter 路由、history 清洗、stream 解码、assistant message 组装
Pos: tests/backend/unit/test_llm_providers.py - FIX-5 配套测试

[FIX-5 2026-05-18 +08:00] 多 provider reasoning 协议适配层。
对应 RESEARCH-01 三方协议矩阵的关键差异点全覆盖。
"""
import pytest
from unittest.mock import MagicMock

from app.core.llm_providers import (
    get_adapter,
    DeepSeekV4Adapter,
    DeepSeekV3Adapter,
    DeepSeekR1Adapter,
    MimoAdapter,
    OpenAIO1Adapter,
    GenericOpenAIAdapter,
    ReasoningAdapter,
)


# ===== 路由测试 =====

class TestGetAdapter:
    def test_deepseek_v4_pro(self):
        assert isinstance(get_adapter("deepseek-v4-pro"), DeepSeekV4Adapter)

    def test_deepseek_v4_flash(self):
        assert isinstance(get_adapter("deepseek-v4-flash"), DeepSeekV4Adapter)

    def test_deepseek_v3(self):
        assert isinstance(get_adapter("deepseek-v3"), DeepSeekV3Adapter)

    def test_deepseek_chat_routes_to_v3(self):
        assert isinstance(get_adapter("deepseek-chat"), DeepSeekV3Adapter)

    def test_deepseek_r1(self):
        assert isinstance(get_adapter("deepseek-r1"), DeepSeekR1Adapter)

    def test_deepseek_reasoner(self):
        assert isinstance(get_adapter("deepseek-reasoner"), DeepSeekR1Adapter)

    def test_mimo(self):
        assert isinstance(get_adapter("mimo-v2.5-pro"), MimoAdapter)

    def test_openai_o1(self):
        assert isinstance(get_adapter("o1-preview"), OpenAIO1Adapter)

    def test_openai_o3(self):
        assert isinstance(get_adapter("o3-mini"), OpenAIO1Adapter)

    def test_unknown_falls_back(self):
        a = get_adapter("gpt-4o")
        assert isinstance(a, GenericOpenAIAdapter)

    def test_none_falls_back(self):
        assert isinstance(get_adapter(None), GenericOpenAIAdapter)

    def test_case_insensitive(self):
        assert isinstance(get_adapter("DeepSeek-V4-Pro"), DeepSeekV4Adapter)


# ===== history 清洗规则 =====

class TestHistoryPolicy:
    def _make_history_with_tool_calls(self):
        """模拟一轮 tool_call 完成后的 history"""
        return [
            {"role": "system", "content": "you are an analyst"},
            {"role": "user", "content": "分析000001"},
            {
                "role": "assistant",
                "content": None,
                "reasoning_content": "我应该先获取数据",
                "tool_calls": [
                    {"id": "call_1", "type": "function",
                     "function": {"name": "get_stock_data", "arguments": "{}"}}
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "{stock:000001 price:10.87}"},
        ]

    def test_v4_keeps_reasoning_in_current_round_tool_call(self):
        """DeepSeek V4: 当前轮 tool_call 的 reasoning_content 必须保留 (协议强制)"""
        a = DeepSeekV4Adapter()
        history = self._make_history_with_tool_calls()
        cleaned, _ = a.normalize_request(history)
        assistant_msgs = [m for m in cleaned if m.get("role") == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].get("reasoning_content") == "我应该先获取数据"

    def test_mimo_keeps_reasoning_in_current_round_tool_call(self):
        """MiMo: 协议同 V4"""
        a = MimoAdapter()
        history = self._make_history_with_tool_calls()
        cleaned, _ = a.normalize_request(history)
        assistant_msgs = [m for m in cleaned if m.get("role") == "assistant"]
        assert assistant_msgs[0].get("reasoning_content") == "我应该先获取数据"

    def test_r1_strips_reasoning_always(self):
        """DeepSeek R1: 任何场景禁止回传 reasoning_content"""
        a = DeepSeekR1Adapter()
        history = self._make_history_with_tool_calls()
        cleaned, _ = a.normalize_request(history)
        assistant_msgs = [m for m in cleaned if m.get("role") == "assistant"]
        assert "reasoning_content" not in assistant_msgs[0]

    def test_o1_strips_reasoning(self):
        """OpenAI o1: API 屏蔽 reasoning_content"""
        a = OpenAIO1Adapter()
        history = self._make_history_with_tool_calls()
        cleaned, _ = a.normalize_request(history)
        assistant_msgs = [m for m in cleaned if m.get("role") == "assistant"]
        assert "reasoning_content" not in assistant_msgs[0]

    def test_generic_strips_reasoning(self):
        """Generic 兜底: 剥离所有 reasoning"""
        a = GenericOpenAIAdapter()
        history = self._make_history_with_tool_calls()
        cleaned, _ = a.normalize_request(history)
        assistant_msgs = [m for m in cleaned if m.get("role") == "assistant"]
        assert "reasoning_content" not in assistant_msgs[0]

    def test_v4_strips_old_round_reasoning(self):
        """V4: 历史轮次(已过 user message 之前)的 reasoning_content 应剥离"""
        a = DeepSeekV4Adapter()
        history = [
            {"role": "user", "content": "first"},
            {
                "role": "assistant",
                "content": "answer1",
                "reasoning_content": "old thinking",
            },
            {"role": "user", "content": "second"},
            {
                "role": "assistant",
                "content": None,
                "reasoning_content": "new thinking",
                "tool_calls": [
                    {"id": "c1", "type": "function",
                     "function": {"name": "f", "arguments": "{}"}}
                ],
            },
        ]
        cleaned, _ = a.normalize_request(history)
        asst = [m for m in cleaned if m.get("role") == "assistant"]
        # 旧轮被剥离
        assert "reasoning_content" not in asst[0]
        # 新轮保留
        assert asst[1]["reasoning_content"] == "new thinking"

    def test_does_not_mutate_input(self):
        """归一化不应改写原始 messages"""
        a = DeepSeekR1Adapter()
        history = self._make_history_with_tool_calls()
        original = [dict(m) for m in history]
        a.normalize_request(history)
        for orig, cur in zip(original, history):
            assert orig.get("reasoning_content") == cur.get("reasoning_content")


# ===== 流式 chunk 解码 =====

def _make_chunk(content=None, reasoning_content=None, tool_calls=None, usage=None):
    """构造 mock OpenAI stream chunk"""
    chunk = MagicMock()
    delta = MagicMock()
    delta.content = content
    delta.reasoning_content = reasoning_content
    delta.reasoning_details = None
    delta.tool_calls = tool_calls
    choice = MagicMock()
    choice.delta = delta
    chunk.choices = [choice]
    chunk.usage = usage
    return chunk


class TestStreamParsing:
    def test_v4_parses_reasoning_content(self):
        a = DeepSeekV4Adapter()
        chunk = _make_chunk(reasoning_content="思考中")
        th, ct, tc, usage = a.parse_stream_chunk(chunk)
        assert th == "思考中"
        assert ct == ""
        assert tc == []

    def test_mimo_parses_reasoning_content(self):
        a = MimoAdapter()
        chunk = _make_chunk(reasoning_content="MiMo 推理")
        th, ct, _, _ = a.parse_stream_chunk(chunk)
        assert th == "MiMo 推理"

    def test_content_delta(self):
        a = DeepSeekV4Adapter()
        chunk = _make_chunk(content="最终答案")
        th, ct, _, _ = a.parse_stream_chunk(chunk)
        assert ct == "最终答案"
        assert th == ""

    def test_generic_ignores_reasoning_field(self):
        """Generic adapter 仍然能解析 reasoning_content delta (响应侧不歧视)，
        但 history 侧会剥离 → 验证流解码与历史清洗解耦"""
        a = GenericOpenAIAdapter()
        chunk = _make_chunk(reasoning_content="x", content="y")
        th, ct, _, _ = a.parse_stream_chunk(chunk)
        # 响应侧统一暴露
        assert th == "x"
        assert ct == "y"

    def test_v4_extracts_cache_usage(self):
        """DeepSeek V4 prefix cache 计费字段透传"""
        a = DeepSeekV4Adapter()
        usage = MagicMock()
        usage.prompt_tokens = 100
        usage.completion_tokens = 50
        usage.total_tokens = 150
        usage.prompt_cache_hit_tokens = 80
        usage.prompt_cache_miss_tokens = 20
        usage.completion_tokens_details = None
        usage.prompt_tokens_details = None
        chunk = _make_chunk(usage=usage)
        chunk.choices = []
        _, _, _, u = a.parse_stream_chunk(chunk)
        assert u["prompt_cache_hit_tokens"] == 80
        assert u["prompt_cache_miss_tokens"] == 20
        assert u["prompt_tokens"] == 100

    def test_usage_details_are_json_serializable(self):
        """OpenAI CompletionTokensDetails 等 SDK 对象不得透传到 SSE json.dumps。"""
        import json

        a = DeepSeekV4Adapter()
        details = MagicMock()
        details.reasoning_tokens = 12
        details.audio_tokens = None
        details.model_dump = MagicMock(
            return_value={"reasoning_tokens": 12, "audio_tokens": None}
        )
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 5
        usage.total_tokens = 15
        usage.prompt_cache_hit_tokens = None
        usage.prompt_cache_miss_tokens = None
        usage.completion_tokens_details = details
        usage.prompt_tokens_details = None
        chunk = _make_chunk(usage=usage)
        chunk.choices = []
        _, _, _, u = a.parse_stream_chunk(chunk)
        assert isinstance(u["completion_tokens_details"], dict)
        assert u["completion_tokens_details"]["reasoning_tokens"] == 12
        # 关键：可直接 json.dumps，不会 TypeError
        json.dumps(u, ensure_ascii=False)

    def test_empty_choices_safe(self):
        a = DeepSeekV4Adapter()
        chunk = MagicMock()
        chunk.choices = []
        chunk.usage = None
        th, ct, tc, u = a.parse_stream_chunk(chunk)
        assert th == "" and ct == "" and tc == [] and u is None

    def test_tool_calls_delta_passthrough(self):
        a = DeepSeekV4Adapter()
        tc_mock = MagicMock()
        tc_mock.index = 0
        chunk = _make_chunk(tool_calls=[tc_mock])
        _, _, tcs, _ = a.parse_stream_chunk(chunk)
        assert len(tcs) == 1


# ===== assemble_assistant_message =====

class TestAssembleAssistantMessage:
    def test_v4_keeps_reasoning_when_tool_calls(self):
        a = DeepSeekV4Adapter()
        msg = a.assemble_assistant_message(
            content="",
            reasoning_content="思考",
            tool_calls=[{"id": "c1", "type": "function",
                         "function": {"name": "f", "arguments": "{}"}}],
        )
        assert msg["role"] == "assistant"
        assert msg["reasoning_content"] == "思考"
        assert len(msg["tool_calls"]) == 1

    def test_mimo_keeps_reasoning_when_tool_calls(self):
        a = MimoAdapter()
        msg = a.assemble_assistant_message(
            content="",
            reasoning_content="MiMo 推理",
            tool_calls=[{"id": "c2", "type": "function",
                         "function": {"name": "f", "arguments": "{}"}}],
        )
        assert msg["reasoning_content"] == "MiMo 推理"

    def test_r1_never_writes_reasoning(self):
        a = DeepSeekR1Adapter()
        msg = a.assemble_assistant_message(
            content="答案",
            reasoning_content="思考",
            tool_calls=[],
        )
        assert "reasoning_content" not in msg

    def test_o1_never_writes_reasoning(self):
        a = OpenAIO1Adapter()
        msg = a.assemble_assistant_message(
            content="答案",
            reasoning_content="思考",
            tool_calls=[],
        )
        assert "reasoning_content" not in msg

    def test_generic_never_writes_reasoning(self):
        a = GenericOpenAIAdapter()
        msg = a.assemble_assistant_message(
            content="答案",
            reasoning_content="思考",
            tool_calls=[],
        )
        assert "reasoning_content" not in msg


# ===== 集成: 模拟两路流式累积 =====

class TestStreamIntegration:
    def test_v4_stream_accumulation(self):
        """模拟 DeepSeek V4 流式: thinking chunks + content chunks 分别累积"""
        a = DeepSeekV4Adapter()
        chunks = [
            _make_chunk(reasoning_content="我"),
            _make_chunk(reasoning_content="先想想"),
            _make_chunk(content="000001"),
            _make_chunk(content="平安银行"),
        ]
        thinking = ""
        content = ""
        for c in chunks:
            th, ct, _, _ = a.parse_stream_chunk(c)
            thinking += th
            content += ct
        assert thinking == "我先想想"
        assert content == "000001平安银行"

    def test_mimo_stream_accumulation(self):
        """MiMo 同协议"""
        a = MimoAdapter()
        chunks = [
            _make_chunk(reasoning_content="嗯"),
            _make_chunk(content="结论"),
        ]
        th_total = ""
        ct_total = ""
        for c in chunks:
            th, ct, _, _ = a.parse_stream_chunk(c)
            th_total += th
            ct_total += ct
        assert th_total == "嗯"
        assert ct_total == "结论"


# ===== 缓存能力 =====

class TestSupportsCache:
    def test_v4_supports_cache(self):
        assert DeepSeekV4Adapter().supports_cache() is True

    def test_v3_supports_cache(self):
        assert DeepSeekV3Adapter().supports_cache() is True

    def test_r1_no_cache(self):
        assert DeepSeekR1Adapter().supports_cache() is False

    def test_generic_no_cache(self):
        assert GenericOpenAIAdapter().supports_cache() is False
