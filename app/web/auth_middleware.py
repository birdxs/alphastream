# Input: Flask request headers (X-API-Key) + env vars (STOCKANAL_API_KEY, AUTH_REQUIRED)
# Output: 401/403 JSON error or pass-through to route handler
# Pos: Security gate, applied globally via before_request + public-path whitelist

from functools import wraps
from flask import request, jsonify
import os
import time
import hashlib
import hmac
import secrets
import logging

logger = logging.getLogger(__name__)

# 缓存运行时生成的临时密钥，避免每次调用都重新生成
_runtime_api_key = None
_runtime_hmac_secret = None

# 公开路由白名单（无需鉴权）
PUBLIC_PATHS = {
    '/health',
    '/api/health/deep',  # S3-G2: 深度健康检查
    '/api/metrics',      # S3-G4: 请求计数器端点
    '/api/csrf_token',
    '/api/market_indices',
    '/api/market-indices',
    '/',
    '/dashboard',
    '/stock_detail',
    '/portfolio',
    '/market_scan',
    '/fundamental',
    '/capital_flow',
    '/scenario_predict',
    '/risk_monitor',
    '/qa',
    '/industry_analysis',
    '/agent_analysis',
    '/etf_analysis',
    '/analyze',
    '/search_us_stocks',
}


def get_api_key() -> str:
    """获取 API Key：优先 STOCKANAL_API_KEY，兼容旧 API_KEY，最终自动生成运行时密钥"""
    global _runtime_api_key
    # 优先读新 key
    key = os.getenv('STOCKANAL_API_KEY') or os.getenv('API_KEY')
    if key:
        return key
    # 环境变量未设置，生成随机临时密钥并记录警告
    if _runtime_api_key is None:
        _runtime_api_key = secrets.token_urlsafe(32)
        logger.warning(
            "环境变量 STOCKANAL_API_KEY 未设置，已生成随机临时密钥: %s "
            "请在生产环境中配置 STOCKANAL_API_KEY。",
            _runtime_api_key,
        )
    return _runtime_api_key


def is_auth_required() -> bool:
    """读取 AUTH_REQUIRED 环境变量；生产默认 true"""
    val = os.getenv('AUTH_REQUIRED', 'true').strip().lower()
    if val in ('false', '0', 'no', 'off'):
        logger.debug("AUTH_REQUIRED=false，鉴权已禁用（仅限开发环境）")
        return False
    return True


def check_api_key() -> 'flask.Response | None':
    """检查当前请求的 API Key，通过返回 None，失败返回 Response。
    供 before_request 调用。
    """
    if not is_auth_required():
        return None

    api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization', '').removeprefix('Bearer ')
    if not api_key:
        return jsonify({'error': '缺少 API Key，请在 X-API-Key 请求头中提供'}), 401

    if not hmac.compare_digest(api_key, get_api_key()):
        return jsonify({'error': '无效的 API Key'}), 403

    return None


def require_api_key(f):
    """需要 API Key 验证的装饰器（向下兼容，单路由使用）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        result = check_api_key()
        if result is not None:
            return result
        return f(*args, **kwargs)
    return decorated_function


def generate_hmac_signature(data, secret_key=None):
    global _runtime_hmac_secret
    if secret_key is None:
        secret_key = os.getenv('HMAC_SECRET')
        if not secret_key:
            # 环境变量未设置，生成随机临时密钥并记录警告
            if _runtime_hmac_secret is None:
                _runtime_hmac_secret = secrets.token_urlsafe(32)
                logger.warning("环境变量 HMAC_SECRET 未设置，已生成随机临时密钥。请在生产环境中配置 HMAC_SECRET。")
            secret_key = _runtime_hmac_secret

    if isinstance(data, dict):
        # 对字典进行排序，确保相同的数据产生相同的签名
        data = '&'.join(f"{k}={v}" for k, v in sorted(data.items()))

    # 使用HMAC-SHA256生成签名
    signature = hmac.new(
        secret_key.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()

    return signature


def verify_hmac_signature(request_signature, data, secret_key=None):
    expected_signature = generate_hmac_signature(data, secret_key)
    return hmac.compare_digest(request_signature, expected_signature)


def require_hmac_auth(f):
    """需要HMAC认证的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        request_signature = request.headers.get('X-HMAC-Signature')
        if not request_signature:
            return jsonify({'error': '缺少HMAC签名'}), 401

        timestamp = request.headers.get('X-Timestamp')
        if not timestamp:
            return jsonify({'error': '缺少时间戳'}), 401

        data = request.get_json(silent=True) or {}

        current_time = int(time.time())
        if abs(current_time - int(timestamp)) > 300:
            return jsonify({'error': '时间戳已过期'}), 401

        # 将时间戳加入验证数据
        verification_data = {**data, 'timestamp': timestamp}

        # 验证签名
        if not verify_hmac_signature(request_signature, verification_data):
            return jsonify({'error': '签名无效'}), 403
        return f(*args, **kwargs)
    return decorated_function
