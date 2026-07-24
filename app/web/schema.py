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
    # market_type: A / HK / US（路由不读该字段，仅为接受前端传参，避免 unknown=RAISE 误拒）
    market_type = fields.String(load_default='A', validate=mv.OneOf(['A', 'HK', 'US', 'B']))


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


# ── S3-D3 扩展 schema（+10 个路由覆盖）──────────────────────────────

class StockNameSchema(Schema):
    """GET /api/stock_name"""
    stock_code = StockCodeField(required=True)


class StockNameSearchSchema(Schema):
    """GET /api/stock_name_search"""
    q = fields.String(required=True, validate=mv.Length(min=1, max=20))
    limit = fields.Integer(load_default=10, validate=mv.Range(min=1, max=100))


class HistoryAnalysisSchema(Schema):
    """GET /api/history_analysis"""
    stock_code = StockCodeField(required=True)
    limit = fields.Integer(load_default=10, validate=mv.Range(min=1, max=500))


class LatestNewsSchema(Schema):
    """GET /api/latest_news"""
    days = fields.Integer(load_default=1, validate=mv.Range(min=1, max=30))
    limit = fields.Integer(load_default=500, validate=mv.Range(min=1, max=500))
    important = fields.String(load_default='0', validate=mv.OneOf(['0', '1']))
    type = fields.String(load_default='all', validate=mv.OneOf(['all', 'hotspot']))


class NewsSentimentSchema(Schema):
    """GET /api/news_sentiment"""
    days = fields.Integer(load_default=1, validate=mv.Range(min=1, max=30))


class IndustryDetailSchema(Schema):
    """GET /api/industry_detail"""
    industry = fields.String(required=True, validate=mv.Length(min=1, max=50))


class IndustryCompareSchema(Schema):
    """GET /api/industry_compare"""
    limit = fields.Integer(load_default=10, validate=mv.Range(min=1, max=500))


class StockQuoteBatchSchema(Schema):
    """GET /api/stock_quote_batch"""
    codes = fields.String(required=True, validate=mv.Length(min=1, max=2000))
    market_type = fields.String(load_default='A', validate=mv.OneOf(['A', 'HK', 'US', 'B']))
    max_codes = fields.Integer(load_default=100, validate=mv.Range(min=1, max=100))


class StartStockAnalysisSchema(Schema):
    """POST /api/start_stock_analysis"""
    stock_code = StockCodeField(required=True)
    market_type = fields.String(load_default='A', validate=mv.OneOf(['A', 'HK', 'US', 'B']))
    research_depth = fields.Integer(load_default=3, validate=mv.Range(min=1, max=5))
    analysts = fields.List(fields.String(), load_default=None, allow_none=True)


class StartAgentAnalysisSchema(Schema):
    """POST /api/start_agent_analysis"""
    stock_code = StockCodeField(required=True)
    market_type = fields.String(load_default='A', validate=mv.OneOf(['A', 'HK', 'US', 'B']))
    research_depth = fields.Integer(load_default=3, validate=mv.Range(min=1, max=5))
    selected_analysts = fields.List(fields.String(), load_default=None, allow_none=True)
    analysis_date = DateField(load_default=None, allow_none=True)
    enable_memory = fields.Boolean(load_default=True)
    max_output_length = fields.Integer(load_default=2048, validate=mv.Range(min=256, max=16384))


# ─────────────────────────────────────────────
# 装饰器
# ─────────────────────────────────────────────

def validate_schema(schema_cls: Type[Schema], source: str = 'args', extra_error_fields: dict | None = None):
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
                # error 字段保持向后兼容（旧测试 / 旧客户端 通过 data["error"] 检测）
                resp_body = {
                    'success': False,
                    'error_code': 'INVALID_INPUT',
                    'error': f'参数校验失败：{msgs}',
                    'message': f'参数校验失败：{msgs}',
                }
                if extra_error_fields:
                    resp_body.update(extra_error_fields)
                return jsonify(resp_body), 400

            request.validated = validated  # type: ignore[attr-defined]
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ─── S3-E1: 新增 15 个 schema（覆盖 capital_flow / risk / qa / agent / mcp 等）───

class NorthFlowHistorySchema(Schema):
    """POST /api/north_flow_history"""
    stock_code = fields.Str(
        required=True,
        validate=mv.Length(min=1, max=20),
        error_messages={"required": "请提供股票代码", "null": "股票代码不能为空"},
    )
    days = fields.Int(load_default=10, validate=mv.Range(min=1, max=365))


