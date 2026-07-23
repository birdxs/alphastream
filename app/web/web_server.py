# -*- coding: utf-8 -*-
"""
智能分析系统（股票） - 股票市场数据分析系统
修改：熊猫大侠
版本：v2.1.0
"""
# web_server.py

import numpy as np
import pandas as pd
import re
from flask import Flask, render_template, request, jsonify, redirect, url_for, g
from app.analysis.stock_analyzer import StockAnalyzer
from app.analysis.us_stock_service import USStockService
from app.web.utils import (
    now_cn, quantize_finance, safe_change_pct, validate_stock_code,
    generate_task_id, convert_numpy_types, convert_messages_to_dict, custom_jsonify
)
import threading
import logging
from logging.handlers import RotatingFileHandler
import traceback
import os
import json
import tempfile
import uuid as _uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
from flask_cors import CORS
from pathlib import Path
import time
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import threading
import sys
from flask_swagger_ui import get_swaggerui_blueprint
from app.core.database import get_session, init_db, StockInfo, AnalysisResult, Portfolio, USE_DATABASE
from dotenv import load_dotenv
from app.analysis.industry_analyzer import IndustryAnalyzer
from app.analysis.fundamental_analyzer import FundamentalAnalyzer
from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
from app.analysis.scenario_predictor import ScenarioPredictor
from app.analysis.stock_qa import StockQA
from app.analysis.risk_monitor import RiskMonitor
from app.analysis.index_industry_analyzer import IndexIndustryAnalyzer
from app.analysis.news_fetcher import news_fetcher, start_news_scheduler
from app.analysis.etf_analyzer import EtfAnalyzer

import sys
import os
import re

# 将 tradingagents 目录添加到系统路径
# 这允许应用从 tradingagents 代码库中导入模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../tradingagents')))


# 加载环境变量（override=True 让 .env 成为单一真相源，覆盖 shell 注入的同名变量）
load_dotenv(override=True)

# ── Sprint 3-C 路由 schema 校验 & OpenAPI spec ────────────────────────────────
from app.web.schema import (
    validate_schema,
    StockDataSchema,
    StockProfileSchema,
    MarketIndicesSchema,
    ConversationsListSchema,
    AgentAnalysisHistorySchema,
    # S3-D3 扩展 schema
    StockNameSchema,
    StockNameSearchSchema,
    HistoryAnalysisSchema,
    LatestNewsSchema,
    NewsSentimentSchema,
    IndustryDetailSchema,
    IndustryCompareSchema,
    StockQuoteBatchSchema,
    StartStockAnalysisSchema,
    StartAgentAnalysisSchema,
    # S3-E1: +15 schema
    NorthFlowHistorySchema,
    FundamentalAnalysisSchema,
    CapitalFlowSchema,
    ScenarioPredictSchema,
    QASchema,
    RiskAnalysisSchema,
    PortfolioRiskSchema,
    IndexAnalysisSchema,
    IndustryAnalysisApiSchema,
    IndustryFundFlowSchema,
    IndividualFundFlowSchema,
    SectorStocksSchema,
    DeleteAgentAnalysisSchema,
    AgentSubmitApprovalSchema,
    McpCallSchema,
    # S3-G1: +15 schema
    StartEtfAnalysisSchema,
    EnhancedAnalysisSchema,
    StartMarketScanSchema,
    IndexStocksSchema,
    IndustryStocksSchema,
    BoardStocksSchema,
    ConceptFundFlowSchema,
    IndividualFundFlowRankSchema,
    AiChatStreamSchema,
    AiAgentAnalyzeSchema,
    SatelliteSearchSchema,
    AdaptersStatusSchema,
    RegistryStatsSchema,
    AgentPendingApprovalsSchema,
    ActiveTasksSchema,
    # S3-J(A): +15 schema（45→60/87 = 69%）
    AnalysisStatusSchema,
    CancelAnalysisSchema,
    EtfAnalysisStatusSchema,
    CancelScanSchema,
    AgentAnalysisStatusSchema,
    McpListToolsSchema,
    UploadImageSchema,
    ConversationDetailSchema,
    ShippingBdiSchema,
    ShippingPortSchema,
    EsgScoreSchema,
    CorporateSearchSchema,
    JobsSearchSchema,
    JobsCompanySchema,
    ScanStatusSchema,
    # BD-7: +10 schema（60→70/91 = 77%）
    MarketStreamSchema,
    HealthBasicSchema,
    GetMetricsSchema,
    GetOpenapiSpecSchema,
    A2aAgentCardSchema,
    A2aJsonRpcSchema,
    ApiEsgClimateSchema,
    ApiCorporateNetworkSchema,
    ApiAltDataSchema,
    GetCsrfTokenSchema,
)
from app.web.openapi_spec import OPENAPI_SPEC

# ── Sprint 1-B 工具函数 ──────────────────────────────────────────────────────

# S1-B3: 时区感知时间工具（Hunt5-C1）
# Asia/Shanghai = UTC+8，与 Asia/Singapore 相同偏移
ASIA_SHANGHAI = timezone(timedelta(hours=8))

# ── BD-3: 全局线程池（避免临时创建浪费资源）────────────────────────────────
_GLOBAL_THREAD_POOL_SIZE = int(os.getenv('GLOBAL_THREAD_POOL_SIZE', '10'))
_GLOBAL_THREAD_POOL = ThreadPoolExecutor(
    max_workers=_GLOBAL_THREAD_POOL_SIZE,
    thread_name_prefix='global-pool-'
)
# 注册 atexit 清理
import atexit
atexit.register(lambda: _GLOBAL_THREAD_POOL.shutdown(wait=False, cancel_futures=True))


def get_global_thread_pool():
    """获取全局线程池实例

    Input: 无
    Output: ThreadPoolExecutor 实例（全局单例）
    Pos: BD-3 资源池化，供所有路由复用
    """
    return _GLOBAL_THREAD_POOL


def now_cn() -> datetime:
    """返回带 Asia/Shanghai (+08:00) 时区的当前时间，替代裸 now_cn()。
    Input: 无
    Output: timezone-aware datetime（+08:00）
    Pos: 全局工具函数，web_server.py 内所有 now_cn() 调用点"""
    return datetime.now(ASIA_SHANGHAI)


# S1-B2: 金融精度 Decimal 量化工具（Hunt5-C2/Hunt6-C3）
def quantize_finance(value, places: int = 2):
    """将浮点数量化为指定小数位的 Decimal，避免 float 精度误差。
    Input: value（int/float/str/None），places（小数位数，默认 2）
    Output: float（JSON 可序列化）或 None（值无效时）
    Pos: 全局工具函数，输出层调用，不参与 pandas/numpy 内部计算"""
    if value is None:
        return None
    try:
        quantizer = Decimal('0.' + '0' * places) if places > 0 else Decimal('1')
        result = Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)
        return float(result)
    except (InvalidOperation, ValueError, TypeError):
        return None


# S1-B4: 涨跌幅除零守卫（Hunt6-C4）
def safe_change_pct(curr, prev) -> float | None:
    """安全计算涨跌幅；prev <= 0 或 None 时返回 None（前端显示 '—'）。
    Input: curr（当前价），prev（前收盘价）
    Output: float 涨跌幅百分比，或 None
    Pos: 全局工具函数，替换所有直接 (curr-prev)/prev*100 的位置"""
    try:
        if prev is None or prev <= 0 or curr is None:
            return None
        return round((float(curr) - float(prev)) / float(prev) * 100, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# ── Sprint 1-B 工具函数 结束 ────────────────────────────────────────────────


def validate_stock_code(stock_code, market_type='A'):
    """验证股票代码格式"""
    if not stock_code or not isinstance(stock_code, str):
        return False, "股票代码不能为空"
    stock_code = stock_code.strip()
    if len(stock_code) > 10:
        return False, "股票代码长度无效"
    patterns = {
        'A': r'^[0-9]{6}$',
        'HK': r'^[0-9]{4,5}$',
        'US': r'^[A-Za-z]{1,5}$'
    }
    pattern = patterns.get(market_type, patterns['A'])
    if not re.match(pattern, stock_code):
        return False, f"股票代码格式无效: {stock_code}"
    return True, stock_code


# 检查是否需要初始化数据库
if USE_DATABASE:
    init_db()

# 配置Swagger
SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "股票智能分析系统 API文档"
    }
)

app = Flask(__name__)
# [K3 2026-04-15 14:32 +08:00] 进程启动时间锚点 — 用于 /health uptime 计算
START_TIME = time.time()
APP_VERSION = "3.1.0"

# ── S3-G4: 基础 metrics 计数器 ─────────────────────────────────────────────
_METRICS_LOCK = threading.RLock()
_METRICS: dict = {
    'requests_total': 0,
    'requests_by_status': {},   # {'2xx': 0, '4xx': 0, '5xx': 0}
    'requests_by_path': {},     # {'/api/market_indices': 123, ...}
    'errors_total': 0,
    'started_at': START_TIME,
}

# ── 安全配置 ────────────────────────────────────────────────────────────────
# SECRET_KEY：Flask session / CSRF 签名所需；生产必须通过 SECRET_KEY env 设置
import secrets as _secrets
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', None) or _secrets.token_hex(32)
app.config['WTF_CSRF_TIME_LIMIT'] = int(os.getenv('WTF_CSRF_TIME_LIMIT', '3600'))
# WTF_CSRF_CHECK_DEFAULT=False：允许我们仅对 SPA 路由做 CSRF exempt（API key 路由已鉴权）
app.config['WTF_CSRF_CHECK_DEFAULT'] = False

# CSRF 保护（Flask-WTF）
from flask_wtf.csrf import CSRFProtect, generate_csrf
csrf = CSRFProtect(app)

# 鉴权中间件
from app.web.auth_middleware import check_api_key, is_auth_required, get_api_key as _get_api_key, PUBLIC_PATHS

# ── S3-F2: correlation_id 注入（每请求生成唯一12位hex ID）───────────────────
@app.before_request
def inject_correlation_id():
    """在 flask.g 中注入 correlation_id，供日志 Filter 和响应头使用。
    S3-G4: 同时记录请求开始时间用于 metrics。
    """
    g.correlation_id = _uuid.uuid4().hex[:12]
    g.request_start_time = time.monotonic()  # S3-G4: metrics 计时


# ── 全局 before_request：绑定 Wind 请求级开关 ────────────────────────────────
@app.before_request
def bind_use_wind_flag():
    """从 X-Use-Wind / query.use_wind / JSON body.use_wind 绑定 contextvar。

    默认 false（opt-in 省积分）。前端 Settings 开关写 localStorage，
    client.ts 统一注入 X-Use-Wind 头。
    """
    try:
        from app.adapters.wind_adapter import set_use_wind, parse_use_wind_flag
        raw = request.headers.get('X-Use-Wind')
        if raw is None or str(raw).strip() == '':
            raw = request.args.get('use_wind')
        if (raw is None or str(raw).strip() == '') and request.method in (
            'POST', 'PUT', 'PATCH',
        ):
            body = request.get_json(silent=True) or {}
            if isinstance(body, dict):
                raw = body.get('use_wind')
        set_use_wind(parse_use_wind_flag(raw))
    except Exception:
        pass  # 绑定失败不阻断请求；默认关闭 Wind


# ── 全局 before_request 鉴权门 ───────────────────────────────────────────────
@app.before_request
def global_auth_gate():
    """所有请求经过此门；PUBLIC_PATHS + /static 无需鉴权，其余必须携带 X-API-Key"""
    path = request.path
    # 静态资源、Swagger UI、页面路由不鉴权
    if (path.startswith('/static')
            or path.startswith('/api/docs')
            or path.startswith('/api-docs')
            or path in PUBLIC_PATHS
            or any(path.startswith(p) for p in ('/stock_detail/', '/api/docs'))):
        return None
    return check_api_key()


# ── CSRF token 端点（SPA 调用此接口获取 token）───────────────────────────────
@app.route('/api/csrf_token', methods=['GET'])
@validate_schema(GetCsrfTokenSchema)  # BD-7: schema 覆盖率提升
def get_csrf_token():
    """公开端点：返回 CSRF token，前端存入 sessionStorage 后随 POST 请求附上"""
    token = generate_csrf()
    resp = jsonify({'csrf_token': token})
    resp.headers['X-CSRFToken'] = token
    return resp


# ────────────────────────────────────────────────────────────────────────────
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:8888,http://127.0.0.1:8888,http://localhost:3000,http://127.0.0.1:3000').split(',')
# Dev兜底: 允许常见局域网IP(192.168.x/10.x)+任意:3000/8888端口, 便于Comdr从多主机访问
_DEV_ORIGIN_PATTERNS = [
    re.compile(r'^http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):(3000|8888)$'),
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins + _DEV_ORIGIN_PATTERNS, "methods": ["GET", "POST", "PUT", "DELETE"], "allow_headers": ["Content-Type", "X-API-Key", "X-CSRFToken", "X-Use-Wind"]}})


# ── S3-F2: after_request: X-Correlation-Id 响应头 + S3-F4: security headers ─
@app.after_request
def add_security_and_correlation_headers(resp):
    """
    S3-F2: 将 correlation_id 写入 X-Correlation-Id 响应头。
    S3-F4: 追加 security headers（nosniff / X-Frame / Referrer / Permissions）。
    CSP 仅在 production 模式（非 debug）启用。
    Input: Flask Response 对象
    Output: 附加了安全及追踪 header 的 Response
    Pos: after_request hook，所有响应必经
    """
    # S3-F2: correlation_id
    cid = getattr(g, 'correlation_id', '-')
    resp.headers['X-Correlation-Id'] = cid

    # S3-F4: security headers
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    resp.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=()')

    # CSP 较激进，仅在 production 模式启用（避免破坏开发热更新）
    if not app.debug:
        resp.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "frame-ancestors 'none'"
        )

    # ── S3-H2: Cache-Control 防御性 header（API 路由）─────────────────────
    req_path = request.path
    if req_path.startswith('/api/'):
        if not resp.headers.get('Cache-Control'):
            if req_path == '/api/openapi.json':
                resp.headers['Cache-Control'] = 'public, max-age=300'
            elif req_path == '/api/metrics':
                resp.headers['Cache-Control'] = 'public, max-age=10'
            else:
                resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
                resp.headers['Pragma'] = 'no-cache'
                resp.headers['Expires'] = '0'

    # ── S3-G4: 更新 metrics 计数器 ───────────────────────────────────────
    try:
        status_code = resp.status_code
        # 路径归一化：优先用 url_rule.rule（Flask route pattern），去掉 query string
        rule = request.url_rule
        if rule is not None:
            # 把 Flask 规则格式 <string:xxx> / <int:xxx> 统一为 :id
            import re as _re
            path_key = _re.sub(r'<[^>]+>', ':id', rule.rule)
        else:
            path_key = request.path.split('?')[0][:80]

        bucket = f'{status_code // 100}xx'
        is_error = status_code >= 500

        with _METRICS_LOCK:
            _METRICS['requests_total'] += 1
            _METRICS['requests_by_status'][bucket] = (
                _METRICS['requests_by_status'].get(bucket, 0) + 1
            )
            _METRICS['requests_by_path'][path_key] = (
                _METRICS['requests_by_path'].get(path_key, 0) + 1
            )
            if is_error:
                _METRICS['errors_total'] += 1
    except Exception:
        pass  # metrics 统计不得影响正常响应

    return resp


analyzer = StockAnalyzer()
us_stock_service = USStockService()

# 配置缓存
cache_config = {
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 300
}

# 如果配置了Redis，使用Redis作为缓存后端
if os.getenv('USE_REDIS_CACHE', 'False').lower() == 'true' and os.getenv('REDIS_URL', None):
    cache_config = {
        'CACHE_TYPE': 'RedisCache',
        'CACHE_REDIS_URL': os.getenv('REDIS_URL', None),
        'CACHE_DEFAULT_TIMEOUT': 300
    }

cache = Cache(config=cache_config)
cache.init_app(app)

# ============ 限流（S2-A4 Hunt1-Major 2026-05-20） ============
# Input: X-API-Key header 或 remote IP
# Output: 超出限额时返回 429 RATE_LIMITED；否则透传
# Pos: 全局 default 600/min + 关键端点单独限流
_RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() not in ('false', '0', 'no')
limiter = Limiter(
    key_func=lambda: request.headers.get('X-API-Key', get_remote_address()),
    default_limits=[os.getenv('RATE_LIMIT_DEFAULT', '600 per minute')] if _RATE_LIMIT_ENABLED else [],
    storage_uri='memory://',
    enabled=_RATE_LIMIT_ENABLED,
)
limiter.init_app(app)

app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)


@app.route('/api-docs', methods=['GET'])
@app.route('/api-docs/', methods=['GET'])
@app.route('/api-docs/<path:path>', methods=['GET'])
def api_docs_compat_redirect(path=None):
    """兼容历史 /api-docs 入口，保持现有 /api/docs/ Swagger UI 不变。"""
    return redirect('/api/docs/', code=302)


# 确保全局变量在重新加载时不会丢失
if 'analyzer' not in globals():
    try:
        from app.analysis.stock_analyzer import StockAnalyzer

        analyzer = StockAnalyzer()
        print("成功初始化全局StockAnalyzer实例")
    except Exception as e:  # broad-catch: startup fallback, benign print failure
        print(f"初始化StockAnalyzer时出错: {e}", file=sys.stderr)
        raise

# 初始化模块实例
fundamental_analyzer = FundamentalAnalyzer()
capital_flow_analyzer = CapitalFlowAnalyzer()
scenario_predictor = ScenarioPredictor(analyzer, os.getenv('OPENAI_API_KEY', None), os.getenv('OPENAI_API_MODEL', None))
stock_qa = StockQA(analyzer, os.getenv('OPENAI_API_KEY', None))
risk_monitor = RiskMonitor(analyzer)
index_industry_analyzer = IndexIndustryAnalyzer(analyzer)
industry_analyzer = IndustryAnalyzer()


def _startup_background_enabled():
    """测试/离线环境不启动导入期后台任务；默认开发启动保持开启。"""
    return os.getenv("DISABLE_NETWORK") != "1"


if _startup_background_enabled():
    start_news_scheduler()

# 线程本地存储
thread_local = threading.local()


def get_analyzer():
    """获取线程本地的分析器实例"""
    # 如果线程本地存储中没有分析器实例，创建一个新的
    if not hasattr(thread_local, 'analyzer'):
        thread_local.analyzer = StockAnalyzer()
    return thread_local.analyzer


# 配置日志
# 从环境变量读取日志级别和文件路径
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
log_file = os.getenv('LOG_FILE', 'data/logs/server.log')

# 确保日志目录存在
os.makedirs(os.path.dirname(log_file), exist_ok=True)

# ── S3-F2: 结构化日志 correlation_id Filter ──────────────────────────────────

class _CorrelationIdFilter(logging.Filter):
    """将当前请求的 correlation_id 注入 LogRecord，非请求上下文时填 '-'。"""
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from flask import g as _g
            record.correlation_id = getattr(_g, 'correlation_id', '-')
        except RuntimeError:
            record.correlation_id = '-'
        return True

_cid_filter = _CorrelationIdFilter()

