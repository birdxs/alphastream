# Input: 请求上下文、数据结构
# Output: 辅助函数结果（时间/格式化/转换）
# Pos: web_server.py 工具函数层

"""
Web 层辅助函数

提供时间处理、数据格式化、类型转换等工具函数。
"""

import json
import logging
import re
import secrets as _secrets
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# +08:00 时区感知（对齐项目 now_cn 范式）
_ASIA_SHANGHAI = timezone(timedelta(hours=8))


def now_cn() -> datetime:
    """返回带 +08:00 的当前时间（S1-B3 时区感知）"""
    return datetime.now(_ASIA_SHANGHAI)


def quantize_finance(value, places: int = 2):
    """
    Decimal 量化至指定小数位（S1-B2）
    Hunt5-C2/Hunt6-C3: 避免 float 精度噪声污染金融数值

    Args:
        value: Decimal/float/str
        places: 小数位数（price=4, change_pct=2）

    Returns:
        Decimal | None（异常时返回 None）
    """
    if value is None:
        return None
    try:
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        quantizer = Decimal('1.' + '0' * places)
        return value.quantize(quantizer)
    except (InvalidOperation, ValueError, TypeError) as e:
        logger.warning(f"quantize_finance 失败: {value}, {e}")
        return None


def safe_change_pct(curr, prev) -> float | None:
    """
    安全计算涨跌幅（S1-B4 除零守卫）
    Hunt6-C4: 当 prev=0 或 None 时不抛异常
    """
    if prev is None or prev == 0 or curr is None:
        return None
    try:
        return ((float(curr) - float(prev)) / float(prev)) * 100.0
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def validate_stock_code(stock_code, market_type='A'):
    """
    股票代码有效性验证

    Args:
        stock_code: 股票代码
        market_type: 市场类型 (A/HK/US/B)

    Returns:
        bool: 是否有效
    """
    if not stock_code:
        return False

    if market_type == 'A':
        # A股: 6位数字
        return bool(re.match(r'^\d{6}$', stock_code))
    elif market_type == 'HK':
        # 港股: 5位数字
        return bool(re.match(r'^\d{5}$', stock_code))
    elif market_type == 'US':
        # 美股: 1-5位字母
        return bool(re.match(r'^[A-Z]{1,5}$', stock_code.upper()))
    elif market_type == 'B':
        # B股: 6位数字
        return bool(re.match(r'^\d{6}$', stock_code))

    return False


def generate_task_id():
    """生成唯一任务 ID"""
    return str(uuid.uuid4())


def convert_numpy_types(obj):
    """
    NumPy/Pandas 类型转 Python 原生类型

    递归转换字典/列表中的 NumPy 类型为 JSON 可序列化类型
    """
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif pd.isna(obj):
        return None
    return obj


def convert_messages_to_dict(obj):
    """
    将 LangChain 消息对象转换为字典

    处理 AIMessage/HumanMessage/ToolMessage 等对象序列化
    """
    if hasattr(obj, 'model_dump'):
        # Pydantic v2 BaseModel
        return obj.model_dump()
    elif hasattr(obj, 'dict'):
        # Pydantic v1 BaseModel
        return obj.dict()
    elif isinstance(obj, dict):
        return {k: convert_messages_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_messages_to_dict(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif pd.isna(obj):
        return None
    return obj


def custom_jsonify(data):
    """
    自定义 JSON 序列化（处理 NumPy/Pandas/LangChain 类型）

    Args:
        data: 待序列化数据

    Returns:
        Flask Response 对象
    """
    from flask import Response

    # 先转换 NumPy/Pandas 类型
    data = convert_numpy_types(data)
    # 再转换 LangChain 消息对象
    data = convert_messages_to_dict(data)

    try:
        json_str = json.dumps(data, ensure_ascii=False, default=str)
        return Response(
            json_str,
            mimetype='application/json',
            headers={'Content-Type': 'application/json; charset=utf-8'}
        )
    except Exception as e:
        logger.error(f"JSON 序列化失败: {e}")
        # 降级处理：尝试简单序列化
        try:
            json_str = json.dumps({'error': str(e)}, ensure_ascii=False)
            return Response(json_str, mimetype='application/json', status=500)
        except:
            return Response('{"error": "JSON serialization failed"}',
                            mimetype='application/json', status=500)
