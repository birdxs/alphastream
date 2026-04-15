# -*- coding: utf-8 -*-
"""
航运 & 港口另类数据适配器 [NEW-FILE:#20260415-23]
Input: port(港口key shanghai/ningbo/...) / days(回溯天数) / bbox(经纬度四元组 minLon,minLat,maxLon,maxLat)
Output: pd.DataFrame 统一长表 — BDI时序 / 港口吞吐量 / AIS船舶实时位置
Pos: app/adapters层 — 另类数据(commodity_shipping)域主源；无Key纯requests；未通降级为空DF
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

权威源（≥4交叉验证, 检索时间 2026-04-15 12:16 +08:00）：
  1) Baltic Exchange / 波罗的海交易所 https://www.balticexchange.com/
     - BDI(Baltic Dry Index) 日度公开值，通过 Clarksons/TradingEconomics 公开RSS/页面可爬
     - Freightos Baltic Index (FBX) https://fbx.freightos.com/ 容器海运40ft日度
  2) AISHub 开放AIS feed https://www.aishub.net/ — 免费注册(共享AIS数据换取API)
     - 端点 https://data.aishub.net/ws.php?username=<u>&format=1&output=json&compress=0
  3) 交通运输部统计公报 https://www.mot.gov.cn/tongjishuju/
     - 港口货物吞吐量月度数据；上港集团 http://www.portshanghai.com.cn/ 投资者关系
  4) VesselFinder 公开页 https://www.vesselfinder.com/ 船舶追踪(限速限量)
     - MarineTraffic 公开页 https://www.marinetraffic.com/
  5) 开源参考实现 AIS-catcher https://github.com/jvde-github/AIS-catcher (接收器)
     — 数据模型字段对齐ITU-R M.1371 AIS报文标准(MMSI/SOG/COG/HDG/NAV_STATUS)

合规：仅研究用途；UA伪装；限流≤1QPS；无Key(AISHub需自行注册username);
         未提供username时 get_ais_vessels 直接降级空DF，绝不抛异常。
"""
import os
import time
import random
import logging
from typing import Dict, List, Optional, Tuple

import requests
import pandas as pd

from .base_adapter import BaseAdapter
from ._retry_utils import random_ua, retry_with_backoff, rotate_ua
from ._proxy_utils import get_proxies

logger = logging.getLogger(__name__)


# BDI / FBX 公开日值可靠来源（RSS/JSON/HTML均可），此处给出候选端点清单
_BDI_ENDPOINTS = [
    # TradingEconomics 公开图表 (无Key只读)
    "https://tradingeconomics.com/commodity/baltic",
    # Investing.com 公开页(带反爬，仅备选)
    "https://www.investing.com/indices/baltic-dry",
]

# 交通运输部 & 主要港集团公报页(备选)
_PORT_ENDPOINTS = {
    "shanghai": "http://www.portshanghai.com.cn/",  # 上港集团
    "ningbo":   "http://www.nbport.com.cn/",         # 宁波港
    "qingdao":  "http://www.qdport.com/",            # 青岛港
    "shenzhen": "https://www.szport.net/",           # 深圳港
}

# AISHub 公开 Web Services (需要免费 username 注册)
_AISHUB_API = "https://data.aishub.net/ws.php"