# 创建日志格式化器
formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] [%(name)s] [cid=%(correlation_id)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 配置根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(log_level)

# 清除所有现有的处理器，以避免重复日志
if root_logger.hasHandlers():
    root_logger.handlers.clear()

# 添加文件处理器
file_handler = RotatingFileHandler(log_file, maxBytes=1024*1024*10, backupCount=5, encoding='utf-8') # 10MB
file_handler.setFormatter(formatter)
file_handler.addFilter(_cid_filter)
root_logger.addHandler(file_handler)

# 添加控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.addFilter(_cid_filter)
root_logger.addHandler(console_handler)

# 将Flask的默认处理器移除，使其日志也遵循我们的配置
from flask.logging import default_handler
app.logger.removeHandler(default_handler)
app.logger.propagate = True

# 将 werkzeug 日志记录器的级别也设置为 .env 中定义的级别
logging.getLogger('werkzeug').setLevel(log_level)

app.logger.info(f"日志系统已初始化，级别: {log_level}, 文件: {log_file}")


# 扩展任务管理系统以支持不同类型的任务
task_types = {
    'scan': 'market_scan',  # 市场扫描任务
    'analysis': 'stock_analysis',  # 个股分析任务
    'agent_analysis': 'agent_analysis', # 智能体分析任务
    'etf_analysis': 'etf_analysis' # ETF分析任务
}

# 任务数据存储
tasks = {
    'market_scan': {},
    'stock_analysis': {},
    'etf_analysis': {},
}



def get_task_store(task_type):
    """获取指定类型的任务存储"""
    return tasks.get(task_type, {})


def generate_task_key(task_type, **params):
    """生成任务键"""
    if task_type == 'stock_analysis':
        # 对于个股分析，使用股票代码和市场类型作为键
        return f"{params.get('stock_code')}_{params.get('market_type', 'A')}"
    if task_type == 'etf_analysis':
        return f"{params.get('etf_code')}"
    return None  # 其他任务类型不使用预生成的键


def get_or_create_task(task_type, **params):
    """获取或创建任务"""
    store = get_task_store(task_type)
    task_key = generate_task_key(task_type, **params)

    # 检查是否有现有任务
    if task_key and task_key in store:
        task = store[task_key]
        # 检查任务是否仍然有效
        if task['status'] in [TASK_PENDING, TASK_RUNNING]:
            return task['id'], task, False
        if task['status'] == TASK_COMPLETED and 'result' in task:
            # 任务已完成且有结果，重用它
            return task['id'], task, False

    # 创建新任务
    task_id = generate_task_id()
    task = {
        'id': task_id,
        'key': task_key,  # 存储任务键以便以后查找
        'type': task_type,
        'status': TASK_PENDING,
        'progress': 0,
        'created_at': now_cn().strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': now_cn().strftime('%Y-%m-%d %H:%M:%S'),
        'params': params
    }

    with task_lock:
        if task_key:
            store[task_key] = task
        store[task_id] = task

    return task_id, task, True


# 添加到web_server.py顶部
# 任务管理系统
scan_tasks = {}  # 存储扫描任务的状态和结果
task_lock = threading.Lock()  # 用于线程安全操作


# 自定义异常，用于任务取消
class TaskCancelledException(Exception):
    pass

# 任务状态常量
TASK_PENDING = 'pending'
TASK_RUNNING = 'running'
TASK_COMPLETED = 'completed'
TASK_FAILED = 'failed'
TASK_CANCELLED = 'cancelled'
TASK_AWAITING_APPROVAL = 'awaiting_approval'  # P0-5 HITL 确认面阻塞态


def generate_task_id():
    """生成唯一的任务ID"""
    import uuid
    return str(uuid.uuid4())


def start_market_scan_task_status(task_id, status, progress=None, result=None, error=None):
    """更新任务状态 - 保持原有签名"""
    with task_lock:
        if task_id in scan_tasks:
            task = scan_tasks[task_id]
            task['status'] = status
            if progress is not None:
                task['progress'] = progress
            if result is not None:
                task['result'] = result
            if error is not None:
                task['error'] = error
            task['updated_at'] = now_cn().strftime('%Y-%m-%d %H:%M:%S')


def update_task_status(task_type, task_id, status, progress=None, result=None, error=None):
    """更新任务状态"""
    with task_lock:
        task = None
        if task_type == 'agent_analysis':
            task = agent_session_manager.load_task(task_id)
        else:
            store = get_task_store(task_type)
            if task_id in store:
                task = store.get(task_id)

        if not task:
            app.logger.warning(f"更新任务状态时未找到任务: {task_id} (类型: {task_type})")
            return

        # 更新任务属性
        task['status'] = status
        if progress is not None:
            task['progress'] = progress
        if result is not None:
            if 'result' not in task or not isinstance(task['result'], dict):
                task['result'] = {}
            task['result'].update(result)
        if error is not None:
            task['error'] = error
        task['updated_at'] = now_cn().strftime('%Y-%m-%d %H:%M:%S')

        # 保存更新后的任务
        if task_type == 'agent_analysis':
            agent_session_manager.save_task(task)
        else:
            # 更新键索引的任务 (如果适用)
            store = get_task_store(task_type)
            if 'key' in task and task.get('key') and task['key'] in store:
                store[task['key']] = task
            store[task_id] = task # also save by id


analysis_tasks = {}


def get_or_create_analysis_task(stock_code, market_type='A'):
    """获取或创建个股分析任务"""
    # 创建一个键，用于查找现有任务
    task_key = f"{stock_code}_{market_type}"

    with task_lock:
        # 检查是否有现有任务
        for task_id, task in analysis_tasks.items():
            if task.get('key') == task_key:
                # 检查任务是否仍然有效
                if task['status'] in [TASK_PENDING, TASK_RUNNING]:
                    return task_id, task, False
                if task['status'] == TASK_COMPLETED and 'result' in task:
                    # 任务已完成且有结果，重用它
                    return task_id, task, False

        # 创建新任务
        task_id = generate_task_id()
        task = {
            'id': task_id,
            'key': task_key,
            'status': TASK_PENDING,
            'progress': 0,
            'created_at': now_cn().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': now_cn().strftime('%Y-%m-%d %H:%M:%S'),
            'params': {
                'stock_code': stock_code,
                'market_type': market_type
            }
        }

        analysis_tasks[task_id] = task

        return task_id, task, True


def update_analysis_task(task_id, status, progress=None, result=None, error=None):
    """更新个股分析任务状态"""
    with task_lock:
        if task_id in analysis_tasks:
            task = analysis_tasks[task_id]
            task['status'] = status
            if progress is not None:
                task['progress'] = progress
            if result is not None:
                task['result'] = result
            if error is not None:
                task['error'] = error
            task['updated_at'] = now_cn().strftime('%Y-%m-%d %H:%M:%S')


# 定义自定义JSON编码器


# 在web_server.py中，更新convert_numpy_types函数以处理NaN值

# 将NumPy类型转换为Python原生类型的函数
def convert_numpy_types(obj):
    """递归地将字典和列表中的NumPy类型转换为Python原生类型"""
    try:
        import numpy as np
        import math

        if isinstance(obj, dict):
            return {convert_numpy_types(key): convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy_types(item) for item in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            # Handle NaN and Infinity specifically
            if np.isnan(obj):
                return None
            elif np.isinf(obj):
                return None if obj < 0 else 1e308  # Use a very large number for +Infinity
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        # Handle Python's own float NaN and Infinity
        elif isinstance(obj, float):
            if math.isnan(obj):
                return None
            elif math.isinf(obj):
                return None
            return obj
        # 添加对date和datetime类型的处理
        elif isinstance(obj, (date, datetime)):
            return obj.isoformat()
        else:
            return obj
    except ImportError:
        # 如果没有安装numpy，但需要处理date和datetime
        import math
        if isinstance(obj, dict):
            return {convert_numpy_types(key): convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy_types(item) for item in obj]
        elif isinstance(obj, (date, datetime)):
            return obj.isoformat()
        # Handle Python's own float NaN and Infinity
        elif isinstance(obj, float):
            if math.isnan(obj):
                return None
            elif math.isinf(obj):
                return None
            return obj
        return obj


# 同样更新 NumpyJSONEncoder 类
class NumpyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        # Handle LangChain message objects first
        try:
            from langchain_core.messages import BaseMessage
            if isinstance(obj, BaseMessage):
                return {"type": obj.__class__.__name__, "content": str(obj.content)}
        except ImportError:
            pass  # If langchain is not installed, just proceed

        # For NumPy data types
        try:
            import numpy as np
            import math
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                # Handle NaN and Infinity specifically
                if np.isnan(obj):
                    return None
                elif np.isinf(obj):
                    return None
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.bool_):
                return bool(obj)
            # Handle Python's own float NaN and Infinity
            elif isinstance(obj, float):
                if math.isnan(obj):
                    return None
                elif math.isinf(obj):
                    return None
                return obj
        except ImportError:
            # Handle Python's own float NaN and Infinity if numpy is not available
            import math
            if isinstance(obj, float):
                if math.isnan(obj):
                    return None
                elif math.isinf(obj):
                    return None

        # 添加对date和datetime类型的处理
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()

        # Fallback for other non-serializable types
        try:
            return super(NumpyJSONEncoder, self).default(obj)
        except TypeError:
            # For LangChain messages or other complex objects, convert to string
            return str(obj)


# Helper to convert LangChain messages to JSON serializable format
def convert_messages_to_dict(obj):
    """Recursively convert LangChain message objects to dictionaries."""
    # Check if langchain_core is available and if the object is a message
    try:
        from langchain_core.messages import BaseMessage
        is_message = isinstance(obj, BaseMessage)
    except ImportError:
        is_message = False

    if is_message:
        # Base case: convert message object to dict
        return {"type": obj.__class__.__name__, "content": str(obj.content)}
    elif isinstance(obj, dict):
        # Recursive step for dictionaries
        return {k: convert_messages_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        # Recursive step for lists
        return [convert_messages_to_dict(elem) for elem in obj]
    else:
        # Return the object as is if no conversion is needed
        return obj


# 使用我们的编码器的自定义 jsonify 函数
def custom_jsonify(data):
    # allow_nan=False 禁止输出字面 NaN/Infinity(非标 JSON)；
    # convert_numpy_types 已把 float NaN/Inf 转 None 作为兜底。
    return app.response_class(
        json.dumps(convert_numpy_types(data), cls=NumpyJSONEncoder, allow_nan=False),
        mimetype='application/json'
    )


# === 全局 JSON Provider: 让 Flask 原生 jsonify 也走 NaN-safe 路径 ===
# 修复 bug: /api/conversations/<id> 等 125+ 处 jsonify 调用原先允许输出
# 字面 NaN/Infinity，前端 JSON.parse 会抛 SyntaxError。
try:
    from flask.json.provider import DefaultJSONProvider

    class NanSafeJSONProvider(DefaultJSONProvider):
        def dumps(self, obj, **kwargs):
            kwargs.setdefault('ensure_ascii', self.ensure_ascii)
            kwargs.setdefault('sort_keys', self.sort_keys)
            kwargs['allow_nan'] = False
            kwargs['cls'] = NumpyJSONEncoder
            return json.dumps(convert_numpy_types(obj), **kwargs)

        def loads(self, s, **kwargs):
            return json.loads(s, **kwargs)

    app.json = NanSafeJSONProvider(app)
except Exception as _e:  # broad-catch: optional NaN-safe provider, fallback acceptable
    app.logger.warning(f"无法安装 NanSafeJSONProvider, 将继续使用默认 provider: {_e}")


# 保持API兼容的路由
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        stock_codes = data.get('stock_codes', [])
        market_type = data.get('market_type', 'A')

        if not stock_codes:
            return api_error('INVALID_INPUT', '请输入代码')

        app.logger.info(f"分析股票请求: {stock_codes}, 市场类型: {market_type}")

        # 设置最大处理时间，每只股票10秒
        max_time_per_stock = 10  # 秒
        max_total_time = max(30, min(60, len(stock_codes) * max_time_per_stock))  # 至少30秒，最多60秒

        start_time = time.time()
        results = []

        for stock_code in stock_codes:
            try:
                # 检查是否已超时
                if time.time() - start_time > max_total_time:
                    app.logger.warning(f"分析股票请求已超过{max_total_time}秒，提前返回已处理的{len(results)}只股票")
                    break

                # 使用线程本地缓存的分析器实例
                current_analyzer = get_analyzer()
                result = current_analyzer.quick_analyze_stock(stock_code.strip(), market_type)

                app.logger.info(
                    f"分析结果: 股票={stock_code}, 名称={result.get('stock_name', '未知')}, 行业={result.get('industry', '未知')}")
                results.append(result)
            except Exception as e:  # broad-catch: 每只股票独立失败不中断批量 (S1-C1 api_error 已规范错误响应)
                app.logger.error(f"分析股票 {stock_code} 时出错: {str(e)}")
                results.append({
                    'stock_code': stock_code,
                    'error': str(e),
                    'stock_name': '分析失败',
                    'industry': '未知'
                })

        return jsonify({'results': results})
    except Exception as e:  # broad-catch: 批量结果汇总兜底 (S1-C1 api_error 已规范错误响应)
        app.logger.error(f"分析股票时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '行情分析失败，请稍后重试', details=str(e))


@app.route('/api/north_flow_history', methods=['POST'])
@validate_schema(NorthFlowHistorySchema, source='json')  # S3-E1: schema 校验扩展
def api_north_flow_history():
    try:
        data = request.json
        stock_code = data.get('stock_code')
        days = data.get('days', 10)  # 默认为10天，对应前端的默认选项

        # 计算 end_date 为当前时间
        end_date = now_cn().strftime('%Y%m%d')

        # 计算 start_date 为 end_date 减去指定的天数
        start_date = (now_cn() - timedelta(days=int(days))).strftime('%Y%m%d')

        if not stock_code:
            return api_error('INVALID_INPUT', '请提供股票代码')

        # 调用北向资金历史数据方法

        analyzer = CapitalFlowAnalyzer()
        result = analyzer.get_north_flow_history(stock_code, start_date, end_date)

        return custom_jsonify(result)
    except Exception as e:  # broad-catch: capital_flow_analyzer 已有上游网络降级日志 (S1-C1 api_error)
        app.logger.error(f"获取北向资金历史数据出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '北向资金数据加载失败，请稍后重试', details=str(e))


@app.route('/search_us_stocks', methods=['GET'])
def search_us_stocks():
    try:
        keyword = request.args.get('keyword', '')
        if not keyword:
            return api_error('INVALID_INPUT', '请输入搜索关键词')

        results = us_stock_service.search_us_stocks(keyword)
        return jsonify({'results': results})

    except Exception as e:  # broad-catch: us_stock_service 内部各类异常统一兜底 (S1-C1 api_error)
        app.logger.error(f"搜索美股代码时出错: {str(e)}")
        return api_error('INTERNAL', '搜索股票失败，请稍后重试', details=str(e))


# 新增可视化分析页面路由
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/stock_detail/<string:stock_code>')
def stock_detail(stock_code):
    market_type = request.args.get('market_type', 'A')
    return render_template('stock_detail.html', stock_code=stock_code, market_type=market_type)


@app.route('/portfolio')
def portfolio():
    return render_template('portfolio.html')


@app.route('/market_scan')
def market_scan():
    return render_template('market_scan.html')


# 基本面分析页面
@app.route('/fundamental')
def fundamental():
    return render_template('fundamental.html')


# 资金流向页面
@app.route('/capital_flow')
def capital_flow():
    return render_template('capital_flow.html')


# 情景预测页面
@app.route('/scenario_predict')
def scenario_predict():
    return render_template('scenario_predict.html')


# 风险监控页面
@app.route('/risk_monitor')
def risk_monitor_page():
    return render_template('risk_monitor.html')


# 智能问答页面
@app.route('/qa')
def qa_page():
    return render_template('qa.html')


# 行业分析页面
@app.route('/industry_analysis')
def industry_analysis():
    return render_template('industry_analysis.html')



# 智能体分析页面
@app.route('/agent_analysis')
def agent_analysis_page():
    return render_template('agent_analysis.html')


@app.route('/etf_analysis')
def etf_analysis_page():
    return render_template('etf_analysis.html')





def make_cache_key_with_stock():
    """创建包含股票代码的自定义缓存键"""
    path = request.path

    # 从请求体中获取股票代码
    stock_code = None
    if request.is_json:
        stock_code = request.json.get('stock_code')

    # 构建包含股票代码的键
    if stock_code:
        return f"{path}_{stock_code}"
    else:
        return path


@app.route('/api/start_stock_analysis', methods=['POST'])
@validate_schema(StartStockAnalysisSchema, source='json')  # S3-D3: schema 校验扩展
def start_stock_analysis():
    """启动个股分析任务"""
    try:
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return api_error('INVALID_INPUT', '请求体必须为有效的JSON格式')
        stock_code = data.get('stock_code')
        market_type = data.get('market_type', 'A')

        if not stock_code:
            return api_error('INVALID_INPUT', '请输入股票代码')

        valid, result = validate_stock_code(stock_code, market_type)
        if not valid:
            return api_error('INVALID_INPUT', result)
        stock_code = result

        app.logger.info(f"准备分析股票: {stock_code}")

        # 获取或创建任务
        task_id, task, is_new = get_or_create_task(
            'stock_analysis',
            stock_code=stock_code,
            market_type=market_type
        )

        # 如果是已完成的任务，直接返回结果
        if task['status'] == TASK_COMPLETED and 'result' in task:
            app.logger.info(f"使用缓存的分析结果: {stock_code}")
            return jsonify({
                'task_id': task_id,
                'status': task['status'],
                'result': task['result']
            })

        # 如果是新创建的任务，启动后台处理
        if is_new:
            app.logger.info(f"创建新的分析任务: {task_id}")

            # 启动后台线程执行分析
            def run_analysis():
                try:
                    update_task_status('stock_analysis', task_id, TASK_RUNNING, progress=10)

                    # 执行分析
                    result = analyzer.perform_enhanced_analysis(stock_code, market_type)

                    # 更新任务状态为完成
                    update_task_status('stock_analysis', task_id, TASK_COMPLETED, progress=100, result=result)
                    app.logger.info(f"分析任务 {task_id} 完成")

                except Exception as e:  # broad-catch: 后台任务各类失败统一降级 (已记录 TASK_FAILED)
                    app.logger.error(f"分析任务 {task_id} 失败: {str(e)}")
                    app.logger.error(traceback.format_exc())
                    update_task_status('stock_analysis', task_id, TASK_FAILED, error=str(e))

            # 启动后台线程
            thread = threading.Thread(target=run_analysis)
            thread.daemon = True
            thread.start()

        # 返回任务ID和状态
        return jsonify({
            'task_id': task_id,
            'status': task['status'],
            'message': f'已启动分析任务: {stock_code}'
        })

    except Exception as e:
        app.logger.error(f"启动个股分析任务时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '启动分析任务失败，请稍后重试', details=str(e))


@app.route('/api/analysis_status/<task_id>', methods=['GET'])
@validate_schema(AnalysisStatusSchema)  # S3-J(A): schema 校验扩展
def get_analysis_status(task_id):
    """获取个股分析任务状态"""
    store = get_task_store('stock_analysis')
    with task_lock:
        if task_id not in store:
            return jsonify({'error': '找不到指定的分析任务'}), 404

        task = store[task_id]

        # 基本状态信息
        status = {
            'id': task['id'],
            'status': task['status'],
            'progress': task.get('progress', 0),
            'created_at': task['created_at'],
            'updated_at': task['updated_at']
        }

        # 如果任务完成，包含结果
        if task['status'] == TASK_COMPLETED and 'result' in task:
            status['result'] = task['result']

        # 如果任务失败，包含错误信息
        if task['status'] == TASK_FAILED and 'error' in task:
            status['error'] = task['error']

        return custom_jsonify(status)


@app.route('/api/cancel_analysis/<task_id>', methods=['POST'])
@validate_schema(CancelAnalysisSchema, source='json')  # S3-J(A): schema 校验扩展
def cancel_analysis(task_id):
    """取消个股分析任务"""
    store = get_task_store('stock_analysis')
    with task_lock:
        if task_id not in store:
            return jsonify({'error': '找不到指定的分析任务'}), 404

        task = store[task_id]

        if task['status'] in [TASK_COMPLETED, TASK_FAILED]:
            return jsonify({'message': '任务已完成或失败，无法取消'})

        # 更新状态为失败
        task['status'] = TASK_FAILED
        task['error'] = '用户取消任务'
        task['updated_at'] = now_cn().strftime('%Y-%m-%d %H:%M:%S')

        # 更新键索引的任务
        if 'key' in task and task['key'] in store:
            store[task['key']] = task

        return jsonify({'message': '任务已取消'})


# ETF 分析路由
@app.route('/api/start_etf_analysis', methods=['POST'])
@validate_schema(StartEtfAnalysisSchema, source='json')  # S3-G1: schema 校验扩展
def start_etf_analysis():
    """启动ETF分析任务"""
    try:
        data = request.json
        etf_code = data.get('etf_code')

        if not etf_code:
            return jsonify({'error': '请输入ETF代码'}), 400

        app.logger.info(f"准备分析ETF: {etf_code}")

        task_id, task, is_new = get_or_create_task(
            'etf_analysis',
            etf_code=etf_code
        )

        if task['status'] == TASK_COMPLETED and 'result' in task:
            app.logger.info(f"使用缓存的ETF分析结果: {etf_code}")
            return jsonify({
                'task_id': task_id,
                'status': task['status'],
                'result': task['result']
            })

        if is_new:
            app.logger.info(f"创建新的ETF分析任务: {task_id}")

            def run_etf_analysis():
                try:
                    update_task_status('etf_analysis', task_id, TASK_RUNNING, progress=10)
                    
                    # 使用一个新的 EtfAnalyzer 实例, 并传入stock_analyzer
                    etf_analyzer_instance = EtfAnalyzer(etf_code, analyzer)
                    result = etf_analyzer_instance.run_analysis()
                    
                    update_task_status('etf_analysis', task_id, TASK_COMPLETED, progress=100, result=result)
                    app.logger.info(f"ETF分析任务 {task_id} 完成")

                except Exception as e:  # broad-catch: ETF 后台任务各类失败统一降级 (已记录 TASK_FAILED)
                    app.logger.error(f"ETF分析任务 {task_id} 失败: {str(e)}")
                    app.logger.error(traceback.format_exc())
                    update_task_status('etf_analysis', task_id, TASK_FAILED, error=str(e))

            thread = threading.Thread(target=run_etf_analysis)
            thread.daemon = True
            thread.start()

        return jsonify({
            'task_id': task_id,
            'status': task['status'],
            'message': f'已启动ETF分析任务: {etf_code}'
        })

    except Exception as e:  # broad-catch: ETF 外层启动异常兜底 (S1-C1 api_error)
        app.logger.error(f"启动ETF分析任务时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '启动ETF分析任务失败，请稍后重试', details=str(e))


@app.route('/api/etf_analysis_status/<task_id>', methods=['GET'])
@validate_schema(EtfAnalysisStatusSchema)  # S3-J(A): schema 校验扩展
def get_etf_analysis_status(task_id):
    """获取ETF分析任务状态"""
    store = get_task_store('etf_analysis')
    with task_lock:
        if task_id not in store:
            return jsonify({'error': '找不到指定的ETF分析任务'}), 404

        task = store[task_id]

        status = {
            'id': task['id'],
            'status': task['status'],
            'progress': task.get('progress', 0),
            'created_at': task['created_at'],
            'updated_at': task['updated_at']
        }

        if task['status'] == TASK_COMPLETED and 'result' in task:
            status['result'] = task['result']
        
        if task['status'] == TASK_FAILED and 'error' in task:
            status['error'] = task['error']

        return custom_jsonify(status)


# 保留原有API用于向后兼容
@app.route('/api/enhanced_analysis', methods=['POST'])
@validate_schema(EnhancedAnalysisSchema, source='json')  # S3-G1: schema 校验扩展
def enhanced_analysis():
    """原增强分析API的向后兼容版本"""
    try:
        data = request.json
        stock_code = data.get('stock_code')
        market_type = data.get('market_type', 'A')

        if not stock_code:
            return custom_jsonify({'error': '请输入股票代码'}), 400

        valid, result = validate_stock_code(stock_code, market_type)
        if not valid:
            return jsonify({'error': result}), 400
        stock_code = result

        # 调用新的任务系统，但模拟同步行为
        # 这会导致和之前一样的超时问题，但保持兼容
        timeout = 300
        start_time = time.time()

        # 获取或创建任务
        task_id, task, is_new = get_or_create_task(
            'stock_analysis',
            stock_code=stock_code,
            market_type=market_type
        )

        # 如果是已完成的任务，直接返回结果
        if task['status'] == TASK_COMPLETED and 'result' in task:
            app.logger.info(f"使用缓存的分析结果: {stock_code}")
            return custom_jsonify({'result': task['result']})

        # 启动分析（如果是新任务）
        if is_new:
            # 同步执行分析
            try:
                result = analyzer.perform_enhanced_analysis(stock_code, market_type)
                update_task_status('stock_analysis', task_id, TASK_COMPLETED, progress=100, result=result)
                app.logger.info(f"分析完成: {stock_code}，耗时 {time.time() - start_time:.2f} 秒")
                return custom_jsonify({'result': result})
            except Exception as e:  # broad-catch: 增强分析任务失败兜底 (已记录 TASK_FAILED)
                app.logger.error(f"分析过程中出错: {str(e)}")
                update_task_status('stock_analysis', task_id, TASK_FAILED, error=str(e))
                return custom_jsonify({'error': f'分析过程中出错: {str(e)}'}), 500
        else:
            # 已存在正在处理的任务，等待其完成
            max_wait = timeout - (time.time() - start_time)
            wait_interval = 0.5
            waited = 0

            store = get_task_store('stock_analysis')
            while waited < max_wait:
                with task_lock:
                    current_task = store[task_id]
                    if current_task['status'] == TASK_COMPLETED and 'result' in current_task:
                        return custom_jsonify({'result': current_task['result']})
                    if current_task['status'] == TASK_FAILED:
                        error = current_task.get('error', '任务失败，无详细信息')
                        return custom_jsonify({'error': error}), 500

                time.sleep(wait_interval)
                waited += wait_interval

            # 超时
            return custom_jsonify({'error': '处理超时，请稍后重试'}), 504

    except Exception as e:  # broad-catch: 增强分析外层兜底 (S1-C1 api_error)
        app.logger.error(f"执行增强版分析时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '增强分析执行失败，请稍后重试', details=str(e))


# ============ 输入校验工具（S2-A1 Hunt3-Major/Hunt5-M5 2026-05-20） ============
# Input: 原始 request 参数字符串
# Output: 清洗后的合法值，非法时抛出 ValidationError
# Pos: 所有接收外部参数的 API 端点入口，防止 SQL 拖垮 / DOS

_STOCK_CODE_RE_STRICT = re.compile(r'^(sh|sz|bj|hk|us)?\.?\d{4,6}$', re.IGNORECASE)
_DATE_RE = re.compile(r'^\d{8}$')  # YYYYMMDD


class ValidationError(Exception):
    """输入校验失败；由 handle_validation_error 统一转为 400 INVALID_INPUT"""
    pass


def validate_stock_code_strict(code: str) -> str:
    """严格校验 stock_code：长度 ≤20、符合 A/HK/US 格式
    与旧 validate_stock_code() 共存；旧函数不破坏，不改名"""
    if not code or not isinstance(code, str):
        raise ValidationError('stock_code 必填')
    code = code.strip()
    if len(code) > 20:
        raise ValidationError('stock_code 长度超限（>20字符）')
    if not _STOCK_CODE_RE_STRICT.match(code):
        raise ValidationError(f'stock_code 格式不合法: {code}')
    return code


def validate_date_param(s, field: str = 'date'):
    """校验 YYYYMMDD 格式，None → None"""
    if s is None or s == '':
        return None
    if not _DATE_RE.match(str(s)):
        raise ValidationError(f'{field} 格式必须为 YYYYMMDD，实际: {s}')
    return str(s)


def validate_int_range(v, field: str, min_v: int = 1, max_v: int = 1000, default=None):
    """将 v 转为整数并钳制在 [min_v, max_v]；v 为空时返回 default"""
    if v is None or v == '':
        return default
    try:
        iv = int(v)
    except (ValueError, TypeError):
        raise ValidationError(f'{field} 必须是整数，实际: {v}')
    if not (min_v <= iv <= max_v):
        raise ValidationError(f'{field} 必须在 [{min_v}, {max_v}] 范围内，实际: {iv}')
    return iv


def validate_kline_period(p, default: str = 'daily') -> str:
    """校验 K 线 period 参数"""
    allowed = {'daily', 'weekly', 'monthly', 'min5', 'min15', 'min30', 'min60',
               '1y', '3m', '6m', '5y', '1m', '10日排行', '10日', 'monthly'}
    if p is None or p == '':
        return default
    if p not in allowed:
        raise ValidationError(f'period 必须是合法值之一，实际: {p}')
    return p


# ============ 统一成功响应外壳（S2-A2 Hunt5-M1 2026-05-20） ============
# Input: 任意 data / meta
# Output: JSON {success:true, data:...}
# Pos: 新增或改造端点的成功路径，旧接口保持原 jsonify schema

def api_ok(data=None, meta: dict = None, **kwargs):
    """统一成功响应外壳；前端 client.ts 通过 success 字段识别新外壳"""
    resp = {'success': True, 'data': data}
    if meta:
        resp['meta'] = meta
    resp.update(kwargs)
    return jsonify(resp)


# ============ 缓存 Header 装饰器（S2-A3 Hunt5-M6 2026-05-20） ============
# Input: seconds 缓存秒数, public 是否公共缓存
# Output: 为 Response 附加 Cache-Control header
# Pos: 套用到行情/日线/公司信息等端点

def with_cache(seconds: int, public: bool = True):
    """为端点添加 Cache-Control header
    实时类 5s / 半实时 60s / 历史 3600s"""
    from functools import wraps

    def deco(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            resp = f(*args, **kwargs)
            # 兼容 (response, status) 二元组
            if isinstance(resp, tuple):
                resp_obj = resp[0]
            else:
                resp_obj = resp
            cc = 'public' if public else 'private'
            # 仅当 resp_obj 是 Response 时附加 header
            if hasattr(resp_obj, 'headers'):
                resp_obj.headers['Cache-Control'] = f'{cc}, max-age={seconds}'
            return resp
        return wrapped
    return deco


# ============ 统一错误响应外壳（S1-C1 Hunt3-Critical 2026-05-20） ============
# Input: error_code 字符串, 用户友好 message, 可选 details（仅 debug 暴露）
# Output: JSON {success:false, error_code, message} + HTTP status
# Pos: 所有 API 错误出口统一经此函数，防止内部细节泄露
ERROR_CODES = {
    'INVALID_INPUT': 400, 'UNAUTHORIZED': 401, 'FORBIDDEN': 403,
    'NOT_FOUND': 404, 'RATE_LIMITED': 429, 'INTERNAL': 500,
    'UPSTREAM_TIMEOUT': 504, 'UPSTREAM_FAILED': 502, 'DEGRADED': 503,
}


def api_error(code: str = 'INTERNAL', message: str = '服务异常，请稍后重试',
              details=None, status: int = None):
    """统一错误响应外壳：不泄露 str(e) / traceback 到 response"""
    resp = {
        'success': False,
        'error_code': code,
        'message': message,
        'error': message,  # 向后兼容旧 {'error': ...} 形式，供已有测试/前端使用
    }
    if details and app.debug:
        resp['details'] = details  # 仅 debug 模式可见
    return jsonify(resp), status or ERROR_CODES.get(code, 500)


@app.errorhandler(Exception)
def handle_unhandled(e):
    """兜底：未被路由 catch 的异常；HTTPException（4xx/5xx）保持原状态码透传"""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        # 405/404 等 werkzeug 标准异常：透传状态码，不升级为 500
        if request.path.startswith('/api/'):
            code_map = {404: 'NOT_FOUND', 405: 'INVALID_INPUT', 400: 'INVALID_INPUT',
                        401: 'UNAUTHORIZED', 403: 'FORBIDDEN', 429: 'RATE_LIMITED'}
            err_code = code_map.get(e.code, 'INTERNAL')
            return api_error(err_code, e.description or str(e), status=e.code)
        return e  # 非 API 路径，Flask 默认 HTML 处理
    app.logger.exception(f"Unhandled exception in {request.path}: {e}")
    if request.path.startswith('/api/'):
        return api_error('INTERNAL', '服务内部错误，请稍后重试', details=str(e))
    return render_template('error.html', error_code=500, message="服务器内部错误"), 500


@app.errorhandler(404)
def not_found(error):
    """处理404错误"""
    if request.path.startswith('/api/'):
        return api_error('NOT_FOUND', '找不到请求的API端点')
    return render_template('error.html', error_code=404, message="找不到请求的页面"), 404


@app.errorhandler(500)
def server_error(error):
    """处理500错误"""
    app.logger.error(f"服务器错误: {str(error)}")
    if request.path.startswith('/api/'):
        return api_error('INTERNAL', '服务器内部错误，请稍后重试')
    return render_template('error.html', error_code=500, message="服务器内部错误"), 500


@app.errorhandler(ValidationError)
def handle_validation_error(e):
    """S2-A1：输入校验失败 → 400 INVALID_INPUT"""
    return api_error('INVALID_INPUT', str(e))


@app.errorhandler(429)
def handle_rate_limit(e):
    """S2-A4：超过限流阈值 → 429 RATE_LIMITED"""
    return api_error('RATE_LIMITED', '请求过于频繁，请稍后重试', status=429)


# ============ A股名称缓存（ak.stock_info_a_code_name fallback） ============
# 解决东方财富接口偶发失败导致stock_name降级为股票代码的问题
_STOCK_NAME_CACHE = {}
_CACHE_LOADED = False
_CACHE_LAST_FAIL_TS = 0.0  # 上次加载失败（超时/异常）的单调时钟时间戳；0 表示从未失败
_CACHE_LOCK = threading.Lock()
_STOCK_NAME_CACHE_LOCK = threading.RLock()  # S1-C4: 并发读写保护（启动期循环写与请求读并发）

# [2026-06-15 本地名称字典] 联网成功后将全量 A 股名称表落盘为 runtime 快照，
# 离线/上游不可达时回退读取该快照填充缓存，消除"离线必退码"的结构性缺口。
_STOCK_NAME_SNAPSHOT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data', 'stock_names.json')


def _persist_stock_name_snapshot(mapping):
    """将 code->name 映射原子落盘到 data/stock_names.json（runtime 数据，非源码）。

    Input : mapping 全量 A 股 code->name dict
    Output: 无；成功落盘则离线可复用
    Pos   : _load_stock_name_cache 联网成功后调用

    防御：仅在条目数达到合理阈值（默认 500）时落盘，避免上游只返回少量/降级数据时
    覆写已有完整快照（铁律 #1：不以残缺数据污染离线名称源）。
    """
    if not mapping:
        return
    _min_rows = int(os.getenv('STOCK_NAME_SNAPSHOT_MIN_ROWS', '500'))
    if len(mapping) < _min_rows:
        app.logger.info(
            f"A股名称表仅 {len(mapping)} 条(<{_min_rows})，跳过快照落盘以保护已有完整快照")
        return
    try:
        os.makedirs(os.path.dirname(_STOCK_NAME_SNAPSHOT_PATH), exist_ok=True)
        # 复用项目已有原子写工具，避免半写文件
        atomic_write_json(_STOCK_NAME_SNAPSHOT_PATH, mapping)
        app.logger.info(
            f"A股名称本地快照已落盘: {_STOCK_NAME_SNAPSHOT_PATH}（{len(mapping)} 条）")
    except Exception as e:
        app.logger.warning(f"A股名称本地快照落盘失败: {str(e)}")


def _load_stock_name_snapshot():
    """从 data/stock_names.json 读取本地名称快照（离线回退）。

    Input : 无（读 _STOCK_NAME_SNAPSHOT_PATH）
    Output: code->name dict（无快照/解析失败返回 {}）
    Pos   : _load_stock_name_cache 联网失败时的离线回退源
    """
    try:
        if not os.path.exists(_STOCK_NAME_SNAPSHOT_PATH):
            return {}
        with open(_STOCK_NAME_SNAPSHOT_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if v}
    except Exception as e:
        app.logger.warning(f"A股名称本地快照读取失败: {str(e)}")
    return {}


def _load_stock_name_cache():
    """首次调用时加载全量A股代码->名称映射（~5000条）到进程级缓存

    Input : 无（隐式调用 ak.stock_info_a_code_name，受 env 配置约束）
    Output: 无返回值；成功时填充 _STOCK_NAME_CACHE 并永久标记 _CACHE_LOADED=True
    Pos   : stock_name 兜底链入口，被 _get_stock_name_safe 等非阻塞调用

    [REAL-01 2026-05-18] 上游 bse.cn 经常被代理 RST 阻塞，加硬超时避免反复重试拖垮 stock_quote_batch。
    [2026-05-29 修复] 原实现在 try 前无条件置 _CACHE_LOADED=True，超时/异常后永久不再重试，
        真实网络下 5s 拉不完全量名称表即导致本进程名称长期退化为代码。改为：
        - 仅在成功填充后才永久标记 _CACHE_LOADED=True；
        - 失败（超时/异常）记录 _CACHE_LAST_FAIL_TS，并在冷却窗（STOCK_NAME_CACHE_RETRY_COOLDOWN_S，
          default 60s）内节流后续重试，避免每请求都打满上游；冷却窗过后允许再次尝试。
        - 默认超时由 5s 提升至 15s（env STOCK_NAME_CACHE_TIMEOUT_S 可覆盖）。
        线程安全：失败/成功标记均在 _CACHE_LOCK 内更新；缓存写入在 _STOCK_NAME_CACHE_LOCK 内。
    """
    global _CACHE_LOADED, _CACHE_LAST_FAIL_TS
    if _CACHE_LOADED:
        return
    _cooldown_s = float(os.getenv('STOCK_NAME_CACHE_RETRY_COOLDOWN_S', '60'))
    # 锁外快速冷却窗检查：上次失败后在冷却窗内则直接放行（不阻塞请求线程、不打满上游）
    if _CACHE_LAST_FAIL_TS and (time.monotonic() - _CACHE_LAST_FAIL_TS) < _cooldown_s:
        return
    with _CACHE_LOCK:
        if _CACHE_LOADED:
            return
        # 锁内复检冷却窗：避免多个线程同时穿过锁外检查后串行重复尝试
        if _CACHE_LAST_FAIL_TS and (time.monotonic() - _CACHE_LAST_FAIL_TS) < _cooldown_s:
            return
        try:
            import akshare as ak
            from concurrent.futures import TimeoutError as _FTimeout
            _timeout_s = float(os.getenv('STOCK_NAME_CACHE_TIMEOUT_S', '15'))
            # BD-3: 改用全局线程池
            # BD-3：全局池不可 shutdown；超时仅 cancel future，不销毁池
            fut = _GLOBAL_THREAD_POOL.submit(ak.stock_info_a_code_name)
            try:
                df = fut.result(timeout=_timeout_s)
            except _FTimeout:
                fut.cancel()
                # 不永久标记已加载：记录失败时间戳，冷却窗后允许重试
                _CACHE_LAST_FAIL_TS = time.monotonic()
                app.logger.warning(
                    f"加载A股名称缓存超时(>{_timeout_s}s)，{_cooldown_s}s 冷却后允许重试")
                # 离线/超时回退：尝试用本地快照填充（不永久标记，联网恢复后仍会重试刷新）
                _snap = _load_stock_name_snapshot()
                if _snap:
                    with _STOCK_NAME_CACHE_LOCK:
                        _STOCK_NAME_CACHE.update(_snap)
                    app.logger.info(
                        f"A股名称缓存超时，已用本地快照回退填充 {len(_snap)} 条")
                return
            with _STOCK_NAME_CACHE_LOCK:
                for _, row in df.iterrows():
                    _STOCK_NAME_CACHE[str(row['code'])] = str(row['name'])
            # 仅成功填充后永久标记，并清除失败时间戳
            _CACHE_LOADED = True
            _CACHE_LAST_FAIL_TS = 0.0
            app.logger.info(f"A股名称缓存加载完成，共 {len(_STOCK_NAME_CACHE)} 条")
            # 联网成功：刷新本地快照，供下次离线回退（在锁外读取快照副本落盘）
            with _STOCK_NAME_CACHE_LOCK:
                _snapshot = dict(_STOCK_NAME_CACHE)
            _persist_stock_name_snapshot(_snapshot)
        except Exception as e:
            # 不永久标记已加载：记录失败时间戳，冷却窗后允许重试
            _CACHE_LAST_FAIL_TS = time.monotonic()
            app.logger.warning(
                f"加载A股名称缓存失败: {str(e)}，{_cooldown_s}s 冷却后允许重试")
            # 离线/异常回退：尝试用本地快照填充（不永久标记，联网恢复后仍会重试刷新）
            try:
                _snap = _load_stock_name_snapshot()
                if _snap:
                    with _STOCK_NAME_CACHE_LOCK:
                        _STOCK_NAME_CACHE.update(_snap)
                    app.logger.info(
                        f"A股名称缓存加载失败，已用本地快照回退填充 {len(_snap)} 条")
            except Exception:
                pass


def _get_stock_name_safe(stock_code, market_type='A'):
    """
    安全获取股票名称：
    1. 优先调用 analyzer.get_stock_info（东方财富，信息最全，3s 硬超时）
    2. 失败则降级**只读** A股名称缓存（_STOCK_NAME_CACHE）
    3. 最终降级返回 None（缺名，不回填 code）

    Input : stock_code 股票代码、market_type 市场类型
    Output: 股票名称字符串；未命中则返回 None（B2 2026-06-15：不再退化为 code，
            交由调用方/前端按占位处理，区分"无名"与"真名"）
    Pos   : stock_name 兜底链入口；请求线程关键路径

    [2026-05-29 后台预热] 第 2 步降级路径不再在请求线程同步调用 _load_stock_name_cache()
        （该函数首发可阻塞至多 STOCK_NAME_CACHE_TIMEOUT_S=15s）。改为只读 _STOCK_NAME_CACHE：
        缓存命中即返回真名，未命中立即走最终兜底退码。全量加载由启动后台预热线程
        _preload_stock_names 负责（沿用 _startup_background_enabled 离线/测试门控），
        后续请求自然命中，请求线程永不被全量加载阻塞。
    """
    # 非A股暂无对应fallback，直接尝试analyzer
    if market_type != 'A':
        try:
            info = analyzer.get_stock_info(stock_code)
            if isinstance(info, dict):
                name = info.get('股票名称') or info.get('name')
                if name and name != '未知':
                    return name
        except Exception:
            pass
        return None

    # 1. 先试主路径 [REAL-01 2026-05-18] 加 3s 硬超时
    # BD-3: 改用全局线程池，不需要手动 shutdown
    try:
        from concurrent.futures import TimeoutError as _FTimeout
        try:
            fut = _GLOBAL_THREAD_POOL.submit(analyzer.get_stock_info, stock_code)
            try:
                info = fut.result(timeout=3)
            except _FTimeout:
                info = None
            if isinstance(info, dict):
                name = info.get('股票名称') or info.get('name')
                if name and name != '未知' and name != stock_code:
                    return name
        except Exception:
            pass
    except Exception as e:
        app.logger.warning(f"analyzer.get_stock_info 失败 {stock_code}: {str(e)}")

    # 2. 降级：只读全量A股缓存（不在请求线程触发全量加载，由后台预热线程填充）
    with _STOCK_NAME_CACHE_LOCK:
        if stock_code in _STOCK_NAME_CACHE:
            return _STOCK_NAME_CACHE[stock_code]

    # 3. 最终降级：缺名返回 None（B2 2026-06-15：不再把 code 当名回填，
    #    让前端区分"无名"与"真名"并按占位处理；与前端 B1 守卫配套）
    return None


# Update the get_stock_data function in web_server.py to handle date formatting properly
@app.route('/api/stock_data', methods=['GET'])
@with_cache(60)  # S2-A3: 半实时 1分钟缓存
@limiter.limit('200 per minute')  # S2-A4
@cache.cached(timeout=300, query_string=True)
@validate_schema(StockDataSchema)  # S3-C4: marshmallow schema 前置校验
def get_stock_data():
    # Input: stock_code/period/start_date/end_date/market_type query params（S3-C4 schema 校验）
    # Output: JSON OHLCV 历史数据
    # Pos: K线页面核心数据端点，已套 S2-A1 校验 + S3-C4 schema 校验
    # S2-A1: validate 在 try 外，ValidationError 直达全局 errorhandler → 400 INVALID_INPUT
    raw_code = request.args.get('stock_code', '')
    stock_code_checked = validate_stock_code_strict(raw_code)
    validate_date_param(request.args.get('start_date'), 'start_date')
    validate_date_param(request.args.get('end_date'), 'end_date')
    validate_kline_period(request.args.get('period', '1y'))
    try:
        stock_code = stock_code_checked
        market_type = request.args.get('market_type', 'A')
        period = request.args.get('period', '1y')

        # 兼容旧 validate_stock_code 的市场类型精确校验（新 validate_stock_code_strict 已初步过滤）
        valid, result = validate_stock_code(stock_code, market_type)
        if not valid:
            return jsonify({'error': result}), 400
        stock_code = result

        # 根据period计算start_date
        end_date = now_cn().strftime('%Y%m%d')
        if period == '1m':
            start_date = (now_cn() - timedelta(days=30)).strftime('%Y%m%d')
        elif period == '3m':
            start_date = (now_cn() - timedelta(days=90)).strftime('%Y%m%d')
        elif period == '6m':
            start_date = (now_cn() - timedelta(days=180)).strftime('%Y%m%d')
        elif period == '1y':
            start_date = (now_cn() - timedelta(days=365)).strftime('%Y%m%d')
        else:
            start_date = (now_cn() - timedelta(days=365)).strftime('%Y%m%d')

        # 获取股票历史数据（30秒硬超时，避免akshare外网卡死占满werkzeug线程池）
        app.logger.info(
            f"获取股票 {stock_code} 的历史数据，市场: {market_type}, 起始日期: {start_date}, 结束日期: {end_date}")
        from concurrent.futures import TimeoutError as _FTimeout
        # BD-3: 改用全局线程池
        try:
            fut = _GLOBAL_THREAD_POOL.submit(analyzer.get_stock_data, stock_code, market_type, start_date, end_date)
            _stock_data_timeout = float(os.getenv('STOCK_DATA_THREAD_TIMEOUT', '50'))
            df = fut.result(timeout=_stock_data_timeout)  # 由 STOCK_DATA_THREAD_TIMEOUT 驱动，与下游 per_call=45 联动，留 5s buffer
        except _FTimeout:
            app.logger.warning(f"analyzer.get_stock_data 超时(30s)：{stock_code}")
            return custom_jsonify({'error': '数据源超时', 'stock_code': stock_code}), 504

        # 检查数据是否为空
        if df.empty:
            app.logger.warning(f"股票 {stock_code} 的数据为空")
            return custom_jsonify({'error': '未找到股票数据'}), 404

        # 计算技术指标
        app.logger.info(f"计算股票 {stock_code} 的技术指标")
        df = analyzer.calculate_indicators(df)

        # 将DataFrame转为JSON格式
        app.logger.info(f"将数据转换为JSON格式，行数: {len(df)}")

        # 确保日期列是字符串格式 - 修复缓存问题
        if 'date' in df.columns:
            try:
                if pd.api.types.is_datetime64_any_dtype(df['date']):
                    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
                else:
                    df = df.copy()
                    df['date'] = pd.to_datetime(df['date'], errors='coerce')
                    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
            except Exception as e:
                app.logger.error(f"处理日期列时出错: {str(e)}")
                df['date'] = df['date'].astype(str)

        # 将NaN值替换为None
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})

        records = df.to_dict('records')

        # 获取股票名称（主路径失败自动降级到akshare全量缓存）
        stock_name = _get_stock_name_safe(stock_code, market_type)

        # B2-3: 标注复权方式，消除 akshare/yfinance 混用歧义
        _adjust_param = request.args.get('adjust', 'qfq')
        _adjust_flag_map = {'qfq': 'qfq', 'hfq': 'hfq', 'none': 'none', '': 'qfq'}
        _adjust_flag = _adjust_flag_map.get(_adjust_param, 'qfq')
        if market_type in ('US', 'HK'):
            # yfinance 默认 auto_adjust=True
            _adjust_flag = 'auto'

        app.logger.info(f"数据处理完成，返回 {len(records)} 条记录, 股票名称: {stock_name}")
        return custom_jsonify({
            'data': records,
            'stock_name': stock_name,
            'meta': {
                'adjust_flag': _adjust_flag,
                'source': 'akshare' if market_type == 'A' else 'yfinance',
            },
        })
    except Exception as e:
        app.logger.error(f"获取股票数据时出错: {str(e)}")
        app.logger.error(traceback.format_exc())
        return api_error('INTERNAL', '行情数据加载失败，请稍后重试', details=str(e))


# 股票概要：名称/行业/市值/PE/PB/ROE — 供对比页快速对比使用（baostock主，不依赖eastmoney）
# baostock使用全局session，并发请求会串线 — 用lock串行化 + profile短缓存 + 启动时一次登录
import threading as _threading
import atexit as _atexit
_BAOSTOCK_LOCK = _threading.Lock()
_PROFILE_CACHE = {}  # {stock_code: (ts, profile)}
_PROFILE_CACHE_LOCK = _threading.RLock()  # S1-C3: 并发读写保护
_PROFILE_CACHE_TTL_S = int(os.getenv('PROFILE_CACHE_TTL_S', '86400'))  # BD-5: 1天默认 TTL
_PROFILE_STALE_MAX_S = int(os.getenv('PROFILE_STALE_MAX_S', '86400'))  # B16：stale cache 最长留存
_BS_LOGGED_IN = False


def _profile_cache_get(key):
    """S1-C3: 线程安全读 _PROFILE_CACHE"""
    with _PROFILE_CACHE_LOCK:
        return _PROFILE_CACHE.get(key)


def _profile_cache_set(key, value):
    """S1-C3: 线程安全写 _PROFILE_CACHE"""
    with _PROFILE_CACHE_LOCK:
        _PROFILE_CACHE[key] = value


def _profile_cache_evict_and_set(stock_code, value, ttl):
    """S1-C3: 先淘汰过期再写入，整体加锁避免 dict size change"""
    now = time.time()
    with _PROFILE_CACHE_LOCK:
        stale_keys = [k for k, (ts, _) in _PROFILE_CACHE.items() if now - ts > ttl]
        for k in stale_keys:
            _PROFILE_CACHE.pop(k, None)
        _PROFILE_CACHE[stock_code] = value

def _ensure_bs_login():
    # [Batch8-FIX 2026-05-19] DISABLE_NETWORK=1 时跳过真实 baostock 网络连接（测试环境）
    if os.getenv("DISABLE_NETWORK") == "1":
        return
    global _BS_LOGGED_IN
    if _BS_LOGGED_IN: return
    with _BAOSTOCK_LOCK:
        if _BS_LOGGED_IN: return
        try:
            import baostock as bs
            bs.login()
            _BS_LOGGED_IN = True
            app.logger.info("baostock 已登录（进程级）")
        except Exception as e:
            app.logger.warning(f"baostock 登录失败: {e}")

@_atexit.register
def _bs_logout_on_exit():
    try:
        import baostock as bs
        bs.logout()
    except Exception as e:  # S3-B1: 裸 except 补 log（Hunt3-M1）
        app.logger.debug(f"baostock logout 失败（进程退出，可忽略）: {e}")

@app.route('/api/stock_profile', methods=['GET'])
@with_cache(60)  # S2-A3: 半实时 1分钟缓存
@validate_schema(StockProfileSchema)  # S3-C4: marshmallow schema 前置校验
def api_stock_profile():
    # Input: stock_code query param（S2-A1 + S3-C4 schema 校验）
    # Output: JSON profile (industry/pe_ttm/pb/roe) or 503 on timeout
    # Pos: baostock I/O 重路径，外层 ThreadPoolExecutor 兜底确保 ≤25s 必返回
    import baostock as bs
    from datetime import datetime, timedelta
    import time as _time
    from concurrent.futures import ThreadPoolExecutor as _TPE, TimeoutError as _TPETimeout

    stock_code = validate_stock_code_strict(request.args.get('stock_code', ''))  # S2-A1

    # 命中短缓存（主线程快速返回,不进入任何 I/O）
    now = _time.time()
    cached = _profile_cache_get(stock_code)
    if cached and (now - cached[0] < _PROFILE_CACHE_TTL_S):
        return custom_jsonify(cached[1])

    # 名称：只读后台预热缓存，不在请求线程触发全量加载（避免首发最多15s阻塞），
    # 也不走analyzer.get_stock_info（该函数在eastmoney阻断时会60s超时）；
    # B2 2026-06-15：缺名 name=None（不回填 code），前端按占位处理
    with _STOCK_NAME_CACHE_LOCK:
        name = _STOCK_NAME_CACHE.get(stock_code)
    # baostock需要 sh./sz. 前缀
    prefix = 'sh.' if stock_code.startswith('6') else 'sz.'
    bs_code = prefix + stock_code

    # B16 辅助函数：用 akshare 多端点并行补齐 baostock 缺失的字段
    def _akshare_fill(prof: dict, fields: list, budget_s: float) -> None:
        """B12 兜底：用 akshare 多端点并行补齐 baostock 缺失的字段

        端点选型（2026-05-19 实测可用）：
          xq  → stock_individual_spot_xq(symbol='SH{code}')，提供 市盈率(TTM)/市净率/流通值
          fa  → stock_financial_abstract(symbol=code)，提供 ROE
          industry 暂时从 xq 无法获取，保持 None 供上游决策

        Args:
            prof: 待填充的 profile dict（原地修改）
            fields: 待填充的字段名列表
            budget_s: 总时间预算（秒）
        """
        import akshare as ak
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 雪球 symbol 格式：SH/SZ + 6位代码
        xq_symbol = ('SH' if stock_code.startswith('6') else 'SZ') + stock_code

        tasks = {}
        pool = get_global_thread_pool()  # BD-3: 使用全局池
        try:
            need_xq = any(k in fields for k in ('pe_ttm', 'pb', 'market_cap'))
            need_fa = 'roe' in fields

            if need_xq:
                tasks[pool.submit(ak.stock_individual_spot_xq, symbol=xq_symbol)] = 'xq'
            if need_fa:
                tasks[pool.submit(ak.stock_financial_abstract, symbol=stock_code)] = 'fa'

            for fut in as_completed(list(tasks.keys()), timeout=budget_s):
                tag = tasks[fut]
                try:
                    df = fut.result()
                    if df is None or len(df) == 0:
                        continue
                    if tag == 'xq':
                        # 长表：第0列为指标名，第1列为值
                        lookup = dict(zip(df.iloc[:, 0].astype(str), df.iloc[:, 1]))
                        if prof.get('pe_ttm') is None:
                            raw = lookup.get('市盈率(TTM)')
                            if raw is not None:
                                try:
                                    prof['pe_ttm'] = float(raw)
                                except (ValueError, TypeError):
                                    pass
                        if prof.get('pb') is None:
                            raw = lookup.get('市净率')
                            if raw is not None:
                                try:
                                    prof['pb'] = float(raw)
                                except (ValueError, TypeError):
                                    pass
                        if prof.get('market_cap') is None:
                            # 流通值 单位为元，转亿元
                            raw = lookup.get('流通值') or lookup.get('资产净值/总市值')
                            if raw is not None:
                                try:
                                    prof['market_cap'] = float(raw) / 1e8
                                except (ValueError, TypeError):
                                    pass
                    elif tag == 'fa':
                        # stock_financial_abstract: 列为 ['选项', '指标', 日期1, 日期2, ...]
                        if prof.get('roe') is None and len(df.columns) > 2:
                            try:
                                for _, row in df.iterrows():
                                    indicator_name = str(row.iloc[1]) if len(row) > 1 else ''
                                    if '净资产收益率' in indicator_name or 'ROE' in indicator_name.upper():
                                        # 从最近日期列向前找非空值（列索引2起）
                                        for col_idx in range(2, len(row)):
                                            val = row.iloc[col_idx]
                                            if val is not None and str(val) not in ('', 'nan', 'None', '--'):
                                                try:
                                                    prof['roe'] = float(val)
                                                    break
                                                except (ValueError, TypeError):
                                                    continue
                                        break
                            except Exception:
                                pass
                except Exception as e:
                    app.logger.warning(f"_akshare_fill {tag} 失败 ({stock_code}): {type(e).__name__}: {e}")
        except TimeoutError:
            app.logger.warning(f"_akshare_fill 总超时 {budget_s}s ({stock_code})")
        # BD-3: 全局池不 shutdown

    # 2026-05-19 B10-FIX：
    # 根因：原实现 _ensure_bs_login() 在主 Flask 线程调用（bs.login() 可阻塞 10-30s），
    #       随后 _BAOSTOCK_LOCK.acquire(timeout=15) 在主线程同步等待锁（最多再加 15s），
    #       两段合计可达 35s+，导致请求 hang。
    # 修复：将 _ensure_bs_login() + lock acquire + 全部 baostock I/O 全部放入子线程，
    #       外层 future.result(timeout=PROFILE_BAOSTOCK_TIMEOUT_S, default=8) 是唯一 hard deadline，
    #       主 Flask 线程最多等 8s，超时后走 akshare-only fallback。
    def _do_all_baostock():
        _local_profile = {
            'stock_code': stock_code, 'stock_name': name,
            'industry': None, 'market_cap': None, 'pe_ttm': None, 'pb': None, 'roe': None
        }
        # --- login（含网络阻塞风险，必须在子线程里）---
        _ensure_bs_login()

        # --- 获取锁（最多等 18s，给外层 22s timeout 留 4s 余量）---
        if not _BAOSTOCK_LOCK.acquire(timeout=18):
            app.logger.warning(f"stock_profile lock acquire timeout 18s ({stock_code})，返回基础数据")
            return _local_profile

        try:
            # 行业
            try:
                rs = bs.query_stock_industry(code=bs_code)
                rows = []
                while rs.error_code == '0' and rs.next():
                    rows.append(rs.get_row_data())
                if rows:
                    _local_profile['industry'] = rows[0][3] if len(rows[0]) > 3 else None
            except Exception as e:
                app.logger.warning(f"baostock industry失败({stock_code}): {e}")

            # PE/PB/close — 取最近可用交易日（baostock数据有2-3天滞后，向前扩展120天）
            try:
                end = now_cn().strftime('%Y-%m-%d')
                start = (now_cn() - timedelta(days=120)).strftime('%Y-%m-%d')
                rs = bs.query_history_k_data_plus(bs_code,
                    'date,code,open,high,low,close,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST',
                    start_date=start, end_date=end, frequency='d', adjustflag='3')
                rows = []
                while rs.error_code == '0' and rs.next():
                    rows.append(rs.get_row_data())
                if rows:
                    last = rows[-1]
                    # 字段索引：5=close, 12=peTTM, 13=pbMRQ
                    def _f(i):
                        try:
                            return float(last[i]) if last[i] else None
                        except (ValueError, TypeError, IndexError):
                            return None
                    _local_profile['pe_ttm'] = _f(12)
                    _local_profile['pb'] = _f(13)
                    close = _f(5)
                    # market_cap 需要total_share，query_stock_basic 不含该字段，暂留close
                    if close:
                        try:
                            bs.query_stock_basic(code=bs_code)
                        except Exception as e:  # S3-B1: 裸 except 补 log（Hunt3-M1）
                            app.logger.debug(f"baostock query_stock_basic({bs_code}) 忽略（仅试探字段）: {e}")
            except Exception as e:
                app.logger.warning(f"baostock k_data失败({stock_code}): {e}")

            # ROE — 最近年报
            try:
                year = now_cn().year
                for y in [year - 1, year - 2]:
                    rs = bs.query_profit_data(code=bs_code, year=y, quarter=4)
                    rows = []
                    while rs.error_code == '0' and rs.next():
                        rows.append(rs.get_row_data())
                    if rows and len(rows[0]) > 3 and rows[0][3]:
                        _local_profile['roe'] = float(rows[0][3]) * 100  # baostock roeAvg 为小数
                        break
            except Exception as e:
                app.logger.warning(f"baostock profit失败({stock_code}): {e}")
        finally:
            _BAOSTOCK_LOCK.release()

        # B12 兜底：baostock 部分字段缺失时用 akshare 补齐
        _missing = [k for k in ('industry', 'pe_ttm', 'pb', 'roe', 'market_cap') if _local_profile.get(k) is None]
        if _missing:
            try:
                _akshare_fill(_local_profile, _missing, budget_s=5.0)
            except Exception as _e:
                app.logger.warning(f"_akshare_fill 异常 ({stock_code}): {_e}")

        return _local_profile

    # 外层 executor：主 Flask 线程最多阻塞 22s，超时 → 503
    # BD-3: 改用全局线程池
    try:
        fut = _GLOBAL_THREAD_POOL.submit(_do_all_baostock)
        try:
            profile = fut.result(timeout=int(os.getenv('PROFILE_BAOSTOCK_TIMEOUT_S', '8')))
        except (_TPETimeout, TimeoutError) as _toe:
            app.logger.warning(f"baostock overall_timeout ({stock_code})，进入 akshare-only 兜底")
            _fb = {
                'stock_code': stock_code,
                'stock_name': _STOCK_NAME_CACHE.get(stock_code),  # B2: 缺名返回 None，不回填 code
                'industry': None, 'market_cap': None,
                'pe_ttm': None, 'pb': None, 'roe': None,
            }
            try:
                _akshare_fill(_fb, ['industry', 'market_cap', 'pe_ttm', 'pb', 'roe'], budget_s=6.0)
            except Exception as _e:
                app.logger.warning(f"akshare-only 兜底失败 ({stock_code}): {_e}")

            if any(_fb.get(k) is not None for k in ('industry', 'pe_ttm', 'pb', 'roe')):
                resp = custom_jsonify(_fb)
                resp.headers['X-Data-Source'] = 'akshare-fallback'
                return resp

            # akshare 也失败 → 尝试 stale cache
            _stale = _profile_cache_get(stock_code)
            if _stale:
                _stale_ts, _stale_data = _stale if isinstance(_stale, tuple) else (0, _stale)
                if (_time.time() - _stale_ts) < _PROFILE_STALE_MAX_S:
                    resp = custom_jsonify(_stale_data)
                    resp.headers['X-Cache'] = 'stale'
                    resp.headers['X-Data-Source'] = 'cache-stale'
                    return resp

            return custom_jsonify({
                'error': 'all_sources_failed',
                'reason': 'baostock_timeout + akshare_fallback_failed',
                'stock_code': stock_code
            }), 503
        except Exception as e:
            app.logger.error(f"api_stock_profile 子线程异常 ({stock_code}): {e}")
            return custom_jsonify({'error': 'internal_error', 'detail': str(e)}), 500
    finally:
        _outer_pool.shutdown(wait=False, cancel_futures=True)

    # 淘汰过期条目并写入（S1-C3 原子操作，整体在锁内）
    now2 = _time.time()
    _profile_cache_evict_and_set(stock_code, (now2, profile), _PROFILE_CACHE_TTL_S)
    return custom_jsonify(profile)


# 轻量名称查询接口 — 直接走A股预加载缓存，避免analyzer.get_stock_info在eastmoney阻断时60s超时
@app.route('/api/stock_name', methods=['GET'])
@validate_schema(StockNameSchema)  # S3-D3: schema 校验扩展
def api_stock_name():
    stock_code = request.args.get('stock_code', '')
    if not stock_code:
        return custom_jsonify({'error': 'stock_code required'}), 400
    try:
        # 只读后台预热缓存，不在请求线程触发全量加载（避免首发最多15s阻塞）
        # B2 2026-06-15：缺名返回 stock_name=None（JSON null），不再回填 code，
        # 让前端区分"无名"与"真名"并按占位处理（与前端 B1 守卫配套）。
        with _STOCK_NAME_CACHE_LOCK:
            name = _STOCK_NAME_CACHE.get(stock_code)
        return custom_jsonify({'stock_code': stock_code, 'stock_name': name})
    except Exception as e:
        app.logger.error(f"获取股票名称出错 {stock_code}: {e}")
        return custom_jsonify({'stock_code': stock_code, 'stock_name': None})


# 股票名称反查接口 — 根据名称关键词搜索代码（FE意图路由用）
@app.route('/api/stock_name_search', methods=['GET'])
@validate_schema(StockNameSearchSchema, extra_error_fields={'results': []})  # S3-D3: schema 校验扩展
def api_stock_name_search():
    q = (request.args.get('q') or '').strip()
    if not q:
        return custom_jsonify({'error': 'q required', 'results': []}), 400
    try:
        # 只读后台预热缓存，不在请求线程触发全量加载（避免首发最多15s阻塞）
        exact = []
        prefix = []
        contains = []
        with _STOCK_NAME_CACHE_LOCK:
            _cache_snapshot = dict(_STOCK_NAME_CACHE)
        for code, name in _cache_snapshot.items():
            if name == q:
                exact.append({'stock_code': code, 'stock_name': name})
            elif name.startswith(q):
                prefix.append({'stock_code': code, 'stock_name': name})
            elif q in name:
                contains.append({'stock_code': code, 'stock_name': name})
            if len(exact) + len(prefix) >= 10:
                break
        results = (exact + prefix + contains)[:10]
        return custom_jsonify({'query': q, 'results': results, 'count': len(results)})
    except Exception as e:
        app.logger.error(f"stock_name_search 出错 q={q}: {e}")
        return custom_jsonify({'query': q, 'results': [], 'error': str(e)}), 500


# @app.route('/api/market_scan', methods=['POST'])
# def api_market_scan():
#     try:
#         data = request.json
#         stock_list = data.get('stock_list', [])
#         min_score = data.get('min_score', 60)
#         market_type = data.get('market_type', 'A')

#         if not stock_list:
#             return jsonify({'error': '请提供股票列表'}), 400

#         # 限制股票数量，避免过长处理时间
#         if len(stock_list) > 100:
#             app.logger.warning(f"股票列表过长 ({len(stock_list)}只)，截取前100只")
#             stock_list = stock_list[:100]

#         # 执行市场扫描
#         app.logger.info(f"开始扫描 {len(stock_list)} 只股票，最低分数: {min_score}")

#         # 使用线程池优化处理
#         results = []
#         max_workers = min(10, len(stock_list))  # 最多10个工作线程

#         # 设置较长的超时时间
#         timeout = 300  # 5分钟

#         def scan_thread():
#             try:
#                 return analyzer.scan_market(stock_list, min_score, market_type)
#             except Exception as e:
#                 app.logger.error(f"扫描线程出错: {str(e)}")
#                 return []

#         thread = threading.Thread(target=lambda: results.append(scan_thread()))
#         thread.start()
#         thread.join(timeout)

#         if thread.is_alive():
#             app.logger.error(f"市场扫描超时，已扫描 {len(stock_list)} 只股票超过 {timeout} 秒")
#             return custom_jsonify({'error': '扫描超时，请减少股票数量或稍后再试'}), 504

#         if not results or not results[0]:
#             app.logger.warning("扫描结果为空")
#             return custom_jsonify({'results': []})

#         scan_results = results[0]
#         app.logger.info(f"扫描完成，找到 {len(scan_results)} 只符合条件的股票")

#         # 使用自定义JSON格式处理NumPy数据类型
#         return custom_jsonify({'results': scan_results})
#     except Exception as e:
#         app.logger.error(f"执行市场扫描时出错: {traceback.format_exc()}")
#         return custom_jsonify({'error': str(e)}), 500

@app.route('/api/start_market_scan', methods=['POST'])
@validate_schema(StartMarketScanSchema, source='json')  # S3-G1: schema 校验扩展
def start_market_scan():
    """启动市场扫描任务"""
    try:
        data = request.json
        stock_list = data.get('stock_list', [])
        min_score = data.get('min_score', 60)
        market_type = data.get('market_type', 'A')

        if not stock_list:
            return jsonify({'error': '请提供股票列表'}), 400

        # 限制股票数量，避免过长处理时间
        if len(stock_list) > 100:
            app.logger.warning(f"股票列表过长 ({len(stock_list)}只)，截取前100只")
            stock_list = stock_list[:100]

        # 创建新任务
        task_id = generate_task_id()
        task = {
            'id': task_id,
            'status': TASK_PENDING,
            'progress': 0,
            'total': len(stock_list),
            'created_at': now_cn().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': now_cn().strftime('%Y-%m-%d %H:%M:%S'),
            'params': {
                'stock_list': stock_list,
                'min_score': min_score,
                'market_type': market_type
            }
        }

        with task_lock:
            scan_tasks[task_id] = task

        # 启动后台线程执行扫描
        def run_scan():
            try:
                start_market_scan_task_status(task_id, TASK_RUNNING)

                # 执行分批处理
                results = []
                total = len(stock_list)
                batch_size = 10

                for i in range(0, total, batch_size):
                    if task_id not in scan_tasks or scan_tasks[task_id]['status'] != TASK_RUNNING:
                        # 任务被取消
                        app.logger.info(f"扫描任务 {task_id} 被取消")
                        return

                    batch = stock_list[i:i + batch_size]
                    batch_results = []

                    for stock_code in batch:
                        try:
                            report = analyzer.quick_analyze_stock(stock_code, market_type)
                            if report['score'] >= min_score:
                                batch_results.append(report)
                        except Exception as e:
                            app.logger.error(f"分析股票 {stock_code} 时出错: {str(e)}")
                            continue

                    results.extend(batch_results)

                    # 更新进度
                    progress = min(100, int((i + len(batch)) / total * 100))
                    start_market_scan_task_status(task_id, TASK_RUNNING, progress=progress)

                # 按得分排序
                results.sort(key=lambda x: x['score'], reverse=True)

                # 更新任务状态为完成
                start_market_scan_task_status(task_id, TASK_COMPLETED, progress=100, result=results)
                app.logger.info(f"扫描任务 {task_id} 完成，找到 {len(results)} 只符合条件的股票")

            except Exception as e:
                app.logger.error(f"扫描任务 {task_id} 失败: {str(e)}")
                app.logger.error(traceback.format_exc())
                start_market_scan_task_status(task_id, TASK_FAILED, error=str(e))

        # 启动后台线程
        thread = threading.Thread(target=run_scan)
        thread.daemon = True
        thread.start()

        return jsonify({
            'task_id': task_id,
            'status': 'pending',
            'message': f'已启动扫描任务，正在处理 {len(stock_list)} 只股票'
        })

    except Exception as e:
        app.logger.error(f"启动市场扫描任务时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '启动市场扫描任务失败，请稍后重试', details=str(e))


@app.route('/api/scan_status/<task_id>', methods=['GET'])
@validate_schema(ScanStatusSchema)  # S3-J(A): schema 校验扩展
def get_scan_status(task_id):
    """获取扫描任务状态"""
    with task_lock:
        if task_id not in scan_tasks:
            return jsonify({'error': '找不到指定的扫描任务'}), 404

        task = scan_tasks[task_id]

        # 基本状态信息
        status = {
            'id': task['id'],
            'status': task['status'],
            'progress': task.get('progress', 0),
            'total': task.get('total', 0),
            'created_at': task['created_at'],
            'updated_at': task['updated_at']
        }

        # 如果任务完成，包含结果
        if task['status'] == TASK_COMPLETED and 'result' in task:
            status['result'] = task['result']

        # 如果任务失败，包含错误信息
        if task['status'] == TASK_FAILED and 'error' in task:
            status['error'] = task['error']

        return custom_jsonify(status)


@app.route('/api/cancel_scan/<task_id>', methods=['POST'])
@validate_schema(CancelScanSchema, source='json')  # S3-J(A): schema 校验扩展
def cancel_scan(task_id):
    """取消扫描任务"""
    with task_lock:
        if task_id not in scan_tasks:
            return jsonify({'error': '找不到指定的扫描任务'}), 404

        task = scan_tasks[task_id]

        if task['status'] in [TASK_COMPLETED, TASK_FAILED]:
            return jsonify({'message': '任务已完成或失败，无法取消'})

        # 更新状态为失败
        task['status'] = TASK_FAILED
        task['error'] = '用户取消任务'
        task['updated_at'] = now_cn().strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({'message': '任务已取消'})


# --- M1/M2: 实时指数内存缓存（避免每次请求都调 akshare）---
_market_indices_cache: dict = {}  # {'data': {...}, 'ts': float, 'source': str}
# B23: 并发保护锁——同时只允许一个线程调 akshare，其他请求等待缓存填充后直接读取
# 避免多个并发请求（prefetch + React fetchIndices）同时触发 akshare 导致 16s 延迟
_market_indices_lock: threading.Lock = threading.Lock()

def _fetch_market_indices_data():
    """内部函数：获取主要市场指数数据（上证/深证/创业板/沪深300），供API和SSE共用。
    Input: 无
    Output: {'indices': [...], 'source': str}
    Pos: 实时指数三级兜底链（东财→新浪→日线），30s 内存缓存
    B23: 加 _market_indices_lock 防止并发竞争 akshare（双重检查锁定模式）
    """
    import akshare as ak
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    _PRIMARY_TIMEOUT = int(os.getenv('INDEX_PRIMARY_TIMEOUT_S', '5'))
    _FALLBACK_TIMEOUT = int(os.getenv('INDEX_FALLBACK_TIMEOUT_S', '15'))  # 新浪约 9s
    _CACHE_TTL = int(os.getenv('INDEX_CACHE_TTL_S', '30'))

    # 快路径：无锁检查缓存
    _cache = _market_indices_cache
    if _cache.get('data') and (time.time() - _cache.get('ts', 0)) < _CACHE_TTL:
        cached = dict(_cache['data'])
        cached['source'] = 'cache'
        return cached

    # B23: 加锁，同时只允许一个线程调 akshare；其余线程在锁内二次检查缓存后直接返回
    # 防止多个并发请求（prefetch + React fetchIndices）竞争 akshare 导致 16s 延迟
    with _market_indices_lock:
        # 二次检查缓存（可能等锁期间其他线程已填充）
        if _cache.get('data') and (time.time() - _cache.get('ts', 0)) < _CACHE_TTL:
            cached = dict(_cache['data'])
            cached['source'] = 'cache'
            return cached

        # --- 主路径: 东财 stock_zh_index_spot_em(symbol="沪深重要指数") ---
        # H1: 必须传 symbol；四目标码未齐时不当完整 HIT，继续 sina/daily 兜底或合并补齐
        _INDEX_TARGET_CODES = ['000001', '399001', '399006', '000300']

        def _try_eastmoney():
            df = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
            result = []
            for code in _INDEX_TARGET_CODES:
                row = df[df['代码'] == code]
                if not row.empty:
                    r = row.iloc[0]
                    result.append({
                        'name': str(r['名称']),
                        'code': code,
                        'price': quantize_finance(r['最新价'], 4),
                        'change_pct': quantize_finance(r['涨跌幅'], 2)
                    })
            return result

        em_partial = None  # 东财部分命中，供后续合并
        # BD-3: 改用全局线程池
        fut = _GLOBAL_THREAD_POOL.submit(_try_eastmoney)
        try:
            result = fut.result(timeout=_PRIMARY_TIMEOUT)
            if result and len(result) >= len(_INDEX_TARGET_CODES):
                data = {'indices': result, 'timestamp': now_cn().isoformat()}
                _market_indices_cache.update({'data': data, 'ts': time.time(), 'source': 'eastmoney'})
                data['source'] = 'eastmoney'
                return data
            if result:
                em_partial = result
                app.logger.warning(
                    f"实时指数主路径仅命中 {len(result)}/{len(_INDEX_TARGET_CODES)}，不当完整 HIT，切兜底补齐"
                )
        except FuturesTimeout:
            app.logger.warning(f"实时指数主路径超时({_PRIMARY_TIMEOUT}s): eastmoney push2, 切兜底")
        except Exception as e:
            app.logger.warning(f"实时指数接口失败: {e}, 切兜底")

        # --- 兜底1: 新浪 stock_zh_index_spot_sina ---
        def _try_sina():
            df = ak.stock_zh_index_spot_sina()
            # 新浪代码格式: sh000001 / sz399001
            sina_map = {
                'sh000001': ('000001', '上证指数'),
                'sz399001': ('399001', '深证成指'),
                'sz399006': ('399006', '创业板指'),
                'sh000300': ('000300', '沪深300'),
            }
            result = []
            for sina_code, (code, name) in sina_map.items():
                row = df[df['代码'] == sina_code]
                if not row.empty:
                    r = row.iloc[0]
                    result.append({
                        'name': str(r['名称']) if '名称' in r.index else name,
                        'code': code,
                        'price': quantize_finance(r['最新价'], 4),
                        'change_pct': quantize_finance(r['涨跌幅'], 2)
                    })
            return result

        def _merge_indices(primary, secondary):
            """按 code 合并指数列表：secondary 补齐 primary 缺失项。"""
            by_code = {}
            for item in (primary or []):
                if item and item.get('code'):
                    by_code[item['code']] = item
            for item in (secondary or []):
                if item and item.get('code') and item['code'] not in by_code:
                    by_code[item['code']] = item
            order = _INDEX_TARGET_CODES
            ordered = [by_code[c] for c in order if c in by_code]
            # 附加非目标码（一般不会有）
            for c, item in by_code.items():
                if c not in order:
                    ordered.append(item)
            return ordered

        # BD-3: 改用全局线程池
        fut = _GLOBAL_THREAD_POOL.submit(_try_sina)
        try:
            result = fut.result(timeout=_FALLBACK_TIMEOUT)
            if em_partial:
                result = _merge_indices(em_partial, result or [])
            if result and len(result) >= len(_INDEX_TARGET_CODES):
                data = {'indices': result, 'timestamp': now_cn().isoformat()}
                src = 'eastmoney+sina' if em_partial else 'sina'
                _market_indices_cache.update({'data': data, 'ts': time.time(), 'source': src})
                data['source'] = src
                return data
            if result:
                # 仍不齐则继续 daily，携带部分结果合并
                em_partial = result
        except FuturesTimeout:
            app.logger.warning(f"实时指数兜底1(新浪)超时({_FALLBACK_TIMEOUT}s), 切日线")
        except Exception as e:
            app.logger.warning(f"实时指数兜底1(新浪)失败: {e}, 切日线")

        # --- 兜底2: 历史日线最后一条（4 路并发，减少串行等待）---
        try:
            indices_config = [
                ('sh000001', '上证指数'),
                ('sz399001', '深证成指'),
                ('sz399006', '创业板指'),
                ('sh000300', '沪深300'),
            ]

            def _fetch_one_daily(args):
                symbol, name = args
                try:
                    df = ak.stock_zh_index_daily(symbol=symbol)
                    if df is not None and len(df) >= 2:
                        latest = df.iloc[-1]
                        prev = df.iloc[-2]
                        price = quantize_finance(latest['close'], 4)
                        change_pct = safe_change_pct(latest['close'], prev['close'])
                        return {'name': name, 'code': symbol[2:], 'price': price, 'change_pct': change_pct}
                except Exception:
                    pass
                return None

            # BD-3: 改用全局线程池（max_workers=4 的并发需求由全局池承载）
            items = []
            futs = [_GLOBAL_THREAD_POOL.submit(_fetch_one_daily, cfg) for cfg in indices_config]
            for fut in futs:
                try:
                    items.append(fut.result(timeout=12))
                except Exception:
                    items.append(None)
            result = [x for x in items if x]
            if em_partial:
                result = _merge_indices(em_partial, result or [])

            if result:
                data = {'indices': result, 'timestamp': now_cn().isoformat()}
                src = 'merged_daily' if em_partial else 'daily'
                _market_indices_cache.update({'data': data, 'ts': time.time(), 'source': src})
                data['source'] = src
                return data
        except Exception as e:
            app.logger.error(f"历史指数数据也失败: {e}")

        # --- 兜底3: 返回已有缓存（无论是否过期）；部分结果不当完整 HIT 缓存 ---
        if _market_indices_cache.get('data'):
            app.logger.warning("所有指数来源均失败，返回过期缓存")
            stale = dict(_market_indices_cache['data'])
            stale['source'] = 'stale_cache'
            return stale

        # 仅有残缺部分结果：返回但不写 cache（避免假 HIT）
        if em_partial:
            return {'indices': em_partial, 'source': 'partial', 'timestamp': now_cn().isoformat()}

        return {'indices': [], 'source': 'degraded'}


@app.route('/api/market_indices', methods=['GET'])
@with_cache(5)  # S2-A3: 实时类 5秒短缓存
@validate_schema(MarketIndicesSchema)  # S3-C4: marshmallow schema 前置校验
def get_market_indices():
    """获取主要市场指数实时行情（上证/深证/创业板/沪深300）
    Input: 无（S3-C4 schema 校验，可选 refresh=bool）
    Output: JSON {'indices': [...], 'source': str}
    Pos: 首页/Dashboard 实时指数端点，三级兜底链，S2-A3 5s 缓存 header
    B23: 添加快速超时路径（FAST_TIMEOUT_MS env）——缓存为空时先返回 degraded，
    避免 Playwright / 浏览器首屏在 loading 状态卡住
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    # 快速超时（默认 1.5s）——缓存命中时忽略超时，直接返回
    _fast_ms = int(os.getenv('INDEX_FAST_TIMEOUT_MS', '1500'))

    # 快路径：缓存命中时跳过 ThreadPoolExecutor 开销
    _cache = _market_indices_cache
    if _cache.get('data') and (time.time() - _cache.get('ts', 0)) < int(os.getenv('INDEX_CACHE_TTL_S', '30')):
        cached = dict(_cache['data'])
        cached['source'] = 'cache'
        data = cached
    else:
        # 慢路径：在线程池里调用，限时 _fast_ms
        # BD-3: 改用全局线程池
        fut = _GLOBAL_THREAD_POOL.submit(_fetch_market_indices_data)
        _timed_out = False
        try:
            data = fut.result(timeout=_fast_ms / 1000)
        except FuturesTimeout:
            # 全局池不需要手动 shutdown，只取消 future
            _timed_out = True
            fut.cancel()
            app.logger.warning(f"get_market_indices 快速超时 {_fast_ms}ms，返回 degraded")
            data = {'indices': [], 'source': 'degraded'}

    source = data.get('source', 'unknown')

    # B2-4: 标注行情时效性
    _dq_map = {
        'cache':       'cached_30s',
        'eastmoney':   'realtime',
        'sina':        'realtime',
        'daily':       'delayed_15min',
        'stale_cache': 'stale_cache',
        'degraded':    'stale_cache',
    }
    data_quality = _dq_map.get(source, 'unknown')
    data.setdefault('meta', {})['data_quality'] = data_quality

    # B2-5: 完全 degraded 时返回 503（无任何有效数据）
    if source == 'degraded' and not data.get('indices'):
        resp = jsonify({'success': False, 'error_code': 'DEGRADED',
                        'message': '所有上游数据源均不可用', 'meta': {'data_quality': 'stale_cache'}})
        resp.status_code = 503
        resp.headers['X-Data-Source'] = source
        resp.headers['X-Cache'] = 'DEGRADED'
        return resp

    resp = jsonify(data)
    resp.headers['X-Data-Source'] = source
    if source == 'cache':
        resp.headers['X-Cache'] = 'HIT'
    elif source in ('degraded', 'stale_cache'):
        resp.headers['X-Cache'] = 'DEGRADED'
    else:
        resp.headers['X-Cache'] = 'MISS'
    return resp


@app.route('/api/market_stream')
@validate_schema(MarketStreamSchema)  # BD-7: schema 覆盖率提升
def market_stream():
    """SSE端点：每10秒推送一次市场指数实时数据流"""
    from flask import Response

    def generate():
        try:
            while True:
                try:
                    data = _fetch_market_indices_data()
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except Exception:
                    yield f"data: {json.dumps({'indices': []})}\n\n"
                time.sleep(10)
        except GeneratorExit:
            # 客户端断开SSE连接，优雅退出
            app.logger.debug("市场数据SSE连接已断开")
        except Exception as e:
            app.logger.warning(f"市场数据SSE流异常退出: {e}")

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


@app.route('/api/index_stocks', methods=['GET'])
@validate_schema(IndexStocksSchema)  # S3-G1: schema 校验扩展
def get_index_stocks():
    """获取指数成分股 - 使用DataProvider统一数据层"""
    try:
        from app.core.data_provider import get_data_provider
        data_provider = get_data_provider()
        index_code = request.args.get('index_code', '000300')  # 默认沪深300

        # 获取指数成分股
        app.logger.info(f"获取指数 {index_code} 成分股")
        if index_code not in ['000300', '000905', '000852', '000001']:
            return jsonify({'error': '不支持的指数代码'}), 400

        stock_list = data_provider.get_index_stocks(index_code)
        app.logger.info(f"找到 {len(stock_list)} 只成分股")

        return jsonify({'stock_list': stock_list})
    except Exception as e:
        app.logger.error(f"获取指数成分股时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取指数成分股失败，请稍后重试', details=str(e))


@app.route('/api/industry_stocks', methods=['GET'])
@validate_schema(IndustryStocksSchema)  # S3-G1: schema 校验扩展
def get_industry_stocks():
    """获取行业成分股 - 使用DataProvider统一数据层"""
    try:
        from app.core.data_provider import get_data_provider
        data_provider = get_data_provider()
        industry = request.args.get('industry', '')

        if not industry:
            return jsonify({'error': '请提供行业名称'}), 400

        # 获取行业成分股
        app.logger.info(f"获取 {industry} 行业成分股")
        stock_list = data_provider.get_industry_stocks(industry)
        app.logger.info(f"找到 {len(stock_list)} 只 {industry} 行业股票")

        return jsonify({'stock_list': stock_list})
    except Exception as e:
        app.logger.error(f"获取行业成分股时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取行业成分股失败，请稍后重试', details=str(e))


# Issue #29: 按板块获取股票列表（科创板/创业板/北交所等）
@app.route('/api/board_stocks', methods=['GET'])
@validate_schema(BoardStocksSchema)  # S3-G1: schema 校验扩展
def get_board_stocks():
    """获取指定板块的股票列表 - 使用DataProvider统一数据层"""
    try:
        from app.core.data_provider import get_data_provider
        data_provider = get_data_provider()
        board = request.args.get('board', 'hs300')

        # 板块映射
        board_map = {
            'hs300': ('000300', '沪深300'),
            'zz500': ('000905', '中证500'),
            'zz1000': ('000852', '中证1000'),
            'kc50': ('000688', '科创50'),
            'kc100': ('000698', '科创100'),
            'bj50': ('899050', '北证50'),
        }

        if board not in board_map:
            return jsonify({'error': f'不支持的板块类型: {board}，支持: {list(board_map.keys())}'}), 400

        index_code, index_name = board_map[board]
        app.logger.info(f"获取 {index_name}({index_code}) 成分股列表")

        stock_list = data_provider.get_index_stocks(index_code)
        app.logger.info(f"找到 {len(stock_list)} 只 {index_name} 成分股")

        return jsonify({'stock_list': stock_list, 'count': len(stock_list), 'index_name': index_name})
    except Exception as e:
        app.logger.error(f"获取板块股票时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取板块股票失败，请稍后重试', details=str(e))


# 添加到web_server.py
def clean_old_tasks():
    """清理旧的扫描任务"""
    with task_lock:
        # 使用 naive datetime 以匹配 strptime 解析的 updated_at 字符串（无时区）
        now = datetime.now()
        to_delete = []

        for task_id, task in scan_tasks.items():
            # 解析更新时间
            try:
                updated_at = datetime.strptime(task['updated_at'], '%Y-%m-%d %H:%M:%S')
                # 如果任务完成或失败且超过1小时，或者任务状态异常且超过3小时，清理它
                if ((task['status'] in [TASK_COMPLETED, TASK_FAILED] and
                     (now - updated_at).total_seconds() > 3600) or
                        ((now - updated_at).total_seconds() > 10800)):
                    to_delete.append(task_id)
            except (ValueError, KeyError) as e:
                # 日期解析错误或缺失字段，添加到删除列表
                logger.warning(f"任务 {task_id} 解析失败: {e}")
                to_delete.append(task_id)

        # 删除旧任务
        for task_id in to_delete:
            del scan_tasks[task_id]
        deleted_count = len(to_delete)

        # 同步清理 tasks 字典中的过期条目
        for task_type in tasks:
            store = tasks[task_type]
            expired = []
            for tid, t in store.items():
                try:
                    t_updated = datetime.strptime(t.get('updated_at', ''), '%Y-%m-%d %H:%M:%S')
                    if ((t.get('status') in [TASK_COMPLETED, TASK_FAILED] and
                         (now - t_updated).total_seconds() > 1800) or
                            (now - t_updated).total_seconds() > 7200):
                        expired.append(tid)
                except Exception:
                    expired.append(tid)
            for tid in expired:
                del store[tid]
            deleted_count += len(expired)

        return deleted_count


# 修改 run_task_cleaner 函数，使其每 5 分钟运行一次并在 16:30 左右清理所有缓存
def run_task_cleaner():
    """定期运行任务清理，并在每天 16:30 左右清理所有缓存"""
    while True:
        try:
            now = now_cn()
            # 判断是否在收盘时间附近（16:25-16:35）
            is_market_close_time = (now.hour == 16 and 25 <= now.minute <= 35)

            cleaned = clean_old_tasks()

            # 如果是收盘时间，清理所有缓存
            if is_market_close_time:
                # 清理分析器的数据缓存
                analyzer.data_cache.clear()

                # 清理 Flask 缓存
                cache.clear()

                # 清理任务存储
                with task_lock:
                    for task_type in tasks:
                        task_store = tasks[task_type]
                        completed_tasks = [task_id for task_id, task in task_store.items()
                                           if task['status'] == TASK_COMPLETED]
                        for task_id in completed_tasks:
                            del task_store[task_id]

                app.logger.info("市场收盘时间检测到，已清理所有缓存数据")

            if cleaned > 0:
                app.logger.info(f"清理了 {cleaned} 个旧的扫描任务")
        except Exception as e:
            app.logger.error(f"任务清理出错: {str(e)}")

        # 每 5 分钟运行一次，而不是每小时
        time.sleep(600)


# 基本面分析路由
@app.route('/api/fundamental_analysis', methods=['POST'])
@validate_schema(FundamentalAnalysisSchema, source='json')  # S3-E1: schema 校验扩展
def api_fundamental_analysis():
    try:
        data = request.json
        stock_code = data.get('stock_code')

        if not stock_code:
            return jsonify({'error': '请提供股票代码'}), 400

        valid, result = validate_stock_code(stock_code)
        if not valid:
            return jsonify({'error': result}), 400
        stock_code = result

        # 获取基本面分析结果
        result = fundamental_analyzer.calculate_fundamental_score(stock_code)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"基本面分析出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '基本面分析失败，请稍后重试', details=str(e))


# 资金流向分析路由
# Add to web_server.py

# 获取概念资金流向的API端点
@app.route('/api/concept_fund_flow', methods=['GET'])
@validate_schema(ConceptFundFlowSchema)  # S3-G1: schema 校验扩展
def api_concept_fund_flow():
    try:
        period = request.args.get('period', '10日排行')  # Default to 10-day ranking

        # Get concept fund flow data
        result = capital_flow_analyzer.get_concept_fund_flow(period)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"Error getting concept fund flow: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取概念资金流向失败，请稍后重试', details=str(e))


# 获取个股资金流向排名的API端点
@app.route('/api/individual_fund_flow_rank', methods=['GET'])
@validate_schema(IndividualFundFlowRankSchema)  # S3-G1: schema 校验扩展
def api_individual_fund_flow_rank():
    try:
        period = request.args.get('period', '10日')  # Default to today

        # Get individual fund flow ranking data
        # H2-4 统一返回契约：{'data': list, 'error': str|None, 'count': int}
        result = capital_flow_analyzer.get_individual_fund_flow_rank(period)
        result.setdefault('amount_unit', 'yuan')

        if result.get('error') is not None:
            return api_error('INTERNAL', '获取个股资金流向排名失败', details=result['error'])

        return api_ok(result)
    except Exception as e:
        app.logger.error(f"Error getting individual fund flow ranking: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取个股资金流向排名失败，请稍后重试', details=str(e))


# 获取个股资金流向的API端点
@app.route('/api/individual_fund_flow', methods=['GET'])
@validate_schema(IndividualFundFlowSchema)  # S3-E1: schema 校验扩展
def api_individual_fund_flow():
    try:
        stock_code = request.args.get('stock_code')
        market_type = request.args.get('market_type', '')  # Auto-detect if not provided
        re_date = request.args.get('period-select')

        if not stock_code:
            return api_error('INVALID_INPUT', 'Stock code is required')

        # Get individual fund flow data
        result = capital_flow_analyzer.get_individual_fund_flow(stock_code, market_type, re_date)
        result.setdefault('amount_unit', 'yuan')
        if isinstance(result.get('summary'), dict):
            result['summary'].setdefault('amount_unit', result['amount_unit'])
        # B2-5: 完全 degraded（无任何有效数据）→ HTTP 503
        if result.get('source') == 'degraded' and not result.get('data'):
            return jsonify({'success': False, 'error_code': 'DEGRADED',
                            'message': '资金流向数据源不可用', 'reason': result.get('reason', ''),
                            'amount_unit': result.get('amount_unit', 'yuan')}), 503
        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"Error getting individual fund flow: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取个股资金流向失败，请稍后重试', details=str(e))


# 获取板块内股票的API端点
@app.route('/api/sector_stocks', methods=['GET'])
@validate_schema(SectorStocksSchema)  # S3-E1: schema 校验扩展
def api_sector_stocks():
    try:
        sector = request.args.get('sector')

        if not sector:
            return api_error('INVALID_INPUT', 'Sector name is required')

        # Get sector stocks data
        result = capital_flow_analyzer.get_sector_stocks(sector)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"Error getting sector stocks: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取板块股票失败，请稍后重试', details=str(e))


# Update the existing capital flow API endpoint
@app.route('/api/capital_flow', methods=['POST'])
@validate_schema(CapitalFlowSchema, source='json')  # S3-E1: schema 校验扩展
def api_capital_flow():
    try:
        data = request.json
        stock_code = data.get('stock_code')
        market_type = data.get('market_type', '')  # Auto-detect if not provided

        if not stock_code:
            return api_error('INVALID_INPUT', 'Stock code is required')

        if market_type:
            valid, result = validate_stock_code(stock_code, market_type)
            if not valid:
                return api_error('INVALID_INPUT', result)
            stock_code = result

        # Calculate capital flow score
        result = capital_flow_analyzer.calculate_capital_flow_score(stock_code, market_type)
        # B2-5: 完全 degraded（无任何有效数据）→ HTTP 503
        if result.get('source') == 'degraded' and not result.get('data'):
            return jsonify({'success': False, 'error_code': 'DEGRADED',
                            'message': '资金流向评分数据源不可用', 'reason': result.get('reason', '')}), 503
        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"Error calculating capital flow score: {traceback.format_exc()}")
        return api_error('INTERNAL', '资金流向评分计算失败，请稍后重试', details=str(e))


# 情景预测路由
@app.route('/api/scenario_predict', methods=['POST'])
@validate_schema(ScenarioPredictSchema, source='json')  # S3-E1: schema 校验扩展
def api_scenario_predict():
    try:
        data = request.json
        stock_code = data.get('stock_code')
        market_type = data.get('market_type', 'A')
        days = data.get('days', 60)

        if not stock_code:
            return jsonify({'error': '请提供股票代码'}), 400

        valid, result = validate_stock_code(stock_code, market_type)
        if not valid:
            return jsonify({'error': result}), 400
        stock_code = result

        # 获取情景预测结果
        result = scenario_predictor.generate_scenarios(stock_code, market_type, days)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"情景预测出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '情景预测失败，请稍后重试', details=str(e))


# 智能问答路由
@app.route('/api/qa', methods=['POST'])
@validate_schema(QASchema, source='json')  # S3-E1: schema 校验扩展
def api_qa():
    try:
        data = request.json
        stock_code = data.get('stock_code')
        question = data.get('question')
        market_type = data.get('market_type', 'A')

        if not stock_code or not question:
            return jsonify({'error': '请提供股票代码和问题'}), 400

        valid, result = validate_stock_code(stock_code, market_type)
        if not valid:
            return jsonify({'error': result}), 400
        stock_code = result

        # 获取智能问答结果
        result = stock_qa.answer_question(stock_code, question, market_type)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"智能问答出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '智能问答失败，请稍后重试', details=str(e))


# 风险分析路由
@app.route('/api/risk_analysis', methods=['POST'])
@validate_schema(RiskAnalysisSchema, source='json')  # S3-E1: schema 校验扩展
def api_risk_analysis():
    try:
        data = request.json
        stock_code = data.get('stock_code')
        market_type = data.get('market_type', 'A')

        if not stock_code:
            return api_error('INVALID_INPUT', '请提供股票代码')

        valid, result = validate_stock_code(stock_code, market_type)
        if not valid:
            return api_error('INVALID_INPUT', result)
        stock_code = result

        # 获取风险分析结果
        result = risk_monitor.analyze_stock_risk(stock_code, market_type)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"风险分析出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '风险分析失败，请稍后重试', details=str(e))


# 投资组合风险分析路由
@app.route('/api/portfolio_risk', methods=['POST'])
@validate_schema(PortfolioRiskSchema, source='json')  # S3-E1: schema 校验扩展
def api_portfolio_risk():
    try:
        data = request.json
        portfolio = data.get('portfolio', [])

        if not portfolio:
            return jsonify({'error': '请提供投资组合'}), 400

        # 获取投资组合风险分析结果
        result = risk_monitor.analyze_portfolio_risk(portfolio)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"投资组合风险分析出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '组合风险分析失败，请稍后重试', details=str(e))


# 指数分析路由
@app.route('/api/index_analysis', methods=['GET'])
@validate_schema(IndexAnalysisSchema)  # S3-E1: schema 校验扩展
def api_index_analysis():
    try:
        index_code = request.args.get('index_code')
        limit = min(max(int(request.args.get('limit', 30)), 1), 500)

        if not index_code:
            return jsonify({'error': '请提供指数代码'}), 400

        # 获取指数分析结果
        result = index_industry_analyzer.analyze_index(index_code, limit)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"指数分析出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '指数分析失败，请稍后重试', details=str(e))


# 行业分析路由
@app.route('/api/industry_analysis', methods=['GET'])
@validate_schema(IndustryAnalysisApiSchema)  # S3-E1: schema 校验扩展
def api_industry_analysis():
    try:
        industry = request.args.get('industry')
        limit = min(max(int(request.args.get('limit', 30)), 1), 500)

        if not industry:
            return jsonify({'error': '请提供行业名称'}), 400

        # 获取行业分析结果
        result = index_industry_analyzer.analyze_industry(industry, limit)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"行业分析出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '行业分析失败，请稍后重试', details=str(e))


@app.route('/api/industry_fund_flow', methods=['GET'])
@validate_schema(IndustryFundFlowSchema)  # S3-E1: schema 校验扩展
def api_industry_fund_flow():
    """获取行业资金流向数据"""
    try:
        symbol = request.args.get('symbol', '即时')

        result = industry_analyzer.get_industry_fund_flow(symbol)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"获取行业资金流向数据出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取行业资金流向失败，请稍后重试', details=str(e))


@app.route('/api/industry_detail', methods=['GET'])
@validate_schema(IndustryDetailSchema)  # S3-D3: schema 校验扩展
def api_industry_detail():
    """获取行业详细信息"""
    try:
        industry = request.args.get('industry')

        if not industry:
            return jsonify({'error': '请提供行业名称'}), 400

        result = industry_analyzer.get_industry_detail(industry)

        app.logger.info(f"返回前 (result)：{result}")
        if not result:
            return jsonify({'error': f'未找到行业 {industry} 的详细信息'}), 404

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"获取行业详细信息出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取行业详情失败，请稍后重试', details=str(e))


# 行业比较路由
@app.route('/api/industry_compare', methods=['GET'])
@validate_schema(IndustryCompareSchema)  # S3-D3: schema 校验扩展
def api_industry_compare():
    try:
        limit = min(max(int(request.args.get('limit', 10)), 1), 500)

        # 获取行业比较结果
        result = index_industry_analyzer.compare_industries(limit)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"行业比较出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '行业对比失败，请稍后重试', details=str(e))


# 保存股票分析结果到数据库
def save_analysis_result(stock_code, market_type, result):
    """保存分析结果到数据库"""
    if not USE_DATABASE:
        return

    try:
        session = get_session()

        # 创建新的分析结果记录
        analysis = AnalysisResult(
            stock_code=stock_code,
            market_type=market_type,
            score=result.get('scores', {}).get('total', 0),
            recommendation=result.get('recommendation', {}).get('action', ''),
            technical_data=result.get('technical_analysis', {}),
            fundamental_data=result.get('fundamental_data', {}),
            capital_flow_data=result.get('capital_flow_data', {}),
            ai_analysis=result.get('ai_analysis', '')
        )

        session.add(analysis)
        session.commit()

    except Exception as e:
        app.logger.error(f"保存分析结果到数据库时出错: {str(e)}")
        if session:
            session.rollback()
    finally:
        if session:
            session.close()


# 从数据库获取历史分析结果
@app.route('/api/history_analysis', methods=['GET'])
@validate_schema(HistoryAnalysisSchema)  # S3-D3: schema 校验扩展
def get_history_analysis():
    """获取股票的历史分析结果"""
    if not USE_DATABASE:
        return jsonify({'error': '数据库功能未启用'}), 400

    stock_code = request.args.get('stock_code')
    limit = min(max(int(request.args.get('limit', 10)), 1), 500)

    if not stock_code:
        return jsonify({'error': '请提供股票代码'}), 400

    try:
        session = get_session()

        # 查询历史分析结果
        results = session.query(AnalysisResult) \
            .filter(AnalysisResult.stock_code == stock_code) \
            .order_by(AnalysisResult.analysis_date.desc()) \
            .limit(limit) \
            .all()

        # 转换为字典列表
        history = [result.to_dict() for result in results]

        return jsonify({'history': history})

    except Exception as e:
        app.logger.error(f"获取历史分析结果时出错: {str(e)}")
        return api_error('INTERNAL', '获取历史分析失败，请稍后重试', details=str(e))
    finally:
        if session:
            session.close()

# 添加新闻API端点
# 添加到web_server.py文件中
@app.route('/api/latest_news', methods=['GET'])
@validate_schema(LatestNewsSchema)  # S3-D3: schema 校验扩展
def get_latest_news():
    # Input: days/limit/important/type query params (S2-A1 校验)
    # Output: JSON news list
    # Pos: 新闻页核心端点
    # S2-A1: validate 在 try 外，ValidationError 直达全局 errorhandler
    days = validate_int_range(request.args.get('days'), 'days', 1, 30, default=1)
    limit = validate_int_range(request.args.get('limit'), 'limit', 1, 500, default=500)
    try:
        only_important = request.args.get('important', '0') == '1'  # 是否只看重要新闻
        news_type = request.args.get('type', 'all')  # 新闻类型，可选值: all, hotspot

        # 从news_fetcher模块获取新闻数据
        news_data = news_fetcher.get_latest_news(days=days, limit=limit)

        # 过滤新闻
        if only_important:
            # 根据关键词过滤重要新闻
            important_keywords = ['重要', '利好', '重磅', '突发', '关注']
            news_data = [news for news in news_data if
                         any(keyword in (news.get('content', '') or '') for keyword in important_keywords)]

        if news_type == 'hotspot':
            # 过滤舆情热点相关新闻
            hotspot_keywords = [
                # 舆情直接相关词
                '舆情', '舆论', '热点', '热议', '热搜', '话题',

                # 关注度相关词
                '关注度', '高度关注', '引发关注', '市场关注', '持续关注', '重点关注',
                '密切关注', '广泛关注', '集中关注', '投资者关注',

                # 传播相关词
                '爆文', '刷屏', '刷爆', '冲上热搜', '纷纷转发', '广泛传播',
                '热传', '病毒式传播', '迅速扩散', '高度转发',

                # 社交媒体相关词
                '微博热搜', '微博话题', '知乎热议', '抖音热门', '今日头条', '朋友圈热议',
                '微信热文', '社交媒体热议', 'APP热榜',

                # 情绪相关词
                '情绪高涨', '市场情绪', '投资情绪', '恐慌情绪', '亢奋情绪',
                '乐观情绪', '悲观情绪', '投资者情绪', '公众情绪',

                # 突发事件相关
                '突发', '紧急', '爆发', '突现', '紧急事态', '快讯', '突发事件',
                '重大事件', '意外事件', '突发新闻',

                # 行业动态相关
                '行业动向', '市场动向', '板块轮动', '资金流向', '产业趋势',
                '政策导向', '监管动态', '风口', '市场风向',

                # 舆情分析相关
                '舆情分析', '舆情监测', '舆情报告', '舆情数据', '舆情研判',
                '舆情趋势', '舆情预警', '舆情通报', '舆情简报',

                # 市场焦点相关
                '市场焦点', '焦点话题', '焦点股', '焦点事件', '投资焦点',
                '关键词', '今日看点', '重点关切', '核心议题',

                # 传统媒体相关
                '头版头条', '财经头条', '要闻', '重磅新闻', '独家报道',
                '深度报道', '特别关注', '重点报道', '专题报道',

                # 特殊提示词
                '投资舆情', '今日舆情', '今日热点', '投资热点', '市场热点',
                '每日热点', '关注要点', '交易热点', '今日重点',

                # AI基础技术
                '人工智能', 'AI', '机器学习', '深度学习', '神经网络', '大模型',
                'LLM', '大语言模型', '生成式AI', '生成式人工智能', '算法',

                # AI细分技术
                '自然语言处理', 'NLP', '计算机视觉', 'CV', '语音识别',
                '图像生成', '多模态', '强化学习', '联邦学习', '知识图谱',
                '边缘计算', '量子计算', '类脑计算', '神经形态计算',

                # 热门AI模型/产品
                'GPT', 'GPT-4', 'GPT-5', 'GPT-4o', 'ChatGPT', 'Claude',
                'Gemini', 'Llama', 'Llama3', 'Stable Diffusion', 'DALL-E',
                'Midjourney', 'Sora', 'Anthropic', 'Runway', 'Copilot',
                'Bard', 'GLM', 'Ernie', '文心一言', '通义千问', '讯飞星火','DeepSeek',

                # AI应用领域
                'AIGC', '智能驾驶', '自动驾驶', '智能助手', '智能医疗',
                '智能制造', '智能客服', '智能金融', '智能教育',
                '智能家居', '机器人', 'RPA', '数字人', '虚拟人',
                '智能安防', '计算机辅助',

                # AI硬件
                'AI芯片', 'GPU', 'TPU', 'NPU', 'FPGA', '算力', '推理芯片',
                '训练芯片', 'NVIDIA', '英伟达', 'AMD', '高性能计算',

                # AI企业
                'OpenAI', '微软AI', '谷歌AI', 'Google DeepMind', 'Meta AI',
                '百度智能云', '阿里云AI', '腾讯AI', '华为AI', '商汤科技',
                '旷视科技', '智源人工智能', '云从科技', '科大讯飞',

                # AI监管/伦理
                'AI监管', 'AI伦理', 'AI安全', 'AI风险', 'AI治理',
                'AI对齐', 'AI偏见', 'AI隐私', 'AGI', '通用人工智能',
                '超级智能', 'AI法规', 'AI责任', 'AI透明度',

                # AI市场趋势
                'AI创业', 'AI投资', 'AI融资', 'AI估值', 'AI泡沫',
                'AI风口', 'AI赛道', 'AI产业链', 'AI应用落地', 'AI转型',
                'AI红利', 'AI市值', 'AI概念股',

                # 新兴AI概念
                'AI Agent', 'AI智能体', '多智能体', '自主AI',
                'AI搜索引擎', 'RAG', '检索增强生成', '思维链', 'CoT',
                '大模型微调', '提示工程', 'Prompt Engineering',
                '基础模型', 'Foundation Model', '小模型', '专用模型',

                # 人工智能舆情专用
                'AI热点', 'AI风潮', 'AI革命', 'AI热议', 'AI突破',
                'AI进展', 'AI挑战', 'AI竞赛', 'AI战略', 'AI政策',
                'AI风险', 'AI恐慌', 'AI威胁', 'AI机遇'
            ]

            # 在API处理中使用
            if news_type == 'hotspot':
                # 过滤舆情热点相关新闻
                def has_keyword(item):
                    title = item.get('title', '')
                    content = item.get('content', '')
                    return any(keyword in title for keyword in hotspot_keywords) or \
                        any(keyword in content for keyword in hotspot_keywords)

                news_data = [news for news in news_data if has_keyword(news)]

        return jsonify({'success': True, 'news': news_data})
    except Exception as e:
        app.logger.error(f"获取最新新闻数据时出错: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/news_sentiment', methods=['GET'])
@validate_schema(NewsSentimentSchema)  # S3-D3: schema 校验扩展
def get_news_sentiment():
    """获取新闻情绪分析统计
    Input: days query param (S2-A1 校验，1-30)
    Output: JSON {total/bullish/bearish/neutral/score}
    Pos: 新闻情绪统计端点
    """
    # S2-A1: validate 在 try 外
    days = validate_int_range(request.args.get('days'), 'days', 1, 30, default=1)
    try:
        news_list = news_fetcher.get_latest_news(days=days)
        if not news_list:
            return jsonify({'total': 0, 'bullish': 0, 'bearish': 0, 'neutral': 0, 'score': 5.0})

        total = len(news_list)
        # 简单情绪分类（基于关键词）
        bullish_keywords = ['增长', '上涨', '利好', '突破', '创新高', '盈利', '分红', '超预期']
        bearish_keywords = ['下跌', '利空', '下降', '亏损', '风险', '制裁', '暴跌', '减持']

        bullish = 0
        bearish = 0
        for item in news_list:
            content = ''
            if isinstance(item, dict):
                content = str(item.get('title', '')) + str(item.get('content', ''))
            elif isinstance(item, str):
                content = item

            is_bull = any(k in content for k in bullish_keywords)
            is_bear = any(k in content for k in bearish_keywords)

            if is_bull and not is_bear:
                bullish += 1
            elif is_bear and not is_bull:
                bearish += 1

        neutral = total - bullish - bearish
        score = round(5.0 + (bullish - bearish) / max(total, 1) * 5, 1)
        score = max(1.0, min(10.0, score))

        return jsonify({
            'total': total,
            'bullish': bullish,
            'bearish': bearish,
            'neutral': neutral,
            'score': score,
            'bullish_pct': round(bullish / max(total, 1) * 100),
            'bearish_pct': round(bearish / max(total, 1) * 100),
            'neutral_pct': round(neutral / max(total, 1) * 100)
        })
    except Exception as e:
        app.logger.error(f"新闻情绪分析失败: {e}")
        return jsonify({'total': 0, 'bullish': 0, 'bearish': 0, 'neutral': 0, 'score': 5.0})


# --- Start of new FileSessionManager implementation ---
def atomic_write_json(filepath, data, encoder_cls=None):
    """原子写 JSON：tempfile + os.replace + fsync，防止 read/write 并发拿到半文件（S1-C2）
    Input: filepath(str|Path), data(dict/list), encoder_cls(JSONEncoder 子类)
    Output: None，成功则 filepath 替换为新内容
    Pos: FileSessionManager.save_task 唯一写出口
    """
    filepath = str(filepath)
    dirpath = os.path.dirname(filepath) or '.'
    fd, tmppath = tempfile.mkstemp(dir=dirpath, prefix='.tmp_', suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4, cls=encoder_cls)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmppath, filepath)
    except Exception:
        try:
            os.unlink(tmppath)
        except OSError:
            pass
        raise


class FileSessionManager:
    """A Flask-compatible file-based session manager for agent tasks."""
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_task_path(self, task_id):
        return self.data_dir / f"{task_id}.json"

    def save_task(self, task_data):
        if 'id' not in task_data:
            app.logger.error("Attempted to save task without an 'id'")
            return
        task_id = task_data['id']
        task_file = self._get_task_path(task_id)
        atomic_write_json(task_file, task_data, encoder_cls=NumpyJSONEncoder)

    def load_task(self, task_id):
        task_file = self._get_task_path(task_id)
        if not task_file.exists():
            return None
        with open(task_file, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                app.logger.error(f"Failed to decode JSON for task {task_id}")
                return None

    def get_all_tasks(self):
        tasks = []
        for task_file in self.data_dir.glob("*.json"):
            with open(task_file, 'r', encoding='utf-8') as f:
                try:
                    tasks.append(json.load(f))
                except json.JSONDecodeError:
                    app.logger.warning(f"Skipping corrupted task file: {task_file.name}")
                    continue
        return tasks

    def cleanup_stale_tasks(self, timeout_hours=2):
        """Clean up stale 'running' tasks that have exceeded a timeout."""
        app.logger.info("开始清理过时的任务...")
        cleaned_count = 0
        # updated_at is persisted as a timezone-free '%Y-%m-%d %H:%M:%S' string.
        # Keep both operands naive to avoid startup cleanup log noise.
        now = now_cn().replace(tzinfo=None)
        
        tasks = self.get_all_tasks()
        for task in tasks:
            if task.get('status') == TASK_RUNNING:
                try:
                    updated_at = datetime.strptime(task.get('updated_at'), '%Y-%m-%d %H:%M:%S')
                    if (now - updated_at).total_seconds() > timeout_hours * 3600:
                        task['status'] = TASK_FAILED
                        task['error'] = '任务因服务器重启或超时而中止'
                        task['updated_at'] = now.strftime('%Y-%m-%d %H:%M:%S')
                        self.save_task(task)
                        cleaned_count += 1
                        app.logger.warning(f"清理了过时的任务 {task.get('id')}，该任务已运行超过 {timeout_hours} 小时。")
                except (ValueError, TypeError) as e:
                    app.logger.error(f"解析任务 {task.get('id')} 的 updated_at 时出错: {e}")
                    continue
        
        if cleaned_count > 0:
            app.logger.info(f"清理完成，共处理了 {cleaned_count} 个过时的任务。")
        else:
            app.logger.info("没有发现需要清理的过时任务。")

    def delete_task(self, task_id):
        """Safely delete a task file."""
        try:
            task_file = self._get_task_path(task_id)
            if task_file.exists():
                task_file.unlink()
                return True
        except Exception as e:
            app.logger.error(f"Failed to delete task {task_id}: {e}")
        return False

# Instantiate the manager
AGENT_SESSIONS_DIR = os.path.join(os.path.dirname(__file__), '../../data/agent_sessions')
agent_session_manager = FileSessionManager(AGENT_SESSIONS_DIR)
agent_session_manager.cleanup_stale_tasks()
# --- End of new FileSessionManager implementation ---


def _validate_agent_params(data: dict) -> tuple:
    """校验并规范化 agent 分析参数

    Input: API request data dict
    Output: (stock_code, research_depth, market_type, selected_analysts,
             analysis_date, enable_memory, max_output_length)
    Pos: start_agent_analysis 参数预处理

    Raises:
        ValueError: 参数不合法时
    """
    stock_code = data.get('stock_code')
    if not stock_code:
        raise ValueError('请提供股票代码')

    research_depth = data.get('research_depth', 3)
    market_type = data.get('market_type', 'A')
    selected_analysts = data.get('selected_analysts', ["market", "social", "news", "fundamentals"])
    analysis_date = data.get('analysis_date')
    enable_memory = data.get('enable_memory', True)
    max_output_length = data.get('max_output_length', 2048)

    # 验证股票代码格式
    is_valid, validated_code = validate_stock_code(stock_code, market_type)
    if not is_valid:
        raise ValueError(validated_code)

    return validated_code, research_depth, market_type, selected_analysts, analysis_date, enable_memory, max_output_length


def _build_agent_task(stock_code: str, research_depth: int, market_type: str,
                      selected_analysts: list, analysis_date: str,
                      enable_memory: bool, max_output_length: int) -> dict:
    """构建 agent 任务对象

    Input: 规范化参数
    Output: task dict（含 id/status/progress/created_at 等字段）
    Pos: start_agent_analysis 任务初始化
    """
    task_id = generate_task_id()
    return {
        'id': task_id,
        'status': TASK_PENDING,
        'progress': 0,
        'current_step': '任务已创建',
        'created_at': now_cn().strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': now_cn().strftime('%Y-%m-%d %H:%M:%S'),
        'params': {
            'stock_code': stock_code,
            'research_depth': research_depth,
            'market_type': market_type,
            'selected_analysts': selected_analysts,
            'analysis_date': analysis_date,
            'enable_memory': enable_memory,
            'max_output_length': max_output_length
        }
    }


def _run_new_agent_system(stock_code: str, market_type: str, research_depth: int,
                          selected_analysts: list, task_id: str) -> None:
    """运行新 LangGraph Agent 系统

    Input: 股票代码、市场类型、研究深度、分析师列表、任务ID
    Output: None（通过 update_task_status 写入结果）
    Pos: 在后台线程中执行新 Agent 系统分析
    """
    from app.agents.coordinator import run_agent_analysis as agent_run

    update_task_status('agent_analysis', task_id, TASK_RUNNING, progress=5,
                      result={'current_step': '正在初始化多Agent分析系统...'})

    # 订阅进度事件
    from app.core.event_bus import get_event_bus as _get_bus
    _bus = _get_bus()

    def _on_progress_advance(payload):
        try:
            if not isinstance(payload, dict) or payload.get('task_id') != task_id:
                return
            update_task_status(
                'agent_analysis', task_id, TASK_RUNNING,
                progress=payload.get('progress', 5),
                result={
                    'current_step': payload.get('current_step') or f"{payload.get('agent_name','')} 完成",
                    'completed_nodes': payload.get('completed'),
                    'total_nodes': payload.get('total'),
                }
            )
        except Exception as _e:
            app.logger.debug(f"progress_advance listener err: {_e}")

    _bus.subscribe('task.progress_advance', _on_progress_advance)

    try:
        result_state = agent_run(
            stock_code=stock_code,
            market_type=market_type,
            research_depth=research_depth,
            selected_analysts=selected_analysts,
            task_id=task_id,
        )
    finally:
        try:
            _bus.unsubscribe('task.progress_advance', _on_progress_advance)
        except Exception:
            pass

    # 获取公司名称
    try:
        stock_info = analyzer.get_stock_info(stock_code)
        stock_name = stock_info.get('股票名称', '未知')
        result_state['company_name'] = stock_name
    except Exception as e:
        app.logger.error(f"获取公司名称时出错: {e}")
        result_state['company_name'] = '名称获取失败'

    # 构造前端期望的 decision 格式
    final_decision = result_state.get('final_decision', {}) or {}
    hitl_meta = result_state.get('hitl') or {}
    decision_obj = {
        'action': final_decision.get('action', 'HOLD'),
        'reasoning': final_decision.get('reasoning', '分析完成'),
        'confidence': final_decision.get('confidence', 0.5),
        'risk_score': 1.0 - float(final_decision.get('confidence', 0.5) or 0.5),
        'risk_level': final_decision.get('risk_level'),
        'approved': final_decision.get('approved'),
        'approval_type': final_decision.get('approval_type'),
        'approval_status': final_decision.get('approval_status'),
    }

    terminal = TASK_FAILED if result_state.get('hitl_rejected') else TASK_COMPLETED
    step_label = (
        'HITL 拒绝/超时拒绝'
        if result_state.get('hitl_rejected')
        else '多Agent分析完成'
    )
    update_task_status('agent_analysis', task_id, terminal, progress=100, result={
        'decision': decision_obj,
        'final_state': result_state,
        'current_step': step_label,
        'execution_log': result_state.get('execution_log', []),
        'errors': result_state.get('errors', []),
        'hitl': hitl_meta,
    }, error=(
        (result_state.get('errors') or [None])[-1]
        if result_state.get('hitl_rejected') else None
    ))
    app.logger.info(f"Agent分析任务 {task_id} 完成 (新系统) hitl={hitl_meta}")


def _run_old_trading_agents(stock_code: str, market_type: str, selected_analysts: list,
                            enable_memory: bool, max_output_length: int,
                            analysis_date: str, task_id: str) -> None:
    """运行旧 TradingAgents 系统（保持兼容）

    Input: 股票代码、市场类型、分析师列表、内存开关、输出长度、分析日期、任务ID
    Output: None（通过 update_task_status 写入结果）
    Pos: 在后台线程中执行旧 TradingAgents 系统分析
    """
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG

    update_task_status('agent_analysis', task_id, TASK_RUNNING, progress=5,
                      result={'current_step': '正在初始化智能体...'})

    config = DEFAULT_CONFIG.copy()
    config['llm_provider'] = 'openai'
    config['backend_url'] = os.getenv('OPENAI_API_URL')
    main_model = os.getenv('OPENAI_API_MODEL', 'gpt-4o')
    config['deep_think_llm'] = main_model
    config['quick_think_llm'] = main_model
    config['memory_enabled'] = enable_memory
    config['max_tokens'] = max_output_length

    if not os.getenv('OPENAI_API_KEY'):
        raise ValueError("OPENAI_API_KEY 未在.env文件中设置")

    ta = TradingAgentsGraph(
        selected_analysts=selected_analysts,
        debug=True,
        config=config
    )

    today = analysis_date or now_cn().strftime('%Y-%m-%d')

    import inspect
    propagate_sig = inspect.signature(ta.propagate)
    propagate_params = propagate_sig.parameters
    kwargs = {}
    if 'market_type' in propagate_params:
        kwargs['market_type'] = market_type

    update_task_status('agent_analysis', task_id, TASK_RUNNING, progress=30,
                      result={'current_step': '正在进行多智能体分析...'})
    state, raw_decision = ta.propagate(stock_code, today, **kwargs)
    update_task_status('agent_analysis', task_id, TASK_RUNNING, progress=90,
                      result={'current_step': '正在生成分析报告...'})

    try:
        stock_info = analyzer.get_stock_info(stock_code)
        stock_name = stock_info.get('股票名称', '未知')
        if isinstance(state, dict):
            state['company_name'] = stock_name
    except Exception as e:
        app.logger.error(f"获取公司名称时出错: {e}")
        if isinstance(state, dict):
            state['company_name'] = '名称获取失败'

    final_trade_decision = state.get('final_trade_decision', '') if isinstance(state, dict) else ''
    action = raw_decision.strip().upper() if raw_decision else 'HOLD'
    if action not in ['BUY', 'SELL', 'HOLD']:
        if 'BUY' in final_trade_decision.upper():
            action = 'BUY'
        elif 'SELL' in final_trade_decision.upper():
            action = 'SELL'
        else:
            action = 'HOLD'

    decision_obj = {
        'action': action,
        'reasoning': final_trade_decision[:500] if final_trade_decision else '分析完成',
        'confidence': 0.7,
        'risk_score': 0.5
    }

    update_task_status('agent_analysis', task_id, TASK_COMPLETED, progress=100,
                      result={'decision': decision_obj, 'final_state': state, 'current_step': '分析完成'})
    app.logger.info(f"智能体分析任务 {task_id} 完成 (旧系统)")


# 智能体分析路由
@app.route('/api/start_agent_analysis', methods=['POST'])
@validate_schema(StartAgentAnalysisSchema, source='json')  # S3-D3: schema 校验扩展
def start_agent_analysis():
    """启动智能体分析任务"""
    try:
        # 参数校验与规范化（提取为子函数 1）
        try:
            stock_code, research_depth, market_type, selected_analysts, \
                analysis_date, enable_memory, max_output_length = _validate_agent_params(request.json)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        # 创建任务对象（提取为子函数 2）
        task = _build_agent_task(
            stock_code, research_depth, market_type, selected_analysts,
            analysis_date, enable_memory, max_output_length
        )
        task_id = task['id']

        # 为任务创建取消事件
        task['cancel_event'] = threading.Event()
        agent_session_manager.save_task(task)

        def run_agent_analysis():
            """在后台线程中运行智能体分析"""
            try:
                # 特性开关：使用新Agent系统或旧TradingAgents
                use_new_agent = os.getenv('USE_AGENT_SYSTEM', 'true').lower() == 'true'

                if use_new_agent:
                    # 新Agent系统（拆分为子函数 3）
                    _run_new_agent_system(stock_code, market_type, research_depth,
                                         selected_analysts, task_id)
                else:
                    # 旧TradingAgents系统（拆分为子函数 4）
                    _run_old_trading_agents(stock_code, market_type, selected_analysts,
                                           enable_memory, max_output_length,
                                           analysis_date, task_id)

            except TaskCancelledException as e:
                app.logger.info(str(e))
                update_task_status('agent_analysis', task_id, TASK_FAILED, error='任务已被用户取消',
                                 result={'current_step': '任务已被用户取消'})
            except Exception as e:
                app.logger.error(f"智能体分析任务 {task_id} 失败: {str(e)}")
                app.logger.error(traceback.format_exc())
                update_task_status('agent_analysis', task_id, TASK_FAILED, error=str(e),
                                 result={'current_step': f'分析失败: {e}'})

        thread = threading.Thread(target=run_agent_analysis)
        thread.daemon = True
        thread.start()

        return jsonify({
            'task_id': task_id,
            'status': 'pending',
            'message': f'已启动对 {stock_code} 的智能体分析'
        })

    except Exception as e:
        app.logger.error(f"启动智能体分析时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '启动智能体分析失败，请稍后重试', details=str(e))

@app.route('/api/agent_analysis_status/<task_id>', methods=['GET'])
@validate_schema(AgentAnalysisStatusSchema)  # S3-J(A): schema 校验扩展
def get_agent_analysis_status(task_id):
    """获取智能体分析任务的状态"""
    task = agent_session_manager.load_task(task_id)

    if not task:
        return jsonify({'error': '找不到指定的智能体分析任务'}), 404
    
    # 准备要返回的数据
    response_data = {
        'id': task['id'],
        'status': task['status'],
        'progress': task.get('progress', 0),
        'created_at': task['created_at'],
        'updated_at': task['updated_at'],
        'params': task.get('params', {})
    }
    
    if 'result' in task:
         response_data['result'] = convert_messages_to_dict(task['result'])
    if 'error' in task:
         response_data['error'] = task['error']
         
    return custom_jsonify(response_data)


@app.route('/api/agent_analysis_history', methods=['GET'])
@validate_schema(AgentAnalysisHistorySchema)  # S3-C4: schema 校验
def get_agent_analysis_history():
    """获取已完成的智能体分析任务历史（S3-C1 cursor 分页）
    Input: cursor（游标）/ limit（1-200）
    Output: JSON {items: [...], next_cursor: str|null, limit: int, history: [...]}
    Pos: 智能体历史任务列表，cursor 分页
    """
    try:
        params = request.validated  # type: ignore[attr-defined]
        limit = params['limit']
        cursor = params.get('cursor')

        # cursor 格式同 conversations：offset:{n}
        skip = 0
        if cursor and cursor.startswith('offset:'):
            try:
                skip = int(cursor[7:])
            except ValueError:
                skip = 0

        all_tasks = agent_session_manager.get_all_tasks()
        history = [
            task for task in all_tasks
            if task.get('status') in [TASK_COMPLETED, TASK_FAILED]
        ]
        # 按更新时间排序，最新的在前
        history.sort(key=lambda x: x.get('updated_at', ''), reverse=True)

        # 多取 1 条判断是否有下一页
        page = history[skip: skip + limit]
        has_more = len(history) > skip + limit
        next_cursor = f'offset:{skip + limit}' if has_more else None

        return custom_jsonify({
            'items': page,
            'next_cursor': next_cursor,
            'limit': limit,
            # 旧字段兼容
            'history': page,
        })
    except Exception as e:
        app.logger.error(f"获取分析历史时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取智能体分析历史失败，请稍后重试', details=str(e))


@app.route('/api/delete_agent_analysis', methods=['POST'])
@validate_schema(DeleteAgentAnalysisSchema, source='json')  # S3-E1: schema 校验扩展
def delete_agent_analysis():
    """Cancel and/or delete one or more agent analysis tasks."""
    try:
        data = request.json
        task_ids = data.get('task_ids', [])
        if not isinstance(task_ids, list):
            return jsonify({'error': 'task_ids 必须是一个列表'}), 400

        if not task_ids:
            return jsonify({'error': '请提供要删除的任务ID'}), 400

        deleted_count = 0
        cancelled_count = 0
        
        for task_id in task_ids:
            task = agent_session_manager.load_task(task_id)
            if not task:
                app.logger.warning(f"尝试删除一个不存在的任务: {task_id}")
                continue

            # If the task is running, mark it as cancelled
            if task.get('status') == TASK_RUNNING:
                task['status'] = TASK_CANCELLED
                task['updated_at'] = now_cn().strftime('%Y-%m-%d %H:%M:%S')
                task['error'] = '任务已被用户取消'
                agent_session_manager.save_task(task)
                cancelled_count += 1
                app.logger.info(f"任务 {task_id} 已被标记为取消。")
            
            # For all other states (or after cancelling), delete the task file
            if agent_session_manager.delete_task(task_id):
                deleted_count += 1
        
        message = f"请求处理 {len(task_ids)} 个任务。已取消 {cancelled_count} 个运行中的任务，并删除了 {deleted_count} 个任务文件。"
        app.logger.info(message)
        return jsonify({'success': True, 'message': message})

    except Exception as e:
        app.logger.error(f"删除分析历史时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '删除分析记录失败，请稍后重试', details=str(e))


@app.route('/api/agent_pending_approvals', methods=['GET'])
@validate_schema(AgentPendingApprovalsSchema)  # S3-G1: schema 校验扩展
def get_pending_approvals():
    """获取待人工审批的Agent决策（P0-5 确认面）"""
    try:
        from app.agents.hitl import approval_manager
        # 惰性绑定任务状态钩子，使 awaiting_approval 可写入任务查询
        if getattr(approval_manager, '_task_status_hook', None) is None:
            approval_manager.set_task_status_hook(update_task_status)
        pending = approval_manager.get_pending_approvals()
        return jsonify({'approvals': pending, 'count': len(pending)})
    except Exception as e:
        return api_error('INTERNAL', '获取待审批任务失败，请稍后重试', details=str(e))


@app.route('/api/agent_submit_approval', methods=['POST'])
@validate_schema(AgentSubmitApprovalSchema, source='json')  # S3-E1: schema 校验扩展
def submit_agent_approval():
    """提交人工审批结果（P0-5 确认面）"""
    try:
        from app.agents.hitl import approval_manager
        if getattr(approval_manager, '_task_status_hook', None) is None:
            approval_manager.set_task_status_hook(update_task_status)
        data = request.json or {}
        task_id = data.get('task_id')
        approved = data.get('approved', False)
        feedback = data.get('feedback', '')
        if not task_id:
            return jsonify({'error': '请提供task_id'}), 400
        success = approval_manager.submit_approval(task_id, approved, feedback)
        if success:
            return jsonify({
                'message': '审批已提交',
                'approved': bool(approved),
                'task_id': task_id,
            })
        return jsonify({'error': '未找到待审批任务'}), 404
    except Exception as e:
        return api_error('INTERNAL', '提交审批失败，请稍后重试', details=str(e))


@app.route('/api/active_tasks', methods=['GET'])
@validate_schema(ActiveTasksSchema)  # S3-G1: schema 校验扩展
def get_active_tasks():
    """获取所有正在进行的智能体分析任务"""
    try:
        all_tasks = agent_session_manager.get_all_tasks()
        active_tasks_list = []
        for task in all_tasks:
            if task.get('status') == TASK_RUNNING:
                task_info = {
                    'task_id': task['id'],
                    'stock_code': task.get('params', {}).get('stock_code'),
                    'progress': task.get('progress', 0),
                    'current_step': task.get('result', {}).get('current_step', '加载中...')
                }
                active_tasks_list.append(task_info)
        # 按创建时间排序，最新的在前
        active_tasks_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return custom_jsonify({'active_tasks': active_tasks_list})
    except Exception as e:
        app.logger.error(f"获取活动任务时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取活跃任务失败，请稍后重试', details=str(e))


# ===== MCP 工具服务端点 =====

@app.route('/api/mcp/tools', methods=['GET'])
@validate_schema(McpListToolsSchema)  # S3-J(A): schema 校验扩展
def mcp_list_tools():
    """列出MCP可用工具"""
    try:
        from app.mcp.stock_data_server import MCP_SERVER_CONFIG
        return jsonify(MCP_SERVER_CONFIG)
    except Exception as e:
        return api_error('INTERNAL', '获取MCP工具列表失败，请稍后重试', details=str(e))

@app.route('/api/mcp/call', methods=['POST'])
@validate_schema(McpCallSchema, source='json')  # S3-E1: schema 校验扩展
def mcp_call_tool():
    """调用MCP工具"""
    try:
        from app.mcp.stock_data_server import handle_mcp_tool_call
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return jsonify({'error': '请求体必须为有效的JSON格式'}), 400
        tool_name = data.get('tool')
        arguments = data.get('arguments', {})
        if not tool_name:
            return jsonify({'error': '请提供tool参数'}), 400
        result = handle_mcp_tool_call(tool_name, arguments)
        return jsonify({'result': result})
    except Exception as e:
        app.logger.error(f"MCP工具调用失败: {traceback.format_exc()}")
        return jsonify({'error': '工具调用失败，请稍后重试'}), 500


# ===== 多模态图片上传接口 =====

@app.route('/api/upload_image', methods=['POST'])
@validate_schema(UploadImageSchema, source='form')  # S3-J(A): schema 校验扩展（multipart form）
def upload_image():
    """接收图片并返回描述（用于多模态分析）
    安全加固（Hunt1-C4）：secure_filename + magic bytes + 扩展名白名单 + 大小限制 + 绝对路径
    """
    from werkzeug.utils import secure_filename as _secure_filename
    import tempfile

    if 'file' not in request.files:
        return jsonify({'error': '未找到文件'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': '未选择文件'}), 400

    # ── 1. 安全文件名（防路径遍历）────────────────────────────────────────────
    safe_name = _secure_filename(file.filename)
    if not safe_name:
        return jsonify({'error': '非法文件名'}), 400

    # ── 2. 扩展名白名单 ──────────────────────────────────────────────────────
    ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'error': f'不支持的文件类型: {ext}，仅允许: {", ".join(sorted(ALLOWED_EXT))}'}), 400

    # ── 3. 文件大小限制 ──────────────────────────────────────────────────────
    _max_mb = int(os.getenv('MAX_UPLOAD_SIZE_MB', '5'))
    MAX_IMAGE_SIZE = _max_mb * 1024 * 1024
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_IMAGE_SIZE:
        return jsonify({'error': f'文件大小超过限制（最大 {_max_mb}MB），当前: {round(file_size / 1024 / 1024, 1)}MB'}), 413

    # ── 4. Magic bytes 校验（防伪装上传）────────────────────────────────────
    MAGIC_BYTES: list[tuple[bytes, str]] = [
        (b'\xff\xd8\xff', '.jpg'),        # JPEG
        (b'\x89PNG\r\n\x1a\n', '.png'),   # PNG
        (b'GIF87a', '.gif'),               # GIF87a
        (b'GIF89a', '.gif'),               # GIF89a
        (b'RIFF', '.webp'),               # WEBP（需进一步判断）
    ]
    header = file.read(12)
    file.seek(0)
    detected_ext: str | None = None
    for magic, mext in MAGIC_BYTES:
        if header.startswith(magic):
            if magic == b'RIFF' and header[8:12] != b'WEBP':
                continue
            detected_ext = mext
            break
    if detected_ext is None:
        return jsonify({'error': 'magic bytes 校验失败，文件内容与声明的图片格式不匹配'}), 400
    # JPEG 文件允许 .jpeg/.jpg 互换
    _ext_group = {'.jpg', '.jpeg'}
    if detected_ext != ext and not (detected_ext in _ext_group and ext in _ext_group):
        return jsonify({'error': f'文件扩展名 ({ext}) 与实际格式 ({detected_ext}) 不匹配'}), 400

    # ── 5. 安全路径拼接（UPLOAD_DIR 为绝对路径，不含用户输入）───────────────
    _upload_dir = os.getenv('UPLOAD_DIR') or os.path.join(tempfile.gettempdir(), 'stockanal_uploads')
    # 强制解析为绝对路径，杜绝相对路径注入
    UPLOAD_DIR = os.path.realpath(os.path.abspath(_upload_dir))
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 加随机前缀防止同名文件覆盖
    import uuid as _uuid
    unique_name = f"{_uuid.uuid4().hex[:8]}_{safe_name}"
    filepath = os.path.join(UPLOAD_DIR, unique_name)

    # 最后防御：确保路径在 UPLOAD_DIR 内
    if not os.path.realpath(filepath).startswith(UPLOAD_DIR):
        return jsonify({'error': '非法路径'}), 400

    file.save(filepath)

    # 返回 URL 不含原始用户输入
    return jsonify({
        'success': True,
        'filename': unique_name,
        'size': os.path.getsize(filepath),
        'message': '图片已上传，多模态分析功能开发中'
    })


# ===== AI对话 & Agent分析 SSE流式端点 =====

@app.route('/api/ai/chat', methods=['POST'])
@limiter.limit(os.getenv('RATE_LIMIT_LLM', '20 per minute'))  # S2-A4: LLM 限流
@validate_schema(AiChatStreamSchema, source='json')  # S3-G1: schema 校验扩展
def ai_chat_stream():
    """AI对话流式端点 — SSE输出Token+工具调用+Agent状态+Artifact
    Input: JSON body {message, conversation_id}
    Output: SSE stream
    Pos: LLM 调用入口，已套 20 req/min 限流防止 API KEY 超支
    """
    from flask import Response, stream_with_context
    import queue
    from app.core.ai_client import get_ai_client, chat_with_tools_stream
    from app.core.tools import OPENAI_TOOLS_SCHEMA
    from app.core.artifact_wrapper import execute_tool_with_artifact
    from app.core.conversation import get_conversation_manager
    from app.core.event_bus import get_event_bus

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'error': '请求体必须为有效的JSON格式'}), 400

    message = data.get('message', '')
    conversation_id = data.get('conversation_id', '')
    stock_code = data.get('stock_code', '')
    market_type = data.get('market_type', 'A')
    research_depth = data.get('research_depth', 3)

    if not message or not isinstance(message, str) or not message.strip():
        return jsonify({'error': '请输入消息'}), 400
    message = message.strip()

    client = get_ai_client()
    if not client:
        return jsonify({'error': 'AI服务未配置'}), 503

    # 获取或创建对话
    conv_mgr = get_conversation_manager()
    if not conversation_id:
        conversation_id = conv_mgr.create_conversation(message[:20])

    # 保存用户消息
    conv_mgr.add_message(conversation_id, 'user', message)

    # 记录股票代码
    if stock_code:
        conv_mgr.add_stock_code(conversation_id, stock_code)

    def generate():
        """SSE事件生成器"""
        import json as _json

        # AI对话总超时（默认 1800s=30min，可经环境变量 AI_CHAT_TIMEOUT 配置）
        AI_CHAT_TIMEOUT = int(os.getenv('AI_CHAT_TIMEOUT', '1800'))
        chat_start_time = time.time()

        def check_timeout():
            """检查是否超时，超时则抛出TimeoutError"""
            elapsed = time.time() - chat_start_time
            if elapsed > AI_CHAT_TIMEOUT:
                raise TimeoutError(f"AI对话处理超时（已耗时{int(elapsed)}秒，限制{AI_CHAT_TIMEOUT}秒）")

        def emit(event_type, data):
            return f"event: {event_type}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

        try:
            # 构建消息历史 — 跨会话记忆增强
            # 加载对话中除当前消息外的最近5条历史消息作为上下文
            all_history = conv_mgr.get_messages_for_ai(conversation_id, max_messages=6)
            # 分离历史消息（排除刚保存的当前用户消息）和当前消息
            if all_history and all_history[-1].get('role') == 'user' and all_history[-1].get('content') == message:
                prior_history = all_history[:-1][-5:]  # 最近5条历史消息
                current_msg = [all_history[-1]]
            else:
                prior_history = all_history[-5:]
                current_msg = [{"role": "user", "content": message}]

            # 系统提示
            history_hint = ""
            if prior_history:
                history_hint = "\n你可以参考之前的对话历史来保持上下文连贯性。"
            system_prompt = f"""你是专业的AI金融分析助手。你可以使用工具获取股票数据进行分析。
当用户提到股票代码时，请使用对应工具获取实时数据后给出专业分析。
当前关注股票: {stock_code or '未指定'}
市场类型: {market_type}
请用中文回复，分析要专业、数据要准确。{history_hint}"""

            messages = [{"role": "system", "content": system_prompt}] + prior_history + current_msg
            # 保存原始messages副本，降级时使用（chat_with_tools_stream会修改messages）
            original_messages = [dict(m) for m in messages]

            # 工具执行器（带artifact包装）
            artifacts_collected = []
            tool_calls_log = []

            def artifact_tool_executor(tool_name, arguments):
                raw_result, artifact = execute_tool_with_artifact(tool_name, arguments)
                if artifact:
                    artifacts_collected.append(artifact)
                return raw_result

            # 收集完整回复
            full_content = ""

            # [REAL-01 Q1/Q3] 心跳改造：阻塞调用移到后台线程 + 主生成器轮询事件队列
            # 1) chat_with_tools_stream 是同步阻塞的；2) event_callback 在 worker 线程触发时把 token 入队；
            # 3) 主线程每秒检查队列拿 token 立即 yield 给前端；4) 每 15s 无 token 则 yield `: heartbeat`
            #    防止 Cloudflare / Nginx / 浏览器 idle 切连。
            import threading as _threading
            import queue as _queue
            HEARTBEAT_INTERVAL = int(os.getenv('AI_CHAT_HEARTBEAT_INTERVAL', '15'))
            event_queue: _queue.Queue = _queue.Queue()

            def event_callback(event_type, data):
                """worker 线程回调：把 token 推入主线程队列"""
                nonlocal full_content
                if event_type == 'token' and data.get('content'):
                    full_content += data['content']
                    # 立即把增量内容入队，主线程 yield 给客户端
                    event_queue.put(('token_delta', data['content']))

            # 执行流式AI对话（带工具调用，模型不支持时降级）
            check_timeout()
            content, tools_log, error = None, [], None

            worker_result = {'content': None, 'tools_log': [], 'error': None, 'exc': None}

            def _chat_worker():
                """后台线程执行真正的阻塞 LLM 调用"""
                try:
                    c, t, e = chat_with_tools_stream(
                        client, messages, OPENAI_TOOLS_SCHEMA,
                        tool_executor=artifact_tool_executor,
                        max_tool_rounds=3,
                        event_callback=event_callback
                    )
                    worker_result['content'] = c
                    worker_result['tools_log'] = t
                    worker_result['error'] = e
                except Exception as ex:
                    worker_result['exc'] = ex
                finally:
                    event_queue.put(('worker_done', None))

            worker_th = _threading.Thread(target=_chat_worker, daemon=True)
            worker_th.start()

            last_event_ts = time.time()
            worker_done = False
            while not worker_done:
                check_timeout()
                try:
                    kind, payload = event_queue.get(timeout=1.0)
                except _queue.Empty:
                    # 队列空：判断是否需要发心跳
                    if time.time() - last_event_ts >= HEARTBEAT_INTERVAL:
                        yield f": heartbeat {int(time.time())}\n\n"
                        last_event_ts = time.time()
                    continue

                if kind == 'token_delta':
                    # 实时推送增量 token 给前端
                    yield emit('token', {'content': payload, 'finish_reason': None})
                    last_event_ts = time.time()
                elif kind == 'worker_done':
                    worker_done = True

            if worker_result['exc'] is not None:
                tool_err = worker_result['exc']
                app.logger.warning(f"带工具的流式调用失败，降级为普通对话: {tool_err}")
                error = None  # 清除错误，尝试降级
            else:
                content = worker_result['content']
                tools_log = worker_result['tools_log']
                error = worker_result['error']

            # 工具调用失败时降级为不带tools的普通对话
            if error and ('400' in str(error) or 'tool' in str(error).lower()):
                app.logger.info("降级为不带工具的普通对话")
                full_content = ""
                from app.core.ai_client import chat_completion_stream, get_completion_content
                # 用干净的原始messages，避免残留的tool_call消息导致API错误
                stream, stream_err = chat_completion_stream(client, original_messages)
                if stream_err:
                    yield emit('error', {'code': 'AI_ERROR', 'message': stream_err})
                    return
                # 收集流式响应 - 同样带心跳
                collected = ""
                last_event_ts = time.time()
                for chunk in stream:
                    check_timeout()
                    if chunk.choices and chunk.choices[0].delta.content:
                        delta = chunk.choices[0].delta.content
                        collected += delta
                        yield emit('token', {'content': delta, 'finish_reason': None})
                        last_event_ts = time.time()
                    elif time.time() - last_event_ts >= HEARTBEAT_INTERVAL:
                        yield f": heartbeat {int(time.time())}\n\n"
                        last_event_ts = time.time()
                content = collected
                error = None
                tools_log = []

            if error:
                yield emit('error', {'code': 'AI_ERROR', 'message': error})
                return

            final_content = content or full_content

            # [REAL-01 Q1/Q3] 增量 token 已在 worker 循环中实时 yield 给前端；
            # 这里仅在 full_content 为空（例如普通对话降级路径已经在自己的循环里推过）时不再重复推送。
            # 只发一个 finish_reason=stop 的空 token 表示结束。
            yield emit('token', {'content': '', 'finish_reason': 'stop'})

            # 推送所有artifact
            for artifact in artifacts_collected:
                yield emit('artifact', artifact)

            # 保存AI回复到对话历史
            conv_mgr.add_message(
                conversation_id, 'assistant', final_content or '',
                artifacts=artifacts_collected,
                tool_calls=tools_log
            )

            # 生成follow-up问题
            follow_ups = _generate_follow_ups(stock_code, final_content)

            # 对话摘要生成 — 消息超过10条时自动生成摘要
            try:
                msg_count = conv_mgr.get_message_count(conversation_id)
                if msg_count > 10 and final_content:
                    # 用最近几条消息生成简短摘要
                    recent = conv_mgr.get_messages_for_ai(conversation_id, max_messages=10)
                    summary_prompt = [
                        {"role": "system", "content": "请用50字以内概括以下对话的核心主题和关键结论，仅输出摘要文本："},
                        {"role": "user", "content": "\n".join([f"{m['role']}: {m['content'][:200]}" for m in recent if m.get('content')])}
                    ]
                    from app.core.ai_client import chat_completion_stream
                    summary_stream, summary_err = chat_completion_stream(client, summary_prompt)
                    if not summary_err and summary_stream:
                        summary_text = ""
                        for chunk in summary_stream:
                            if chunk.choices and chunk.choices[0].delta.content:
                                summary_text += chunk.choices[0].delta.content
                        if summary_text.strip():
                            conv_mgr.update_summary(conversation_id, summary_text.strip())
            except Exception as sum_err:
                app.logger.warning(f"生成对话摘要失败: {sum_err}")

            # 推送完成事件
            yield emit('done', {
                'conversation_id': conversation_id,
                'follow_up_questions': follow_ups
            })

        except TimeoutError as te:
            app.logger.warning(f"AI对话超时: {te}")
            yield emit('error', {'code': 'TIMEOUT', 'message': 'AI响应超时，请稍后重试或缩短问题长度'})
        except GeneratorExit:
            app.logger.debug("AI对话SSE连接已断开")
        except Exception as e:
            app.logger.error(f"AI对话流式处理失败: {traceback.format_exc()}")
            yield emit('error', {'code': 'STREAM_ERROR', 'message': 'AI服务处理异常，请稍后重试'})

    return Response(
        stream_with_context(generate()),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


def _generate_follow_ups(stock_code, analysis_text):
    """生成预判性后续问题"""
    if stock_code:
        return [
            f"{stock_code}的估值水平与同行业相比如何？",
            f"{stock_code}近期主力资金流向如何？",
            f"{stock_code}有哪些潜在的风险因素？",
            f"对{stock_code}做深度Agent分析",
        ]
    return [
        "分析600519贵州茅台",
        "今日大盘走势如何？",
        "推荐几只低估值蓝筹股",
    ]


@app.route('/api/conversations', methods=['GET'])
@validate_schema(ConversationsListSchema)  # S3-C4: schema 校验
def list_conversations():
    """获取对话列表（S3-C1 cursor 分页）
    Input: cursor（游标）/ limit（1-200）/ offset（deprecated 兼容旧客户端）
    Output: JSON {items: [...], next_cursor: str|null, limit: int}
    Pos: 对话历史列表端点，cursor 分页替代 offset，兼容旧 offset 参数
    """
    from app.core.conversation import get_conversation_manager
    params = request.validated  # type: ignore[attr-defined]
    limit = params['limit']
    cursor = params.get('cursor')
    offset = params.get('offset')

    # offset 兼容：将 offset 转成 cursor（offset 是 skip 数量，cursor 编码为 "offset:{n}"）
    # 旧客户端传 offset 时返回 Deprecation header 提示
    use_offset_compat = offset is not None and cursor is None
    if use_offset_compat:
        cursor = f'offset:{offset}'

    mgr = get_conversation_manager()
    # cursor 分页实现：cursor 格式 "offset:{n}" 表示跳过 n 条
    # 默认从 0 开始（无 cursor）；updated_at 倒序
    skip = 0
    if cursor:
        if cursor.startswith('offset:'):
            try:
                skip = int(cursor[7:])
            except ValueError:
                skip = 0
        # 未来可扩展为 "ts:{iso}" 格式的 timestamp cursor

    # 多取 1 条以判断是否有下一页
    all_convs = mgr.list_conversations(skip + limit + 1)
    page = all_convs[skip: skip + limit]
    has_more = len(all_convs) > skip + limit
    next_cursor = f'offset:{skip + limit}' if has_more else None

    resp = jsonify({
        'items': page,
        'next_cursor': next_cursor,
        'limit': limit,
        # 旧字段兼容（前端可能仍读 conversations）
        'conversations': page,
    })
    if use_offset_compat:
        resp.headers['Deprecation'] = (
            'offset 参数已废弃，请改用 cursor 分页；'
            'next_cursor 在响应体中'
        )
    return resp


@app.route('/api/conversations/<conversation_id>', methods=['GET'])
@validate_schema(ConversationDetailSchema)  # S3-J(A): schema 校验扩展
def get_conversation(conversation_id):
    """获取单个对话详情"""
    from app.core.conversation import get_conversation_manager
    conv = get_conversation_manager().get_conversation(conversation_id)
    if not conv:
        return jsonify({'error': '对话不存在'}), 404
    return jsonify(conv)


@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
@validate_schema(ConversationDetailSchema, source='json')  # S3-J(A): schema 校验扩展
def delete_conversation(conversation_id):
    """删除对话"""
    from app.core.conversation import get_conversation_manager
    success = get_conversation_manager().delete_conversation(conversation_id)
    if success:
        return jsonify({'message': '对话已删除'})
    return jsonify({'error': '删除失败'}), 404


# ============================================================
# A2A Protocol v1.0 预留端点 [2026-04-17]
# 参考: https://a2a-protocol.org/latest/specification/ (v1.0.0, 2026-03-12)
# 现状: 仅暴露 AgentCard 供外部发现本项目的 agent 能力; Task/Message RPC 暂未实施
# 路线: 如需支持跨框架调用, 实施 JSON-RPC SendMessage/GetTask/CancelTask (见 TODO)
# ============================================================

def _build_agent_card():
    """返回符合 A2A Protocol v1.0 规范的 AgentCard JSON。
    字段参考: https://a2a-protocol.org/latest/specification/#agentcard
    注意: 当前为 stub, skills 暴露读性能力, Task RPC 尚未实现。
    """
    base_url = request.host_url.rstrip('/') if request else ''
    return {
        "name": "StockAnal Multi-Agent Analyst",
        "description": "14个专业Agent协同分析A股/港股/美股的投研系统: 技术/基本面/资金流/情绪/多空辩论/风险/决策/投资者人格",
        "url": f"{base_url}/a2a/v1",
        "version": "0.1.0-stub",
        "provider": {
            "organization": "StockAnal_Sys",
            "url": base_url or "https://github.com/",
        },
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["application/json", "text/event-stream"],
        "skills": [
            {
                "id": "stock-deep-analysis",
                "name": "股票深度分析",
                "description": "对给定股票代码执行多Agent协同分析, 返回投资决策/多空观点/风险评估",
                "tags": ["finance", "stock", "analysis"],
                "examples": ["分析 600519 贵州茅台", "research_depth=5 对 AAPL 做完整分析"],
            },
        ],
        "_stub": True,
        "_stub_note": "A2A Task/Message RPC尚未实施; 如需发起远程调用, 使用 /api/ai/agent-analyze (内部SSE)",
    }


@app.route('/.well-known/agent-card.json', methods=['GET'])
@validate_schema(A2aAgentCardSchema)  # BD-7: schema 覆盖率提升
def a2a_agent_card():
    """A2A v1.0 标准发现端点 (RFC 8615 well-known)。"""
    return jsonify(_build_agent_card())


@app.route('/.well-known/agent.json', methods=['GET'])
def a2a_agent_card_legacy():
    """A2A v0.2 兼容路径 (v0.3 起改为 agent-card.json, 此处提供向后兼容)。"""
    return jsonify(_build_agent_card())


@app.route('/a2a/v1', methods=['POST'])
@validate_schema(A2aJsonRpcSchema, source='json')  # BD-7: schema 覆盖率提升
def a2a_json_rpc():
    """A2A JSON-RPC 2.0 绑定端点 — 预留未实施。"""
    return jsonify({
        "jsonrpc": "2.0",
        "error": {
            "code": -32601,
            "message": "Method not implemented: A2A Task/Message RPC尚未实施",
            "data": {
                "stub": True,
                "supported_discovery": "/.well-known/agent-card.json",
                "internal_alternative": "/api/ai/agent-analyze (SSE)",
            },
        },
        "id": (request.get_json(silent=True) or {}).get('id'),
    }), 501


@app.route('/api/ai/agent-analyze', methods=['POST'])
@validate_schema(AiAgentAnalyzeSchema, source='json')  # S3-G1: schema 校验扩展
def ai_agent_analyze_stream():
    """Agent深度分析SSE端点 — 流式推送Agent执行过程"""
    from flask import Response, stream_with_context
    from app.core.event_bus import get_event_bus
    import queue
    import threading

    from app.core.conversation import get_conversation_manager

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'error': '请求体必须为有效的JSON格式'}), 400
    stock_code = data.get('stock_code', '')
    market_type = data.get('market_type', 'A')
    research_depth = data.get('research_depth', 3)
    conversation_id = data.get('conversation_id', '')
    # 前端 use-chat-stream 发 user_message 字段；保留 message 兜底
    user_message = (data.get('user_message') or data.get('message') or '').strip()

    if not stock_code:
        return jsonify({'error': '请提供股票代码'}), 400

    # 验证股票代码
    is_valid, validated_code = validate_stock_code(stock_code, market_type)
    if not is_valid:
        return jsonify({'error': validated_code}), 400
    stock_code = validated_code

    # 保存用户消息到 conversation，使后续 turn 能在 /api/ai/chat 加载历史
    conv_mgr = get_conversation_manager()
    if not conversation_id:
        conversation_id = conv_mgr.create_conversation(
            (user_message or f'分析 {stock_code}')[:20]
        )
    if user_message:
        conv_mgr.add_message(conversation_id, 'user', user_message)
    conv_mgr.add_stock_code(conversation_id, stock_code)

    def generate():
        import json as _json

        def emit(event_type, data):
            return f"event: {event_type}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

        # 创建SSE桥接队列
        event_bus = get_event_bus()
        bridge_queue = event_bus.create_sse_bridge()

        # 后台线程执行Agent分析
        result_holder = [None]
        error_holder = [None]

        def run_analysis():
            try:
                from app.agents.coordinator import run_agent_analysis
                result_holder[0] = run_agent_analysis(
                    stock_code=stock_code,
                    market_type=market_type,
                    research_depth=research_depth,
                    conversation_id=conversation_id,
                )
            except Exception as e:
                error_holder[0] = str(e)
            finally:
                # 发送结束信号
                bridge_queue.put(None)

        analysis_thread = threading.Thread(target=run_analysis, daemon=True)
        analysis_thread.start()

        try:
            # 从桥接队列读取事件并推送
            # FIX-E1+E3: 短超时循环 + SSE 注释心跳，避免中间代理切断；总时长 AGENT_TASK_MAX_DURATION_S（默认 2h）才视为真超时
            HEARTBEAT_INTERVAL = int(os.getenv('SSE_HEARTBEAT_INTERVAL_S', '15'))
            MAX_TOTAL = int(os.getenv('AGENT_TASK_MAX_DURATION_S', '7200'))
            start_ts = time.time()
            while True:
                try:
                    event = bridge_queue.get(timeout=HEARTBEAT_INTERVAL)
                    if event is None:
                        break
                    yield emit(event.get('event_type', 'info'), event.get('data', {}))
                except queue.Empty:
                    # SSE 注释行心跳（: 开头被客户端忽略），保活连接
                    yield f": heartbeat {int(time.time())}\n\n"
                    if time.time() - start_ts > MAX_TOTAL:
                        yield emit('error', {'code': 'TIMEOUT', 'message': f'分析超时（已超过{MAX_TOTAL}秒）'})
                        break
                    continue

            # 发送最终结果
            if error_holder[0]:
                yield emit('error', {'code': 'ANALYSIS_ERROR', 'message': error_holder[0]})
            elif result_holder[0]:
                result = result_holder[0]
                final_decision = result.get('final_decision', {})
                yield emit('artifact', {
                    'type': 'artifact',
                    'artifact_type': 'decision_card',
                    'title': f'{stock_code} 投资决策',
                    'data': final_decision
                })
                # 投资者共识 artifact（depth>=5 时可用）
                investor_consensus = result.get('investor_consensus')
                if investor_consensus:
                    yield emit('artifact', {
                        'type': 'artifact',
                        'artifact_type': 'investor_consensus',
                        'title': f'{stock_code} 投资者共识',
                        'data': investor_consensus
                    })
                # 投资者观点 artifact（depth>=5 时可用）
                investor_opinions = result.get('investor_opinions')
                if investor_opinions:
                    yield emit('artifact', {
                        'type': 'artifact',
                        'artifact_type': 'investor_opinions',
                        'title': f'{stock_code} 大师视角',
                        'data': investor_opinions
                    })
                # 保存 assistant 摘要到 conversation，供后续多轮对话加载上下文
                try:
                    fd = final_decision or {}
                    summary_parts = [f"[Agent深度分析-{stock_code}]"]
                    if fd.get('action'):
                        summary_parts.append(f"操作建议: {fd['action']}")
                    if fd.get('confidence') is not None:
                        summary_parts.append(f"置信度: {fd['confidence']}")
                    if fd.get('reasoning'):
                        summary_parts.append(f"理由: {str(fd['reasoning'])[:800]}")
                    if fd.get('bull_case'):
                        summary_parts.append(f"看多观点: {str(fd['bull_case'])[:400]}")
                    if fd.get('bear_case'):
                        summary_parts.append(f"看空观点: {str(fd['bear_case'])[:400]}")
                    summary_text = "\n".join(summary_parts)
                    conv_mgr.add_message(
                        conversation_id, 'assistant', summary_text,
                        artifacts=[{'artifact_type': 'decision_card', 'data': fd}]
                    )
                except Exception as _e:
                    app.logger.warning(f"agent-analyze 保存assistant消息失败: {_e}")

                yield emit('done', {
                    'stock_code': stock_code,
                    'conversation_id': conversation_id,
                    'execution_log': result.get('execution_log', []),
                    'follow_up_questions': [
                        f"对{stock_code}的技术面做更深入分析",
                        f"{stock_code}的投资者人格分析结果如何？",
                        f"对比{stock_code}与同行业龙头"
                    ]
                })
        finally:
            event_bus.destroy_sse_bridge(bridge_queue)

    return Response(
        stream_with_context(generate()),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


# ============================================================
# F3 P3 Domain REST API [NEW-FILE:#20260415-36] 2026-04-15 13:08 +08:00
# 暴露Registry的P3 domain (shipping/esg/corporate/jobs/satellite/alt_data)
# 调用链: Flask route -> AdapterRegistry.call_with_fallback(domain, method) -> artifact_wrapper.wrap_*
# 超时保护(20s), 参数校验400, 上游异常500, 错误响应 {success:false, error:...}
# ============================================================
def _p3_call_with_timeout(domain: str, method: str, timeout: int = 60, **kwargs):  # 2026-05-18 拉富足：P3 报告生成多步调用（技术分析+AI+数据源），原 20s 不足
    """统一封装 Registry 调用 + 超时保护。抛异常则向上传播。"""
    from concurrent.futures import TimeoutError as _FTimeout
    from app.adapters.adapter_registry import AdapterRegistry
    reg = AdapterRegistry.default()
    # BD-3: 改用全局线程池
    fut = _GLOBAL_THREAD_POOL.submit(reg.call_with_fallback, domain, method, **kwargs)
    return fut.result(timeout=timeout)


def _p3_call_soft(domain: str, method: str, timeout: int = 20, **kwargs):
    """[G2 B1/B2/B5 软降级] Registry 调用，所有异常(含全数据源空)静默返回 None。
    用于 P3 端点在上游真网络失败时仍返回 200 + 空 artifact 的契约保持场景。"""
    try:
        return _p3_call_with_timeout(domain, method, timeout=timeout, **kwargs)
    except Exception as e:
        app.logger.info(f"[_p3_call_soft] {domain}.{method} 软降级: {type(e).__name__}: {e}")
        return None


def _p3_error(message: str, status: int = 500, **extra):
    payload = {"success": False, "error": message}
    payload.update(extra)
    return custom_jsonify(payload), status


def _p3_ok(artifact: dict, **extra):
    payload = {"success": True, "artifact": artifact}
    payload.update(extra)
    return custom_jsonify(payload)


# ============================================================
# [DEDUP 2026-04-15 13:25 +08:00] 10 端点改调 wrap_*_v2 (唯一实现),
# 前后端 Artifact 字段契约严格对齐 (详见 F4 章节).
# ============================================================

# -------- Shipping --------
@app.route('/api/shipping/bdi', methods=['GET'])
@validate_schema(ShippingBdiSchema)  # S3-J(A): schema 校验扩展
def api_shipping_bdi():
    from app.core.artifact_wrapper import wrap_shipping_v2
    try:
        days = request.args.get('days', '30')
        try:
            days_i = int(days)
        except ValueError:
            return _p3_error("参数days必须为整数", 400)
        if days_i <= 0 or days_i > 365:
            return _p3_error("days范围应在[1,365]", 400)
        result = _p3_call_soft("commodity_shipping", "get_bdi_index", days=days_i)
        artifact = wrap_shipping_v2(stock_name="", bdi_df=result)
        artifact["artifact_type"] = "shipping_bdi"
        artifact["metadata"] = {"days": days_i, "domain": "shipping"}
        return _p3_ok(artifact)
    except Exception as e:
        app.logger.error(f"/api/shipping/bdi 失败: {e}")
        return _p3_error(str(e), 500)


@app.route('/api/shipping/port/<string:port>', methods=['GET'])
@validate_schema(ShippingPortSchema)  # S3-J(A): schema 校验扩展
def api_shipping_port(port: str):
    from app.core.artifact_wrapper import wrap_shipping_v2
    try:
        if not port or len(port) > 50:
            return _p3_error("port名称非法", 400)
        period = request.args.get('period', 'monthly')
        if period not in ('monthly', 'yearly', 'daily'):
            return _p3_error("period必须是monthly/yearly/daily", 400)
        result = _p3_call_soft(
            "commodity_shipping", "get_port_throughput", port=port, period=period
        )
        artifact = wrap_shipping_v2(stock_name="", port_df=result)
        artifact["artifact_type"] = "shipping_port"
        artifact["metadata"] = {"port": port, "period": period, "domain": "shipping"}
        return _p3_ok(artifact)
    except Exception as e:
        app.logger.error(f"/api/shipping/port/{port} 失败: {e}")
        return _p3_error(str(e), 500)


# -------- ESG --------
@app.route('/api/esg/<string:ticker>', methods=['GET'])
@validate_schema(EsgScoreSchema)  # S3-J(A): schema 校验扩展
def api_esg_score(ticker: str):
    from app.core.artifact_wrapper import wrap_esg_v2
    try:
        if not ticker or len(ticker) > 20:
            return _p3_error("ticker非法", 400)
        source = request.args.get('source', 'esgbook')
        result = _p3_call_with_timeout(
            "esg_rating", "get_esg_score", ticker=ticker, source=source
        )
        artifact = wrap_esg_v2(stock_name=ticker, scores=result or {})
        artifact["artifact_type"] = "esg_score"
        artifact["metadata"] = {"ticker": ticker, "source": source, "domain": "esg"}
        return _p3_ok(artifact)
    except Exception as e:
        app.logger.error(f"/api/esg/{ticker} 失败: {e}")
        return _p3_error(str(e), 500)


@app.route('/api/esg/climate/<string:cik>', methods=['GET'])
@validate_schema(ApiEsgClimateSchema)  # BD-7: schema 覆盖率提升
def api_esg_climate(cik: str):
    """EDGAR气候披露（通过 ESGAdapter.get_climate_disclosure）"""
    from app.core.artifact_wrapper import wrap_esg_v2
    try:
        if not cik or not cik.strip():
            return _p3_error("cik不能为空", 400)
        result = _p3_call_with_timeout(
            "esg_rating", "get_climate_disclosure", cik=cik
        )
        artifact = wrap_esg_v2(stock_name=cik, disclosures=result or {})
        artifact["artifact_type"] = "esg_climate"
        artifact["metadata"] = {"cik": cik, "domain": "esg"}
        return _p3_ok(artifact)
    except Exception as e:
        app.logger.error(f"/api/esg/climate/{cik} 失败: {e}")
        return _p3_error(str(e), 500)


# -------- Corporate --------
@app.route('/api/corporate/search', methods=['GET'])
@validate_schema(CorporateSearchSchema)  # S3-J(A): schema 校验扩展
def api_corporate_search():
    from app.core.artifact_wrapper import _build_p3_artifact
    try:
        q = request.args.get('q', '').strip()
        if not q:
            return _p3_error("参数q不能为空", 400)
        if len(q) > 100:
            return _p3_error("参数q过长", 400)
        result = _p3_call_soft(
            "corporate_entity", "search_company", name=q
        )
        # search_company 返回 pd.DataFrame (B3 修复: 统一转 list[dict])
        import pandas as _pd
        if isinstance(result, _pd.DataFrame):
            items = result.to_dict(orient="records") if not result.empty else []
        elif isinstance(result, list):
            items = result
        elif result is None:
            items = []
        else:
            items = (result or {}).get("items") or []
        artifact = _build_p3_artifact(
            artifact_type="corporate_search",
            title=f"企业搜索: {q}",
            data={"items": items, "count": len(items), "query": q},
            domain="corporate",
            confidence=0.75,
            metadata={"query": q},
        )
        return _p3_ok(artifact)
    except Exception as e:
        app.logger.error(f"/api/corporate/search 失败: {e}")
        return _p3_error(str(e), 500)


@app.route('/api/corporate/<path:company_id>/network', methods=['GET'])
@validate_schema(ApiCorporateNetworkSchema)  # BD-7: schema 覆盖率提升
def api_corporate_network(company_id: str):
    """[G2 B4] 改 <path:> 以允许 company_id 内含斜杠 (如 us_ca/SAMPLEID)。
    Flask 默认 <string:> 不匹配斜杠, 即使客户端 URL-encode %2F 也会被解码后截断。"""
    from app.core.artifact_wrapper import wrap_corporate_network_v2
    try:
        if not company_id:
            return _p3_error("company_id非法", 400)
        result = _p3_call_soft(
            "corporate_entity", "get_company_network", company_id=company_id
        )
        artifact = wrap_corporate_network_v2(stock_name=company_id, network=result or {})
        artifact["artifact_type"] = "corporate_network"
        artifact["metadata"] = {"company_id": company_id, "domain": "corporate"}
        return _p3_ok(artifact)
    except Exception as e:
        app.logger.error(f"/api/corporate/{company_id}/network 失败: {e}")
        return _p3_error(str(e), 500)


# -------- Jobs --------
@app.route('/api/jobs/search', methods=['GET'])
@validate_schema(JobsSearchSchema)  # S3-J(A): schema 校验扩展
def api_jobs_search():
    from app.core.artifact_wrapper import wrap_hiring_v2
    try:
        q = request.args.get('q', '').strip()
        if not q:
            return _p3_error("参数q不能为空", 400)
        try:
            limit = int(request.args.get('limit', '20'))
        except ValueError:
            return _p3_error("limit必须为整数", 400)
        if limit <= 0 or limit > 100:
            return _p3_error("limit范围应在[1,100]", 400)
        result = _p3_call_with_timeout(
            "hiring_signal", "search_jobs", query=q, limit=limit
        )
        artifact = wrap_hiring_v2(stock_name=q, postings_df=result)
        artifact["artifact_type"] = "jobs_search"
        artifact["metadata"] = {"query": q, "limit": limit, "domain": "jobs"}
        return _p3_ok(artifact)
    except Exception as e:
        app.logger.error(f"/api/jobs/search 失败: {e}")
        return _p3_error(str(e), 500)


@app.route('/api/jobs/company/<string:company>', methods=['GET'])
@validate_schema(JobsCompanySchema)  # S3-J(A): schema 校验扩展
def api_jobs_company(company: str):
    from app.core.artifact_wrapper import wrap_hiring_v2
    try:
        if not company or len(company) > 100:
            return _p3_error("company非法", 400)
        result = _p3_call_soft(
            "hiring_signal", "get_company_postings", company=company
        )
        artifact = wrap_hiring_v2(stock_name=company, postings_df=result)
        artifact["artifact_type"] = "jobs_company"
        artifact["metadata"] = {"company": company, "domain": "jobs"}
        return _p3_ok(artifact)
    except Exception as e:
        app.logger.error(f"/api/jobs/company/{company} 失败: {e}")
        return _p3_error(str(e), 500)


# -------- Satellite --------
@app.route('/api/satellite/search', methods=['GET'])
@validate_schema(SatelliteSearchSchema)  # S3-G1: schema 校验扩展
def api_satellite_search():
    from app.core.artifact_wrapper import wrap_satellite_artifact
    try:
        q = request.args.get('q', '').strip()
        if not q:
            return _p3_error("参数q不能为空", 400)
        result = _p3_call_with_timeout(
            "earth_observation", "search_datasets", keyword=q
        )
        artifact = wrap_satellite_artifact(result, keyword=q)
        return _p3_ok(artifact)
    except Exception as e:
        app.logger.error(f"/api/satellite/search 失败: {e}")
        return _p3_error(str(e), 500)


# -------- Alt Data Aggregate --------
@app.route('/api/alt_data/<string:ticker>', methods=['GET'])
@validate_schema(ApiAltDataSchema)  # BD-7: schema 覆盖率提升
def api_alt_data(ticker: str):
    """聚合另类数据: shipping(BDI) + esg + hiring + corporate. 部分失败不阻断。

    [N1 2026-04-15 15:18 +08:00] 修复:
      - P0: errors 记录 type+message+tried, 避免 details 空字符串
      - P1: stock_code 正确透传到 artifact
      - P1: 每个 domain 独立记录到 partial_errors/details, 无静默丢失
    """
    from app.core.artifact_wrapper import (
        wrap_shipping_v2, wrap_esg_v2, wrap_hiring_v2,
        wrap_alt_data_v2, _build_p3_artifact,
    )
    if not ticker or len(ticker) > 20:
        return _p3_error("ticker非法", 400)

    shipping = esg = hiring = corp = None
    errors = {}  # type: ignore[var-annotated]

    def _fmt_err(exc: Exception) -> str:
        """标准化错误消息: 含 type + message, 至少不空。"""
        msg = str(exc) if exc is not None else ""
        tname = type(exc).__name__ if exc is not None else "UnknownError"
        if not msg:
            msg = f"{tname}: <no message>"
        else:
            msg = f"{tname}: {msg}"
        return msg[:500]

    _subtasks = [
        ("shipping",  "commodity_shipping", "get_bdi_index",       {"days": 30}),
        ("esg",       "esg_rating",         "get_esg_score",       {"ticker": ticker}),
        ("hiring",    "hiring_signal",      "get_company_postings", {"company": ticker}),
        ("corporate", "corporate_entity",   "search_company",       {"name": ticker}),
    ]
    _results = {"shipping": None, "esg": None, "hiring": None, "corporate": None}
    for key, domain, method, kw in _subtasks:
        try:
            _alt_data_timeout = float(os.getenv('ALT_DATA_SUBTASK_TIMEOUT', '45'))
            _results[key] = _p3_call_with_timeout(domain, method, timeout=_alt_data_timeout, **kw)  # 由 ALT_DATA_SUBTASK_TIMEOUT 驱动
        except Exception as e:
            errors[key] = _fmt_err(e)
            app.logger.info(f"[alt_data] {key}({domain}.{method}) 失败: {errors[key]}")
    shipping = _results["shipping"]
    esg      = _results["esg"]
    hiring   = _results["hiring"]
    corp     = _results["corporate"]

    # 4域全败 → 502 + 完整 details (每个 domain 至少有 type+msg, 不空串)
    if all(v is None for v in (shipping, esg, hiring, corp)):
        # 确保 4 个 domain 都在 details 中 (若某域既无异常也返回 None, 补占位)
        for k in ("shipping", "esg", "hiring", "corporate"):
            if k not in errors or not errors[k]:
                errors[k] = "Unknown: 返回空且未抛异常"
        return _p3_error("所有另类数据源均失败", 502, details=errors)

    # 各子域 adapter 原始结果 → v2 包装 dict → wrap_alt_data_v2 聚合
    shipping_wrapped = wrap_shipping_v2(stock_name=ticker, bdi_df=shipping) if shipping is not None else None
    esg_wrapped = wrap_esg_v2(stock_name=ticker, scores=esg if isinstance(esg, dict) else {}) if esg is not None else None
    hiring_wrapped = wrap_hiring_v2(stock_name=ticker, postings_df=hiring) if hiring is not None else None
    # corporate: search_company 返回 list, 转为最小 corporate 子域 dict (company_name 用首条)
    corp_wrapped = None
    if corp is not None:
        import pandas as _pd_alt
        if isinstance(corp, _pd_alt.DataFrame):
            corp_items = corp.to_dict(orient="records") if not corp.empty else []
        elif isinstance(corp, list):
            corp_items = corp
        else:
            corp_items = []
        first = corp_items[0] if corp_items else {}
        corp_wrapped = {
            "data": {
                "company_id": first.get("company_number", ""),
                "company_name": first.get("name", ticker),
                "jurisdiction_code": first.get("jurisdiction_code", ""),
                "incorporation_date": "",
                "current_status": "",
                "parents": [],
                "children": [],
                "officers": [],
                "opencorporates_url": "",
                "search_results": corp_items,
            }
        }

    aggregated = wrap_alt_data_v2(
        stock_name=ticker,
        stock_code=ticker,
        shipping=shipping_wrapped,
        esg=esg_wrapped,
        hiring=hiring_wrapped,
        corporate=corp_wrapped,
    )
    filled = sum(1 for v in (shipping_wrapped, esg_wrapped, hiring_wrapped, corp_wrapped) if v)
    # [N1] 4 domain 均进入 data (失败/空值 → None 占位, 前端可明确感知)
    for k in ("shipping", "esg", "hiring", "corporate"):
        if k not in aggregated.get("data", {}):
            aggregated.setdefault("data", {})[k] = None
    # 补充 F3 兼容元数据字段
    aggregated["artifact_type"] = "alt_data_aggregate"
    aggregated["metadata"] = {
        "ticker": ticker, "coverage": f"{filled}/4", "domain": "alt_data",
        "partial_errors": errors if errors else None,
    }
    aggregated["confidence"] = 0.60
    aggregated["sources"] = [{"name": "聚合:航运+ESG+招聘+企业", "type": "另类数据"}]
    return _p3_ok(aggregated, partial_errors=errors if errors else None)


# ============================================================
# K3 健康检查 + 监控端点 [NEW-FILE:#20260415-49 2026-04-15 14:32 +08:00]
# /health           基础存活 (docker HEALTHCHECK / nginx upstream)
# /api/adapters/status  22 adapter 逐一 health_check (5s/每个)
# /api/registry/stats   16 domain 注册映射 + 可用实例计数
# ============================================================

# 22 Adapter 清单 (与 adapter_registry.DEFAULT_DOMAIN_MAP 对齐)
_ADAPTER_SPECS = [
    ("AkshareAdapter",       "app.adapters.akshare_adapter"),
    ("BaostockAdapter",      "app.adapters.baostock_adapter"),
    ("EfinanceAdapter",      "app.adapters.efinance_adapter"),
    ("YFinanceAdapter",      "app.adapters.yfinance_adapter"),
    ("EDGARAdapter",         "app.adapters.edgar_adapter"),
    ("NBSAdapter",           "app.adapters.nbs_adapter"),
    ("FREDAdapter",          "app.adapters.fred_adapter"),
    ("CCXTAdapter",          "app.adapters.ccxt_adapter"),
    ("CoinGeckoAdapter",     "app.adapters.coingecko_adapter"),
    ("WorldBankAdapter",     "app.adapters.worldbank_adapter"),
    ("IMFAdapter",           "app.adapters.imf_adapter"),
    ("OpenCLIBridge",        "app.adapters.opencli_bridge"),
    ("OpenBBAdapter",        "app.adapters.openbb_adapter"),
    ("AshareAdapter",        "app.adapters.ashare_adapter"),
    ("EasyquotationAdapter", "app.adapters.easyquotation_adapter"),
    ("RSSNewsAdapter",       "app.adapters.rss_news_adapter"),
    ("ESGAdapter",           "app.adapters.esg_adapter"),
    ("ShippingAdapter",      "app.adapters.shipping_adapter"),
    ("SatelliteAdapter",     "app.adapters.satellite_adapter"),
    ("CorporateAdapter",     "app.adapters.corporate_adapter"),
    ("JobsAdapter",          "app.adapters.jobs_adapter"),
]


def _hc_one(cls_name: str, mod_path: str, timeout_s: float = 5.0) -> dict:
    """单 adapter 健康检查. 永不抛, 返回 {ok,msg,latency_ms}."""
    import importlib
    import time as _tm
    t0 = _tm.time()
    try:
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, cls_name, None)
        if cls is None:
            return {"ok": False, "msg": f"class {cls_name} not found", "latency_ms": 0}
        inst = cls()
        # health_check 可能自身很慢; 这里不强制线程超时 (test_client 友好),
        # 交由 adapter 内部超时或由调用方整体超时控制
        ok = False
        try:
            ok = bool(inst.health_check())
            msg = "ok" if ok else "health_check returned False"
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
        latency = int((_tm.time() - t0) * 1000)
        return {"ok": ok, "msg": msg, "latency_ms": latency}
    except Exception as e:
        return {"ok": False, "msg": f"{type(e).__name__}: {e}",
                "latency_ms": int((_tm.time() - t0) * 1000)}


@app.route('/api/stock_quote_batch', methods=['GET'])
@validate_schema(StockQuoteBatchSchema)  # S3-D3: schema 校验扩展
@cache.cached(timeout=60, query_string=True)
def stock_quote_batch():
    """
    FIX-E5: 批量轻量行情接口
    Input: codes=600519,000001,...  market_type=A|HK|US
    Output: {results: [{code, name, latest_price, change_pct, change}], errors: [{code, msg}], ts}
    思路: 复用 analyzer.get_stock_data 取最近 7 天 K 线, 用末两行 close 计算 change_pct;
          单只硬超时 8s; 批量并发上限 8; 总响应应 <5s.
    """
    codes_raw = request.args.get('codes', '').strip()
    market_type = request.args.get('market_type', 'A')
    if not codes_raw:
        return custom_jsonify({'error': '请提供 codes 参数 (逗号分隔)'}), 400

    codes = [c.strip() for c in codes_raw.split(',') if c.strip()]
    if not codes:
        return custom_jsonify({'error': 'codes 解析为空'}), 400
    # [REAL-01 2026-05-18] 提升上限到 100；超过 100 直接拒绝；支持 max_codes 客户端限批
    if len(codes) > 100:
        return custom_jsonify({'error': 'codes 最多 100 个'}), 400
    try:
        max_codes = int(request.args.get('max_codes', '100'))
    except ValueError:
        max_codes = 100
    if max_codes > 0 and len(codes) > max_codes:
        codes = codes[:max_codes]

    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FTimeout, as_completed
    end_date = now_cn().strftime('%Y%m%d')
    start_date = (now_cn() - timedelta(days=14)).strftime('%Y%m%d')

    def _fetch_one(code):
        try:
            valid, normalized = validate_stock_code(code, market_type)
            if not valid:
                return {'code': code, 'error': str(normalized)}
            df = analyzer.get_stock_data(normalized, market_type, start_date, end_date)
            if df is None or getattr(df, 'empty', True):
                return {'code': normalized, 'error': 'no data'}
            # 取末两根 close
            closes = df['close'].dropna().tolist() if 'close' in df.columns else []
            if not closes:
                return {'code': normalized, 'error': 'no close'}
            latest = float(closes[-1])
            prev = float(closes[-2]) if len(closes) > 1 else latest
            change = latest - prev
            change_pct = safe_change_pct(latest, prev) or 0.0
            name = _get_stock_name_safe(normalized, market_type)
            return {
                'code': normalized,
                'name': name,
                'latest_price': round(latest, 4),
                'change': round(change, 4),
                'change_pct': round(change_pct, 4),
            }
        except Exception as e:
            return {'code': code, 'error': f'{type(e).__name__}: {e}'}

    results = []
    errors = []
    # [REAL-01 2026-05-18] 用 try/except 包裹 as_completed，超时立即返回已完成部分
    # [REAL-01 2026-05-18] 并发上限 20（原 8），整体 25s 超时（原 20s）
    # [BD-3] 使用全局线程池
    ex = get_global_thread_pool()
    try:
        future_map = {ex.submit(_fetch_one, c): c for c in codes}
        try:
            for fut in as_completed(future_map, timeout=25):
                try:
                    r = fut.result(timeout=1)
                    if 'error' in r:
                        errors.append({'code': r.get('code'), 'msg': r['error']})
                    else:
                        results.append(r)
                except _FTimeout:
                    errors.append({'code': future_map[fut], 'msg': 'timeout'})
                except Exception as e:
                    errors.append({'code': future_map[fut], 'msg': str(e)})
        except _FTimeout:
            # as_completed 整体超时，把剩余未完成 future 标记 timeout
            for fut, code in future_map.items():
                if not fut.done():
                    errors.append({'code': code, 'msg': 'overall-timeout'})
    finally:
        pass  # BD-3: 全局池不 shutdown

    return custom_jsonify({
        'results': results,
        'errors': errors,
        'ts': int(time.time()),
    }), 200


@app.route('/health', methods=['GET'])
@validate_schema(HealthBasicSchema)  # BD-7: schema 覆盖率提升
def health_basic():
    """轻量存活探针 — 返回 200 + uptime + version. <100ms."""
    return jsonify({
        "status": "ok",
        "uptime_s": round(time.time() - START_TIME, 3),
        "version": APP_VERSION,
        "ts": int(time.time()),
    }), 200


# ── S3-K: health_deep check 函数（模块级，便于 patch）─────────────────────────
def _hd_check_sqlite() -> dict:
    """SELECT 1 to langgraph checkpoint db（模块级，供 health_deep 调用及测试 patch）"""
    import sqlite3 as _sq3
    try:
        db_dir = os.path.join(os.path.dirname(__file__), '../../data')
        db_path = os.path.join(db_dir, 'langgraph_checkpoint.db')
        t0 = time.monotonic()
        conn = _sq3.connect(db_path, timeout=1.0)
        conn.execute('SELECT 1')
        conn.close()
        return {'ok': True, 'latency_ms': round((time.monotonic() - t0) * 1000, 2)}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:200]}


def _hd_check_akshare() -> dict:
    """AkshareAdapter.health_check 封装（模块级，供 health_deep 调用及测试 patch）"""
    try:
        from app.adapters.akshare_adapter import AkshareAdapter
        adapter = AkshareAdapter()
        t0 = time.monotonic()
        result = adapter.health_check()
        latency = round((time.monotonic() - t0) * 1000, 2)
        ok = result.get('status') == 'ok' if isinstance(result, dict) else bool(result)
        info: dict = {'ok': ok, 'latency_ms': latency}
        if isinstance(result, dict) and 'probe_symbol' in result:
            info['source'] = result.get('probe_symbol', 'stock_individual_spot_xq')
        return info
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:200]}


def _hd_check_llm() -> dict:
    """LLM 客户端可创建性 check（MOCK_LLM=1 时跳过，模块级）"""
    if os.getenv('MOCK_LLM', '0') == '1':
        return {'ok': True, 'skipped': True, 'reason': 'MOCK_LLM=1'}
    try:
        from app.core.ai_client import get_ai_client
        t0 = time.monotonic()
        _ = get_ai_client()
        return {'ok': True, 'latency_ms': round((time.monotonic() - t0) * 1000, 2), 'skipped': False}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:200]}


def _hd_check_market_cache() -> dict:
    """market_indices_cache 新鲜度 check（模块级）"""
    cache_ts = _market_indices_cache.get('ts', 0)
    ttl = int(os.getenv('INDEX_CACHE_TTL_S', '30'))
    age_s = round(time.time() - cache_ts, 1) if cache_ts else None
    has_data = bool(_market_indices_cache.get('data'))
    ok = has_data and (age_s is not None) and (age_s < ttl)
    return {'ok': ok, 'age_s': age_s, 'ttl_s': ttl, 'has_data': has_data}


def _hd_check_wind() -> dict:
    """Wind adapter health_check 封装（模块级，供 health_deep 调用）
    检查 Wind API key 配置状态与 adapter 可用性（0 积分）
    """
    try:
        from app.adapters.wind_adapter import WindAdapter
        adapter = WindAdapter()
        t0 = time.monotonic()
        result = adapter.health_check()
        latency = round((time.monotonic() - t0) * 1000, 2)

        # Wind adapter health_check 返回 bool（有 key 为 True，无 key 为 False）
        ok = bool(result)
        info: dict = {
            'ok': ok,
            'latency_ms': latency,
            'enabled': ok,  # 与 health_check 语义对齐
        }
        if not ok:
            info['reason'] = 'WIND_API_KEY not configured'
        return info
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:200]}


def _hd_check_daemon_threads() -> dict:
    """守护线程存活性检查（BD-8）
    检查已知的 5 个守护线程是否存活（_preload_stock_names/_preload_profiles/_preload_market_indices/chat_worker/analysis_worker）
    """
    import threading
    all_threads = threading.enumerate()
    daemon_threads = [t for t in all_threads if t.daemon]

    # 已知后台预热线程名称模式
    known_daemons = {
        'stock_names': lambda t: '_preload_stock_names' in t.name or 'stock_names' in t.name,
        'profiles': lambda t: '_preload_profiles' in t.name or 'profiles' in t.name,
        'market_indices': lambda t: '_preload_market_indices' in t.name or 'market_indices' in t.name,
        'chat_worker': lambda t: 'chat_worker' in t.name or '_chat_worker' in t.name,
        'analysis_worker': lambda t: 'analysis' in t.name and 'run_analysis' in str(t),
    }

    alive_daemons = {}
    for key, pred in known_daemons.items():
        matches = [t for t in daemon_threads if pred(t)]
        alive_daemons[key] = len(matches)

    total_daemons = len(daemon_threads)
    ok = total_daemons > 0  # 至少有一个守护线程存活

    return {
        'ok': ok,
        'total_daemon_threads': total_daemons,
        'known_daemons': alive_daemons,
    }


@app.route('/api/health/deep', methods=['GET'])
def health_deep():
    """深度健康检查 — sqlite / akshare / llm / market_indices_cache / daemon_threads / wind（S3-G2 Hunt5-M; BD-8; WM-4）
    Input: 无必需参数
    Output: JSON {status, uptime_s, version, checks:{sqlite,akshare,llm,market_indices_cache,daemon_threads,wind}}
    Pos: 可观测性探针，PUBLIC_PATHS 白名单，总超时 ≤ 3s

    S3-K 修复：改为手动管理 pool（shutdown(wait=False)），每个 future 独立 try/except
    TimeoutError + Exception，确保任何情况下返回 HTTP 200（degraded），不冒泡 500。
    BD-8: 新增 daemon_threads 检查，统计后台线程存活状态。
    WM-4: 新增 wind 检查，验证 Wind adapter 配置与可用性（0 积分）。
    """
    from concurrent.futures import ThreadPoolExecutor as _TPE, TimeoutError as _FutTimeout

    started = time.monotonic()
    checks: dict = {}
    _DEEP_TIMEOUT = float(os.getenv('HEALTH_DEEP_TIMEOUT_S', '3.0'))

    check_fns: dict = {
        'sqlite': _hd_check_sqlite,
        'akshare': _hd_check_akshare,
        'llm': _hd_check_llm,
        'market_indices_cache': _hd_check_market_cache,
        'daemon_threads': _hd_check_daemon_threads,  # BD-8: 守护线程监控
        'wind': _hd_check_wind,  # WM-4: Wind adapter 配置检查（0 积分）
    }

    # 手动管理 pool：避免 with 语句的 __exit__ shutdown(wait=True) 在 TimeoutError 时挂死
    pool = _TPE(max_workers=4, thread_name_prefix='health_deep')
    try:
        futures = {pool.submit(fn): name for name, fn in check_fns.items()}
        deadline = started + _DEEP_TIMEOUT

        for fut, name in futures.items():
            remaining = max(0.05, deadline - time.monotonic())
            try:
                checks[name] = fut.result(timeout=remaining)
            except _FutTimeout:
                checks[name] = {
                    'ok': False,
                    'timeout': True,
                    'message': f'check exceeded {remaining:.2f}s deadline',
                }
                fut.cancel()
            except Exception as exc:
                checks[name] = {'ok': False, 'error': True, 'message': str(exc)[:200]}
    finally:
        # cancel_futures=True 取消排队任务；wait=False 不等待正在执行的线程，确保立即返回
        pool.shutdown(wait=False, cancel_futures=True)

    # 填补极端情况下未收到结果的 check 项
    for name in check_fns:
        if name not in checks:
            checks[name] = {'ok': False, 'timeout': True, 'message': 'overall deadline exceeded'}

    overall_ok = all(c.get('ok') is True or c.get('skipped') is True for c in checks.values())
    status = 'ok' if overall_ok else 'degraded'

    return jsonify({
        'status': status,
        'uptime_s': round(time.time() - START_TIME, 3),
        'version': APP_VERSION,
        'checks': checks,
        'elapsed_ms': int((time.monotonic() - started) * 1000),
    }), 200


@app.route('/api/metrics', methods=['GET'])
@validate_schema(GetMetricsSchema)  # BD-7: schema 覆盖率提升
def get_metrics():
    """基础请求计数器快照（S3-G4 Hunt5-M）
    Input: 无必需参数
    Output: JSON {uptime_s, requests_total, requests_by_status, top_paths, errors_total, error_rate}
    Pos: 可观测性端点，PUBLIC_PATHS 白名单，只读 _METRICS 快照
    """
    with _METRICS_LOCK:
        snap = {
            'requests_total': _METRICS['requests_total'],
            'requests_by_status': dict(_METRICS['requests_by_status']),
            'requests_by_path': dict(_METRICS['requests_by_path']),
            'errors_total': _METRICS['errors_total'],
        }

    total = snap['requests_total']
    errors = snap['errors_total']
    error_rate = round(errors / total, 4) if total > 0 else 0.0

    # top_paths: 按计数降序，取 top 10
    sorted_paths = sorted(snap['requests_by_path'].items(), key=lambda x: x[1], reverse=True)
    top_paths = [[p, c] for p, c in sorted_paths[:10]]

    return jsonify({
        'uptime_s': round(time.time() - START_TIME, 3),
        'requests_total': total,
        'requests_by_status': snap['requests_by_status'],
        'top_paths': top_paths,
        'errors_total': errors,
        'error_rate': error_rate,
    }), 200


# ============================ Wind 运维端点（2026-07-09）============================

@app.route('/api/wind/quota', methods=['GET'])
def api_wind_quota():
    """Wind 配额查询（运维监控）。

    Input: 无
    Output: {remaining: {S/A/B}, total: {S/A/B}, date: str, percentage: {S/A/B}}
    Pos: 运维监控端点，不消耗配额
    """
    try:
        from app.core.wind_budget import WindQuota
        q = WindQuota()
        remaining = q.remaining()

        # 读取配额总量
        total = {
            'S': int(os.getenv('WIND_QUOTA_S', '50')),
            'A': int(os.getenv('WIND_QUOTA_A', '30')),
            'B': int(os.getenv('WIND_QUOTA_B', '20'))
        }

        # 计算剩余百分比
        percentage = {
            tier: round(remaining[tier] / total[tier] * 100, 1)
            for tier in ['S', 'A', 'B']
        }

        return api_ok({
            'remaining': remaining,
            'total': total,
            'date': now_cn().strftime('%Y-%m-%d'),
            'percentage': percentage
        })
    except Exception as e:
        return api_error('INTERNAL', 'Wind 配额查询失败', details=str(e))


@app.route('/api/wind/tools', methods=['GET'])
def api_wind_tools():
    """列出 Wind 可用工具（调试用）。

    Input: 无
    Output: {tools: [{name, description}], count: int}
    Pos: 调试端点，不消耗配额
    """
    try:
        from app.adapters.wind_adapter import WindAdapter
        adapter = WindAdapter()
        tools = adapter.list_available_tools()

        return api_ok({
            'tools': [
                {
                    'name': t['name'],
                    'description': t.get('description', 'N/A')[:100]  # 截断长描述
                }
                for t in tools
            ],
            'count': len(tools)
        })
    except Exception as e:
        return api_error('INTERNAL', 'Wind tools/list 失败', details=str(e))


@app.route('/api/openapi.json', methods=['GET'])
@validate_schema(GetOpenapiSpecSchema)  # BD-7: schema 覆盖率提升
def get_openapi_spec():
    """暴露 OpenAPI 3.0 spec（S3-C3 Hunt5-Major）
    Input: 无
    Output: OpenAPI 3.0 JSON（10 个核心路由）
    Pos: API 文档契约端点，Swagger UI 可直接消费
    """
    from flask import make_response
    import json as _json
    resp = make_response(_json.dumps(OPENAPI_SPEC, ensure_ascii=False, indent=2))
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp


@app.route('/api/adapters/status', methods=['GET'])
@validate_schema(AdaptersStatusSchema)  # S3-G1: schema 校验扩展
def adapters_status():
    """遍历所有 adapter 调用 health_check, 返回逐个健康状态.
    2026-05-18 B1 修复：原串行循环最多 22×5s=110s 导致端点 HANG；
    改为 ThreadPoolExecutor 并行，每个 future 独立 timeout=5s，整体 10s 内必返回。
    超时的 adapter 标记 degraded，不阻塞整体响应。
    2026-05-19 B9 修复：with ThreadPoolExecutor 的 __exit__ 调用 shutdown(wait=True)；
    当 as_completed 超时抛 TimeoutError 时，__exit__ 会等待所有未完成 future（包括
    BaostockAdapter.health_check → bs.login() 无限阻塞），导致端点永久 HANG。
    改为 try/finally 手动管理 pool，finally 用 shutdown(wait=False, cancel_futures=True)
    确保超时后立即返回，不等待阻塞中的线程。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as _FutTimeout

    total = len(_ADAPTER_SPECS)
    results: dict = {}

    _overall_timeout = float(os.getenv('ADAPTERS_STATUS_OVERALL_TIMEOUT', '10'))
    _per_call_timeout = float(os.getenv('ADAPTERS_STATUS_PER_CALL_TIMEOUT', '5'))
    # 并行执行所有 adapter 健康检查，整体超时由 ADAPTERS_STATUS_OVERALL_TIMEOUT 驱动
    # [BD-3] 使用全局线程池
    pool = get_global_thread_pool()
    try:
        future_map = {
            pool.submit(_hc_one, cls_name, mod_path, _per_call_timeout): cls_name
            for cls_name, mod_path in _ADAPTER_SPECS
        }
        try:
            for fut in as_completed(future_map, timeout=_overall_timeout):
                cls_name = future_map[fut]
                try:
                    results[cls_name] = fut.result(timeout=0)  # result 已就绪，立即取
                except _FutTimeout:
                    results[cls_name] = {"ok": False, "latency_ms": None, "error": "timeout", "status": "degraded"}
                except Exception as exc:
                    results[cls_name] = {"ok": False, "latency_ms": None, "error": str(exc), "status": "degraded"}
        except _FutTimeout:
            # as_completed 整体超时：未收集到的 future 在下面补 degraded
            pass
    finally:
        pass  # BD-3: 全局池不 shutdown（任务会在全局池中自然完成或超时）

    # as_completed 超过 overall_timeout 后未完成的 future 不会出现在结果中，补上 degraded
    for cls_name, _ in _ADAPTER_SPECS:
        if cls_name not in results:
            results[cls_name] = {"ok": False, "latency_ms": None, "error": "overall_timeout", "status": "degraded"}

    ok_count = sum(1 for r in results.values() if r.get("ok"))
    return jsonify({
        "status": "ok",
        "total": total,
        "healthy": ok_count,
        "unhealthy": total - ok_count,
        "adapters": results,
        "ts": int(time.time()),
    }), 200


@app.route('/api/registry/stats', methods=['GET'])
@validate_schema(RegistryStatsSchema)  # S3-G1: schema 校验扩展
def registry_stats():
    """AdapterRegistry 16 domain × adapter 注册表快照 (轻量, 只查字典)."""
    try:
        from app.adapters.adapter_registry import AdapterRegistry
        reg = AdapterRegistry.default()
        default_map = AdapterRegistry.DEFAULT_DOMAIN_MAP
        domains_info = []
        for dname, specs in default_map.items():
            instances = reg.get_adapters(dname)
            inst_names = [a.name for a in instances]
            domains_info.append({
                "name": dname,
                "configured": specs,
                "configured_count": len(specs),
                "available": inst_names,
                "available_count": len(inst_names),
                "first_available": inst_names[0] if inst_names else None,
            })
        status_snapshot = reg.get_status()
        return jsonify({
            "status": "ok",
            "domain_count": len(default_map),
            "domains": domains_info,
            "fail_count": status_snapshot.get("fail_count", {}),
            "ts": int(time.time()),
        }), 200
    except Exception as e:
        app.logger.error(f"/api/registry/stats 失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# 在应用启动时启动清理线程
if _startup_background_enabled():
    cleaner_thread = threading.Thread(target=run_task_cleaner)
    cleaner_thread.daemon = True
    cleaner_thread.start()

# ── S3-A4 API v1 版本前缀 alias（2026-05-20）────────────────────────────────
# 批量注册 /api/v1/<path> → /api/<path> 别名，不破坏现有路由
# 采用 add_url_rule，原因：Flask 不允许直接修改 request.path

def _register_v1_aliases() -> None:
    """将所有 /api/* 路由批量注册为 /api/v1/* 别名。

    在所有路由注册完毕后调用（模块加载末尾）。
    """
    registered = 0
    skipped = 0
    for rule in list(app.url_map.iter_rules()):
        if not rule.rule.startswith('/api/'):
            continue
        if rule.rule.startswith('/api/v1/'):
            continue
        rest = rule.rule[len('/api/'):]
        new_rule = f'/api/v1/{rest}'
        new_endpoint = f'v1_{rule.endpoint}'
        if new_endpoint in app.view_functions:
            skipped += 1
            continue
        original_func = app.view_functions.get(rule.endpoint)
        if original_func is None:
            skipped += 1
            continue
        try:
            app.add_url_rule(
                new_rule,
                endpoint=new_endpoint,
                view_func=original_func,
                methods=list(rule.methods or ['GET']),
            )
            registered += 1
        except Exception as exc:
            app.logger.warning(f"v1 alias skip {new_rule}: {exc}")
            skipped += 1
    app.logger.info(f"[S3-A4] /api/v1/* alias 注册完成：{registered} 条，跳过 {skipped} 条")


_register_v1_aliases()

# 启动时后台预加载A股名称缓存，避免首次请求时名字降级为代码
# [2026-05-29 后台预热] 由一次性调用改为循环重试预热：首发加载若超时/失败，
#   _load_stock_name_cache 内部冷却窗会节流；本线程按冷却窗节流轮询直到加载成功即止，
#   避免常驻烧资源。请求线程已改为只读缓存，全量加载完全交由本后台线程负责。
def _preload_stock_names():
    """后台预热线程：循环重试 _load_stock_name_cache() 直到成功，加载成功即退出。

    Input : 无（沿用 _startup_background_enabled 离线/测试门控，DISABLE_NETWORK=1 时不启动）
    Output: 无返回值；填充 _STOCK_NAME_CACHE，成功后线程自然结束
    Pos   : 启动期后台预热注册点；接管原请求线程的全量加载职责，使前台永不阻塞
    """
    # 首次等少许时间让端口绑定/导入完成（参考 market indices 预热风格）
    time.sleep(0.5)
    _cooldown_s = float(os.getenv('STOCK_NAME_CACHE_RETRY_COOLDOWN_S', '60'))
    while not _CACHE_LOADED:
        try:
            _load_stock_name_cache()  # 内部已含超时 + 冷却窗节流 + 成功标记
        except Exception as e:  # noqa: BLE001 - 后台线程兜底，绝不让异常杀死预热
            app.logger.warning(f"A股名称缓存后台预热异常: {e}")
        if _CACHE_LOADED:
            break
        # 未加载成功（超时/异常/处于冷却窗）：按冷却窗节流后重试
        time.sleep(max(1.0, _cooldown_s))


# 离线环境名称字典冷启动逻辑（模块级执行，需在 Flask app 初始化之前）
_offline_logger = logging.getLogger(__name__)

if _startup_background_enabled():
    # 联网环境：启动后台循环预热线程
    _preload_thread = threading.Thread(target=_preload_stock_names, daemon=True)
    _preload_thread.start()
else:
    # 离线环境：同步加载本地字典填充缓存（一次性）
    try:
        snapshot = _load_stock_name_snapshot()
        if snapshot:
            with _STOCK_NAME_CACHE_LOCK:
                _STOCK_NAME_CACHE.update(snapshot)
            _offline_logger.info(f"离线环境已加载本地股票名称字典，共 {len(snapshot)} 条")
    except Exception as e:
        _offline_logger.warning(f"离线环境加载本地名称字典失败: {e}")

# 预热 /api/stock_profile 常用股票，避免首次访问compare/dashboard时等待baostock
def _preload_profiles():
    import time as _t
    _t.sleep(3)  # 等A股名称缓存先加载
    common = ['600519', '000858', '300750', '000001', '300059', '688981']
    for code in common:
        try:
            with app.test_request_context(f'/api/stock_profile?stock_code={code}'):
                api_stock_profile()
        except Exception as e:
            app.logger.warning(f"预热profile失败 {code}: {e}")
    app.logger.info(f"profile预热完成: {common}")

if _startup_background_enabled():
    threading.Thread(target=_preload_profiles, daemon=True).start()

# M1/M2 启动预热 + 定时刷新：每 INDEX_REFRESH_INTERVAL_S 秒刷新一次缓存
# B23: 从一次性预热改为定时循环刷新，避免缓存 30s TTL 过期后请求出现 17s 延迟
def _preload_market_indices():
    # 首次等 0.5s 让端口绑定完成
    time.sleep(0.5)
    _refresh_interval = int(os.getenv('INDEX_REFRESH_INTERVAL_S', '25'))

    while True:
        try:
            data = _fetch_market_indices_data()
            if data.get('indices'):
                app.logger.info(f"指数缓存刷新完成: source={data.get('source')} count={len(data['indices'])}")
            else:
                app.logger.warning("指数缓存刷新返回空数据")
        except Exception as e:
            app.logger.warning(f"指数缓存刷新异常: {e}")

        # 等待下次刷新（缓存 TTL 30s，刷新间隔 25s，确保缓存始终有效）
        time.sleep(_refresh_interval)

if _startup_background_enabled():
    threading.Thread(target=_preload_market_indices, daemon=True).start()

if __name__ == '__main__':
    # 强制禁用Flask的调试模式，以确保日志配置生效
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", "8888")), debug=False)
