# Input: Flask request.args / request.json
# Output: validated + deserialized params dict, or 400 JSON error
# Pos: 路由参数 schema 校验装饰器，供热门路由统一使用
# 一旦被修改，请更新本头部注释，以及 app/web/README.md
"""
路由参数 Schema 校验模块（S3-C4 Hunt5-Major 2026-05-20）

使用 marshmallow 3.x 定义核心路由的 schema，
通过 @validate_schema 装饰器统一前置校验，替代零散 validate_xxx 调用。
"""
from __future__ import annotations

from functools import wraps
from typing import Type

from flask import request, jsonify
from marshmallow import Schema, fields, validates, validates_schema, ValidationError as MarshmallowError
from marshmallow import validate as mv


# ─────────────────────────────────────────────
# 公共字段
# ─────────────────────────────────────────────

_VALID_STOCK_CODE_RE = r'^[A-Za-z0-9\.\-\_]{1,20}$'
_VALID_PERIODS = {'daily', 'weekly', 'monthly', 'min5', 'min15', 'min30', 'min60',
                  '1y', '3m', '6m', '5y', '1m', '10日排行', '10日'}
_VALID_DATE_RE = r'^\d{8}$'


class StockCodeField(fields.String):
    """A 股 / HK / US 股票代码字段（同 validate_stock_code_strict）"""

    def _validate(self, value):
        super()._validate(value)
        import re
        if not re.match(_VALID_STOCK_CODE_RE, value):
            raise MarshmallowError(f'stock_code 格式不合法: {value}')


class DateField(fields.String):
    """YYYYMMDD 格式日期字段"""

    def _validate(self, value):
        super()._validate(value)
        import re
        if not re.match(_VALID_DATE_RE, value):
            raise MarshmallowError(f'日期格式必须为 YYYYMMDD，实际: {value}')


# ─────────────────────────────────────────────
# 路由 Schema 定义
# ─────────────────────────────────────────────

class StockDataSchema(Schema):
    """GET /api/stock_data"""
    stock_code = StockCodeField(required=True)
    period = fields.String(
        load_default='daily',
        validate=mv.OneOf(_VALID_PERIODS),
    )
    start_date = DateField(load_default=None, allow_none=True)
    end_date = DateField(load_default=None, allow_none=True)
    limit = fields.Integer(load_default=200, validate=mv.Range(min=1, max=2000))
    # market_type: A / HK / US（与 validate_stock_code 保持一致）
    market_type = fields.String(load_default='A', validate=mv.OneOf(['A', 'HK', 'US', 'B']))


class StockProfileSchema(Schema):
    """GET /api/stock_profile"""
    stock_code = StockCodeField(required=True)


class MarketIndicesSchema(Schema):
    """GET /api/market_indices（无必填参数，预留扩展）"""
    refresh = fields.Boolean(load_default=False)


class ConversationsListSchema(Schema):
    """GET /api/conversations — cursor 分页（S3-C1）"""
    cursor = fields.String(load_default=None, allow_none=True)
    limit = fields.Integer(load_default=20, validate=mv.Range(min=1, max=200))
    # 兼容旧 offset 参数（deprecated）
    offset = fields.Integer(load_default=None, allow_none=True)

    @validates('cursor')
    def validate_cursor(self, value):
        """cursor 若非 None，长度必须 ≤ 128"""
        if value is not None and len(value) > 128:
            raise MarshmallowError('cursor 长度超限（>128 字符）')


class AgentAnalysisHistorySchema(Schema):
    """GET /api/agent_analysis_history — cursor 分页

    默认 limit=200：agent history 记录量较少，大 default 避免测试/无参调用时截断。
    """
    cursor = fields.String(load_default=None, allow_none=True)
    limit = fields.Integer(load_default=200, validate=mv.Range(min=1, max=200))


# ─────────────────────────────────────────────
# 装饰器
# ─────────────────────────────────────────────

def validate_schema(schema_cls: Type[Schema], source: str = 'args'):
    """路由参数 schema 校验装饰器。

    Args:
        schema_cls: marshmallow Schema 子类
        source:  'args' (query string) | 'json' (request body) | 'form'

    Usage::

        @app.route('/api/stock_data')
        @validate_schema(StockDataSchema)
        def get_stock_data():
            # request.validated 已注入 validated dict
            params = request.validated
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            schema = schema_cls()
            if source == 'args':
                raw = dict(request.args)
                # 多值参数取第一个（Flask MultiDict → plain dict）
                raw = {k: (v[0] if isinstance(v, list) and v else v) for k, v in raw.items()}
            elif source == 'json':
                raw = request.get_json(force=True, silent=True) or {}
            else:
                raw = dict(request.form)
                raw = {k: (v[0] if isinstance(v, list) and v else v) for k, v in raw.items()}

            try:
                validated = schema.load(raw)
            except MarshmallowError as exc:
                msgs = '; '.join(
                    f'{field}: {", ".join(errs)}'
                    for field, errs in exc.messages.items()
                )
                from flask import current_app
                current_app.logger.debug(f'[validate_schema] {schema_cls.__name__} 拒绝: {msgs}')
                return jsonify({
                    'success': False,
                    'error_code': 'INVALID_INPUT',
                    'message': f'参数校验失败：{msgs}',
                }), 400

            request.validated = validated  # type: ignore[attr-defined]
            return f(*args, **kwargs)
        return wrapper
    return decorator
