# -*- coding: utf-8 -*-
"""
FRED (Federal Reserve Economic Data) 适配器 [NEW-FILE:#20260415-07]
Input: series_id (如 GDP/CPIAUCSL/UNRATE/FEDFUNDS/DGS10)、query、release_id、start/end
Output: pd.DataFrame (时间序列/搜索结果) 或 dict (release 元数据/常用指标包)
Pos: app/adapters层，宏观数据源(St. Louis Fed 80万+序列)；供宏观Agent与fallback_manager调度

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

联网调研权威源 (2026-04-15 12:00 +08:00)：
  1. https://fred.stlouisfed.org/docs/api/fred/ - 官方API规范(端点/参数/限额)
  2. https://pypi.org/project/fredapi/ - Mortada fredapi Python SDK v0.5.x
  3. https://github.com/mortada/fredapi - SDK源码与接口签名
  4. https://fred.stlouisfed.org/docs/api/api_key.html - API Key申请(免费+仅需邮箱)

关键约束：
1. API Key必填(免费, 仅需邮箱申请; 无Key → log.warning + 返回空结构)
2. Fair Use: 官方无硬性限流, 建议 ≤120 req/min
3. fredapi 软依赖: 未安装 → log.warning + 降级空结构, 不抛异常
"""
import os
import logging
from typing import Dict, List, Optional

import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

# 软依赖：fredapi 未安装时模块仍可 import，方法降级返回空结构
try:
    from fredapi import Fred  # type: ignore
    _FREDAPI_AVAILABLE = True
except ImportError:
    Fred = None  # type: ignore
    _FREDAPI_AVAILABLE = False
    logger.warning("fredapi未安装，FREDAdapter将返回空结构。pip install fredapi 启用")


