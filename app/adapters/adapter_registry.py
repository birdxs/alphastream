# -*- coding: utf-8 -*-
"""
适配器统一注册中心 [NEW-FILE:#20260415-21]
Input: domain(业务域字符串)、method(适配器方法名)、**kwargs
Output: 第一个成功适配器的返回值 (DataFrame/dict/list)，全fail时raise
Pos: app/adapters层，跨数据源自动降级路由表，融合FallbackManager核心算法

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

联网调研权威源 (2026-04-15 12:30 +08:00)：
  1. FallbackManager 实现 app/core/fallback_manager.py (本项目) - 复用_is_valid_result逻辑
  2. OpenBB Platform 多provider路由思想 https://docs.openbb.co/platform/user_guides/basic_syntax
  3. 现有BaseAdapter契约 app/adapters/base_adapter.py

Domain映射（覆盖 P0/P1/P2）：
  a_stock_kline        : Akshare → Baostock → Efinance → YFinance
  a_stock_realtime     : Efinance → Akshare → OpenCLI
  us_stock             : YFinance → OpenBB → EDGAR
  hk_stock             : YFinance → Akshare
  macro_us             : FRED → OpenBB → WorldBank
  macro_cn             : NBS → Akshare
  macro_global         : WorldBank → IMF → OpenBB
  crypto               : CCXT → CoinGecko → YFinance → OpenBB
  news                 : OpenCLI → Akshare
  sentiment_social     : OpenCLI
  xbrl_financials      : EDGAR → YFinance → OpenBB
  esg_rating           : ESG (ESG Book/CDP/B Corp/CUFE + SEC气候复用EDGAR) [P3-D3]
  commodity_shipping   : Shipping (BDI/港口吞吐/AIS AISHub+交通运输部) [P3-D1 2026-04-15]
  earth_observation    : Satellite (NASA CMR对地观测collections+granules)  [P3-D1 2026-04-15]
  corporate_entity     : OpenCorporates v0.4 (search/details/network) [P3-D2 2026-04-15]
  hiring_signal        : Jobs (Arbeitnow + 拉勾降级) [P3-D2 2026-04-15]
"""
import logging
import threading
from typing import Any, Dict, List, Optional, Type
import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


def _safe_instantiate(cls: Type[BaseAdapter]) -> Optional[BaseAdapter]:
    """静默实例化适配器；构造失败(如依赖缺失)返回None。"""
    try:
        return cls()
    except Exception as e:
        logger.warning(f"[AdapterRegistry] {cls.__name__} 实例化失败，跳过: {type(e).__name__}: {e}")
        return None


