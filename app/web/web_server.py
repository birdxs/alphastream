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
from flask import Flask, render_template, request, jsonify, redirect, url_for
from app.analysis.stock_analyzer import StockAnalyzer
from app.analysis.us_stock_service import USStockService
import threading
import logging
from logging.handlers import RotatingFileHandler
import traceback
import os
import json
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
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

# ── Sprint 1-B 工具函数 ──────────────────────────────────────────────────────

# S1-B3: 时区感知时间工具（Hunt5-C1）
# Asia/Shanghai = UTC+8，与 Asia/Singapore 相同偏移
ASIA_SHANGHAI = timezone(timedelta(hours=8))


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

# ── 安全配置 ────────────────────────────────────────────────────────────────
# SECRET_KEY：Flask session / CSRF 签名所需；生产必须通过 SECRET_KEY env 设置
import secrets as _secrets
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or _secrets.token_hex(32)
app.config['WTF_CSRF_TIME_LIMIT'] = int(os.getenv('WTF_CSRF_TIME_LIMIT', '3600'))
# WTF_CSRF_CHECK_DEFAULT=False：允许我们仅对 SPA 路由做 CSRF exempt（API key 路由已鉴权）
app.config['WTF_CSRF_CHECK_DEFAULT'] = False

# CSRF 保护（Flask-WTF）
from flask_wtf.csrf import CSRFProtect, generate_csrf
csrf = CSRFProtect(app)

# 鉴权中间件
from app.web.auth_middleware import check_api_key, is_auth_required, get_api_key as _get_api_key, PUBLIC_PATHS

# ── 全局 before_request 鉴权门 ───────────────────────────────────────────────
@app.before_request
def global_auth_gate():
    """所有请求经过此门；PUBLIC_PATHS + /static 无需鉴权，其余必须携带 X-API-Key"""
    path = request.path
    # 静态资源、Swagger UI、页面路由不鉴权
    if (path.startswith('/static')
            or path.startswith('/api/docs')
            or path in PUBLIC_PATHS
            or any(path.startswith(p) for p in ('/stock_detail/', '/api/docs'))):
        return None
    return check_api_key()


# ── CSRF token 端点（SPA 调用此接口获取 token）───────────────────────────────
@app.route('/api/csrf_token', methods=['GET'])
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
CORS(app, resources={r"/api/*": {"origins": allowed_origins + _DEV_ORIGIN_PATTERNS, "methods": ["GET", "POST", "PUT", "DELETE"], "allow_headers": ["Content-Type", "X-API-Key", "X-CSRFToken"]}})
analyzer = StockAnalyzer()
us_stock_service = USStockService()

# 配置缓存
cache_config = {
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 300
}

