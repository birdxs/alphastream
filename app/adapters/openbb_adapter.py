# -*- coding: utf-8 -*-
"""
OpenBB Platform SDK 桥接适配器 [NEW-FILE:#20260415-20]
Input: symbol/indicator + provider(免费优先: yfinance/fred/intrinio免费层)
Output: pd.DataFrame (K线/宏观) 或 dict (profile)
Pos: app/adapters层，OpenBB Platform(AGPL-3.0) 统一接口桥，跨市场+宏观+加密 (obb v4.x)

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

联网调研权威源 (2026-04-15 12:30 +08:00)：
  1. https://github.com/OpenBB-finance/OpenBB - 官方仓库, Platform v4.x, AGPL-3.0(核心)
  2. https://docs.openbb.co/platform - Python SDK `from openbb import obb`; equity/crypto/economy路由
  3. https://pypi.org/project/openbb/ - openbb>=4.0 元包，按需装 providers
  4. 免费provider清单：yfinance(免费)/fmp(免费层)/intrinio(沙盒)/fred(需免费Key)/sec(免费)
"""
import logging
from typing import List, Dict, Optional
import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

# 软依赖：openbb未安装时整模块可用，方法降级返回空结构
try:
    from openbb import obb  # type: ignore
    _OBB_AVAILABLE = True
except Exception:  # ImportError 或 初始化异常
    obb = None  # type: ignore
    _OBB_AVAILABLE = False
    logger.warning("openbb未安装，OpenBBAdapter将返回空结构。pip install openbb 启用")


