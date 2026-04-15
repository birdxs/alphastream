# -*- coding: utf-8 -*-
"""
World Bank Open Data 适配器 - 老王说：全球200+国家宏观指标+无Key免费，分页format=json必带！
Input: ISO 国家码(CN/US/WLD等) + 指标代码(NY.GDP.MKTP.CD / FP.CPI.TOTL / SP.POP.TOTL等) + 年份范围
Output: pd.DataFrame 格式的年度指标时间序列 / 指标目录 / 多国横向对比
Pos: app/adapters层，宏观数据源，配合IMF适配器为宏观分析Agent提供全球对标数据

World Bank 官方规范 (已交叉验证3源)：
- https://datahelpdesk.worldbank.org/knowledgebase/articles/889392 (Indicator API基础用法)
- https://datahelpdesk.worldbank.org/knowledgebase/articles/898581 (API advanced queries)
- https://data.worldbank.org/ (数据门户)
关键约束：
1. URL格式 api.worldbank.org/v2/country/{cc}/indicator/{ind}?format=json
2. 响应为 [meta, data] 二元数组；data 每行含 country/indicator/date/value/unit
3. 分页 per_page≤32500；date可用 2020:2024 形式
4. 多国对比用 cc=CN;US;JP 分号分隔

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
from typing import Dict, List, Optional

import requests
import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class WorldBankAdapter(BaseAdapter):
    """World Bank Open Data 适配器

    端点：
    - https://api.worldbank.org/v2/country/{cc}/indicator/{ind}?format=json
    - https://api.worldbank.org/v2/indicator?format=json  (指标目录)
    - https://api.worldbank.org/v2/country?format=json    (国家目录)
    """

    BASE_URL = "https://api.worldbank.org/v2"
    DEFAULT_PER_PAGE = 1000

    def __init__(self, timeout: int = 20, per_page: int = DEFAULT_PER_PAGE):
        self.timeout = timeout
        self.per_page = per_page
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "StockAnalSys-WorldBank/1.0",
        })

    @property
    def name(self) -> str:
        return "worldbank"

    # --------------------------- 内部工具 ---------------------------

    def _get_json(self, url: str, params: Optional[dict] = None):
        """统一GET，返回解析后的JSON；失败返回 None"""
        try:
            p = dict(params or {})
            p.setdefault("format", "json")
            resp = self.session.get(url, params=p, timeout=self.timeout)
            if resp.status_code != 200:
                logger.warning(f"WorldBank HTTP {resp.status_code}: {url}")
                return None
            return resp.json()
        except Exception as e:
            logger.warning(f"WorldBank 请求失败 {url}: {type(e).__name__}: {e}")
            return None

    @staticmethod
    def _parse_rows(payload) -> List[dict]:
        """WB 响应统一为 [meta, rows]；若不符则返回 []"""
        if not isinstance(payload, list) or len(payload) < 2:
            return []
        rows = payload[1]
        if not isinstance(rows, list):
            return []
        return rows

    # --------------------------- 核心端点 ---------------------------

    def get_indicator(
        self,
        country: str,
        indicator: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> pd.DataFrame:
        """获取单国单指标时间序列

        Args:
            country: ISO2/ISO3 国家码或 "WLD"(世界)；分号分隔支持多国
            indicator: 指标代码，如 NY.GDP.MKTP.CD (GDP 现价美元)
            start/end: 起止年份（含）

        Returns:
            DataFrame columns: country, country_id, indicator, indicator_id,
                               date, value, unit
        """
        if not country or not indicator:
            return pd.DataFrame()

        url = f"{self.BASE_URL}/country/{country}/indicator/{indicator}"
        params = {"per_page": self.per_page}
        if start is not None and end is not None:
            params["date"] = f"{start}:{end}"
        elif start is not None:
            params["date"] = f"{start}:{start}"

        payload = self._get_json(url, params)
        rows = self._parse_rows(payload)
        if not rows:
            return pd.DataFrame()

        records = []
        for r in rows:
            try:
                records.append({
                    "country": (r.get("country") or {}).get("value"),
                    "country_id": (r.get("country") or {}).get("id"),
                    "indicator": (r.get("indicator") or {}).get("value"),
                    "indicator_id": (r.get("indicator") or {}).get("id"),
                    "date": r.get("date"),
                    "value": r.get("value"),
                    "unit": r.get("unit") or "",
                })
            except (AttributeError, TypeError):
                continue
        df = pd.DataFrame(records)
        if not df.empty and "date" in df.columns:
            df = df.sort_values("date").reset_index(drop=True)
        return df

    def list_indicators(self, keyword: Optional[str] = None) -> pd.DataFrame:
        """搜索/列出指标目录

        Args:
            keyword: 关键字（大小写不敏感，匹配 id/name）；为空则返回首页

        Returns:
            DataFrame columns: id, name, source, source_note, topics
        """
        url = f"{self.BASE_URL}/indicator"
        payload = self._get_json(url, {"per_page": self.per_page})
        rows = self._parse_rows(payload)
        if not rows:
            return pd.DataFrame()

        records = []
        for r in rows:
            try:
                records.append({
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "source": (r.get("source") or {}).get("value"),
                    "source_note": r.get("sourceNote") or "",
                    "topics": ";".join(
                        str(t.get("value", "")) for t in (r.get("topics") or [])
                        if isinstance(t, dict)
                    ),
                })
            except (AttributeError, TypeError):
                continue
        df = pd.DataFrame(records)
        if keyword and not df.empty:
            kw = keyword.lower()
            mask = (
                df["id"].fillna("").str.lower().str.contains(kw, regex=False)
                | df["name"].fillna("").str.lower().str.contains(kw, regex=False)
            )
            df = df[mask].reset_index(drop=True)
        return df

    def compare_countries(
        self,
        countries: List[str],
        indicator: str,
        year: int,
    ) -> pd.DataFrame:
        """多国单指标单年横向对比

        Args:
            countries: 国家码列表，如 ["CN", "US", "JP", "DE"]
            indicator: 指标代码
            year: 目标年份

        Returns:
            DataFrame 按 value 降序 columns: country, country_id, value, date
        """
        if not countries or not indicator:
            return pd.DataFrame()
        cc = ";".join(c.strip() for c in countries if c and c.strip())
        if not cc:
            return pd.DataFrame()
        df = self.get_indicator(cc, indicator, start=year, end=year)
        if df.empty:
            return df
        keep = ["country", "country_id", "value", "date",
                "indicator", "indicator_id"]
        df = df[[c for c in keep if c in df.columns]]
        # 非空值优先、数值降序
        df = df.sort_values(
            by="value", ascending=False, na_position="last"
        ).reset_index(drop=True)
        return df

    # 常用全球宏观指标（WorldBank 代码）
    COMMON_INDICATORS: Dict[str, str] = {
        "GDP": "NY.GDP.MKTP.CD",
        "GDPGrowth": "NY.GDP.MKTP.KD.ZG",
        "CPI": "FP.CPI.TOTL.ZG",
        "Unemployment": "SL.UEM.TOTL.ZS",
        "Population": "SP.POP.TOTL",
        "FDI": "BX.KLT.DINV.CD.WD",
    }

    def get_macro_indicators(
        self,
        indicators: Optional[List[str]] = None,
        country: str = "WLD",
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> Dict[str, pd.DataFrame]:
        """J1 [NEW-FILE:#20260415-43] 全球宏观指标 alias — agent 统一入口。

        Args:
            indicators: 支持 COMMON_INDICATORS 键名或 WorldBank 原生代码列表；
                        None→ 返回全部 COMMON_INDICATORS
            country: ISO2/ISO3 国家码，默认 "WLD"(世界)
            start/end: 起止年份

        Returns:
            Dict[key, DataFrame]；失败的 key 跳过；全失败返回空 dict。
        """
        keys = indicators or list(self.COMMON_INDICATORS.keys())
        out: Dict[str, pd.DataFrame] = {}
        for k in keys:
            code = self.COMMON_INDICATORS.get(k, k)
            try:
                df = self.get_indicator(country, code, start=start, end=end)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    out[k] = df
            except Exception as e:
                logger.warning(f"[WorldBankAdapter] get_macro_indicators({k}) 失败: {type(e).__name__}: {e}")
        return out

    # ------------------------- Base 抽象方法 -------------------------

    def get_stock_history(
        self, code: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """WorldBank 不提供行情K线"""
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        """WorldBank 不提供指数成分"""
        return []

    def get_stock_info(self, code: str) -> Dict:
        """WorldBank 不提供个股信息"""
        return {}

    def get_financial_data(self, code: str) -> Dict:
        """WorldBank 不提供公司财务，返回空"""
        return {}

    def health_check(self) -> bool:
        """健康检查：拉取少量指标元数据"""
        try:
            payload = self._get_json(
                f"{self.BASE_URL}/country/WLD/indicator/NY.GDP.MKTP.CD",
                {"per_page": 1, "date": "2020:2020"},
            )
            return bool(self._parse_rows(payload))
        except Exception as e:
            logger.warning(f"WorldBank 健康检查失败: {type(e).__name__}: {e}")
            return False
