# -*- coding: utf-8 -*-
"""
故障转移管理器 - 老王说：接口挂了？自动给你换一个！
Input: 适配器列表、方法名及参数
Output: 第一个成功适配器的返回结果
Pos: app/core层，调度多数据源适配器实现故障转移；为每次 adapter 单次调用加 per-call 超时，
     使 REST 与 agent 工具两条数据链统一获得超时保护（治本修复 get_stock_data 卡死）
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import os
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import List, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

# 单次 adapter 调用的硬超时（秒），由 FALLBACK_PER_CALL_TIMEOUT 驱动，default 30。
# 超时被视为该 adapter 本次失败，落入 execute 的 except 走现有 fallback/重试语义。
_FALLBACK_PER_CALL_TIMEOUT = float(os.getenv('FALLBACK_PER_CALL_TIMEOUT', '30'))


class FallbackManager:
    """故障转移管理器，支持多数据源自动切换"""

    def __init__(self, adapters: List, max_retries: int = 2, retry_delay: float = 0.5,
                 per_call_timeout: Optional[float] = None):
        """
        Args:
            adapters: 按优先级排序的适配器列表
            max_retries: 每个适配器最大重试次数
            retry_delay: 重试间隔（秒）
            per_call_timeout: 单次 adapter 调用的硬超时（秒）；None 时取
                env FALLBACK_PER_CALL_TIMEOUT（default 30）
        """
        self.adapters = adapters
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._per_call_timeout = (
            per_call_timeout if per_call_timeout is not None
            else _FALLBACK_PER_CALL_TIMEOUT)
        self._lock = threading.Lock()
        # 适配器健康状态
        self._adapter_status = {a.name: True for a in adapters}
        # 失败计数
        self._fail_count = {a.name: 0 for a in adapters}

    def execute(self, method_name: str, *args, **kwargs) -> Any:
        """执行方法，自动故障转移

        Args:
            method_name: 要调用的方法名
            *args, **kwargs: 方法参数

        Returns:
            方法返回值

        Raises:
            Exception: 所有数据源均不可用时抛出
        """
        def _loop_once() -> tuple[bool, list, Exception | None, object]:
            """返回(success, tried, last_error, result)"""
            le = None
            tried: list[str] = []
            for adapter in self.adapters:
                adapter_name = adapter.name

                # 跳过已标记为不可用的适配器（但失败次数超过阈值才跳过）
                with self._lock:
                    if self._fail_count.get(adapter_name, 0) >= 5:
                        continue

                # 检查适配器是否有该方法
                if not hasattr(adapter, method_name):
                    continue

                tried.append(adapter_name)
                for retry in range(self.max_retries):
                    try:
                        method = getattr(adapter, method_name)
                        result = self._call_with_timeout(method, args, kwargs)
                        if self._is_valid_result(result):
                            with self._lock:
                                self._fail_count[adapter_name] = 0
                                self._adapter_status[adapter_name] = True
                            return True, tried, None, result
                    except Exception as e:
                        le = e
                        logger.warning(f"[{adapter_name}] {method_name} 失败(重试{retry+1}/{self.max_retries}): {e}")
                        if retry < self.max_retries - 1:
                            time.sleep(self.retry_delay)
                with self._lock:
                    self._fail_count[adapter_name] = self._fail_count.get(adapter_name, 0) + 1
                logger.warning(f"[{adapter_name}] 失败次数: {self._fail_count[adapter_name]}")
            return False, tried, le, None

        success, tried_adapters, last_error, result = _loop_once()
        if success:
            return result
        # 若无adapter被尝试（全被阻塞），重置fail_count重试一次
        if not tried_adapters and self.adapters:
            logger.info(f"所有adapter已阻塞，重置fail_count以重试 {method_name}")
            with self._lock:
                self._fail_count.clear()
            success, tried_adapters, last_error, result = _loop_once()
            if success:
                return result

        # 所有适配器都失败了
        error_msg = f"所有数据源均不可用 (尝试了: {tried_adapters})"
        if last_error:
            error_msg += f", 最后错误: {last_error}"
        raise Exception(error_msg)

    def _call_with_timeout(self, method, args: tuple, kwargs: dict) -> Any:
        """对单次 adapter 调用施加 per-call 硬超时。

        akshare 底层 requests 无 socket timeout，网络停顿时会永久阻塞。这里用
        ThreadPoolExecutor(max_workers=1) + future.result(timeout) 强制单次调用上限，
        超时抛 TimeoutError，由 execute 的 except Exception 捕获，按现有语义重试 /
        切换下一 adapter / 最终降级，绝不整体挂死。

        线程治理：with 语句保证 executor 退出即 shutdown；超时分支显式
        shutdown(wait=False, cancel_futures=True) 避免阻塞与线程泄漏（参考 S3-K 经验）。
        """
        timeout = self._per_call_timeout
        ex = ThreadPoolExecutor(max_workers=1)
        try:
            future = ex.submit(method, *args, **kwargs)
            try:
                return future.result(timeout=timeout)
            except FutureTimeoutError as fte:
                future.cancel()
                logger.warning(
                    f"adapter 单次调用超过 {timeout}s 超时: "
                    f"{getattr(method, '__name__', method)}")
                # 超时 = 该 adapter 本次失败，转成异常走 execute 的 fallback 链
                raise TimeoutError(
                    f"adapter call timeout after {timeout}s") from fte
        finally:
            # 不等待已挂死线程：取消未开始的 future，立即返回（线程随底层调用结束自然回收）
            ex.shutdown(wait=False, cancel_futures=True)

    def _is_valid_result(self, result: Any) -> bool:
        """检查结果是否有效"""
        if result is None:
            return False
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return False
            # 检查K线数据必需列
            required_cols = {'date', 'open', 'high', 'low', 'close', 'volume'}
            if required_cols.issubset(set(result.columns)):
                return True
            # 如果不是K线数据但非空，也视为有效
            return len(result.columns) > 0
        if isinstance(result, (list, dict)) and len(result) == 0:
            return False
        return True

    def reset_status(self):
        """重置所有适配器状态"""
        with self._lock:
            for adapter in self.adapters:
                self._adapter_status[adapter.name] = True
                self._fail_count[adapter.name] = 0

    def get_status(self) -> dict:
        """获取适配器状态"""
        with self._lock:
            return {
                'status': self._adapter_status.copy(),
                'fail_count': self._fail_count.copy()
            }