class FREDAdapter(BaseAdapter):
    """FRED 宏观经济数据适配器 (St. Louis Fed, 80万+ 序列)

    端点（由 fredapi 封装）：
      - series/observations      → get_series(series_id, start, end)
      - series/search            → search(query, limit)
      - release/series           → get_release(release_id)

    常用序列ID：
      - GDP          美国国内生产总值 (季度)
      - CPIAUCSL     CPI 全项 (月度, 季调)
      - UNRATE       失业率 (月度)
      - FEDFUNDS     联邦基金利率 (月度)
      - DGS10        10年期美债收益率 (日度)
      - T10Y2Y       10Y-2Y 期限利差 (日度, 衰退先行指标)
      - DEXUSEU      美元/欧元汇率 (日度)
      - M2SL         M2 货币供给 (月度)
      - PAYEMS       非农就业 (月度)
      - INDPRO       工业生产指数 (月度)
    """

    # 便捷封装用：常用宏观指标映射 (中文名 → series_id)
    COMMON_INDICATORS: Dict[str, str] = {
        "GDP": "GDP",
        "CPI": "CPIAUCSL",
        "Unemployment": "UNRATE",
        "FedFundsRate": "FEDFUNDS",
        "UST10Y": "DGS10",
        "YieldSpread_10Y2Y": "T10Y2Y",
        "USD_EUR": "DEXUSEU",
        "M2": "M2SL",
        "NonfarmPayrolls": "PAYEMS",
        "IndustrialProduction": "INDPRO",
    }

    def __init__(self, api_key: Optional[str] = None):
        """初始化

        Args:
            api_key: FRED API Key；缺省从环境变量 FRED_API_KEY 读取。
                     无Key时不抛异常，仅 log.warning，所有方法返回空结构。
        """
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "")
        self._client = None

        if not _FREDAPI_AVAILABLE:
            # 软依赖缺失，已在 import 处告警
            return

        if not self.api_key:
            logger.warning(
                "FRED_API_KEY 未设置，FREDAdapter 将返回空结构。"
                "前往 https://fred.stlouisfed.org/docs/api/api_key.html 免费申请"
            )
            return

        try:
            self._client = Fred(api_key=self.api_key)
        except Exception as e:
            logger.warning(f"FRED 客户端初始化失败: {type(e).__name__}: {e}")
            self._client = None

    @property
    def name(self) -> str:
        return "fred"

    # ============================ 核心方法 ============================

    def get_series(
        self,
        series_id: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取单个时间序列观测值

        Args:
            series_id: FRED 序列ID，如 "GDP" / "CPIAUCSL" / "DGS10"
            start: 起始日期 "YYYY-MM-DD"，None 表示序列起点
            end:   终止日期 "YYYY-MM-DD"，None 表示最新

        Returns:
            DataFrame: columns=[date, value, series_id]；失败或无数据返回空 DataFrame
        """
        if self._client is None:
            return pd.DataFrame()
        try:
            s = self._client.get_series(
                series_id,
                observation_start=start,
                observation_end=end,
            )
            if s is None or len(s) == 0:
                return pd.DataFrame()
            df = s.rename("value").reset_index().rename(columns={"index": "date"})
            df["series_id"] = series_id
            return df
        except Exception as e:
            logger.warning(
                f"FRED get_series 失败 series_id={series_id}: "
                f"{type(e).__name__}: {e}"
            )
            return pd.DataFrame()

    def search_series(self, query: str, limit: int = 20) -> pd.DataFrame:
        """按关键字搜索 FRED 序列

        Args:
            query: 关键字，如 "inflation" / "GDP China" / "yield curve"
            limit: 返回数量上限 (默认 20)

        Returns:
            DataFrame: 官方字段含 id/title/units/frequency/seasonal_adjustment/
                       last_updated/popularity/notes 等；失败返回空 DataFrame
        """
        if self._client is None:
            return pd.DataFrame()
        try:
            df = self._client.search(query, limit=limit)
            if df is None:
                return pd.DataFrame()
            return df
        except Exception as e:
            logger.warning(
                f"FRED search_series 失败 query={query!r}: "
                f"{type(e).__name__}: {e}"
            )
            return pd.DataFrame()

    def get_release(self, release_id: int) -> dict:
        """获取发布(release)元数据

        Args:
            release_id: 发布ID，如 53 (Gross Domestic Product), 10 (CPI)

        Returns:
            dict: 含 id/name/press_release/link/notes 等；失败返回 {}
        """
        if self._client is None:
            return {}
        try:
            # fredapi 暴露 get_release 返回 DataFrame(单行)或 dict
            info = self._client.get_release(release_id)
            if isinstance(info, pd.DataFrame):
                if info.empty:
                    return {}
                return info.iloc[0].to_dict()
            if isinstance(info, dict):
                return info
            return {}
        except Exception as e:
            logger.warning(
                f"FRED get_release 失败 release_id={release_id}: "
                f"{type(e).__name__}: {e}"
            )
            return {}

    def get_common_indicators(self) -> Dict[str, pd.DataFrame]:
        """便捷封装：一次性拉取常用宏观指标 (GDP/CPI/UNRATE/FEDFUNDS/DGS10 等)

        Returns:
            Dict[指标中文Key, DataFrame(date,value,series_id)]；
            某个指标失败只影响该 key，其余正常。
            客户端不可用时返回空 dict。
        """
        if self._client is None:
            return {}
        out: Dict[str, pd.DataFrame] = {}
        for key, sid in self.COMMON_INDICATORS.items():
            out[key] = self.get_series(sid)
        return out

    def get_macro_indicators(
        self,
        indicators: Optional[List[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> Dict[str, pd.DataFrame]:
        """J1 [NEW-FILE:#20260415-43] 宏观指标 alias — agent 统一入口。

        Args:
            indicators: FRED series_id 列表或 COMMON_INDICATORS 的中文key；
                        None→ 返回全部 COMMON_INDICATORS
            start/end:  日期范围

        Returns:
            Dict[key, DataFrame(date,value,series_id)]；
            某个指标失败不影响其他；全失败返回空 dict。
        """
        if self._client is None:
            return {}
        if not indicators:
            # 不带参 → 复用 get_common_indicators 语义
            return self.get_common_indicators()
        out: Dict[str, pd.DataFrame] = {}
        for ind in indicators:
            # 支持中文key → series_id 映射
            sid = self.COMMON_INDICATORS.get(ind, ind)
            df = self.get_series(sid, start=start, end=end)
            if isinstance(df, pd.DataFrame) and not df.empty:
                out[ind] = df
        return out

    # ====================== BaseAdapter 抽象方法占位 ======================

    def get_stock_history(
        self, code: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """FRED 不提供股票K线，返回空 DataFrame"""
        logger.debug("FRED 不支持股票K线，交由其它适配器")
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> list:
        """FRED 不提供指数成分股"""
        return []

    def get_stock_info(self, code: str) -> Dict:
        """用 series_id 反查：返回 fredapi get_series_info 的字段"""
        if self._client is None:
            return {}
        try:
            info = self._client.get_series_info(code)
            if isinstance(info, pd.Series):
                return info.to_dict()
            if isinstance(info, dict):
                return info
            return {}
        except Exception as e:
            logger.warning(
                f"FRED get_series_info 失败 code={code}: "
                f"{type(e).__name__}: {e}"
            )
            return {}

    def get_financial_data(self, code: str) -> Dict:
        """FRED 是宏观而非公司财报源，返回空 dict"""
        return {}

    def health_check(self) -> bool:
        """健康检查：拉一个小序列(UNRATE)判活"""
        if self._client is None:
            return False
        try:
            df = self.get_series("UNRATE")
            return not df.empty
        except Exception as e:
            logger.warning(f"FRED 健康检查失败: {type(e).__name__}: {e}")
            return False
