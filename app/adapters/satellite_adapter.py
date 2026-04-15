# -*- coding: utf-8 -*-
"""
NASA Earth Data / 对地观测卫星数据适配器 [NEW-FILE:#20260415-24]
Input: keyword(关键词 如 'NDVI'/'flood') / bbox(经纬度包围盒) / start|end(ISO日期) / collection_id(C...NASA)
Output: list[dict]数据集清单 / dict集合元数据 / pd.DataFrame 搜索结果扁平长表
Pos: app/adapters层 — earth_observation域骨架；CMR Search无Key免费；预留NASA EarthData登录后下载
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

权威源（≥4交叉验证, 检索时间 2026-04-15 12:16 +08:00）：
  1) NASA EarthData / CMR Common Metadata Repository
     - https://cmr.earthdata.nasa.gov/search/  REST 公开 search (json/atom/umm_json)
     - 端点 /search/collections.json  /search/granules.json
     - 官方文档 https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html
  2) NASA EarthData Login (Earthdata Login/URS)
     - https://urs.earthdata.nasa.gov/  (免费注册；下载粒度数据需Token/cookie，搜索接口不需要)
  3) Copernicus Sentinel Hub (ESA) 免费层 https://www.sentinel-hub.com/explore/eobrowser/
     - OpenEO 标准 https://openeo.org/ 可选补充
  4) USGS Earth Explorer https://earthexplorer.usgs.gov/ Landsat系列
     - Machine-to-Machine API https://m2m.cr.usgs.gov/api/docs/json/
  5) CMR 开源参考 https://github.com/nasa/cmr  (Apache-2.0)

合规：CMR search API 官方明确 "public, no authentication required"；
         UA 规范 "StockAnalSys/1.0 (research)"；≤2 QPS；超时重试。
"""
import time
import random
import logging
from typing import Dict, List, Optional, Tuple

