# -*- coding: utf-8 -*-
"""
ccxt加密货币统一交易所适配器 [NEW-FILE:#20260415-11]
Input: exchange_id (binance/okx/coinbase...)、symbol (BTC/USDT)、timeframe/limit
Output: pd.DataFrame (OHLCV/markets) 或 Dict (ticker/order_book)
Pos: app/adapters层，加密货币跨交易所统一接入 (ccxt v4+, MIT)

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

联网调研权威源 (2026-04-15 12:00 +08:00)：
  1. https://github.com/ccxt/ccxt - 官方仓库 README (MIT, 100+交易所)
  2. https://docs.ccxt.com/ - 统一API：fetch_ticker/fetch_ohlcv/fetch_order_book/load_markets
  3. https://pypi.org/project/ccxt/ - PyPI release 版本兼容矩阵
  4. ccxt Manual 符号格式：BASE/QUOTE（如 BTC/USDT），timeframe标准 1m/5m/15m/1h/4h/1d/1w
"""
import logging
from typing import List, Dict, Optional
import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

# 软依赖：ccxt未安装时模块可import，方法降级返回空结构
try:
    import ccxt  # type: ignore
    _CCXT_AVAILABLE = True
except ImportError:
    ccxt = None  # type: ignore
    _CCXT_AVAILABLE = False
    logger.warning("ccxt未安装，CCXTAdapter将返回空结构。pip install ccxt 启用")


class CCXTAdapter(BaseAdapter):
    """ccxt统一交易所适配器，覆盖Binance/OKX/Coinbase/Kraken等100+交易所。

    符号规范：`BASE/QUOTE`（如 `BTC/USDT`、`ETH/BTC`）
    timeframe：`1m/5m/15m/30m/1h/4h/1d/1w/1M`
    """

    VALID_TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
                        "6h", "8h", "12h", "1d", "3d", "1w", "1M"}

    def __init__(self, exchange_id: str = "binance"):
        self.exchange_id = exchange_id
        self._exchange = None
        if _CCXT_AVAILABLE:
            try:
                klass = getattr(ccxt, exchange_id, None)
                if klass is None:
                    logger.warning(f"ccxt未知交易所 exchange_id={exchange_id}")
                else:
                    # enableRateLimit 启用内建限流，避免触发交易所风控
                    self._exchange = klass({"enableRateLimit": True, "timeout": 20000})
            except Exception as e:
                logger.warning(f"ccxt实例化失败({exchange_id}): {type(e).__name__}: {e}")

    @property
    def name(self) -> str:
        return f"ccxt:{self.exchange_id}"

    # ==================== 核心业务接口 ====================
    def get_ticker(self, symbol: str) -> Dict:
        """获取单交易对实时行情 (fetch_ticker)。

        Returns:
            {symbol, last, bid, ask, high, low, volume, timestamp, ...} 或 {}
        """
        if not self._exchange:
            return {}
        try:
            t = self._exchange.fetch_ticker(symbol)
            return dict(t) if t else {}
        except Exception as e:
            logger.warning(f"ccxt get_ticker失败({self.exchange_id}:{symbol}): {type(e).__name__}: {e}")
            return {}

    def get_ohlcv(self, symbol: str, timeframe: str = "1d",
                  limit: int = 100) -> pd.DataFrame:
        """获取K线 (fetch_ohlcv)。

        Returns:
            DataFrame columns: date, open, high, low, close, volume
        """
        if not self._exchange:
            return pd.DataFrame()
        if timeframe not in self.VALID_TIMEFRAMES:
            logger.warning(f"非法timeframe={timeframe}，降级为1d")
            timeframe = "1d"
        try:
            rows = self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df[["date", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            logger.warning(f"ccxt get_ohlcv失败({self.exchange_id}:{symbol}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """获取盘口深度 (fetch_order_book)。

        Returns:
            {"bids": [[price, amount], ...], "asks": [...], "timestamp": ms, "symbol": str}
        """
        if not self._exchange:
            return {"bids": [], "asks": [], "timestamp": None, "symbol": symbol}
        try:
            ob = self._exchange.fetch_order_book(symbol, limit=limit)
            return {
                "bids": ob.get("bids", []) or [],
                "asks": ob.get("asks", []) or [],
                "timestamp": ob.get("timestamp"),
                "symbol": symbol,
            }
        except Exception as e:
            logger.warning(f"ccxt get_order_book失败({self.exchange_id}:{symbol}): {type(e).__name__}: {e}")
            return {"bids": [], "asks": [], "timestamp": None, "symbol": symbol}

    def list_markets(self) -> pd.DataFrame:
        """列出该交易所全部交易对 (load_markets)。

        Returns:
            DataFrame columns: symbol, base, quote, active, type
        """
        if not self._exchange:
            return pd.DataFrame()
        try:
            markets = self._exchange.load_markets()
            if not markets:
                return pd.DataFrame()
            rows = []
            for sym, m in markets.items():
                if not isinstance(m, dict):
                    continue
                rows.append({
                    "symbol": sym,
                    "base": m.get("base"),
                    "quote": m.get("quote"),
                    "active": m.get("active"),
                    "type": m.get("type") or ("spot" if m.get("spot") else None),
                })
            return pd.DataFrame(rows)
        except Exception as e:
            logger.warning(f"ccxt list_markets失败({self.exchange_id}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    # ==================== BaseAdapter契约 ====================
    def get_stock_history(self, code: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> pd.DataFrame:
        """BaseAdapter契约：按日期区间取日K（code作为symbol，如 BTC/USDT）。"""
        if not self._exchange:
            return pd.DataFrame()
        # 加密货币无复权概念，忽略adjust
        df = self.get_ohlcv(code, timeframe="1d", limit=1000)
        if df.empty:
            return df
        def _fmt(d: str) -> str:
            d = str(d).strip()
            return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d
        try:
            start = pd.to_datetime(_fmt(start_date))
            end = pd.to_datetime(_fmt(end_date))
            df = df[(df["date"] >= start) & (df["date"] <= end)].copy()
            df["amount"] = df["close"] * df["volume"]
            return df
        except Exception as e:
            logger.warning(f"ccxt get_stock_history日期过滤失败: {type(e).__name__}: {e}")
            return df

    def get_index_stocks(self, index_code: str) -> List[str]:
        """加密货币无传统指数成分概念，返回空列表。"""
        logger.info(f"ccxt不支持指数成分股({index_code})")
        return []

    def get_stock_info(self, code: str) -> Dict:
        """契约：委托 get_ticker。"""
        return self.get_ticker(code)

    def get_financial_data(self, code: str) -> Dict:
        """加密货币无财报，返回空结构。"""
        return {}

    def health_check(self) -> bool:
        """健康检查：load_markets 是否成功。"""
        if not self._exchange:
            return False
        try:
            markets = self._exchange.load_markets()
            return bool(markets)
        except Exception as e:
            logger.warning(f"ccxt健康检查失败({self.exchange_id}): {type(e).__name__}: {e}")
            return False