class FundamentalAnalysisSchema(Schema):
    """POST /api/fundamental_analysis"""
    stock_code = fields.Str(required=True, validate=mv.Length(min=1, max=20))


class CapitalFlowSchema(Schema):
    """POST /api/capital_flow"""
    stock_code = fields.Str(required=True, validate=mv.Length(min=1, max=20))
    market_type = fields.Str(load_default='', validate=mv.Length(max=10))


class ScenarioPredictSchema(Schema):
    """POST /api/scenario_predict"""
    stock_code = fields.Str(required=True, validate=mv.Length(min=1, max=20))
    market_type = fields.Str(load_default='A', validate=mv.Length(max=10))
    days = fields.Int(load_default=60, validate=mv.Range(min=1, max=365))


class QASchema(Schema):
    """POST /api/qa"""
    stock_code = fields.Str(required=True, validate=mv.Length(min=1, max=20))
    question = fields.Str(required=True, validate=mv.Length(min=1, max=1000))
    market_type = fields.Str(load_default='A', validate=mv.Length(max=10))


class RiskAnalysisSchema(Schema):
    """POST /api/risk_analysis"""
    stock_code = fields.Str(required=True, validate=mv.Length(min=1, max=20))
    market_type = fields.Str(load_default='A', validate=mv.Length(max=10))


class PortfolioRiskSchema(Schema):
    """POST /api/portfolio_risk"""
    portfolio = fields.List(
        fields.Raw(),
        required=True,
        validate=mv.Length(min=1, max=100),
    )


class IndexAnalysisSchema(Schema):
    """GET /api/index_analysis"""
    index_code = fields.Str(required=True, validate=mv.Length(min=1, max=20))
    limit = fields.Int(load_default=30, validate=mv.Range(min=1, max=500))


class IndustryAnalysisApiSchema(Schema):
    """GET /api/industry_analysis"""
    industry = fields.Str(required=True, validate=mv.Length(min=1, max=50))
    limit = fields.Int(load_default=30, validate=mv.Range(min=1, max=500))


class IndustryFundFlowSchema(Schema):
    """GET /api/industry_fund_flow"""
    symbol = fields.Str(load_default='即时', validate=mv.Length(max=20))


class IndividualFundFlowSchema(Schema):
    """GET /api/individual_fund_flow"""
    stock_code = fields.Str(required=True, validate=mv.Length(min=1, max=20))
    market_type = fields.Str(load_default='', validate=mv.Length(max=10))


class SectorStocksSchema(Schema):
    """GET /api/sector_stocks"""
    sector = fields.Str(required=True, validate=mv.Length(min=1, max=50))


class DeleteAgentAnalysisSchema(Schema):
    """POST /api/delete_agent_analysis"""
    task_ids = fields.List(
        fields.Str(validate=mv.Length(min=1, max=100)),
        required=True,
        validate=mv.Length(min=1, max=200),
    )


class AgentSubmitApprovalSchema(Schema):
    """POST /api/agent_submit_approval"""
    task_id = fields.Str(required=True, validate=mv.Length(min=1, max=100))
    approved = fields.Bool(load_default=False)
    feedback = fields.Str(load_default='', validate=mv.Length(max=2000))


class AgentPlansSchema(Schema):
    """GET /api/agent_plans — 只读包装 plan_dag.list_plans"""
    limit = fields.Int(load_default=20, validate=mv.Range(min=1, max=100))


class ApplyPortfolioProposalSchema(Schema):
    """POST /api/agent_apply_portfolio_proposal — 本地标记 apply，不撮合、不广播已成交"""
    proposal_id = fields.Str(required=True, validate=mv.Length(min=1, max=100))
    approval_id = fields.Str(load_default='', validate=mv.Length(max=100))


class McpCallSchema(Schema):
    """POST /api/mcp/call"""
    tool = fields.Str(required=True, validate=mv.Length(min=1, max=100))
    arguments = fields.Dict(load_default={})


# ─────────────────────────────────────────────
# S3-G1 +15 schema（2026-05-20）
# ─────────────────────────────────────────────