class ShippingAdapter(BaseAdapter):
    """航运 & 港口另类数据源适配器"""

    DEFAULT_TIMEOUT = 15
    MAX_RETRIES = 4  # K1: 反爬站需要更多尝试
    _MIN_INTERVAL = 1.0  # ≤1 QPS

    # K1 [NEW-FILE:#20260415-44] UA由_retry_utils.UA_POOL轮询提供

    # K1 反爬Referer伪造：investing.com 等
    _REFERER_MAP = {
        "investing.com": "https://www.investing.com/",
        "tradingeconomics.com": "https://tradingeconomics.com/",
    }

    def __init__(self, timeout: int = DEFAULT_TIMEOUT,
                 aishub_username: Optional[str] = None):
        self.timeout = timeout
        # AISHub username 可通过环境变量注入；未设置则 AIS 能力降级空DF
        self.aishub_username = aishub_username or os.environ.get("AISHUB_USERNAME")
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })
        # K1: 代理强制应用 (H4 proxy utils)
        proxies = get_proxies()
        if proxies:
            self._session.proxies.update(proxies)
        self._last_request_ts = 0.0

    @property
    def name(self) -> str:
        return "shipping"

    # ==================== BDI 波罗的海干散货指数 ====================

    def get_bdi_index(self, days: int = 30) -> pd.DataFrame:
        """获取波罗的海干散货指数 (BDI) 近 N 日序列

        优先走 TradingEconomics 公开HTML/JSON端点；均失败返回空DF。

        Returns:
            DataFrame[date, indicator, value, source]  空DF表示全降级失败
        """
        for url in _BDI_ENDPOINTS:
            try:
                text = self._get_text(url)
                if not text:
                    continue
                df = self._parse_bdi_html(text, days=days)
                if not df.empty:
                    df["indicator"] = "BDI"
                    df["source"] = url
                    return df
            except Exception as e:
                logger.warning(f"BDI 端点 {url} 解析失败: {type(e).__name__}: {e}")
                continue
        logger.info("BDI 全部端点降级失败，返回空DF")
        return pd.DataFrame()

    # ==================== 港口吞吐量 ====================

    def get_port_throughput(self, port: str = "shanghai",
                            period: str = "monthly") -> pd.DataFrame:
        """获取中国主要港口月度/年度吞吐量 (TEU / 万吨)

        Args:
            port:   港口key, shanghai/ningbo/qingdao/shenzhen
            period: monthly / yearly

        Returns:
            DataFrame[date, port, indicator, value, unit, source]
        """
        url = _PORT_ENDPOINTS.get(port.lower())
        if not url:
            logger.info(f"未知港口 {port}，返回空DF")
            return pd.DataFrame()
        try:
            text = self._get_text(url)
            if not text:
                return pd.DataFrame()
            df = self._parse_port_throughput(text, port=port, period=period)
            if not df.empty:
                df["source"] = url
            return df
        except Exception as e:
            logger.warning(f"港口 {port} 吞吐量解析失败: {type(e).__name__}: {e}")
            return pd.DataFrame()

    # ==================== AIS 船舶实时位置 ====================

    def get_ais_vessels(self, bbox: Optional[Tuple[float, float, float, float]] = None
                        ) -> pd.DataFrame:
        """获取 AIS 船舶位置快照

        Args:
            bbox: (minLon, minLat, maxLon, maxLat) 经纬度包围盒；None 则全量(由服务端限制)

        Returns:
            DataFrame[mmsi, name, lat, lon, sog, cog, heading, nav_status, ship_type, ts]
            未配置 AISHUB_USERNAME 时直接降级空DF。
        """
        if not self.aishub_username:
            logger.info("AISHUB_USERNAME 未配置，AIS能力降级空DF")
            return pd.DataFrame()

        params: Dict[str, str] = {
            "username": self.aishub_username,
            "format":   "1",      # json
            "output":   "json",
            "compress": "0",
        }
        if bbox and len(bbox) == 4:
            params.update({
                "latmin": str(bbox[1]),
                "latmax": str(bbox[3]),
                "lonmin": str(bbox[0]),
                "lonmax": str(bbox[2]),
            })
        raw = self._get_json(_AISHUB_API, params)
        if not raw:
            return pd.DataFrame()
        return self._parse_aishub(raw)

    # ==================== BaseAdapter 抽象方法（另类数据源不提供个股） ====================

    def get_stock_history(self, code, start_date, end_date, adjust="qfq") -> pd.DataFrame:
        logger.info("Shipping 为另类数据源，不提供个股K线")
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        return []

    def get_stock_info(self, code: str) -> Dict:
        return {}

    def get_financial_data(self, code: str) -> Dict:
        return {}

    def health_check(self) -> bool:
        """健康检查：BDI 任一端点可达即通过"""
        try:
            for url in _BDI_ENDPOINTS:
                if self._get_text(url):
                    return True
            return False
        except Exception as e:
            logger.warning(f"Shipping 健康检查失败: {type(e).__name__}: {e}")
            return False

    # ==================== 内部 ====================

    def _throttle(self):
        elapsed = time.time() - self._last_request_ts
        if elapsed < self._MIN_INTERVAL:
            time.sleep(self._MIN_INTERVAL - elapsed)

    def _pick_referer(self, url: str) -> Optional[str]:
        """根据URL匹配Referer伪造，K1反爬强化"""
        for host, ref in self._REFERER_MAP.items():
            if host in url:
                return ref
        return None

    def _get_text(self, url: str, params: Optional[Dict] = None) -> Optional[str]:
        """K1: UA池轮询+retry_with_backoff指数退避+Referer伪造，失败返回None"""
        self._throttle()
        # 每请求轮换UA
        rotate_ua(self._session)
        headers = {}
        ref = self._pick_referer(url)
        if ref:
            headers["Referer"] = ref
        try:
            resp = retry_with_backoff(
                lambda: self._session.get(url, params=params, headers=headers, timeout=self.timeout),
                max_retries=self.MAX_RETRIES,
                backoff_base=0.5,
                name=f"shipping:{url[:60]}",
            )
            self._last_request_ts = time.time()
            if resp is not None and resp.status_code == 200 and resp.text:
                return resp.text
            logger.warning(f"Shipping GET 最终非200 url={url} status={getattr(resp,'status_code',None)}")
            return None
        except Exception as e:
            logger.warning(f"Shipping GET 最终失败 url={url} err={type(e).__name__}: {e}")
            return None

    def _get_json(self, url: str, params: Dict) -> Optional[List]:
        """AISHub K1重试包装"""
        self._throttle()
        rotate_ua(self._session)
        try:
            resp = retry_with_backoff(
                lambda: self._session.get(url, params=params, timeout=self.timeout),
                max_retries=self.MAX_RETRIES,
                backoff_base=0.5,
                name="aishub",
            )
            self._last_request_ts = time.time()
            if resp is not None and resp.status_code == 200:
                try:
                    return resp.json()
                except Exception as je:
                    logger.warning(f"AISHub JSON解析失败: {je}")
            return None
        except Exception as e:
            logger.warning(f"AISHub GET 最终失败 err={type(e).__name__}: {e}")
            return None

    # ---------- 解析器 ----------

    @staticmethod
    def _parse_bdi_html(text: str, days: int = 30) -> pd.DataFrame:
        """从 TradingEconomics 等HTML中尝试提取 BDI 时序。

        真实页面结构易变；此解析器采用宽松策略：
          - 优先提取 <script> 内的 data:[[ts,val],...] 数组
          - 回落：匹配 "BDI" 附近数值
        失败返回空DF。
        """
        import re
        rows: List[Dict] = []
        # 宽松 data:[[ms_ts, value], ...] 样式
        pattern = re.compile(r"\[(\d{10,13})\s*,\s*([0-9]+\.?[0-9]*)\]")
        for m in pattern.finditer(text):
            ts_raw, val = m.group(1), m.group(2)
            try:
                ts_ms = int(ts_raw)
                if ts_ms < 10 ** 12:
                    ts_ms *= 1000  # 秒→毫秒
                dt = pd.to_datetime(ts_ms, unit="ms").strftime("%Y-%m-%d")
                rows.append({"date": dt, "value": float(val)})
            except Exception:
                continue
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).drop_duplicates("date").sort_values("date")
        if days and len(df) > days:
            df = df.tail(days).reset_index(drop=True)
        return df

    @staticmethod
    def _parse_port_throughput(text: str, port: str, period: str) -> pd.DataFrame:
        """从港集团公报HTML提取吞吐量。

        真实公报页多样化，采用宽松正则匹配 "YYYY年M月 ... 吞吐量 ... 万TEU/万吨"。
        解析失败返回空DF，绝不抛异常。
        """
        import re
        rows: List[Dict] = []
        # 例：2026年3月完成集装箱吞吐量 420.5 万TEU
        pat = re.compile(
            r"(20\d{2})\s*年\s*(\d{1,2})\s*月[^0-9]{0,30}([0-9]+\.?[0-9]*)\s*万?(TEU|吨)",
            re.UNICODE,
        )
        for m in pat.finditer(text):
            y, mo, val, unit = m.group(1), m.group(2), m.group(3), m.group(4)
            rows.append({
                "date":      f"{y}-{int(mo):02d}",
                "port":      port,
                "indicator": "throughput",
                "value":     float(val),
                "unit":      f"万{unit}",
                "period":    period,
            })
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).drop_duplicates(["date", "port", "unit"]).sort_values("date")

    @staticmethod
    def _parse_aishub(raw) -> pd.DataFrame:
        """AISHub WS 返回：[ {"ERROR":false,"USERNAME":..}, [ {MMSI,LAT,LON,...}, ... ] ]"""
        try:
            if not isinstance(raw, list) or len(raw) < 2:
                return pd.DataFrame()
            meta = raw[0] if isinstance(raw[0], dict) else {}
            if meta.get("ERROR") is True:
                logger.warning(f"AISHub 业务错误: {meta.get('ERROR_MESSAGE')}")
                return pd.DataFrame()
            vessels = raw[1] if isinstance(raw[1], list) else []
            rows: List[Dict] = []
            for v in vessels:
                if not isinstance(v, dict):
                    continue
                rows.append({
                    "mmsi":        v.get("MMSI"),
                    "name":        v.get("NAME", ""),
                    "lat":         v.get("LATITUDE") or v.get("LAT"),
                    "lon":         v.get("LONGITUDE") or v.get("LON"),
                    "sog":         v.get("SOG"),
                    "cog":         v.get("COG"),
                    "heading":     v.get("HEADING"),
                    "nav_status":  v.get("NAVSTAT"),
                    "ship_type":   v.get("TYPE"),
                    "ts":          v.get("TIME"),
                })
            return pd.DataFrame(rows)
        except Exception as e:
            logger.warning(f"AISHub 解析异常: {type(e).__name__}: {e}")
            return pd.DataFrame()
