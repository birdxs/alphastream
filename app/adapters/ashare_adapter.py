# -*- coding: utf-8 -*-
"""
Ashare适配器 - 单文件库直调：新浪/腾讯A股日/周/月/分钟线
Input: 股票代码(sh600519/sz000001/600519)、frequency(1d/1w/1M/1m/5m/15m/30m/60m)、count
Output: pd.DataFrame[open,close,high,low,volume] 索引为时间
Pos: app/adapters层，A股行情轻量兜底；未装Ashare静默降级
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

权威源（≥3交叉验证, 检索时间 2026-04-15 12:30 +08:00）：
  1) GitHub mpquant/Ashare README + Ashare.py 源码 @ main
     https://github.com/mpquant/Ashare
     说明：单文件 ~200行；code规范 sh600519/sz000001；frequency 1d/1w/1M/1m/5m/15m/30m/60m；count 默认10
  2) 新浪财经日K数据接口 http://money.finance.sina.com.cn/quotes_service/api/json_v2.php
     （Ashare 日/周/月线走此源）
  3) 腾讯财经分钟K接口 http://ifzq.gtimg.cn/appstock/app/kline/mkline
     （Ashare 分钟级走此源）

设计：
  - Ashare为单文件库，装法极简 `from Ashare import get_price`
  - 未装时软降级为返回空DF，不抛异常
  - _normalize(code, market) 统一入参为 sh/sz 前缀格式
"""
import logging
from typing import List, Dict, Optional

import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

# try-import：Ashare单文件库，未装时 get_price=None
try:
    from Ashare import get_price as _ashare_get_price  # type: ignore
    _ASHARE_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    _ashare_get_price = None  # type: ignore
    _ASHARE_AVAILABLE = False
    logger.warning(f"Ashare未安装或导入失败，AshareAdapter进入降级模式: {type(_e).__name__}: {_e}")


# Ashare官方合法frequency
_VALID_FREQ = {"1d", "1w", "1M", "1m", "5m", "15m", "30m", "60m"}


class AshareAdapter(BaseAdapter):
    """Ashare单文件库适配器：A股日/周/月/分钟K线轻量兜底"""

    @property
    def name(self) -> str:
        return "ashare"

    # ---------- 代码规范化 ----------

    @staticmethod
    def _normalize(code: str, market: Optional[str] = None) -> str:
        """转换代码为Ashare规范：sh600519 / sz000001

        Args:
            code: 原始代码，可能是 600519 / sh600519 / 600519.SH / 000001.SZ
            market: 可选显式指定 'sh' 或 'sz'

        Returns:
            Ashare规范字符串 sh600519 / sz000001
        """
        if not code:
            return ""
        s = str(code).strip().lower()
        # 去后缀 .sh/.sz
        for suf in (".sh", ".sz", ".ss"):
            if s.endswith(suf):
                s = s[: -len(suf)]
                break
        # 已带前缀
        if s.startswith("sh") or s.startswith("sz"):
            return s
        # 纯数字：按market或首位推断
        digits = "".join(ch for ch in s if ch.isdigit())
        if not digits:
            return s
        if market and market.lower() in ("sh", "sz"):
            return f"{market.lower()}{digits}"
        # 6/9开头→sh(沪市/科创), 0/3开头→sz(深市/创业), 8/4→bj(北交所，Ashare不支持→sz兜底日志)
        if digits.startswith(("6", "9")):
            return f"sh{digits}"
        if digits.startswith(("0", "3")):
            return f"sz{digits}"
        logger.info(f"Ashare不支持的代码前缀 {digits}，按sz兜底")
        return f"sz{digits}"

    # ---------- 核心：get_price ----------

    def get_price(self, code: str, frequency: str = "1d", count: int = 100) -> pd.DataFrame:
        """获取K线

        Args:
            code: 股票代码，任意格式；内部 _normalize
            frequency: 1d/1w/1M 日周月 或 1m/5m/15m/30m/60m 分钟
            count: 返回条数，Ashare默认10

        Returns:
            DataFrame[open,close,high,low,volume]，索引为datetime
        """
        if not _ASHARE_AVAILABLE:
            logger.warning("Ashare未就绪，get_price返回空DF")
            return pd.DataFrame()
        if frequency not in _VALID_FREQ:
            logger.warning(f"非法frequency={frequency}，合法值{_VALID_FREQ}，回退1d")
            frequency = "1d"
        norm = self._normalize(code)
        try:
            df = _ashare_get_price(norm, frequency=frequency, count=count)
            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                return pd.DataFrame()
            return df
        except Exception as e:
            logger.warning(f"Ashare.get_price失败(code={norm},freq={frequency}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    # ---------- BaseAdapter 抽象方法实现 ----------

    def get_stock_history(self, code: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> pd.DataFrame:
        """日线历史 — Ashare无start/end参数，使用count=2000约8年足够，调用方自行切片

        注：Ashare不支持复权参数；adjust仅为签名兼容被忽略。
        """
        df = self.get_price(code, frequency="1d", count=2000)
        if df.empty:
            return df
        # 切片到 [start_date, end_date]
        try:
            if start_date:
                sd = pd.to_datetime(str(start_date).replace('-', ''), format='%Y%m%d', errors='coerce')
                if pd.notna(sd):
                    df = df[df.index >= sd]
            if end_date:
                ed = pd.to_datetime(str(end_date).replace('-', ''), format='%Y%m%d', errors='coerce')
                if pd.notna(ed):
                    df = df[df.index <= ed]
        except Exception as e:
            logger.warning(f"Ashare日期切片失败: {type(e).__name__}: {e}")
        return df

    def get_index_stocks(self, index_code: str) -> List[str]:
        """Ashare无指数成分接口，返回空 — 由akshare兜底"""
        logger.info(f"Ashare无指数成分股接口(index={index_code})，返回空")
        return []

    def get_stock_info(self, code: str) -> Dict:
        """Ashare仅K线，无个股信息"""
        return {}

    def get_financial_data(self, code: str) -> Dict:
        """Ashare无财务接口"""
        return {}

    def health_check(self) -> bool:
        """健康检查：拉取上证指数 sh000001 最近2根日线"""
        if not _ASHARE_AVAILABLE:
            return False
        try:
            df = _ashare_get_price("sh000001", frequency="1d", count=2)
            return df is not None and not df.empty
        except Exception as e:
            logger.warning(f"Ashare健康检查失败: {type(e).__name__}: {e}")
            return False
