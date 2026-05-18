"""
Input: 任意外部数据源函数 + 调用参数
Output: 包装后的可调用，自带指数退避重试 + 单次调用超时熔断 + 失败时缓存兜底
Pos: app/core/network_resilience.py - 网络韧性 wrapper, 解决 akshare 外网 RemoteDisconnected

[FIX-7 2026-05-18 +08:00] 三层防御：
  1. tenacity 指数退避重试 (RemoteDisconnected/ConnectionError/Timeout/SSLError, 3 次)
  2. 单次调用超时 (默认 8s, ThreadPoolExecutor.future.result)
  3. 失败降级到最近缓存 (即使过期, 比无数据强)

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import functools
import hashlib
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger(__name__)


class DataSourceTimeoutError(Exception):
    """单次数据源调用超时（用于让 Agent 节点优雅跳过，progress 不卡死）"""
    pass


class DataSourceUnavailableError(Exception):
    """数据源完全不可用且无缓存兜底"""
    pass


# === 异常分类: 何时该重试 ===

def _is_retryable_exception(exc: BaseException) -> bool:
    """识别可重试的网络层异常。

    覆盖:
      - http.client.RemoteDisconnected
      - urllib3.exceptions.ProtocolError / NewConnectionError
      - requests.exceptions.ConnectionError / Timeout / SSLError / ChunkedEncodingError
      - socket.timeout / TimeoutError
      - ConnectionResetError / ConnectionAbortedError / ConnectionRefusedError
    """
    name = type(exc).__name__
    retryable_names = {
        'RemoteDisconnected',
        'ProtocolError',
        'NewConnectionError',
        'ConnectionError',
        'ConnectTimeout',
        'ReadTimeout',
        'Timeout',
        'SSLError',
        'ChunkedEncodingError',
        'ConnectionResetError',
        'ConnectionAbortedError',
        'ConnectionRefusedError',
        'IncompleteRead',
    }
    if name in retryable_names:
        return True
    # 兜底: 通过 msg 关键字
    msg = str(exc)
    keywords = ('Connection aborted', 'Remote end closed', 'EOF occurred',
                'timed out', 'Read timed out', 'ProtocolError')
    return any(k in msg for k in keywords)


# === 缓存兜底 (内存级, 进程内有效) ===

class _StaleCache:
    """简单的 K-V 缓存，记录值与时间戳。失败时可读取过期数据兜底。"""

    def __init__(self):
        self._store: dict = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        with self._lock:
            self._store[key] = (value, time.time(), ttl)

    def get_fresh(self, key: str) -> Tuple[Optional[Any], bool]:
        """返回 (值, 是否命中且未过期)"""
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None, False
            value, ts, ttl = entry
            fresh = (time.time() - ts) < ttl
            return value, fresh

    def get_stale(self, key: str) -> Optional[Any]:
        """返回值（无论过期与否），不存在则 None"""
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            return entry[0]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_GLOBAL_CACHE = _StaleCache()


def reset_cache_for_tests():
    """测试用: 清空缓存。"""
    _GLOBAL_CACHE.clear()


# === 主 wrapper ===

def _make_cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """根据 函数名 + 参数 计算缓存键"""
    fn_name = getattr(func, '__name__', repr(func))
    try:
        args_repr = json.dumps([args, kwargs], default=str, sort_keys=True)
    except Exception:
        args_repr = repr((args, kwargs))
    h = hashlib.md5(args_repr.encode('utf-8')).hexdigest()[:12]
    return f"resilience:{fn_name}:{h}"


def resilient_call(
    func: Callable,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    *,
    max_attempts: int = 3,
    base_wait: float = 1.0,
    max_wait: float = 8.0,
    per_call_timeout: float = 8.0,
    cache_ttl: int = 300,
    use_stale_on_failure: bool = True,
    cache_key: Optional[str] = None,
) -> Any:
    """带重试 + 超时 + 缓存兜底的调用。

    Raises:
        DataSourceTimeoutError: 单次调用超过 per_call_timeout 且无 stale 缓存
        DataSourceUnavailableError: 所有重试失败且无 stale 缓存
        原始异常: 非可重试异常直接抛出
    """
    kwargs = kwargs or {}
    key = cache_key or _make_cache_key(func, args, kwargs)

    # 命中新鲜缓存直接返回
    cached, fresh = _GLOBAL_CACHE.get_fresh(key)
    if fresh:
        return cached

    last_exc: Optional[BaseException] = None

    for attempt in range(1, max_attempts + 1):
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(func, *args, **kwargs)
                try:
                    result = future.result(timeout=per_call_timeout)
                except FutureTimeoutError:
                    future.cancel()
                    last_exc = DataSourceTimeoutError(
                        f"{getattr(func,'__name__',func)} 单次调用超过 {per_call_timeout}s")
                    logger.warning(
                        f"[resilient_call] timeout attempt={attempt}/{max_attempts} "
                        f"func={getattr(func,'__name__',func)}")
                    # 超时不计入"可重试"循环—— 直接走降级
                    break
            # 成功: 写缓存返回
            _GLOBAL_CACHE.set(key, result, ttl=cache_ttl)
            return result
        except Exception as e:
            last_exc = e
            if _is_retryable_exception(e) and attempt < max_attempts:
                wait = min(max_wait, base_wait * (2 ** (attempt - 1)))
                logger.warning(
                    f"[resilient_call] retryable err attempt={attempt}/{max_attempts} "
                    f"wait={wait}s func={getattr(func,'__name__',func)} err={type(e).__name__}: {e}")
                time.sleep(wait)
                continue
            # 不可重试或重试耗尽
            logger.warning(
                f"[resilient_call] giving up attempt={attempt} "
                f"func={getattr(func,'__name__',func)} err={type(e).__name__}: {e}")
            break

    # 降级到 stale 缓存
    if use_stale_on_failure:
        stale = _GLOBAL_CACHE.get_stale(key)
        if stale is not None:
            logger.warning(
                f"[resilient_call] returning stale cache for "
                f"func={getattr(func,'__name__',func)} (last_err={type(last_exc).__name__})")
            return stale

    # 无兜底
    if isinstance(last_exc, DataSourceTimeoutError):
        raise last_exc
    if last_exc:
        raise DataSourceUnavailableError(
            f"{getattr(func,'__name__',func)} 失败且无缓存: {type(last_exc).__name__}: {last_exc}"
        ) from last_exc
    raise DataSourceUnavailableError(
        f"{getattr(func,'__name__',func)} 失败 (无异常上下文)"
    )


def resilient(
    *,
    max_attempts: int = 3,
    per_call_timeout: float = 8.0,
    cache_ttl: int = 300,
    use_stale_on_failure: bool = True,
):
    """装饰器形式包装函数。
    Usage:
        @resilient(per_call_timeout=10, cache_ttl=1800)
        def fetch_stock_data(code): ...
    """
    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return resilient_call(
                fn, args, kwargs,
                max_attempts=max_attempts,
                per_call_timeout=per_call_timeout,
                cache_ttl=cache_ttl,
                use_stale_on_failure=use_stale_on_failure,
            )
        wrapper._original_fn = fn  # type: ignore[attr-defined]
        return wrapper
    return decorator
