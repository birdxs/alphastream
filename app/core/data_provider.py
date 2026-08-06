# -*- coding: utf-8 -*-
"""
统一数据提供层 - 老王说：调数据就找我，别管底下用的啥！
单例模式，全局共享
Input: 股票代码、日期范围等业务查询参数
Output: DataFrame或Dict格式的统一数据结果
Pos: app/core层，业务代码唯一入口，封装故障转移与限流
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
import time
from typing import List, Dict, Optional
import pandas as pd

from .fallback_manager import FallbackManager
from .cache import get_cache
from ..adapters.akshare_adapter import AkshareAdapter
from ..adapters.baostock_adapter import BaostockAdapter

logger = logging.getLogger(__name__)


class DataProvider:
    """统一数据提供层，封装多数据源故障转移"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._init_adapters()
        self._cache = get_cache()
        self._last_request_time = 0
        self._min_interval = 0.2  # 最小200ms间隔
        self._initialized = True

    def _rate_limit(self):
        """简单的请求限流"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _init_adapters(self):
        """初始化适配器"""
        self.akshare = AkshareAdapter()
        self.baostock = BaostockAdapter()

        # DP-P1-1: 引入 AdapterRegistry（渐进统一）
        from ..adapters.adapter_registry import AdapterRegistry
        self._registry = AdapterRegistry.default()

        # 故障转移管理器：保留（向后兼容）
        self.fallback = FallbackManager([
            self.akshare,
            self.baostock,
        ])

        logger.info("DataProvider初始化完成，数据源: Registry(主), FallbackManager(备)")

    def get_stock_history(self, code: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> tuple:
        """
        获取股票历史K线。

        DP-P1-1/P1-2: 返回 (DataFrame, source) 元组。
        - DataFrame: K线数据
        - source: 实际命中的 adapter 名称（如 'akshare' / 'baostock' / 'cache'）
        """
        self._rate_limit()

        cache_key = f"history_{code}_{start_date}_{end_date}_{adjust}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            cached_source = cached.get('source', 'cache') if isinstance(cached, dict) else 'cache'
            cached_data = cached.get('data', cached) if isinstance(cached, dict) else cached
            return pd.DataFrame(cached_data), cached_source

        # DP-P1-1: 优先使用 Registry（a_stock_kline domain）
        try:
            result_dict = self._registry.call_with_fallback(
                'a_stock_kline',
                'get_stock_history',
                stock_code=code,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
                _return_metadata=True
            )
            df = result_dict['data']
            source = result_dict['source']
        except Exception as e:
            logger.warning(f"[DataProvider] Registry 降级失败，回退 FallbackManager: {e}")
            # 回退到旧 FallbackManager
            df = self.fallback.execute('get_stock_history', code, start_date, end_date, adjust)
            source = 'fallback'  # 标记降级路径

        if df is not None and not df.empty:
            self._cache.set(cache_key, {
                'data': df.to_dict('records'),
                'source': source
            }, ttl=1800)
            return df, source

        return pd.DataFrame(), 'empty'

    def get_index_stocks(self, index_code: str) -> List[str]:
        """获取指数成分股"""
        self._rate_limit()
        return self.fallback.execute('get_index_stocks', index_code)

    def get_stock_info(self, code: str) -> Dict:
        """获取股票基本信息"""
        self._rate_limit()

        cache_key = f"info_{code}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        result = self.fallback.execute('get_stock_info', code)

        if result:
            self._cache.set(cache_key, result, ttl=3600)
        return result

    def get_financial_data(self, code: str) -> Dict:
        """获取财务数据"""
        self._rate_limit()

        cache_key = f"financial_{code}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        result = self.fallback.execute('get_financial_data', code)

        if result:
            self._cache.set(cache_key, result, ttl=3600)
        return result

    # ========== akshare专有方法（无baostock备用）==========

    def get_board_stocks(self, board: str) -> List[str]:
        """获取板块股票列表（仅akshare支持）"""
        self._rate_limit()
        return self.akshare.get_board_stocks(board)

    def get_industry_list(self) -> pd.DataFrame:
        """获取行业板块列表（仅akshare支持）"""
        self._rate_limit()
        return self.akshare.get_industry_list()

    def get_industry_stocks(self, industry: str) -> List[str]:
        """获取行业成分股（仅akshare支持）"""
        self._rate_limit()
        return self.akshare.get_industry_stocks(industry)

    def get_concept_stocks(self, concept: str) -> List[str]:
        """获取概念板块成分股代码列表"""
        self._rate_limit()
        return self.akshare.get_concept_stocks(concept)

    def get_concept_stocks_detail(self, concept: str) -> List[Dict]:
        """获取概念板块成分股详细信息（含名称、价格等）"""
        self._rate_limit()
        return self.akshare.get_concept_stocks_detail(concept)

    def get_capital_flow(self, code: str) -> Dict:
        """获取资金流向（仅akshare支持）"""
        self._rate_limit()
        return self.akshare.get_capital_flow(code)

    def get_north_flow(self) -> pd.DataFrame:
        """获取北向资金（仅akshare支持）"""
        self._rate_limit()
        return self.akshare.get_north_flow()

    # ========== 状态管理 ==========

    def health_check(self) -> Dict:
        """健康检查"""
        return {
            'akshare': self.akshare.health_check(),
            'baostock': self.baostock.health_check(),
        }

    def get_status(self) -> Dict:
        """获取数据源状态"""
        return self.fallback.get_status()

    def reset_status(self):
        """重置数据源状态"""
        self.fallback.reset_status()


# 全局单例
_data_provider = None


def get_data_provider() -> DataProvider:
    """获取DataProvider单例"""
    global _data_provider
    if _data_provider is None:
        _data_provider = DataProvider()
    return _data_provider
