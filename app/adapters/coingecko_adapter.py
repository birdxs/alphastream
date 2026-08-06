# -*- coding: utf-8 -*-
"""
CoinGecko公开API适配器 [NEW-FILE:#20260415-12]
Input: coin_id (bitcoin/ethereum...)、vs_currency、days
Output: Dict (price/global/trending) 或 pd.DataFrame (market_chart)
Pos: app/adapters层，加密货币市场概览+趋势（CoinGecko 免费层 ≤30 req/min）

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

联网调研权威源 (2026-04-15 12:00 +08:00)：
  1. https://www.coingecko.com/api/documentation - 官方API文档 (/simple/price,/coins,/global,/search/trending)
  2. https://docs.coingecko.com/reference/introduction - Public API Demo Plan rate limit 30 calls/min
  3. https://github.com/man-c/pycoingecko - Python SDK 参考实现 (MIT)
  4. https://pypi.org/project/pycoingecko/ - 版本/端点矩阵
"""
import logging
import time
import threading
from typing import List, Dict
import pandas as pd
import requests

from .base_adapter import BaseAdapter
from ._proxy_utils import get_proxies

logger = logging.getLogger(__name__)


class CoinGeckoAdapter(BaseAdapter):
    """CoinGecko公开API适配器，免费层≤30 req/min，纯requests无需API Key。"""

    BASE_URL = "https://api.coingecko.com/api/v3"
    # 30 req/min → 最小间隔 2.0s，留余量
    _MIN_INTERVAL = 2.1

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._last_request_ts = 0.0
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "coingecko"

    # ==================== 限流 ====================
    def _throttle(self):
        """线程安全的最小间隔限流，确保 ≤30 req/min。"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_ts
            if elapsed < self._MIN_INTERVAL:
                time.sleep(self._MIN_INTERVAL - elapsed)
            self._last_request_ts = time.time()

    def _get(self, path: str, params: Dict = None) -> Dict:
        """统一GET请求，带限流+异常兜底。"""
        self._throttle()
        url = f"{self.BASE_URL}{path}"
        try:
            resp = requests.get(url, params=params or {}, timeout=self.timeout,
                                headers={"Accept": "application/json",
                                         "User-Agent": "StockAnalSys/CoinGeckoAdapter"},
                                proxies=get_proxies())
            if resp.status_code == 429:
                logger.warning("CoinGecko 429限流，退避2s")
                time.sleep(2.0)
                return {}
            if resp.status_code != 200:
                logger.warning(f"CoinGecko非200响应 {resp.status_code} path={path}")
                return {}
            return resp.json()
        except Exception as e:
            logger.warning(f"CoinGecko请求失败 path={path}: {type(e).__name__}: {e}")
            return {}

    # ==================== 核心业务接口 ====================
    def get_price(self, coin_ids: List[str], vs: str = "usd") -> Dict:
        """批量获取实时价格 (/simple/price)。

        Args:
            coin_ids: ["bitcoin", "ethereum", ...]
            vs: 计价货币 "usd"/"cny"/"eur"/"btc"...

        Returns:
            {"bitcoin": {"usd": 65000.0}, "ethereum": {"usd": 3200.0}}
        """
        if not coin_ids:
            return {}
        data = self._get("/simple/price", {
            "ids": ",".join(coin_ids),
            "vs_currencies": vs,
        })
        if isinstance(data, dict) and data:
            return data
        # P2: AkShare 加密货币降级 (2026-08-05)
        logger.warning(f"CoinGecko price失败，尝试AkShare降级 coin_ids={coin_ids}")
        try:
            return self._akshare_crypto_price_fallback(coin_ids, vs)
        except Exception as e:
            logger.error(f"AkShare加密货币price降级失败: {type(e).__name__}: {e}")
            return {}

    def get_market_chart(self, coin_id: str, days: int = 30,
                         vs: str = "usd") -> pd.DataFrame:
        """获取市场历史 (/coins/{id}/market_chart)。

        Returns:
            DataFrame columns: date, price, market_cap, volume
        """
        data = self._get(f"/coins/{coin_id}/market_chart", {
            "vs_currency": vs,
            "days": days,
        })
        if not isinstance(data, dict) or not data.get("prices"):
            # P2: AkShare 加密货币历史降级 (2026-08-05)
            logger.warning(f"CoinGecko market_chart失败({coin_id})，尝试AkShare降级")
            try:
                return self._akshare_crypto_hist_fallback(coin_id, days, vs)
            except Exception as e:
                logger.error(f"AkShare加密货币历史降级失败: {type(e).__name__}: {e}")
                return pd.DataFrame()
        try:
            prices = data.get("prices", [])
            mcaps = data.get("market_caps", [])
            vols = data.get("total_volumes", [])
            df = pd.DataFrame(prices, columns=["timestamp", "price"])
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
            if mcaps and len(mcaps) == len(prices):
                df["market_cap"] = [m[1] for m in mcaps]
            if vols and len(vols) == len(prices):
                df["volume"] = [v[1] for v in vols]
            cols = [c for c in ["date", "price", "market_cap", "volume"] if c in df.columns]
            return df[cols]
        except Exception as e:
            logger.warning(f"CoinGecko market_chart解析失败({coin_id}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_trending(self) -> List[Dict]:
        """获取24h趋势榜 (/search/trending)。

        Returns:
            [{"id","name","symbol","market_cap_rank","score"}, ...]
        """
        data = self._get("/search/trending")
        if not isinstance(data, dict):
            return []
        coins = data.get("coins", []) or []
        result = []
        for entry in coins:
            item = entry.get("item") if isinstance(entry, dict) else None
            if not item:
                continue
            result.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "symbol": item.get("symbol"),
                "market_cap_rank": item.get("market_cap_rank"),
                "score": item.get("score"),
            })
        return result

    def get_global(self) -> Dict:
        """获取全球加密市场总览 (/global)。

        Returns:
            {"total_market_cap_usd","total_volume_usd","btc_dominance",
             "active_cryptocurrencies","markets"}
        """
        data = self._get("/global")
        if not isinstance(data, dict):
            return {}
        inner = data.get("data") or {}
        if not isinstance(inner, dict):
            return {}
        mcap = inner.get("total_market_cap", {}) or {}
        vol = inner.get("total_volume", {}) or {}
        dominance = inner.get("market_cap_percentage", {}) or {}
        return {
            "total_market_cap_usd": mcap.get("usd"),
            "total_volume_usd": vol.get("usd"),
            "btc_dominance": dominance.get("btc"),
            "eth_dominance": dominance.get("eth"),
            "active_cryptocurrencies": inner.get("active_cryptocurrencies"),
            "markets": inner.get("markets"),
            "updated_at": inner.get("updated_at"),
        }

    # ==================== BaseAdapter契约 ====================
    def _akshare_crypto_price_fallback(self, coin_ids: List[str], vs: str = "usd") -> Dict:
        """P2: AkShare 加密货币价格降级 (2026-08-05)

        Args:
            coin_ids: ["bitcoin", "ethereum", ...]
            vs: 计价货币

        Returns:
            {"bitcoin": {"usd": 65000.0}, ...}
        """
        try:
            import akshare as ak
        except ImportError:
            logger.warning("[CoinGecko] akshare未安装，无法降级")
            return {}

        result = {}
        # AkShare crypto_js_spot() 返回实时快照
        try:
            df = ak.crypto_js_spot()
            if df.empty:
                return {}

            # 映射币种名称
            symbol_map = {
                "bitcoin": ["比特币", "BTC"],
                "ethereum": ["以太坊", "ETH"],
                "binancecoin": ["币安币", "BNB"],
                "cardano": ["艾达币", "ADA"],
                "solana": ["SOL"],
                "ripple": ["瑞波币", "XRP"],
                "polkadot": ["DOT"],
                "dogecoin": ["狗狗币", "DOGE"],
            }

            for coin_id in coin_ids:
                keywords = symbol_map.get(coin_id.lower(), [])
                if not keywords:
                    continue

                # 查找匹配行
                for keyword in keywords:
                    matched = df[df.iloc[:, 0].astype(str).str.contains(keyword, na=False)]
                    if not matched.empty:
                        # 假设第二列为价格
                        latest_price = float(matched.iloc[0, 1])
                        result[coin_id] = {vs: latest_price}
                        break
        except Exception as e:
            logger.error(f"[CoinGecko] AkShare crypto_js_spot降级失败: {type(e).__name__}: {e}")

        return result

    def _akshare_crypto_hist_fallback(self, coin_id: str, days: int, vs: str) -> pd.DataFrame:
        """P2: AkShare 加密货币历史降级 (2026-08-05)

        Returns:
            DataFrame columns: date, price, volume
        """
        try:
            import akshare as ak
        except ImportError:
            logger.warning("[CoinGecko] akshare未安装，无法降级")
            return pd.DataFrame()

        # AkShare crypto_js_spot 仅返回实时快照，无历史接口
        # 降级策略：返回空 DataFrame
        logger.warning(f"[CoinGecko] AkShare不支持加密货币历史数据，coin_id={coin_id}")
        return pd.DataFrame()

    # ==================== BaseAdapter契约 ====================
    def get_stock_history(self, code: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> pd.DataFrame:
        """契约：code作为coin_id，按区间取日线。"""
        def _parse(d: str) -> pd.Timestamp:
            d = str(d).strip()
            fmt = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d
            return pd.to_datetime(fmt)
        try:
            start = _parse(start_date)
            end = _parse(end_date)
            days = max(1, (end - start).days + 1)
            df = self.get_market_chart(code, days=days)
            if df.empty:
                return df
            df = df[(df["date"] >= start) & (df["date"] <= end)].copy()
            return df
        except Exception as e:
            logger.warning(f"CoinGecko get_stock_history失败({code}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        """CoinGecko无传统指数成分。"""
        return []

    def get_stock_info(self, code: str) -> Dict:
        """契约：委托 get_price。"""
        data = self.get_price([code])
        return data.get(code, {}) if isinstance(data, dict) else {}

    def get_financial_data(self, code: str) -> Dict:
        """加密货币无财报。"""
        return {}

    def health_check(self) -> bool:
        """健康检查：/ping端点。"""
        data = self._get("/ping")
        return isinstance(data, dict) and data.get("gecko_says") is not None
