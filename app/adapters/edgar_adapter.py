# -*- coding: utf-8 -*-
"""
SEC EDGAR 官方适配器 - 老王说：美股XBRL标准财报，UA必填+10req/s硬上限！
Input: ticker/CIK/XBRL tag等查询参数 (如 AAPL, 0000320193, us-gaap:Revenues)
Output: dict/DataFrame 格式的申报历史、全量财务事实、单指标时间序列
Pos: app/adapters层，作为美股基本面数据源，由fallback_manager在基本面Agent中调度

SEC EDGAR 官方规范 (已交叉验证3源)：
- https://www.sec.gov/edgar/sec-api-documentation (官方API文档)
- https://www.sec.gov/os/accessing-edgar-data (Fair Access: 10req/s上限)
- https://www.sec.gov/files/company_tickers.json (ticker→CIK映射)
关键约束：
1. User-Agent必填，格式 "CompanyName ContactEmail" (否则403)
2. 限流 ≤10 requests/second (否则 403 Undeclared Automated Tools)
3. CIK必须 padding 为10位 (如 320193 → 0000320193)

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import os
import time
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime, timedelta

import requests
import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class EDGARAdapter(BaseAdapter):
    """SEC EDGAR 官方XBRL财报适配器

    端点：
    - https://www.sec.gov/files/company_tickers.json          (ticker→CIK映射)
    - https://data.sec.gov/submissions/CIK{cik10}.json        (申报历史)
    - https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json   (全XBRL)
    - https://data.sec.gov/api/xbrl/companyconcept/CIK{cik10}/{taxonomy}/{tag}.json
    """

    BASE_WWW = "https://www.sec.gov"
    BASE_DATA = "https://data.sec.gov"

    # 限流：SEC Fair Access 10req/s → 最小间隔 0.11s
    _MIN_INTERVAL = 0.11

    # ticker_map 缓存 TTL（秒）
    _TICKER_MAP_TTL = 24 * 3600

    def __init__(self, user_agent: Optional[str] = None, timeout: int = 20):
        """初始化

        Args:
            user_agent: SEC要求UA格式 "CompanyName ContactEmail"；
                        缺省从环境变量 SEC_EDGAR_UA 读取，否则用默认兜底UA。
            timeout: 单次请求超时秒数。
        """
        ua = (
            user_agent
            or os.environ.get("SEC_EDGAR_UA")
            or "StockAnalSys research@example.com"
        )
        if " " not in ua or "@" not in ua:
            logger.warning(
                f"SEC EDGAR UA 疑似不合规 (应为 'Name Email'): {ua!r}"
            )
        self.user_agent = ua
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        })

        # 限流 token bucket（简化为最小间隔锁）
        self._lock = threading.Lock()
        self._last_request_ts = 0.0

        # ticker→CIK 缓存
        self._ticker_map_cache: Optional[Dict[str, str]] = None
        self._ticker_map_fetched_at: float = 0.0

    @property
    def name(self) -> str:
        return "sec_edgar"

    # ----------------------------- 限流 -----------------------------

    def _throttle(self) -> None:
        """强制 ≤10req/s：同步锁保证任意两次请求间隔 ≥ 0.11s"""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_ts
            if elapsed < self._MIN_INTERVAL:
                time.sleep(self._MIN_INTERVAL - elapsed)
            self._last_request_ts = time.monotonic()

    def _get_json(self, url: str, host_override: Optional[str] = None) -> dict:
        """统一GET，强制UA+限流。返回JSON dict；失败返回空dict"""
        self._throttle()
        headers = {}
        if host_override:
            headers["Host"] = host_override
        try:
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code == 429:
                logger.warning(f"SEC EDGAR 429限流触发: {url}，退避2s")
                time.sleep(2.0)
                return {}
            if resp.status_code != 200:
                logger.warning(
                    f"SEC EDGAR HTTP {resp.status_code}: {url}"
                )
                return {}
            return resp.json()
        except Exception as e:
            logger.warning(f"SEC EDGAR 请求失败 {url}: {type(e).__name__}: {e}")
            return {}

    # --------------------------- CIK 映射 ---------------------------

    @staticmethod
    def _pad_cik(cik) -> str:
        """CIK 左填零到10位：320193 → '0000320193'"""
        s = str(cik).strip().lstrip("CIK").lstrip("cik").lstrip("0") or "0"
        return s.zfill(10)

    def get_ticker_cik_map(self, force_refresh: bool = False) -> Dict[str, str]:
        """拉取 company_tickers.json，返回 {TICKER_UPPER: cik10}

        缓存 24h，过期自动刷新。
        """
        now = time.time()
        if (
            not force_refresh
            and self._ticker_map_cache is not None
            and (now - self._ticker_map_fetched_at) < self._TICKER_MAP_TTL
        ):
            return self._ticker_map_cache

        url = f"{self.BASE_WWW}/files/company_tickers.json"
        data = self._get_json(url, host_override="www.sec.gov")
        if not data:
            # 刷新失败但有旧缓存就继续用
            return self._ticker_map_cache or {}

        mapping: Dict[str, str] = {}
        # 官方格式：{"0": {"cik_str":320193,"ticker":"AAPL","title":"Apple Inc."}, ...}
        for _, entry in data.items():
            try:
                ticker = str(entry["ticker"]).upper().strip()
                cik10 = self._pad_cik(entry["cik_str"])
                mapping[ticker] = cik10
            except (KeyError, TypeError):
                continue

        self._ticker_map_cache = mapping
        self._ticker_map_fetched_at = now
        return mapping

    def get_cik(self, ticker: str) -> str:
        """ticker → 10位 padded CIK 字符串；找不到返回空串"""
        if not ticker:
            return ""
        mp = self.get_ticker_cik_map()
        return mp.get(ticker.upper().strip(), "")

    # --------------------------- 核心端点 ---------------------------

    def get_submissions(self, cik: str) -> dict:
        """公司申报历史 CIK{cik10}.json"""
        cik10 = self._pad_cik(cik)
        url = f"{self.BASE_DATA}/submissions/CIK{cik10}.json"
        return self._get_json(url, host_override="data.sec.gov")

    def get_company_facts(self, cik: str) -> dict:
        """全量 XBRL facts"""
        cik10 = self._pad_cik(cik)
        url = f"{self.BASE_DATA}/api/xbrl/companyfacts/CIK{cik10}.json"
        return self._get_json(url, host_override="data.sec.gov")

    def get_concept(self, cik: str, tag: str, taxonomy: str = "us-gaap") -> dict:
        """单指标时间序列 companyconcept/CIK{cik10}/{taxonomy}/{tag}.json"""
        cik10 = self._pad_cik(cik)
        url = (
            f"{self.BASE_DATA}/api/xbrl/companyconcept/"
            f"CIK{cik10}/{taxonomy}/{tag}.json"
        )
        return self._get_json(url, host_override="data.sec.gov")

    # --------------------------- 便捷封装 ---------------------------

    def get_revenue_series(self, ticker: str) -> pd.DataFrame:
        """获取营收时间序列：依次尝试 Revenues / RevenueFromContractWithCustomerExcludingAssessedTax

        Returns:
            DataFrame columns: end, val, fy, fp, form, accn, unit
        """
        cik = self.get_cik(ticker)
        if not cik:
            logger.warning(f"未找到 ticker 对应的 CIK: {ticker}")
            return pd.DataFrame()

        candidate_tags = [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
        ]
        for tag in candidate_tags:
            data = self.get_concept(cik, tag, taxonomy="us-gaap")
            units = (data or {}).get("units") or {}
            if not units:
                continue
            # 优先 USD
            unit_key = "USD" if "USD" in units else next(iter(units.keys()))
            rows = units.get(unit_key) or []
            if not rows:
                continue
            df = pd.DataFrame(rows)
            df["unit"] = unit_key
            df["tag"] = tag
            return df

        return pd.DataFrame()

    # ------------------------- Base 抽象方法 -------------------------

    def get_stock_history(
        self, code: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """SEC EDGAR 不提供行情K线，返回空 DataFrame"""
        logger.debug("SEC EDGAR 不支持行情K线，交由其它适配器")
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        """SEC EDGAR 不提供指数成分股"""
        return []

    def get_stock_info(self, code: str) -> Dict:
        """基本公司信息，来自 submissions.json 头部字段"""
        cik = self.get_cik(code) or code
        sub = self.get_submissions(cik)
        if not sub:
            return {}
        keys = [
            "cik", "name", "tickers", "exchanges", "sic", "sicDescription",
            "category", "fiscalYearEnd", "stateOfIncorporation",
        ]
        return {k: sub.get(k) for k in keys if k in sub}

    def get_financial_data(self, code: str) -> Dict:
        """返回 company facts 全量 XBRL"""
        cik = self.get_cik(code) or code
        return self.get_company_facts(cik)

    def health_check(self) -> bool:
        """拉一下 ticker_map 判活"""
        try:
            mp = self.get_ticker_cik_map(force_refresh=True)
            return len(mp) > 0
        except Exception as e:
            logger.warning(f"SEC EDGAR 健康检查失败: {type(e).__name__}: {e}")
            return False