class AdapterRegistry:
    """适配器注册与降级调度中心。

    使用方式：
        reg = AdapterRegistry.default()
        df = reg.call_with_fallback("a_stock_kline", "get_stock_history",
                                    code="000001", start_date="20240101", end_date="20240201")
    """

    # 默认 domain → adapter类名 优先级映射
    DEFAULT_DOMAIN_MAP: Dict[str, List[str]] = {
        "a_stock_kline":     ["AkshareAdapter", "BaostockAdapter", "EfinanceAdapter", "AshareAdapter", "YFinanceAdapter"],
        "a_stock_realtime":  ["EfinanceAdapter", "EasyquotationAdapter", "AkshareAdapter", "OpenCLIBridge"],
        "us_stock":          ["YFinanceAdapter", "OpenBBAdapter", "EDGARAdapter"],
        "hk_stock":          ["YFinanceAdapter", "AkshareAdapter"],
        "macro_us":          ["FREDAdapter", "OpenBBAdapter", "WorldBankAdapter"],
        "macro_cn":          ["NBSAdapter", "AkshareAdapter"],
        "macro_global":      ["WorldBankAdapter", "IMFAdapter", "OpenBBAdapter"],
        "crypto":            ["CCXTAdapter", "CoinGeckoAdapter", "YFinanceAdapter", "OpenBBAdapter"],
        "news":              ["RSSNewsAdapter", "OpenCLIBridge", "AkshareAdapter"],
        "sentiment_social":  ["OpenCLIBridge"],
        "xbrl_financials":   ["EDGARAdapter", "YFinanceAdapter", "OpenBBAdapter"],
        "esg_rating":        ["ESGAdapter"],
        "commodity_shipping": ["ShippingAdapter"],
        "earth_observation":  ["SatelliteAdapter"],
        "corporate_entity":   ["CorporateAdapter"],
        "hiring_signal":      ["JobsAdapter"],
    }

    def __init__(self, max_retries: int = 2, retry_delay: float = 0.5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._registry: Dict[str, List[BaseAdapter]] = {}
        self._lock = threading.Lock()
        self._fail_count: Dict[str, int] = {}

    # ==================== 注册 ====================
    def register(self, domain: str, adapter: BaseAdapter) -> None:
        """注册单个适配器到域。"""
        with self._lock:
            self._registry.setdefault(domain, []).append(adapter)
            self._fail_count.setdefault(adapter.name, 0)

    def register_adapters(self, domain_map: Optional[Dict[str, List[str]]] = None) -> None:
        """批量注册：按类名查找并实例化，失败静默跳过。"""
        # 延迟导入，避免循环
        # 以字符串名延迟加载，缺失模块不阻塞注册
        import importlib
        module_index: Dict[str, Optional[Type[BaseAdapter]]] = {}
        for cls_name, mod_name in [
            ("AkshareAdapter",       "akshare_adapter"),
            ("BaostockAdapter",      "baostock_adapter"),
            ("EfinanceAdapter",      "efinance_adapter"),
            ("YFinanceAdapter",      "yfinance_adapter"),
            ("EDGARAdapter",         "edgar_adapter"),
            ("NBSAdapter",           "nbs_adapter"),
            ("FREDAdapter",          "fred_adapter"),
            ("CCXTAdapter",          "ccxt_adapter"),
            ("CoinGeckoAdapter",     "coingecko_adapter"),
            ("WorldBankAdapter",     "worldbank_adapter"),
            ("IMFAdapter",           "imf_adapter"),
            ("OpenCLIBridge",        "opencli_bridge"),
            ("OpenBBAdapter",        "openbb_adapter"),
            ("AshareAdapter",        "ashare_adapter"),
            ("EasyquotationAdapter", "easyquotation_adapter"),
            ("RSSNewsAdapter",       "rss_news_adapter"),
            ("ESGAdapter",           "esg_adapter"),
            ("ShippingAdapter",      "shipping_adapter"),
            ("SatelliteAdapter",     "satellite_adapter"),
            ("CorporateAdapter",     "corporate_adapter"),
            ("JobsAdapter",          "jobs_adapter"),
        ]:
            try:
                mod = importlib.import_module(f".{mod_name}", package="app.adapters")
                module_index[cls_name] = getattr(mod, cls_name, None)
            except Exception as e:
                logger.warning(f"[AdapterRegistry] 模块 {mod_name} 加载失败: {type(e).__name__}: {e}")
                module_index[cls_name] = None
        # 实例化缓存：同一适配器只创建一次
        inst_cache: Dict[str, Optional[BaseAdapter]] = {}
        dmap = domain_map or self.DEFAULT_DOMAIN_MAP
        for domain, names in dmap.items():
            for n in names:
                if n not in inst_cache:
                    cls = module_index.get(n)
                    inst_cache[n] = _safe_instantiate(cls) if cls else None
                inst = inst_cache[n]
                if inst is not None:
                    self.register(domain, inst)

    # ==================== 查询 ====================
    def get_adapters(self, domain: str) -> List[BaseAdapter]:
        """按优先级返回已注册适配器列表。"""
        with self._lock:
            return list(self._registry.get(domain, []))

    def list_domains(self) -> List[str]:
        with self._lock:
            return sorted(self._registry.keys())

    # ==================== 调度 ====================
    def call_with_fallback(self, domain: str, method: str, **kwargs) -> Any:
        """按domain降级调用 method(**kwargs)，首个有效结果即返回。"""
        adapters = self.get_adapters(domain)
        if not adapters:
            raise ValueError(f"domain={domain} 未注册任何适配器")

        tried: List[str] = []
        last_error: Optional[Exception] = None

        for adapter in adapters:
            aname = adapter.name
            if not hasattr(adapter, method):
                logger.debug(f"[{aname}] 无方法 {method}，跳过")
                continue
            tried.append(aname)
            for retry in range(self.max_retries):
                try:
                    result = getattr(adapter, method)(**kwargs)
                    if self._is_valid_result(result):
                        with self._lock:
                            self._fail_count[aname] = 0
                        return result
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"[{aname}] {domain}.{method} 失败(重试{retry+1}/{self.max_retries}): {type(e).__name__}: {e}"
                    )
            with self._lock:
                self._fail_count[aname] = self._fail_count.get(aname, 0) + 1

        msg = f"domain={domain} method={method} 全部数据源降级失败 (tried={tried})"
        if last_error:
            msg += f", last_error={last_error}"
        raise Exception(msg)

    @staticmethod
    def _is_valid_result(result: Any) -> bool:
        """复用 FallbackManager 的有效性判定。"""
        if result is None:
            return False
        if isinstance(result, pd.DataFrame):
            return not result.empty
        if isinstance(result, (list, dict)) and len(result) == 0:
            return False
        return True

    def get_status(self) -> Dict[str, Any]:
        """获取各域与失败计数快照。"""
        with self._lock:
            return {
                "domains": {d: [a.name for a in adapters] for d, adapters in self._registry.items()},
                "fail_count": dict(self._fail_count),
            }

    # ==================== 单例 ====================
    _default: Optional["AdapterRegistry"] = None
    _default_lock = threading.Lock()

    @classmethod
    def default(cls) -> "AdapterRegistry":
        """进程级单例；首次调用自动 register_adapters()。"""
        with cls._default_lock:
            if cls._default is None:
                inst = cls()
                inst.register_adapters()
                cls._default = inst
            return cls._default

    @classmethod
    def reset_default(cls) -> None:
        """重置单例（测试用）。"""
        with cls._default_lock:
            cls._default = None