class OpenBBAdapter(BaseAdapter):
    """OpenBB Platform SDK 桥接适配器。

    - 仅走免费 provider：equity/crypto→yfinance；economy→fred；profile→yfinance
    - 所有失败降级为空结构，不向上游抛异常
    - 非A股数据源，`get_index_stocks` 等A股专属方法返回空
    """

    # 免费 provider 白名单（避免误用付费/需Key Provider）
    FREE_PROVIDERS = {"yfinance", "fred", "sec", "intrinio", "fmp"}

    def __init__(self, default_equity_provider: str = "yfinance",
                 default_economy_provider: str = "fred"):
        self.default_equity_provider = default_equity_provider
        self.default_economy_provider = default_economy_provider

    @property
    def name(self) -> str:
        return "openbb"

    # ==================== 内部工具 ====================
    @staticmethod
    def _obb_to_df(result) -> pd.DataFrame:
        """OpenBB返回对象 → DataFrame。

        OBB result 通常有 `.to_df()` 或 `.results` (list of Pydantic)。
        """
        if result is None:
            return pd.DataFrame()
        # v4 OBBject 约定
        if hasattr(result, "to_df"):
            try:
                df = result.to_df()
                if isinstance(df, pd.DataFrame):
                    return df.reset_index() if df.index.name else df
            except Exception as e:
                logger.warning(f"OpenBB to_df失败: {type(e).__name__}: {e}")
        if hasattr(result, "results"):
            items = result.results
            if not items:
                return pd.DataFrame()
            try:
                rows = [i.model_dump() if hasattr(i, "model_dump") else dict(i) for i in items]
                return pd.DataFrame(rows)
            except Exception as e:
                logger.warning(f"OpenBB results→DataFrame失败: {type(e).__name__}: {e}")
        return pd.DataFrame()

    @staticmethod
    def _obb_to_dict(result) -> Dict:
        """OpenBB返回 → 单条 dict (profile 等)。"""
        if result is None:
            return {}
        if hasattr(result, "results"):
            items = result.results
            if not items:
                return {}
            first = items[0] if isinstance(items, list) else items
            if hasattr(first, "model_dump"):
                return first.model_dump()
            try:
                return dict(first)
            except Exception:
                return {}
        if hasattr(result, "to_df"):
            try:
                df = result.to_df()
                if df is not None and not df.empty:
                    return df.iloc[0].to_dict()
            except Exception:
                pass
        return {}

    def _guard_provider(self, provider: str) -> str:
        """若 provider 不在免费白名单，降级为默认 yfinance。"""
        if provider not in self.FREE_PROVIDERS:
            logger.warning(f"provider={provider} 非免费白名单，降级为yfinance")
            return "yfinance"
        return provider

    # ==================== 核心业务接口 ====================
    def get_equity_price(self, symbol: str, start: Optional[str] = None,
                         end: Optional[str] = None,
                         provider: str = "yfinance") -> pd.DataFrame:
        """股票历史K线 (obb.equity.price.historical)。

        Returns:
            DataFrame columns: date, open, high, low, close, volume (OpenBB标准)
        """
        if not _OBB_AVAILABLE:
            return pd.DataFrame()
        provider = self._guard_provider(provider)
        try:
            kwargs = {"symbol": symbol, "provider": provider}
            if start:
                kwargs["start_date"] = start
            if end:
                kwargs["end_date"] = end
            result = obb.equity.price.historical(**kwargs)
            df = self._obb_to_df(result)
            if df.empty:
                return df
            # 规范列名对齐BaseAdapter
            rename = {}
            for src, dst in (("Date", "date"), ("Open", "open"), ("High", "high"),
                             ("Low", "low"), ("Close", "close"), ("Volume", "volume")):
                if src in df.columns and dst not in df.columns:
                    rename[src] = dst
            if rename:
                df = df.rename(columns=rename)
            return df
        except Exception as e:
            logger.warning(f"openbb get_equity_price失败(symbol={symbol}, provider={provider}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_equity_profile(self, symbol: str, provider: str = "yfinance") -> Dict:
        """公司概况 (obb.equity.profile)。"""
        if not _OBB_AVAILABLE:
            return {}
        provider = self._guard_provider(provider)
        try:
            result = obb.equity.profile(symbol=symbol, provider=provider)
            return self._obb_to_dict(result)
        except Exception as e:
            logger.warning(f"openbb get_equity_profile失败(symbol={symbol}): {type(e).__name__}: {e}")
            return {}

    def get_crypto_price(self, symbol: str, provider: str = "yfinance") -> pd.DataFrame:
        """加密货币K线 (obb.crypto.price.historical)。"""
        if not _OBB_AVAILABLE:
            return pd.DataFrame()
        provider = self._guard_provider(provider)
        try:
            result = obb.crypto.price.historical(symbol=symbol, provider=provider)
            return self._obb_to_df(result)
        except Exception as e:
            logger.warning(f"openbb get_crypto_price失败(symbol={symbol}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_economy_indicator(self, indicator: str,
                              provider: str = "fred") -> pd.DataFrame:
        """宏观指标 (obb.economy.gdp/cpi/... 按 indicator 路由)。

        Args:
            indicator: "gdp" / "cpi" / "unemployment" / 或 FRED series_id
            provider: fred (默认，免费Key) / oecd
        """
        if not _OBB_AVAILABLE:
            return pd.DataFrame()
        provider = self._guard_provider(provider) if provider in self.FREE_PROVIDERS else "fred"
        ind = (indicator or "").lower()
        try:
            if ind in ("gdp", "gdp_real", "gdp_nominal"):
                result = obb.economy.gdp.real(provider=provider)
            elif ind in ("cpi", "inflation"):
                result = obb.economy.cpi(provider=provider)
            elif ind in ("unemployment", "unemp"):
                # OpenBB 无统一unemployment路由 → 走 fred indicators
                result = obb.economy.indicators(symbol="UNRATE", provider=provider) \
                    if hasattr(obb.economy, "indicators") else None
            else:
                # 自定义 FRED series_id
                if hasattr(obb.economy, "fred_series"):
                    result = obb.economy.fred_series(symbol=indicator, provider=provider)
                else:
                    result = obb.economy.indicators(symbol=indicator, provider=provider) \
                        if hasattr(obb.economy, "indicators") else None
            return self._obb_to_df(result)
        except Exception as e:
            logger.warning(f"openbb get_economy_indicator失败(indicator={indicator}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    # ==================== BaseAdapter契约 ====================
    def get_stock_history(self, code: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> pd.DataFrame:
        """委托 get_equity_price；A股6位→Yahoo后缀。"""
        symbol = code
        if code.isdigit() and len(code) == 6:
            symbol = f"{code}.SS" if code.startswith("6") else f"{code}.SZ"

        def _fmt(d: str) -> str:
            d = str(d).strip()
            return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d

        return self.get_equity_price(symbol, start=_fmt(start_date), end=_fmt(end_date))

    def get_index_stocks(self, index_code: str) -> List[str]:
        """OpenBB 默认不覆盖A股指数成分股。"""
        logger.info(f"openbb不支持A股指数成分股({index_code})")
        return []

    def get_stock_info(self, code: str) -> Dict:
        """委托 get_equity_profile。"""
        symbol = code
        if code.isdigit() and len(code) == 6:
            symbol = f"{code}.SS" if code.startswith("6") else f"{code}.SZ"
        return self.get_equity_profile(symbol)

    def get_financial_data(self, code: str) -> Dict:
        """OpenBB fundamentals 需付费provider，免费层返回空，交由yfinance/edgar承担。"""
        logger.info(f"openbb免费层不覆盖财务三表({code})，应由yfinance/edgar提供")
        return {}

    def health_check(self) -> bool:
        """健康检查：尝试取 AAPL 1d 近况。"""
        if not _OBB_AVAILABLE:
            return False
        try:
            df = self.get_equity_price("AAPL")
            return df is not None and not df.empty
        except Exception as e:
            logger.warning(f"openbb健康检查失败: {type(e).__name__}: {e}")
            return False
