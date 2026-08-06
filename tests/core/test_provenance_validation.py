"""
provenance 验证：确认 Agent SSE 工具调用血统完整性
"""
import pytest


def test_tool_call_result_payload_has_provenance():
    """测试工具调用结果包含 provenance 字段"""
    from app.core.ai_client import _tool_call_result_payload

    result = _tool_call_result_payload(
        tool_call_id='call_123',
        tool_name='get_stock_data',
        result='{"data": [1, 2, 3]}',
        duration_ms=250,
        source='akshare',
        ok=True
    )

    # 验证 provenance 字段存在
    assert 'provenance' in result
    assert isinstance(result['provenance'], list)

    # 验证 provenance 格式
    if result['provenance']:  # 可能为空列表（normalize 清洗后）
        for item in result['provenance']:
            assert isinstance(item, dict)
            # 至少包含 source
            assert 'source' in item


def test_provenance_normalized_no_price_fields():
    """测试 provenance 不含价格字段（铁律 #1）"""
    from app.core.ai_client import _tool_call_result_payload

    result = _tool_call_result_payload(
        tool_call_id='call_456',
        tool_name='get_fundamental_data',
        result='{"pe": 20.5, "pb": 6.2}',
        duration_ms=180,
        source='wind',
        ok=True
    )

    # 验证 provenance 被 normalize
    assert 'provenance' in result
    provenance = result['provenance']

    # 不应包含价格/行情字段
    for item in provenance:
        # normalize_provenance_item 应已清洗价格字段
        forbidden_keys = ['price', 'close', 'high', 'low', 'open', 'volume', 'amount']
        for key in forbidden_keys:
            assert key not in item, f"provenance 不应包含 {key} 字段"


def test_provenance_error_fallback():
    """测试 provenance 构建异常时的兜底"""
    from app.core.ai_client import _tool_call_result_payload

    # 即使 source 异常，也应返回安全的 provenance
    result = _tool_call_result_payload(
        tool_call_id='call_789',
        tool_name='test_tool',
        result='test result',
        duration_ms=100,
        source=None,  # 缺失 source
        ok=True
    )

    # 兜底仍应返回 provenance（可能为空列表）
    assert 'provenance' in result
    assert isinstance(result['provenance'], list)


def test_provenance_string_source_rejected():
    """测试裸字符串 source 被拒绝（仅接受 dict）"""
    from app.core.artifact_wrapper import normalize_provenance_item

    # 裸字符串应被拒绝
    assert normalize_provenance_item("akshare") is None
    assert normalize_provenance_item("wind") is None

    # dict 应被接受
    valid = normalize_provenance_item({"source": "akshare", "tool": "get_stock_data"})
    assert valid is not None
    assert valid['source'] == 'akshare'


def test_provenance_merge_dedup():
    """测试 provenance 合并去重"""
    from app.core.artifact_wrapper import merge_provenance

    list1 = [{"source": "akshare", "tool": "get_stock_data"}]
    list2 = [{"source": "akshare", "tool": "get_stock_data"}]  # 重复
    list3 = [{"source": "wind", "tool": "get_fundamental_data"}]

    merged = merge_provenance(list1, list2, list3)

    # 应去重
    sources = [item['source'] for item in merged]
    assert 'akshare' in sources
    assert 'wind' in sources
    # 不应有重复的 akshare
    assert sources.count('akshare') == 1