# 如果配置了Redis，使用Redis作为缓存后端
if os.getenv('USE_REDIS_CACHE', 'False').lower() == 'true' and os.getenv('REDIS_URL'):
    cache_config = {
        'CACHE_TYPE': 'RedisCache',
        'CACHE_REDIS_URL': os.getenv('REDIS_URL'),
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


# 确保全局变量在重新加载时不会丢失
if 'analyzer' not in globals():
    try:
        from app.analysis.stock_analyzer import StockAnalyzer

        analyzer = StockAnalyzer()
        print("成功初始化全局StockAnalyzer实例")
    except Exception as e:
        print(f"初始化StockAnalyzer时出错: {e}", file=sys.stderr)
        raise

# 初始化模块实例
fundamental_analyzer = FundamentalAnalyzer()
capital_flow_analyzer = CapitalFlowAnalyzer()
scenario_predictor = ScenarioPredictor(analyzer, os.getenv('OPENAI_API_KEY'), os.getenv('OPENAI_API_MODEL'))
stock_qa = StockQA(analyzer, os.getenv('OPENAI_API_KEY'))
risk_monitor = RiskMonitor(analyzer)
index_industry_analyzer = IndexIndustryAnalyzer(analyzer)
industry_analyzer = IndustryAnalyzer()

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

# 创建日志格式化器
formatter = logging.Formatter(
    '[%(asctime)s] [%(process)d:%(thread)d] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s',
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
root_logger.addHandler(file_handler)

# 添加控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
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
except Exception as _e:
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
            return jsonify({'error': '请输入代码'}), 400

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
            except Exception as e:
                app.logger.error(f"分析股票 {stock_code} 时出错: {str(e)}")
                results.append({
                    'stock_code': stock_code,
                    'error': str(e),
                    'stock_name': '分析失败',
                    'industry': '未知'
                })

        return jsonify({'results': results})
    except Exception as e:
        app.logger.error(f"分析股票时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '行情分析失败，请稍后重试', details=str(e))


@app.route('/api/north_flow_history', methods=['POST'])
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
            return jsonify({'error': '请提供股票代码'}), 400

        # 调用北向资金历史数据方法

        analyzer = CapitalFlowAnalyzer()
        result = analyzer.get_north_flow_history(stock_code, start_date, end_date)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"获取北向资金历史数据出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '北向资金数据加载失败，请稍后重试', details=str(e))


@app.route('/search_us_stocks', methods=['GET'])
def search_us_stocks():
    try:
        keyword = request.args.get('keyword', '')
        if not keyword:
            return jsonify({'error': '请输入搜索关键词'}), 400

        results = us_stock_service.search_us_stocks(keyword)
        return jsonify({'results': results})

    except Exception as e:
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
def start_stock_analysis():
    """启动个股分析任务"""
    try:
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return jsonify({'error': '请求体必须为有效的JSON格式'}), 400
        stock_code = data.get('stock_code')
        market_type = data.get('market_type', 'A')

        if not stock_code:
            return jsonify({'error': '请输入股票代码'}), 400

        valid, result = validate_stock_code(stock_code, market_type)
        if not valid:
            return jsonify({'error': result}), 400
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

                except Exception as e:
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

                except Exception as e:
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

    except Exception as e:
        app.logger.error(f"启动ETF分析任务时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '启动ETF分析任务失败，请稍后重试', details=str(e))


@app.route('/api/etf_analysis_status/<task_id>', methods=['GET'])
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
            except Exception as e:
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

    except Exception as e:
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
_CACHE_LOCK = threading.Lock()
_STOCK_NAME_CACHE_LOCK = threading.RLock()  # S1-C4: 并发读写保护（启动期循环写与请求读并发）


def _load_stock_name_cache():
    """首次调用时加载全量A股代码->名称映射（~5000条）到进程级缓存
    [REAL-01 2026-05-18] 上游 bse.cn 经常被代理 RST 阻塞 30s+，加 5s 硬超时 + 永久标记，避免反复重试拖垮 stock_quote_batch
    """
    global _CACHE_LOADED
    if _CACHE_LOADED:
        return
    with _CACHE_LOCK:
        if _CACHE_LOADED:
            return
        # 永久置真：即使本次失败，下次也不再重试（进程内 1 次成本封顶），由 _get_stock_name_safe 兜底降级到 stock_code
        _CACHE_LOADED = True
        try:
            import akshare as ak
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FTimeout
            with ThreadPoolExecutor(max_workers=1) as _ex:
                fut = _ex.submit(ak.stock_info_a_code_name)
                try:
                    df = fut.result(timeout=5)
                except _FTimeout:
                    app.logger.warning("加载A股名称缓存超时(>5s)，本进程不再重试")
                    return
            with _STOCK_NAME_CACHE_LOCK:
                for _, row in df.iterrows():
                    _STOCK_NAME_CACHE[str(row['code'])] = str(row['name'])
            app.logger.info(f"A股名称缓存加载完成，共 {len(_STOCK_NAME_CACHE)} 条")
        except Exception as e:
            app.logger.warning(f"加载A股名称缓存失败: {str(e)}")


def _get_stock_name_safe(stock_code, market_type='A'):
    """
    安全获取股票名称：
    1. 优先调用 analyzer.get_stock_info（东方财富，信息最全）
    2. 失败则降级查全量A股缓存（akshare stock_info_a_code_name）
    3. 最终降级为股票代码本身
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
        return stock_code

    # 1. 先试主路径 [REAL-01 2026-05-18] 加 3s 硬超时 + shutdown(wait=False)，
    # 避免 with __exit__ 等阻塞 future 真完成（上游 ProxyError 可阻塞 30s+）
    try:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FTimeout
        _ex = ThreadPoolExecutor(max_workers=1)
        try:
            fut = _ex.submit(analyzer.get_stock_info, stock_code)
            try:
                info = fut.result(timeout=3)
            except _FTimeout:
                info = None
        finally:
            _ex.shutdown(wait=False)
        if isinstance(info, dict):
            name = info.get('股票名称') or info.get('name')
            if name and name != '未知' and name != stock_code:
                return name
    except Exception as e:
        app.logger.warning(f"analyzer.get_stock_info 失败 {stock_code}: {str(e)}")

    # 2. 降级：全量A股缓存
    _load_stock_name_cache()
    with _STOCK_NAME_CACHE_LOCK:
        if stock_code in _STOCK_NAME_CACHE:
            return _STOCK_NAME_CACHE[stock_code]

    # 3. 最终降级
    return stock_code


# Update the get_stock_data function in web_server.py to handle date formatting properly
@app.route('/api/stock_data', methods=['GET'])
@with_cache(60)  # S2-A3: 半实时 1分钟缓存
@limiter.limit('200 per minute')  # S2-A4
@cache.cached(timeout=300, query_string=True)
def get_stock_data():
    # Input: stock_code/period/start_date/end_date/market_type query params
    # Output: JSON OHLCV 历史数据
    # Pos: K线页面核心数据端点，已套 S2-A1 校验
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
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FTimeout
        try:
            with ThreadPoolExecutor(max_workers=1) as _ex:
                fut = _ex.submit(analyzer.get_stock_data, stock_code, market_type, start_date, end_date)
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

        app.logger.info(f"数据处理完成，返回 {len(records)} 条记录, 股票名称: {stock_name}")
        return custom_jsonify({'data': records, 'stock_name': stock_name})
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
_PROFILE_TTL = 3600  # 1小时
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
    except: pass

@app.route('/api/stock_profile', methods=['GET'])
@with_cache(60)  # S2-A3: 半实时 1分钟缓存
def api_stock_profile():
    # Input: stock_code query param (S2-A1 校验)
    # Output: JSON profile (industry/pe_ttm/pb/roe) or 503 on timeout
    # Pos: baostock I/O 重路径，外层 ThreadPoolExecutor 兜底确保 ≤25s 必返回
    import baostock as bs
    from datetime import datetime, timedelta
    import time as _time
    from concurrent.futures import ThreadPoolExecutor as _TPE, TimeoutError as _TPETimeout

    stock_code = validate_stock_code_strict(request.args.get('stock_code', ''))  # S2-A1

    # 命中短缓存（主线程快速返回，不进入任何 I/O）
    now = _time.time()
    cached = _profile_cache_get(stock_code)
    if cached and (now - cached[0] < _PROFILE_TTL):
        return custom_jsonify(cached[1])

    # 名称：直接走预加载缓存，不走analyzer.get_stock_info（该函数在eastmoney阻断时会60s超时）
    _load_stock_name_cache()
    name = _STOCK_NAME_CACHE.get(stock_code, stock_code)
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
        pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='ak_fill')
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
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

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
                        try: return float(last[i]) if last[i] else None
                        except: return None
                    _local_profile['pe_ttm'] = _f(12)
                    _local_profile['pb'] = _f(13)
                    close = _f(5)
                    # market_cap 需要total_share，query_stock_basic 不含该字段，暂留close
                    if close:
                        try:
                            bs.query_stock_basic(code=bs_code)
                        except: pass
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
    _outer_pool = _TPE(max_workers=1, thread_name_prefix='profile_outer')
    try:
        fut = _outer_pool.submit(_do_all_baostock)
        try:
            profile = fut.result(timeout=int(os.getenv('PROFILE_BAOSTOCK_TIMEOUT_S', '8')))
        except (_TPETimeout, TimeoutError) as _toe:
            app.logger.warning(f"baostock overall_timeout ({stock_code})，进入 akshare-only 兜底")
            _fb = {
                'stock_code': stock_code,
                'stock_name': _STOCK_NAME_CACHE.get(stock_code) or stock_code,
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
    _profile_cache_evict_and_set(stock_code, (now2, profile), _PROFILE_TTL)
    return custom_jsonify(profile)


# 轻量名称查询接口 — 直接走A股预加载缓存，避免analyzer.get_stock_info在eastmoney阻断时60s超时
@app.route('/api/stock_name', methods=['GET'])
def api_stock_name():
    stock_code = request.args.get('stock_code', '')
    if not stock_code:
        return custom_jsonify({'error': 'stock_code required'}), 400
    try:
        _load_stock_name_cache()
        name = _STOCK_NAME_CACHE.get(stock_code, stock_code)
        return custom_jsonify({'stock_code': stock_code, 'stock_name': name})
    except Exception as e:
        app.logger.error(f"获取股票名称出错 {stock_code}: {e}")
        return custom_jsonify({'stock_code': stock_code, 'stock_name': stock_code})


# 股票名称反查接口 — 根据名称关键词搜索代码（FE意图路由用）
@app.route('/api/stock_name_search', methods=['GET'])
def api_stock_name_search():
    q = (request.args.get('q') or '').strip()
    if not q:
        return custom_jsonify({'error': 'q required', 'results': []}), 400
    try:
        _load_stock_name_cache()
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

        # --- 主路径: 东财 stock_zh_index_spot_em ---
        def _try_eastmoney():
            df = ak.stock_zh_index_spot_em()
            target_codes = ['000001', '399001', '399006', '000300']
            result = []
            for code in target_codes:
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

        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_try_eastmoney)
            try:
                result = fut.result(timeout=_PRIMARY_TIMEOUT)
                if result:
                    data = {'indices': result, 'timestamp': now_cn().isoformat()}
                    _market_indices_cache.update({'data': data, 'ts': time.time(), 'source': 'eastmoney'})
                    data['source'] = 'eastmoney'
                    return data
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

        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_try_sina)
            try:
                result = fut.result(timeout=_FALLBACK_TIMEOUT)
                if result:
                    data = {'indices': result, 'timestamp': now_cn().isoformat()}
                    _market_indices_cache.update({'data': data, 'ts': time.time(), 'source': 'sina'})
                    data['source'] = 'sina'
                    return data
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

            with ThreadPoolExecutor(max_workers=4) as ex:
                items = list(ex.map(_fetch_one_daily, indices_config, timeout=12))
            result = [x for x in items if x]

            if result:
                data = {'indices': result, 'timestamp': now_cn().isoformat()}
                _market_indices_cache.update({'data': data, 'ts': time.time(), 'source': 'daily'})
                data['source'] = 'daily'
                return data
        except Exception as e:
            app.logger.error(f"历史指数数据也失败: {e}")

        # --- 兜底3: 返回已有缓存（无论是否过期）---
        if _market_indices_cache.get('data'):
            app.logger.warning("所有指数来源均失败，返回过期缓存")
            stale = dict(_market_indices_cache['data'])
            stale['source'] = 'stale_cache'
            return stale

        return {'indices': [], 'source': 'degraded'}


@app.route('/api/market_indices', methods=['GET'])
@with_cache(5)  # S2-A3: 实时类 5秒短缓存
def get_market_indices():
    """获取主要市场指数实时行情（上证/深证/创业板/沪深300）
    Input: 无
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
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_fetch_market_indices_data)
            try:
                data = fut.result(timeout=_fast_ms / 1000)
            except FuturesTimeout:
                # 超时：先返回 degraded，后台继续等待（锁里的 akshare 还在跑）
                app.logger.warning(f"get_market_indices 快速超时 {_fast_ms}ms，返回 degraded（后台继续刷新）")
                data = {'indices': [], 'source': 'degraded'}

    source = data.get('source', 'unknown')
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
            except:
                # 日期解析错误，添加到删除列表
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
def api_individual_fund_flow_rank():
    try:
        period = request.args.get('period', '10日')  # Default to today

        # Get individual fund flow ranking data
        result = capital_flow_analyzer.get_individual_fund_flow_rank(period)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"Error getting individual fund flow ranking: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取个股资金流向排名失败，请稍后重试', details=str(e))


# 获取个股资金流向的API端点
@app.route('/api/individual_fund_flow', methods=['GET'])
def api_individual_fund_flow():
    try:
        stock_code = request.args.get('stock_code')
        market_type = request.args.get('market_type', '')  # Auto-detect if not provided
        re_date = request.args.get('period-select')

        if not stock_code:
            return jsonify({'error': 'Stock code is required'}), 400

        # Get individual fund flow data
        result = capital_flow_analyzer.get_individual_fund_flow(stock_code, market_type, re_date)
        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"Error getting individual fund flow: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取个股资金流向失败，请稍后重试', details=str(e))


# 获取板块内股票的API端点
@app.route('/api/sector_stocks', methods=['GET'])
def api_sector_stocks():
    try:
        sector = request.args.get('sector')

        if not sector:
            return jsonify({'error': 'Sector name is required'}), 400

        # Get sector stocks data
        result = capital_flow_analyzer.get_sector_stocks(sector)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"Error getting sector stocks: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取板块股票失败，请稍后重试', details=str(e))


# Update the existing capital flow API endpoint
@app.route('/api/capital_flow', methods=['POST'])
def api_capital_flow():
    try:
        data = request.json
        stock_code = data.get('stock_code')
        market_type = data.get('market_type', '')  # Auto-detect if not provided

        if not stock_code:
            return jsonify({'error': 'Stock code is required'}), 400

        if market_type:
            valid, result = validate_stock_code(stock_code, market_type)
            if not valid:
                return jsonify({'error': result}), 400
            stock_code = result

        # Calculate capital flow score
        result = capital_flow_analyzer.calculate_capital_flow_score(stock_code, market_type)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"Error calculating capital flow score: {traceback.format_exc()}")
        return api_error('INTERNAL', '资金流向评分计算失败，请稍后重试', details=str(e))


# 情景预测路由
@app.route('/api/scenario_predict', methods=['POST'])
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
def api_risk_analysis():
    try:
        data = request.json
        stock_code = data.get('stock_code')
        market_type = data.get('market_type', 'A')

        if not stock_code:
            return jsonify({'error': '请提供股票代码'}), 400

        valid, result = validate_stock_code(stock_code, market_type)
        if not valid:
            return jsonify({'error': result}), 400
        stock_code = result

        # 获取风险分析结果
        result = risk_monitor.analyze_stock_risk(stock_code, market_type)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"风险分析出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '风险分析失败，请稍后重试', details=str(e))


# 投资组合风险分析路由
@app.route('/api/portfolio_risk', methods=['POST'])
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
        now = now_cn()
        
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


# 智能体分析路由
@app.route('/api/start_agent_analysis', methods=['POST'])
def start_agent_analysis():
    """启动智能体分析任务"""
    try:
        data = request.json
        stock_code = data.get('stock_code')
        research_depth = data.get('research_depth', 3)
        market_type = data.get('market_type', 'A')
        selected_analysts = data.get('selected_analysts', ["market", "social", "news", "fundamentals"])
        analysis_date = data.get('analysis_date')
        enable_memory = data.get('enable_memory', True)
        max_output_length = data.get('max_output_length', 2048)

        if not stock_code:
            return jsonify({'error': '请提供股票代码'}), 400

        # 验证股票代码格式
        is_valid, validated_code = validate_stock_code(stock_code, market_type)
        if not is_valid:
            return jsonify({'error': validated_code}), 400
        stock_code = validated_code

        # 创建新任务
        task_id = generate_task_id()
        task = {
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
        
        # 为任务创建取消事件
        task['cancel_event'] = threading.Event()
        agent_session_manager.save_task(task)
        
        def run_agent_analysis():
            """在后台线程中运行智能体分析"""
            try:
                # 特性开关：使用新Agent系统或旧TradingAgents
                use_new_agent = os.getenv('USE_AGENT_SYSTEM', 'true').lower() == 'true'

                if use_new_agent:
                    # === 新Agent系统（LangGraph编排） ===
                    from app.agents.coordinator import run_agent_analysis as agent_run

                    update_task_status('agent_analysis', task_id, TASK_RUNNING, progress=5, result={'current_step': '正在初始化多Agent分析系统...'})

                    # [FIX-6 2026-05-18] 订阅 task.progress_advance 事件，让 LangGraph 节点完成时回写 task.progress
                    from app.core.event_bus import get_event_bus as _get_bus
                    _bus = _get_bus()

                    def _on_progress_advance(payload):
                        try:
                            if not isinstance(payload, dict):
                                return
                            if payload.get('task_id') != task_id:
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
                        # 解订阅，防止跨任务串流
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

                    # 构造前端期望的decision格式
                    final_decision = result_state.get('final_decision', {})
                    decision_obj = {
                        'action': final_decision.get('action', 'HOLD'),
                        'reasoning': final_decision.get('reasoning', '分析完成'),
                        'confidence': final_decision.get('confidence', 0.5),
                        'risk_score': 1.0 - final_decision.get('confidence', 0.5)
                    }

                    update_task_status('agent_analysis', task_id, TASK_COMPLETED, progress=100, result={
                        'decision': decision_obj,
                        'final_state': result_state,
                        'current_step': '多Agent分析完成',
                        'execution_log': result_state.get('execution_log', []),
                        'errors': result_state.get('errors', [])
                    })
                    app.logger.info(f"Agent分析任务 {task_id} 完成 (新系统)")

                else:
                    # === 旧TradingAgents系统（保持兼容） ===
                    from tradingagents.graph.trading_graph import TradingAgentsGraph
                    from tradingagents.default_config import DEFAULT_CONFIG

                    update_task_status('agent_analysis', task_id, TASK_RUNNING, progress=5, result={'current_step': '正在初始化智能体...'})

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

                    update_task_status('agent_analysis', task_id, TASK_RUNNING, progress=30, result={'current_step': '正在进行多智能体分析...'})
                    state, raw_decision = ta.propagate(stock_code, today, **kwargs)
                    update_task_status('agent_analysis', task_id, TASK_RUNNING, progress=90, result={'current_step': '正在生成分析报告...'})

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

                    update_task_status('agent_analysis', task_id, TASK_COMPLETED, progress=100, result={'decision': decision_obj, 'final_state': state, 'current_step': '分析完成'})
                    app.logger.info(f"智能体分析任务 {task_id} 完成 (旧系统)")

            except TaskCancelledException as e:
                app.logger.info(str(e))
                update_task_status('agent_analysis', task_id, TASK_FAILED, error='任务已被用户取消', result={'current_step': '任务已被用户取消'})
            except Exception as e:
                app.logger.error(f"智能体分析任务 {task_id} 失败: {str(e)}")
                app.logger.error(traceback.format_exc())
                update_task_status('agent_analysis', task_id, TASK_FAILED, error=str(e), result={'current_step': f'分析失败: {e}'})

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
def get_agent_analysis_history():
    """获取已完成的智能体分析任务历史"""
    try:
        all_tasks = agent_session_manager.get_all_tasks()
        history = [
            task for task in all_tasks 
            if task.get('status') in [TASK_COMPLETED, TASK_FAILED]
        ]
        # 按更新时间排序，最新的在前
        history.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        return custom_jsonify({'history': history})
    except Exception as e:
        app.logger.error(f"获取分析历史时出错: {traceback.format_exc()}")
        return api_error('INTERNAL', '获取智能体分析历史失败，请稍后重试', details=str(e))


@app.route('/api/delete_agent_analysis', methods=['POST'])
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
def get_pending_approvals():
    """获取待人工审批的Agent决策"""
    try:
        from app.agents.hitl import approval_manager
        pending = approval_manager.get_pending_approvals()
        return jsonify({'approvals': pending})
    except Exception as e:
        return api_error('INTERNAL', '获取待审批任务失败，请稍后重试', details=str(e))


@app.route('/api/agent_submit_approval', methods=['POST'])
def submit_agent_approval():
    """提交人工审批结果"""
    try:
        from app.agents.hitl import approval_manager
        data = request.json
        task_id = data.get('task_id')
        approved = data.get('approved', False)
        feedback = data.get('feedback', '')
        if not task_id:
            return jsonify({'error': '请提供task_id'}), 400
        success = approval_manager.submit_approval(task_id, approved, feedback)
        if success:
            return jsonify({'message': '审批已提交', 'approved': approved})
        return jsonify({'error': '未找到待审批任务'}), 404
    except Exception as e:
        return api_error('INTERNAL', '提交审批失败，请稍后重试', details=str(e))


@app.route('/api/active_tasks', methods=['GET'])
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
def mcp_list_tools():
    """列出MCP可用工具"""
    try:
        from app.mcp.stock_data_server import MCP_SERVER_CONFIG
        return jsonify(MCP_SERVER_CONFIG)
    except Exception as e:
        return api_error('INTERNAL', '获取MCP工具列表失败，请稍后重试', details=str(e))

@app.route('/api/mcp/call', methods=['POST'])
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
def list_conversations():
    """获取对话列表
    Input: limit query param (S2-A1 校验，1-200)
    Output: JSON {conversations: [...]}
    Pos: 对话历史列表端点
    """
    from app.core.conversation import get_conversation_manager
    limit = validate_int_range(request.args.get('limit'), 'limit', 1, 200, default=20)  # S2-A1
    conversations = get_conversation_manager().list_conversations(limit)
    return jsonify({'conversations': conversations})


@app.route('/api/conversations/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """获取单个对话详情"""
    from app.core.conversation import get_conversation_manager
    conv = get_conversation_manager().get_conversation(conversation_id)
    if not conv:
        return jsonify({'error': '对话不存在'}), 404
    return jsonify(conv)


@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
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
def a2a_agent_card():
    """A2A v1.0 标准发现端点 (RFC 8615 well-known)。"""
    return jsonify(_build_agent_card())


@app.route('/.well-known/agent.json', methods=['GET'])
def a2a_agent_card_legacy():
    """A2A v0.2 兼容路径 (v0.3 起改为 agent-card.json, 此处提供向后兼容)。"""
    return jsonify(_build_agent_card())


@app.route('/a2a/v1', methods=['POST'])
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
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FTimeout
    from app.adapters.adapter_registry import AdapterRegistry
    reg = AdapterRegistry.default()
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(reg.call_with_fallback, domain, method, **kwargs)
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
    # [REAL-01 2026-05-18] 用 try/except 包裹 as_completed，超时立即返回已完成部分，
    # 并 shutdown(wait=False) 不阻塞响应；避免 with 块 __exit__ 等到全部线程结束(60s+)
    # [REAL-01 2026-05-18] 并发上限 20（原 8），整体 25s 超时（原 20s）
    ex = ThreadPoolExecutor(max_workers=min(20, len(codes)))
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
        ex.shutdown(wait=False)

    return custom_jsonify({
        'results': results,
        'errors': errors,
        'ts': int(time.time()),
    }), 200


@app.route('/health', methods=['GET'])
def health_basic():
    """轻量存活探针 — 返回 200 + uptime + version. <100ms."""
    return jsonify({
        "status": "ok",
        "uptime_s": round(time.time() - START_TIME, 3),
        "version": APP_VERSION,
        "ts": int(time.time()),
    }), 200


@app.route('/api/adapters/status', methods=['GET'])
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
    # 不使用 with 语句：with __exit__ 默认 shutdown(wait=True)，会在超时时阻塞等待慢线程
    pool = ThreadPoolExecutor(max_workers=min(total, 16))
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
        # cancel_futures=True 取消排队但未运行的任务；wait=False 不等待正在运行的线程
        # 这确保即使 BaostockAdapter.bs.login() 无限阻塞，此函数也能在 overall_timeout+ε 返回
        pool.shutdown(wait=False, cancel_futures=True)

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


# 在应用启动时启动清理线程（保持原有代码不变）
cleaner_thread = threading.Thread(target=run_task_cleaner)
cleaner_thread.daemon = True
cleaner_thread.start()

# 启动时后台预加载A股名称缓存，避免首次请求时名字降级为代码
_preload_thread = threading.Thread(target=_load_stock_name_cache, daemon=True)
_preload_thread.start()

# 预热 /api/stock_profile 常用股票，避免首次访问compare/dashboard时等待baostock
def _preload_profiles():
    # [Batch8-FIX 2026-05-19] DISABLE_NETWORK=1 时（测试环境）跳过 baostock 真实连接
    if os.getenv("DISABLE_NETWORK") == "1":
        return
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

threading.Thread(target=_preload_profiles, daemon=True).start()

# M1/M2 启动预热 + 定时刷新：每 INDEX_REFRESH_INTERVAL_S 秒刷新一次缓存
# B23: 从一次性预热改为定时循环刷新，避免缓存 30s TTL 过期后请求出现 17s 延迟
def _preload_market_indices():
    if os.getenv("DISABLE_NETWORK") == "1":
        return
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

threading.Thread(target=_preload_market_indices, daemon=True).start()

if __name__ == '__main__':
    # 强制禁用Flask的调试模式，以确保日志配置生效
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", "8888")), debug=False)