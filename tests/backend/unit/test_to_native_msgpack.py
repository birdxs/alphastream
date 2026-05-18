"""
Input: 含 numpy.float64 / numpy.ndarray / pandas.Timestamp 的 state dict
Output: 归一化后可被 ormsgpack/msgpack 成功打包，且数值保持精度
Pos: tests/backend/unit/test_to_native_msgpack.py - FIX-2 配套测试

[FIX-2 2026-05-18] 验证 app.agents.coordinator._to_native 能消除
"Type is not msgpack serializable: numpy.float64" 错误。
"""
import pytest
import numpy as np
import pandas as pd

from app.agents.coordinator import _to_native


def test_to_native_numpy_float64():
    """numpy.float64 -> Python float"""
    result = _to_native(np.float64(3.14))
    assert isinstance(result, float)
    assert result == pytest.approx(3.14)


def test_to_native_numpy_integer():
    """numpy.int64 -> Python int"""
    assert _to_native(np.int64(42)) == 42
    assert isinstance(_to_native(np.int64(42)), int)


def test_to_native_numpy_ndarray():
    """numpy.ndarray -> list[float]"""
    arr = np.array([1.1, 2.2, 3.3], dtype=np.float64)
    result = _to_native(arr)
    assert isinstance(result, list)
    assert len(result) == 3
    assert all(isinstance(x, float) for x in result)


def test_to_native_nested_state():
    """嵌套 dict 含 numpy 标量与 ndarray，全部递归归一化"""
    state = {
        'stock_code': '000001',
        'progress': np.int64(40),
        'score': np.float64(0.85),
        'history_close': np.array([10.5, 10.6, 10.7]),
        'agent_results': {
            'technical': {'confidence': np.float64(0.9), 'rsi': np.float64(55.3)},
            'fundamental': {'roe': np.float64(0.12)},
        },
        'tags': ['HOLD', np.float64(1.0)],
    }
    out = _to_native(state)

    # 类型断言
    assert isinstance(out['progress'], int)
    assert isinstance(out['score'], float)
    assert isinstance(out['history_close'], list)
    assert isinstance(out['agent_results']['technical']['confidence'], float)
    assert isinstance(out['agent_results']['fundamental']['roe'], float)
    assert isinstance(out['tags'][1], float)

    # 值保持
    assert out['stock_code'] == '000001'
    assert out['score'] == pytest.approx(0.85)
    assert out['agent_results']['technical']['rsi'] == pytest.approx(55.3)


def test_to_native_pandas_timestamp():
    """pandas.Timestamp -> ISO 字符串"""
    ts = pd.Timestamp('2026-05-18 10:30:00')
    result = _to_native(ts)
    assert isinstance(result, str)
    assert '2026-05-18' in result


def test_to_native_state_is_msgpack_serializable():
    """核心回归: 归一化后的 state 能被 ormsgpack/msgpack 成功 packb"""
    import msgpack
    state = {
        'progress': np.int64(40),
        'score': np.float64(0.85),
        'history_close': np.array([10.5, 10.6, 10.7]),
        'confidence_map': {'bull': np.float64(0.7), 'bear': np.float64(0.3)},
    }

    # 直接打包 numpy 应失败（验证问题真实存在）
    with pytest.raises((TypeError, msgpack.exceptions.PackException)):
        msgpack.packb(state)

    # 归一化后必须成功
    normalized = _to_native(state)
    packed = msgpack.packb(normalized)
    assert isinstance(packed, bytes)

    # 解包回检
    unpacked = msgpack.unpackb(packed, raw=False)
    assert unpacked['progress'] == 40
    assert unpacked['score'] == pytest.approx(0.85)


def test_to_native_ormsgpack_serializable():
    """LangGraph 实际用的是 ormsgpack，验证它也能处理"""
    try:
        import ormsgpack
    except ImportError:
        pytest.skip("ormsgpack not installed")

    state = {
        'score': np.float64(0.85),
        'rsi': np.float64(55.3),
        'progress': np.int64(40),
        'history': np.array([1.0, 2.0, 3.0]),
    }
    # 原始失败 (ormsgpack 对 numpy.float64 抛 TypeError，msg 含 "not msgpack serializable")
    with pytest.raises(TypeError, match="numpy.float64"):
        ormsgpack.packb(state)
    # 归一化成功
    normalized = _to_native(state)
    packed = ormsgpack.packb(normalized)
    assert isinstance(packed, bytes)


def test_to_native_preserves_primitives():
    """原生类型不被破坏"""
    assert _to_native(None) is None
    assert _to_native(True) is True
    assert _to_native('hello') == 'hello'
    assert _to_native(42) == 42
    assert _to_native(3.14) == 3.14
    assert _to_native([1, 'a', None]) == [1, 'a', None]


def test_to_native_numpy_bool():
    """numpy.bool_ -> Python bool"""
    assert _to_native(np.bool_(True)) is True
    assert _to_native(np.bool_(False)) is False
    assert isinstance(_to_native(np.bool_(True)), bool)