class StartEtfAnalysisSchema(Schema):
    """POST /api/start_etf_analysis"""
    etf_code = fields.Str(required=True, validate=mv.Length(min=1, max=20))
    market_type = fields.Str(load_default='A', validate=mv.Length(max=10))
    research_depth = fields.Int(load_default=3, validate=mv.Range(min=1, max=5))


class EnhancedAnalysisSchema(Schema):
    """POST /api/enhanced_analysis"""
    stock_code = fields.Str(required=True, validate=mv.Length(min=1, max=20))
    market_type = fields.Str(load_default='A', validate=mv.Length(max=10))
    research_depth = fields.Int(load_default=3, validate=mv.Range(min=1, max=5))


class StartMarketScanSchema(Schema):
    """POST /api/start_market_scan"""
    stock_list = fields.List(
        fields.Str(validate=mv.Length(min=1, max=20)),
        load_default=None,
    )
    market_type = fields.Str(load_default='A', validate=mv.Length(max=10))
    min_score = fields.Float(load_default=0.0, validate=mv.Range(min=0.0, max=100.0))
    max_stocks = fields.Int(load_default=50, validate=mv.Range(min=1, max=500))


class ScanStatusSchema(Schema):
    """GET /api/scan_status/<task_id>  — path param only, no query validation needed"""
    # path param validated by Flask routing; schema used as sentinel for documentation
    pass


class IndexStocksSchema(Schema):
    """GET /api/index_stocks"""
    index_code = fields.Str(
        load_default='000300',
        validate=mv.OneOf(['000300', '000905', '000852', '000001']),
    )


class IndustryStocksSchema(Schema):
    """GET /api/industry_stocks"""
    industry = fields.Str(required=True, validate=mv.Length(min=1, max=50))


class BoardStocksSchema(Schema):
    """GET /api/board_stocks"""
    board = fields.Str(
        load_default='hs300',
        validate=mv.OneOf(['hs300', 'zz500', 'zz1000', 'kc50', 'kc100', 'bj50']),
    )


class ConceptFundFlowSchema(Schema):
    """GET /api/concept_fund_flow"""
    period = fields.Str(load_default='10日排行', validate=mv.Length(max=20))


class IndividualFundFlowRankSchema(Schema):
    """GET /api/individual_fund_flow_rank"""
    period = fields.Str(load_default='今日', validate=mv.Length(max=20))
    market = fields.Str(load_default='', validate=mv.Length(max=10))


class AiChatStreamSchema(Schema):
    """POST /api/ai/chat — SSE 流式；Sprint2 可选 portfolio_snapshot 注入真仓"""
    message = fields.Str(required=True, validate=mv.Length(min=1, max=5000))
    conversation_id = fields.Str(load_default='', validate=mv.Length(max=100))
    stock_code = fields.Str(load_default='', validate=mv.Length(max=20))
    market_type = fields.Str(load_default='A', validate=mv.Length(max=10))
    research_depth = fields.Int(load_default=3, validate=mv.Range(min=1, max=5))
    # Sprint2: 前端 portfolio-store 真值；holdings 可空；服务端不造假持仓
    portfolio_snapshot = fields.Dict(load_default=None, allow_none=True, keys=fields.String())


class AiAgentAnalyzeSchema(Schema):
    """POST /api/ai/agent-analyze"""
    stock_code = fields.Str(required=True, validate=mv.Length(min=1, max=20))
    market_type = fields.Str(load_default='A', validate=mv.Length(max=10))
    research_depth = fields.Int(load_default=3, validate=mv.Range(min=1, max=5))
    conversation_id = fields.Str(load_default='', validate=mv.Length(max=100))
    user_message = fields.Str(load_default='', validate=mv.Length(max=5000))
    message = fields.Str(load_default='', validate=mv.Length(max=5000))


class SatelliteSearchSchema(Schema):
    """GET /api/satellite/search"""
    q = fields.Str(required=True, validate=mv.Length(min=1, max=200))


class AdaptersStatusSchema(Schema):
    """GET /api/adapters/status  — no required params"""
    pass


class RegistryStatsSchema(Schema):
    """GET /api/registry/stats  — no required params"""
    pass


class AgentPendingApprovalsSchema(Schema):
    """GET /api/agent_pending_approvals  — no required params"""
    pass


class ActiveTasksSchema(Schema):
    """GET /api/active_tasks  — no required params"""
    pass


