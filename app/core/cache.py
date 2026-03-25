# -*- coding: utf-8 -*-
"""
Input: 缓存key + 值
Output: 缓存读写操作
Pos: app/core/cache.py - 统一缓存层(Redis优先/内存降级)
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import os
import json
import time
import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)


class UnifiedCache:
    """统一缓存层：Redis优先，内存dict降级"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._redis = None
        self._memory_cache = {}
        self._memory_ttl = {}
        self._init_redis()
        self._initialized = True

    def _init_redis(self):
        """尝试初始化Redis连接"""
        redis_url = os.getenv('REDIS_URL')
        use_redis = os.getenv('USE_REDIS_CACHE', 'false').lower() == 'true'
        if redis_url and use_redis:
            try:
                import redis
                self._redis = redis.from_url(redis_url, decode_responses=True, socket_timeout=3)
                self._redis.ping()
                logger.info(f"Redis缓存已连接: {redis_url}")
            except Exception as e:
                logger.warning(f"Redis连接失败，降级到内存缓存: {e}")
                self._redis = None
        else:
            logger.info("使用内存缓存（未配置Redis或USE_REDIS_CACHE=false）")

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if self._redis:
            try:
                data = self._redis.get(f"stockanal:{key}")
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis读取失败: {e}")

        # 内存降级
        if key in self._memory_cache:
            if key in self._memory_ttl and time.time() > self._memory_ttl[key]:
                del self._memory_cache[key]
                del self._memory_ttl[key]
                return None
            return self._memory_cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 1800) -> None:
        """设置缓存"""
        if self._redis:
            try:
                self._redis.setex(
                    f"stockanal:{key}", ttl,
                    json.dumps(value, ensure_ascii=False, default=str)
                )
                return
            except Exception as e:
                logger.warning(f"Redis写入失败: {e}")

        # 内存降级
        self._memory_cache[key] = value
        self._memory_ttl[key] = time.time() + ttl

    def delete(self, key: str) -> None:
        """删除缓存"""
        if self._redis:
            try:
                self._redis.delete(f"stockanal:{key}")
            except Exception:
                pass
        self._memory_cache.pop(key, None)
        self._memory_ttl.pop(key, None)

    def clear_expired(self) -> int:
        """清理过期的内存缓存"""
        now = time.time()
        expired_keys = [k for k, t in self._memory_ttl.items() if now > t]
        for k in expired_keys:
            self._memory_cache.pop(k, None)
            self._memory_ttl.pop(k, None)
        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 条过期缓存")
        return len(expired_keys)

    @property
    def is_redis(self) -> bool:
        return self._redis is not None


def get_cache() -> UnifiedCache:
    """获取统一缓存单例"""
    return UnifiedCache()