import requests
import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class SatelliteAdapter(BaseAdapter):
    """NASA CMR 对地观测数据适配器骨架。

    使用方式：
        sat = SatelliteAdapter()
        cols = sat.search_datasets("NDVI", bbox=(100, 20, 130, 45))
        meta = sat.get_collection_metadata(cols[0]["id"])
    """

    CMR_BASE = "https://cmr.earthdata.nasa.gov/search"
    DEFAULT_TIMEOUT = 15
    MAX_RETRIES = 3
    _MIN_INTERVAL = 0.5  # ≤2 QPS

    _UA = "StockAnalSys/1.0 (research; cmr-client)"

    def __init__(self, timeout: int = DEFAULT_TIMEOUT,
                 edl_token: Optional[str] = None):
        self.timeout = timeout
        # Earthdata Login Token；仅下载粒度数据时使用，search 不需要
        self.edl_token = edl_token
        self._session = requests.Session()
        headers = {
            "User-Agent": self._UA,
            "Accept": "application/json",
        }
        if self.edl_token:
            headers["Authorization"] = f"Bearer {self.edl_token}"
        self._session.headers.update(headers)
        self._last_request_ts = 0.0

    @property
    def name(self) -> str:
        return "satellite"

    # ==================== CMR Collections 搜索 ====================

    def search_datasets(self, keyword: str,
                        bbox: Optional[Tuple[float, float, float, float]] = None,
                        start: Optional[str] = None,
                        end: Optional[str] = None,
                        page_size: int = 20) -> List[Dict]:
        """搜索 CMR collections (数据集清单)

        Args:
            keyword: 关键词，映射 CMR 的 keyword 参数
            bbox:    (W, S, E, N) 经纬度包围盒 → bounding_box=W,S,E,N
            start:   ISO8601 起始，如 2025-01-01T00:00:00Z
            end:     ISO8601 终止
            page_size: 单页数量，默认20，上限2000

        Returns:
            list[dict]: 每项含 id / short_name / title / data_center / time_start / time_end / links
        """
        params: Dict[str, str] = {
            "keyword":   keyword,
            "page_size": str(min(max(page_size, 1), 2000)),
        }
        if bbox and len(bbox) == 4:
            params["bounding_box"] = ",".join(str(x) for x in bbox)
        if start and end:
            params["temporal"] = f"{start},{end}"
        elif start:
            params["temporal"] = f"{start},"
        raw = self._get_json(f"{self.CMR_BASE}/collections.json", params)
        if not raw:
            return []
        try:
            entries = raw.get("feed", {}).get("entry", [])
            out: List[Dict] = []
            for e in entries:
                out.append({
                    "id":          e.get("id"),
                    "short_name":  e.get("short_name"),
                    "version_id":  e.get("version_id"),
                    "title":       e.get("title") or e.get("dataset_id"),
                    "summary":     e.get("summary", "")[:300],
                    "data_center": e.get("data_center"),
                    "time_start":  e.get("time_start"),
                    "time_end":    e.get("time_end"),
                    "links":       [l.get("href") for l in e.get("links", []) if l.get("href")][:5],
                })
            return out
        except Exception as ex:
            logger.warning(f"CMR collections 解析异常: {type(ex).__name__}: {ex}")
            return []

    # ---------- J1 alias ----------
    def search_collections(self, keyword: str,
                           bbox: Optional[Tuple[float, float, float, float]] = None,
                           start: Optional[str] = None,
                           end: Optional[str] = None,
                           page_size: int = 20) -> List[Dict]:
        """J1 [NEW-FILE:#20260415-43] 对地观测集合搜索 alias — 转发 search_datasets。

        agent 端统一以 search_collections 命名 (与 NASA CMR /collections.json 端点语义一致)。
        """
        return self.search_datasets(
            keyword=keyword, bbox=bbox, start=start, end=end, page_size=page_size
        )

    # ==================== 单集合元数据 ====================

    def get_collection_metadata(self, collection_id: str) -> Dict:
        """按 collection id (C...) 获取完整元数据 (UMM-JSON)

        Args:
            collection_id: e.g. C1711961296-LPCLOUD

        Returns:
            dict: 空dict表示失败
        """
        if not collection_id:
            return {}
        # umm_json 端点返回带完整 UMM schema
        params = {"concept_id": collection_id}
        raw = self._get_json(f"{self.CMR_BASE}/collections.umm_json", params)
        if not raw:
            return {}
        try:
            items = raw.get("items", [])
            if not items:
                return {}
            item = items[0]
            umm = item.get("umm", {})
            return {
                "id":            collection_id,
                "short_name":    umm.get("ShortName"),
                "version":       umm.get("Version"),
                "entry_title":   umm.get("EntryTitle"),
                "abstract":      (umm.get("Abstract") or "")[:500],
                "data_center":   [d.get("ShortName") for d in umm.get("DataCenters", [])],
                "platforms":     [p.get("ShortName") for p in umm.get("Platforms", [])],
                "processing_level": (umm.get("ProcessingLevel") or {}).get("Id"),
                "temporal":      umm.get("TemporalExtents", []),
                "spatial":       umm.get("SpatialExtent", {}),
                "related_urls":  [u.get("URL") for u in umm.get("RelatedUrls", [])][:10],
            }
        except Exception as e:
            logger.warning(f"CMR collection 元数据解析异常: {type(e).__name__}: {e}")
            return {}

    # ==================== 粒度 granules (预留) ====================

    def search_granules(self, collection_id: str,
                        bbox: Optional[Tuple[float, float, float, float]] = None,
                        start: Optional[str] = None,
                        end: Optional[str] = None,
                        page_size: int = 20) -> pd.DataFrame:
        """按集合查询具体粒度(granule)列表 — 预留下载入口

        Returns:
            DataFrame[granule_id, title, time_start, time_end, download_url]
        """
        if not collection_id:
            return pd.DataFrame()
        params: Dict[str, str] = {
            "collection_concept_id": collection_id,
            "page_size": str(min(max(page_size, 1), 2000)),
        }
        if bbox and len(bbox) == 4:
            params["bounding_box"] = ",".join(str(x) for x in bbox)
        if start and end:
            params["temporal"] = f"{start},{end}"
        raw = self._get_json(f"{self.CMR_BASE}/granules.json", params)
        if not raw:
            return pd.DataFrame()
        try:
            entries = raw.get("feed", {}).get("entry", [])
            rows: List[Dict] = []
            for e in entries:
                # 下载链接：寻找 rel=data 的
                dl = ""
                for l in e.get("links", []):
                    if l.get("rel", "").endswith("/data#"):
                        dl = l.get("href")
                        break
                rows.append({
                    "granule_id": e.get("id"),
                    "title":      e.get("title"),
                    "time_start": e.get("time_start"),
                    "time_end":   e.get("time_end"),
                    "download_url": dl,
                })
            return pd.DataFrame(rows)
        except Exception as ex:
            logger.warning(f"CMR granules 解析异常: {type(ex).__name__}: {ex}")
            return pd.DataFrame()

    # ==================== BaseAdapter 抽象方法（卫星源不提供个股） ====================

    def get_stock_history(self, code, start_date, end_date, adjust="qfq") -> pd.DataFrame:
        logger.info("Satellite 为对地观测源，不提供个股K线")
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        return []

    def get_stock_info(self, code: str) -> Dict:
        return {}

    def get_financial_data(self, code: str) -> Dict:
        return {}

    def health_check(self) -> bool:
        """健康检查：CMR collections ping 一条即通过"""
        try:
            raw = self._get_json(f"{self.CMR_BASE}/collections.json",
                                 {"keyword": "landsat", "page_size": "1"})
            return bool(raw and raw.get("feed", {}).get("entry"))
        except Exception as e:
            logger.warning(f"Satellite 健康检查失败: {type(e).__name__}: {e}")
            return False

    # ==================== 内部 ====================

    def _throttle(self):
        elapsed = time.time() - self._last_request_ts
        if elapsed < self._MIN_INTERVAL:
            time.sleep(self._MIN_INTERVAL - elapsed)

    def _get_json(self, url: str, params: Dict) -> Optional[Dict]:
        """带重试+限流的GET；失败返回None"""
        self._throttle()
        last_err = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout)
                self._last_request_ts = time.time()
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception as je:
                        last_err = f"JSON解析失败: {je}"
                else:
                    last_err = f"HTTP {resp.status_code}"
            except requests.RequestException as e:
                last_err = f"{type(e).__name__}: {e}"
            if attempt < self.MAX_RETRIES:
                time.sleep(0.5 * attempt + random.random() * 0.3)
        logger.warning(f"Satellite CMR GET 最终失败 url={url} err={last_err}")
        return None