# ─────────────────────────────────────────────
# S3-J(A): 新增 15 个端点 Schema（45→60/87 = 69%）
# 2026-05-20 19:49 +08:00
# ─────────────────────────────────────────────

_VALID_TASK_ID_RE = r'^[A-Za-z0-9_\-\.]{1,64}$'


class AnalysisStatusSchema(Schema):
    """GET /api/analysis_status/<task_id> — path param by Flask; no extra query params"""
    pass


class CancelAnalysisSchema(Schema):
    """POST /api/cancel_analysis/<task_id> — path param by Flask; no extra body params"""
    pass


class EtfAnalysisStatusSchema(Schema):
    """GET /api/etf_analysis_status/<task_id> — path param by Flask; no extra query params"""
    pass


class CancelScanSchema(Schema):
    """POST /api/cancel_scan/<task_id> — path param by Flask; no extra body params"""
    pass


class AgentAnalysisStatusSchema(Schema):
    """GET /api/agent_analysis_status/<task_id> — path param by Flask; no extra query params"""
    pass


class McpListToolsSchema(Schema):
    """GET /api/mcp/tools — no required params"""
    pass


class UploadImageSchema(Schema):
    """POST /api/upload_image — multipart/form-data; file field validated at handler level"""
    pass


class ConversationDetailSchema(Schema):
    """GET|DELETE /api/conversations/<conversation_id> — path param by Flask; no extra params"""
    pass


class ShippingBdiSchema(Schema):
    """GET /api/shipping/bdi — days: int 1-365"""
    days = fields.Int(
        load_default=30,
        validate=mv.Range(min=1, max=365, error='days 必须在 1-365 范围内'),
    )


class ShippingPortSchema(Schema):
    """GET /api/shipping/port/<port> — period: monthly|yearly|daily"""
    period = fields.Str(
        load_default='monthly',
        validate=mv.OneOf(
            ['monthly', 'yearly', 'daily'],
            error='period 必须是 monthly/yearly/daily',
        ),
    )


class EsgScoreSchema(Schema):
    """GET /api/esg/<ticker> — source: esgbook|msci|refinitiv (default esgbook)"""
    source = fields.Str(
        load_default='esgbook',
        validate=mv.Length(max=32, error='source 不能超过 32 字符'),
    )


class CorporateSearchSchema(Schema):
    """GET /api/corporate/search — q: company name keyword, required"""
    q = fields.Str(
        required=True,
        validate=mv.Length(min=1, max=100, error='q 长度必须在 1-100 之间'),
    )
    limit = fields.Int(
        load_default=20,
        validate=mv.Range(min=1, max=100, error='limit 必须在 1-100 范围内'),
    )


class JobsSearchSchema(Schema):
    """GET /api/jobs/search — q: keyword, limit: result count"""
    q = fields.Str(
        required=True,
        validate=mv.Length(min=1, max=100, error='q 长度必须在 1-100 之间'),
    )
    limit = fields.Int(
        load_default=20,
        validate=mv.Range(min=1, max=200, error='limit 必须在 1-200 范围内'),
    )


class JobsCompanySchema(Schema):
    """GET /api/jobs/company/<company> — path param by Flask; no extra query params"""
    pass


# BD-7: schema 覆盖率提升（10 个新 Schema）
class MarketStreamSchema(Schema):
    """GET /api/market_stream — SSE endpoint, no params"""
    pass


class HealthBasicSchema(Schema):
    """GET /health — no params"""
    pass


class GetMetricsSchema(Schema):
    """GET /api/metrics — no params"""
    pass


class GetOpenapiSpecSchema(Schema):
    """GET /api/openapi.json — no params"""
    pass


class A2aAgentCardSchema(Schema):
    """GET /.well-known/agent-card.json — no params"""
    pass


class A2aJsonRpcSchema(Schema):
    """POST /a2a/v1 — JSON-RPC 2.0 body validated at handler"""
    pass


class ApiEsgClimateSchema(Schema):
    """GET /api/esg/climate/<cik> — path param by Flask; no extra query params"""
    pass


class ApiCorporateNetworkSchema(Schema):
    """GET /api/corporate/<company_id>/network — path param by Flask; no extra query params"""
    pass


class ApiAltDataSchema(Schema):
    """GET /api/alt_data/<ticker> — path param by Flask; no extra query params"""
    pass


class GetCsrfTokenSchema(Schema):
    """GET /api/csrf_token — no params"""
    pass
