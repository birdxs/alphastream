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
from datetime import date, datetime, timedelta
from flask_cors import CORS
from pathlib import Path
import time
from flask_caching import Cache
import threading
import sys
from flask_swagger_ui import get_swaggerui_blueprint
from app.core.database import get_session, StockInfo, AnalysisResult, Portfolio, USE_DATABASE
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
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:8888,http://127.0.0.1:8888,http://localhost:3000,http://127.0.0.1:3000').split(',')
# Dev兜底: 允许常见局域网IP(192.168.x/10.x)+任意:3000/8888端口, 便于Comdr从多主机访问
_DEV_ORIGIN_PATTERNS = [
    re.compile(r'^http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):(3000|8888)$'),
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins + _DEV_ORIGIN_PATTERNS, "methods": ["GET", "POST"], "allow_headers": ["Content-Type", "X-API-Key"]}})
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
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
            task['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


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
        task['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
            task['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


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
        return jsonify({'error': str(e)}), 500


@app.route('/api/north_flow_history', methods=['POST'])
def api_north_flow_history():
    try:
        data = request.json
        stock_code = data.get('stock_code')
        days = data.get('days', 10)  # 默认为10天，对应前端的默认选项

        # 计算 end_date 为当前时间
        end_date = datetime.now().strftime('%Y%m%d')

        # 计算 start_date 为 end_date 减去指定的天数
        start_date = (datetime.now() - timedelta(days=int(days))).strftime('%Y%m%d')

        if not stock_code:
            return jsonify({'error': '请提供股票代码'}), 400

        # 调用北向资金历史数据方法

        analyzer = CapitalFlowAnalyzer()
        result = analyzer.get_north_flow_history(stock_code, start_date, end_date)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"获取北向资金历史数据出错: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        task['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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
        return jsonify({'error': str(e)}), 500


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
        return custom_jsonify({'error': str(e)}), 500


# 添加在web_server.py主代码中
@app.errorhandler(404)
def not_found(error):
    """处理404错误"""
    if request.path.startswith('/api/'):
        # 为API请求返回JSON格式的错误
        return jsonify({
            'error': '找不到请求的API端点',
            'path': request.path,
            'method': request.method
        }), 404
    # 为网页请求返回HTML错误页
    return render_template('error.html', error_code=404, message="找不到请求的页面"), 404


@app.errorhandler(500)
def server_error(error):
    """处理500错误"""
    app.logger.error(f"服务器错误: {str(error)}")
    if request.path.startswith('/api/'):
        # 为API请求返回JSON格式的错误
        return jsonify({
            'error': '服务器内部错误',
            'message': str(error)
        }), 500
    # 为网页请求返回HTML错误页
    return render_template('error.html', error_code=500, message="服务器内部错误"), 500


# ============ A股名称缓存（ak.stock_info_a_code_name fallback） ============
# 解决东方财富接口偶发失败导致stock_name降级为股票代码的问题
_STOCK_NAME_CACHE = {}
_CACHE_LOADED = False
_CACHE_LOCK = threading.Lock()


def _load_stock_name_cache():
    """首次调用时加载全量A股代码->名称映射（~5000条）到进程级缓存"""
    global _CACHE_LOADED
    if _CACHE_LOADED:
        return
    with _CACHE_LOCK:
        if _CACHE_LOADED:
            return
        try:
            import akshare as ak
            df = ak.stock_info_a_code_name()
            for _, row in df.iterrows():
                _STOCK_NAME_CACHE[str(row['code'])] = str(row['name'])
            _CACHE_LOADED = True
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

    # 1. 先试主路径
    try:
        info = analyzer.get_stock_info(stock_code)
        if isinstance(info, dict):
            name = info.get('股票名称') or info.get('name')
            if name and name != '未知' and name != stock_code:
                return name
    except Exception as e:
        app.logger.warning(f"analyzer.get_stock_info 失败 {stock_code}: {str(e)}")

    # 2. 降级：全量A股缓存
    _load_stock_name_cache()
    if stock_code in _STOCK_NAME_CACHE:
        return _STOCK_NAME_CACHE[stock_code]

    # 3. 最终降级
    return stock_code


# Update the get_stock_data function in web_server.py to handle date formatting properly
@app.route('/api/stock_data', methods=['GET'])
@cache.cached(timeout=300, query_string=True)
def get_stock_data():
    try:
        stock_code = request.args.get('stock_code')
        market_type = request.args.get('market_type', 'A')
        period = request.args.get('period', '1y')  # 默认1年

        if not stock_code:
            return custom_jsonify({'error': '请提供股票代码'}), 400

        valid, result = validate_stock_code(stock_code, market_type)
        if not valid:
            return jsonify({'error': result}), 400
        stock_code = result

        # 根据period计算start_date
        end_date = datetime.now().strftime('%Y%m%d')
        if period == '1m':
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        elif period == '3m':
            start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
        elif period == '6m':
            start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d')
        elif period == '1y':
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        else:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

        # 获取股票历史数据（15秒硬超时，避免akshare外网卡死占满werkzeug线程池）
        app.logger.info(
            f"获取股票 {stock_code} 的历史数据，市场: {market_type}, 起始日期: {start_date}, 结束日期: {end_date}")
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FTimeout
        try:
            with ThreadPoolExecutor(max_workers=1) as _ex:
                fut = _ex.submit(analyzer.get_stock_data, stock_code, market_type, start_date, end_date)
                df = fut.result(timeout=15)
        except _FTimeout:
            app.logger.warning(f"analyzer.get_stock_data 超时(15s)：{stock_code}")
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
        return custom_jsonify({'error': str(e)}), 500


# 股票概要：名称/行业/市值/PE/PB/ROE — 供对比页快速对比使用（baostock主，不依赖eastmoney）
# baostock使用全局session，并发请求会串线 — 用lock串行化 + profile短缓存 + 启动时一次登录
import threading as _threading
import atexit as _atexit
_BAOSTOCK_LOCK = _threading.Lock()
_PROFILE_CACHE = {}  # {stock_code: (ts, profile)}
_PROFILE_TTL = 3600  # 1小时
_BS_LOGGED_IN = False

def _ensure_bs_login():
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
def api_stock_profile():
    import baostock as bs
    from datetime import datetime, timedelta
    import time as _time
    stock_code = request.args.get('stock_code', '')
    if not stock_code:
        return custom_jsonify({'error': 'stock_code required'}), 400

    # 命中短缓存
    now = _time.time()
    cached = _PROFILE_CACHE.get(stock_code)
    if cached and (now - cached[0] < _PROFILE_TTL):
        return custom_jsonify(cached[1])

    # 名称：直接走预加载缓存，不走analyzer.get_stock_info（该函数在eastmoney阻断时会60s超时）
    _load_stock_name_cache()
    name = _STOCK_NAME_CACHE.get(stock_code, stock_code)
    profile = {'stock_code': stock_code, 'stock_name': name,
               'industry': None, 'market_cap': None, 'pe_ttm': None, 'pb': None, 'roe': None}
    # baostock需要 sh./sz. 前缀
    prefix = 'sh.' if stock_code.startswith('6') else 'sz.'
    bs_code = prefix + stock_code
    _ensure_bs_login()
    with _BAOSTOCK_LOCK:
      try:
        pass  # 进程级session已登录
        # 行业
        try:
            rs = bs.query_stock_industry(code=bs_code)
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            if rows:
                profile['industry'] = rows[0][3] if len(rows[0]) > 3 else None
        except Exception as e:
            app.logger.warning(f"baostock industry失败({stock_code}): {e}")
        # PE/PB/close — 取最近可用交易日（baostock数据有2-3天滞后，向前扩展90天）
        try:
            end = datetime.now().strftime('%Y-%m-%d')
            start = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
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
                profile['pe_ttm'] = _f(12)
                profile['pb'] = _f(13)
                close = _f(5)
                # market_cap 需要total_share，由 query_stock_basic 或独立接口获取
                if close:
                    try:
                        rs2 = bs.query_stock_basic(code=bs_code)
                        # query_stock_basic returns: code, code_name, ipoDate, outDate, type, status
                        # 不含 total_share，需要 query_history_k_data_plus 中的 turn 等估算不可行
                        # 使用 akshare name cache中可能缺失 market cap，暂留close作价格展示
                        pass
                    except: pass
        except Exception as e:
            app.logger.warning(f"baostock k_data失败({stock_code}): {e}")
        # ROE — 最近年报
        try:
            year = datetime.now().year
            for y in [year - 1, year - 2]:
                rs = bs.query_profit_data(code=bs_code, year=y, quarter=4)
                rows = []
                while rs.error_code == '0' and rs.next():
                    rows.append(rs.get_row_data())
                if rows and len(rows[0]) > 3 and rows[0][3]:
                    profile['roe'] = float(rows[0][3]) * 100  # baostock roeAvg 为小数
                    break
        except Exception as e:
            app.logger.warning(f"baostock profit失败({stock_code}): {e}")
      except Exception as e:
        app.logger.error(f"baostock 查询失败: {e}")
    # 淘汰过期条目，防止无限增长
    now = _time.time()
    stale_keys = [k for k, (ts, _) in _PROFILE_CACHE.items() if now - ts > _PROFILE_TTL]
    for k in stale_keys:
        del _PROFILE_CACHE[k]
    _PROFILE_CACHE[stock_code] = (now, profile)
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
        for code, name in _STOCK_NAME_CACHE.items():
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
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
        return jsonify({'error': str(e)}), 500


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
        task['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({'message': '任务已取消'})


def _fetch_market_indices_data():
    """内部函数：获取主要市场指数数据（上证/深证/创业板/沪深300），供API和SSE共用"""
    import akshare as ak

    # 方案1: 尝试实时行情接口
    try:
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
                    'price': float(r['最新价']),
                    'change_pct': float(r['涨跌幅'])
                })
        if result:
            return {'indices': result}
    except Exception as e:
        app.logger.warning(f"实时指数接口失败: {e}")

    # 方案2: 用历史日线数据的最后一条（更稳定）
    try:
        indices_config = [
            ('sh000001', '上证指数'),
            ('sz399001', '深证成指'),
            ('sz399006', '创业板指'),
            ('sh000300', '沪深300'),
        ]
        result = []
        for symbol, name in indices_config:
            try:
                df = ak.stock_zh_index_daily(symbol=symbol)
                if df is not None and len(df) >= 2:
                    latest = df.iloc[-1]
                    prev = df.iloc[-2]
                    price = float(latest['close'])
                    change_pct = round((price - float(prev['close'])) / float(prev['close']) * 100, 2)
                    result.append({
                        'name': name,
                        'code': symbol[2:],
                        'price': price,
                        'change_pct': change_pct
                    })
            except Exception:
                continue
        if result:
            return {'indices': result}
    except Exception as e:
        app.logger.error(f"历史指数数据也失败: {e}")

    return {'indices': []}


@app.route('/api/market_indices', methods=['GET'])
def get_market_indices():
    """获取主要市场指数实时行情（上证/深证/创业板/沪深300）"""
    return jsonify(_fetch_market_indices_data())


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


# 添加到web_server.py
def clean_old_tasks():
    """清理旧的扫描任务"""
    with task_lock:
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
            now = datetime.now()
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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


@app.route('/api/industry_fund_flow', methods=['GET'])
def api_industry_fund_flow():
    """获取行业资金流向数据"""
    try:
        symbol = request.args.get('symbol', '即时')

        result = industry_analyzer.get_industry_fund_flow(symbol)

        return custom_jsonify(result)
    except Exception as e:
        app.logger.error(f"获取行业资金流向数据出错: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500
    finally:
        if session:
            session.close()

# 添加新闻API端点
# 添加到web_server.py文件中
@app.route('/api/latest_news', methods=['GET'])
def get_latest_news():
    try:
        days = int(request.args.get('days', 1))  # 默认获取1天的新闻
        limit = min(max(int(request.args.get('limit', 1000)), 1), 500)  # 限制范围1-500
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
    """获取新闻情绪分析统计"""
    try:
        days = request.args.get('days', 1, type=int)

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
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, ensure_ascii=False, indent=4, cls=NumpyJSONEncoder)

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
        now = datetime.now()
        
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
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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

                    today = analysis_date or datetime.now().strftime('%Y-%m-%d')

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
        return jsonify({'error': str(e)}), 500

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
        return jsonify({'error': str(e)}), 500


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
                task['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
        return jsonify({'error': str(e)}), 500


@app.route('/api/agent_pending_approvals', methods=['GET'])
def get_pending_approvals():
    """获取待人工审批的Agent决策"""
    try:
        from app.agents.hitl import approval_manager
        pending = approval_manager.get_pending_approvals()
        return jsonify({'approvals': pending})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'error': str(e)}), 500


# ===== MCP 工具服务端点 =====

@app.route('/api/mcp/tools', methods=['GET'])
def mcp_list_tools():
    """列出MCP可用工具"""
    try:
        from app.mcp.stock_data_server import MCP_SERVER_CONFIG
        return jsonify(MCP_SERVER_CONFIG)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    """接收图片并返回描述（用于多模态分析）"""
    if 'file' not in request.files:
        return jsonify({'error': '未找到文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    # 校验文件大小（最大10MB）
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_IMAGE_SIZE:
        return jsonify({'error': f'文件大小超过限制（最大10MB），当前: {round(file_size / 1024 / 1024, 1)}MB'}), 413
    # 校验文件类型
    allowed_ext = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        return jsonify({'error': f'不支持的文件类型: {ext}'}), 400
    # 保存到临时目录
    import tempfile
    temp_dir = tempfile.mkdtemp()
    filepath = os.path.join(temp_dir, file.filename)
    file.save(filepath)
    # 返回成功（实际图片分析需要多模态AI模型，暂返回占位）
    return jsonify({
        'success': True,
        'filename': file.filename,
        'size': os.path.getsize(filepath),
        'filepath': filepath,
        'message': '图片已上传，多模态分析功能开发中'
    })


# ===== AI对话 & Agent分析 SSE流式端点 =====

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat_stream():
    """AI对话流式端点 — SSE输出Token+工具调用+Agent状态+Artifact"""
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

        # AI对话总超时（120秒）
        AI_CHAT_TIMEOUT = 120
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

            def event_callback(event_type, data):
                nonlocal full_content
                if event_type == 'token' and data.get('content'):
                    full_content += data['content']

            # 执行流式AI对话（带工具调用，模型不支持时降级）
            check_timeout()
            content, tools_log, error = None, [], None
            try:
                content, tools_log, error = chat_with_tools_stream(
                    client, messages, OPENAI_TOOLS_SCHEMA,
                    tool_executor=artifact_tool_executor,
                    max_tool_rounds=3,
                    event_callback=event_callback
                )
            except Exception as tool_err:
                app.logger.warning(f"带工具的流式调用失败，降级为普通对话: {tool_err}")
                error = None  # 清除错误，尝试降级

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
                # 收集流式响应
                collected = ""
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        collected += chunk.choices[0].delta.content
                content = collected
                error = None
                tools_log = []

            if error:
                yield emit('error', {'code': 'AI_ERROR', 'message': error})
                return

            final_content = content or full_content

            # 推送AI文本回复
            if final_content:
                yield emit('token', {'content': final_content, 'finish_reason': 'stop'})

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
    """获取对话列表"""
    from app.core.conversation import get_conversation_manager
    limit = request.args.get('limit', 20, type=int)
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
            while True:
                try:
                    event = bridge_queue.get(timeout=300)
                    if event is None:
                        break
                    yield emit(event.get('event_type', 'info'), event.get('data', {}))
                except queue.Empty:
                    yield emit('error', {'code': 'TIMEOUT', 'message': '分析超时'})
                    break

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
def _p3_call_with_timeout(domain: str, method: str, timeout: int = 20, **kwargs):
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
            _results[key] = _p3_call_with_timeout(domain, method, timeout=15, **kw)
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
    """遍历所有 adapter 调用 health_check, 返回逐个健康状态."""
    results: dict = {}
    total = len(_ADAPTER_SPECS)
    ok_count = 0
    for cls_name, mod_path in _ADAPTER_SPECS:
        r = _hc_one(cls_name, mod_path, timeout_s=5.0)
        results[cls_name] = r
        if r.get("ok"):
            ok_count += 1
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

if __name__ == '__main__':
    # 强制禁用Flask的调试模式，以确保日志配置生效
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", "8888")), debug=False)