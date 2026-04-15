# -*- coding: utf-8 -*-
"""
IMF SDMX-JSON REST 适配器 - 老王说：IFS/WEO/DOT全免费Key，数据集ID+freq.country.indicator 三段式！
Input: dataset_id (IFS/WEO/DOT等) + SDMX key (如 A.CN.PCPI_IX) + 起止期
Output: pd.DataFrame 格式的时间序列 (period/value/attrs)
Pos: app/adapters层，国际金融数据源，配合WorldBank适配器为宏观分析Agent提供IMF口径数据

IMF SDMX 官方规范 (已交叉验证3源)：
- https://sdmxcentral.imf.org/ (SDMX Central 数据门户/文档)
- https://datahelp.imf.org/knowledgebase/articles/630877-api (官方API使用说明)
- https://www.imf.org/external/datamapper/api/help (WEO DataMapper 补充)
关键约束：
1. SDMX 2.1 JSON：CompactData/{dataset}/{freq}.{ref_area}.{indicator}
2. 典型数据集：IFS(国际金融统计) / WEO(世界经济展望) / DOT(贸易方向)
3. freq: A年 / Q季 / M月；ref_area ISO2；indicator 如 PCPI_IX(CPI指数)
4. 时间范围: startPeriod=2010&endPeriod=2024

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
from typing import Dict, List, Optional

import requests
import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class IMFAdapter(BaseAdapter):
    """IMF SDMX-JSON 适配器

    端点：
    - https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/{dataset}/{key}
      ?startPeriod=YYYY&endPeriod=YYYY
    - https://dataservices.imf.org/REST/SDMX_JSON.svc/DataStructure/{dataset}
    """

    BASE_URL = "https://dataservices.imf.org/REST/SDMX_JSON.svc"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "StockAnalSys-IMF/1.0",
        })

    @property
    def name(self) -> str:
        return "imf"

    # --------------------------- 内部工具 ---------------------------

    def _get_json(self, url: str, params: Optional[dict] = None):
        """统一GET，返回 JSON dict；失败返回 None"""
        try:
            resp = self.session.get(
                url, params=params or {}, timeout=self.timeout
            )
            if resp.status_code != 200:
                logger.warning(f"IMF HTTP {resp.status_code}: {url}")
                return None
            return resp.json()
        except Exception as e:
            logger.warning(f"IMF 请求失败 {url}: {type(e).__name__}: {e}")
            return None

    @staticmethod
    def _extract_series(payload) -> List[dict]:
        """从 SDMX-JSON CompactData 提取序列列表

        SDMX 结构：
        CompactData.DataSet.Series (可能是 dict 或 list)
           每个 Series 含 @freq/@REF_AREA/... 以及 Obs (可能 dict 或 list)
        """
        if not isinstance(payload, dict):
            return []
        ds = (
            (payload.get("CompactData") or {}).get("DataSet") or {}
        )
        series = ds.get("Series")
        if series is None:
            return []
        if isinstance(series, dict):
            series = [series]
        return series

    @staticmethod
    def _flatten_series(series_list: List[dict]) -> pd.DataFrame:
        """将 Series[].Obs[] 打平为 DataFrame

        字段：
        - period: @TIME_PERIOD
        - value:  @OBS_VALUE (float, 缺失为 None)
        - freq / ref_area / indicator: 从 Series 维度继承
        """
        records = []
        for s in series_list:
            if not isinstance(s, dict):
                continue
            freq = s.get("@FREQ")
            ref_area = s.get("@REF_AREA")
            indicator = s.get("@INDICATOR")
            obs = s.get("Obs") or []
            if isinstance(obs, dict):
                obs = [obs]
            for o in obs:
                if not isinstance(o, dict):
                    continue
                v = o.get("@OBS_VALUE")
                try:
                    v_float = float(v) if v not in (None, "") else None
                except (TypeError, ValueError):
                    v_float = None
                records.append({
                    "freq": freq,
                    "ref_area": ref_area,
                    "indicator": indicator,
                    "period": o.get("@TIME_PERIOD"),
                    "value": v_float,
                })
        df = pd.DataFrame(records)
        if not df.empty and "period" in df.columns:
            df = df.sort_values(["ref_area", "indicator", "period"]).reset_index(
                drop=True
            )
        return df

    # --------------------------- 核心端点 ---------------------------

    def get_dataset(
        self,
        dataset_id: str,
        query: str,
        start_period: Optional[int] = None,
        end_period: Optional[int] = None,
    ) -> pd.DataFrame:
        """通用 SDMX CompactData 查询

        Args:
            dataset_id: 如 "IFS" / "WEO" / "DOT"
            query: SDMX key, 如 "A.CN.PCPI_IX" (年/中国/CPI指数)
                   多维可用 "+" 扩选：如 "A.CN+US.PCPI_IX"
            start_period / end_period: 年份 int（或 "2020-Q1" 这样的季度串）

        Returns:
            DataFrame columns: freq, ref_area, indicator, period, value
        """
        if not dataset_id or not query:
            return pd.DataFrame()
        url = f"{self.BASE_URL}/CompactData/{dataset_id}/{query}"
        params = {}
        if start_period is not None:
            params["startPeriod"] = str(start_period)
        if end_period is not None:
            params["endPeriod"] = str(end_period)

        payload = self._get_json(url, params)
        series_list = self._extract_series(payload)
        if not series_list:
            return pd.DataFrame()
        return self._flatten_series(series_list)

    def get_ifs(
        self,
        indicator: str,
        country: str,
        freq: str = "A",
        start_period: Optional[int] = None,
        end_period: Optional[int] = None,
    ) -> pd.DataFrame:
        """国际金融统计(IFS)便捷查询

        Args:
            indicator: 指标代码，如 "PCPI_IX"(CPI) / "FPOLM_PA"(政策利率)
            country: ISO2 国家码，如 "CN" / "US"
            freq: "A"年 / "Q"季 / "M"月
            start_period/end_period: 起止期

        Returns:
            DataFrame columns: freq, ref_area, indicator, period, value
        """
        if not indicator or not country:
            return pd.DataFrame()
        key = f"{freq}.{country}.{indicator}"
        return self.get_dataset("IFS", key, start_period, end_period)

    def get_data_structure(self, dataset_id: str) -> dict:
        """获取数据集 DataStructure（维度/编码表）

        主要用于运行时探查维度顺序；返回原始 JSON dict。
        """
        if not dataset_id:
            return {}
        url = f"{self.BASE_URL}/DataStructure/{dataset_id}"
        return self._get_json(url) or {}

    # ------------------------- Base 抽象方法 -------------------------

    def get_stock_history(
        self, code: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """IMF 不提供行情K线"""
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        """IMF 不提供指数成分"""
        return []

    def get_stock_info(self, code: str) -> Dict:
        """IMF 不提供个股信息"""
        return {}

    def get_financial_data(self, code: str) -> Dict:
        """IMF 不提供公司财务，返回空"""
        return {}

    def health_check(self) -> bool:
        """健康检查：拉一条小 IFS 序列"""
        try:
            df = self.get_ifs("PCPI_IX", "US", "A",
                              start_period=2020, end_period=2021)
            return not df.empty
        except Exception as e:
            logger.warning(f"IMF 健康检查失败: {type(e).__name__}: {e}")
            return False
