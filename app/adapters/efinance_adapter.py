# -*- coding: utf-8 -*-
"""
efinance适配器 - 分钟K线/龙虎榜/融资融券/实时行情（东财反向接口）
Input: 股票代码/日期范围/K线周期标识(klt)
Output: pd.DataFrame (minute/billboard/margin/realtime)
Pos: app/adapters层，作为行情/情绪类Agent的高频补充源；不可用时静默降级
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

权威源（≥3交叉验证, 检索时间 2026-04-15 11:30 +08:00）：
  1) GitHub Micro-sheep/efinance 源码 efinance/stock/getter.py @ main(84eca44)
     https://github.com/Micro-sheep/efinance
  2) PyPI efinance 0.5.8 (released 2026-03-18, MIT)
     https://pypi.org/project/efinance/
  3) GitHub Release v0.5.5 (2025-03-15) + tags 链
     https://github.com/Micro-sheep/efinance/releases

API映射确认：
  - 分钟K线   → efinance.stock.get_quote_history(stock_codes, beg, end, klt, fqt)
                klt: 1/5/15/30/60分钟；101日线
  - 龙虎榜    → efinance.stock.get_daily_billboard(start_date, end_date)
                注：efinance官方无get_top_list，实际函数名get_daily_billboard
  - 融资融券  → efinance无原生接口（仅在get_belong_board返回板块名中出现）
                本适配器保留get_margin_trading签名供调度层统一，返回空DF
  - 实时行情  → efinance.stock.get_realtime_quotes(fs) 传股票代码列表

合规：efinance反向工程东财接口，仅研究用途，UA限速≤2QPS。
"""
import logging
from typing import List, Dict, Optional

import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

# try-import：未装不崩，调用时返回空DF
try:
    import efinance as ef  # type: ignore
    _EF_AVAILABLE = True
except Exception as _e:  # pragma: no cover - 环境缺失降级
    ef = None  # type: ignore
    _EF_AVAILABLE = False
    logger.warning(f"efinance未安装或导入失败，EfinanceAdapter进入降级模式: {type(_e).__name__}: {_e}")


# 东财原始中文列 → 统一英文列（与akshare_adapter对齐）
_KLINE_FIELD_MAP = {
    '股票名称': 'name', '股票代码': 'code',
    '日期': 'date', '开盘': 'open', '收盘': 'close',
    '最高': 'high', '最低': 'low',
    '成交量': 'volume', '成交额': 'amount',
    '振幅': 'amplitude', '涨跌幅': 'change_percent',
    '涨跌额': 'change_amount', '换手率': 'turnover',
}

_BILLBOARD_FIELD_MAP = {
    '股票代码': 'code', '股票名称': 'name',
    '上榜日期': 'list_date', '解读': 'interpretation',
    '收盘价': 'close', '涨跌幅': 'change_percent',
    '换手率': 'turnover',
    '龙虎榜净买额': 'net_buy', '龙虎榜买入额': 'buy_amount',
    '龙虎榜卖出额': 'sell_amount', '龙虎榜成交额': 'total_amount',
    '市场总成交额': 'market_amount',
    '净买额占总成交比': 'net_buy_ratio',
    '成交额占总成交比': 'amount_ratio',
    '流通市值': 'float_mv',
    '上榜原因': 'reason',
}

_REALTIME_FIELD_MAP = {
    '股票代码': 'code', '股票名称': 'name',
    '涨跌幅': 'change_percent', '最新价': 'price',
    '最高': 'high', '最低': 'low', '今开': 'open',
    '涨跌额': 'change_amount', '换手率': 'turnover',
    '量比': 'volume_ratio', '动态市盈率': 'pe_ttm',
    '成交量': 'volume', '成交额': 'amount',
    '昨日收盘': 'pre_close',
    '总市值': 'total_mv', '流通市值': 'float_mv',
    '行情ID': 'quote_id', '市场类型': 'market',
}

# 合法klt值（efinance官方）：1/5/15/30/60 分钟, 101 日, 102 周, 103 月
_VALID_KLT = {1, 5, 15, 30, 60, 101, 102, 103}


class EfinanceAdapter(BaseAdapter):
    """efinance数据源适配器：东财高频补充（分钟线/龙虎榜/实时）"""

    @property
    def name(self) -> str:
        return "efinance"

    # ---------- BaseAdapter 抽象方法实现 ----------

    def get_stock_history(self, code: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> pd.DataFrame:
        """日线历史（klt=101）。adjust: qfq前复权/hfq后复权/''不复权"""
        if not _EF_AVAILABLE:
            logger.warning("efinance未就绪，get_stock_history返回空DF")
            return pd.DataFrame()
        fqt = {"qfq": 1, "hfq": 2, "": 0}.get(adjust, 1)
        try:
            df = ef.stock.get_quote_history(
                code, beg=self._norm_date(start_date),
                end=self._norm_date(end_date),
                klt=101, fqt=fqt,
            )
            return self._rename(df, _KLINE_FIELD_MAP)
        except Exception as e:
            logger.warning(f"efinance日线失败(code={code}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        """指数成分股 - efinance通过 get_members 获取"""
        if not _EF_AVAILABLE:
            return []
        try:
            df = ef.stock.get_members(index_code)
            if df is not None and not df.empty:
                col = '股票代码' if '股票代码' in df.columns else df.columns[0]
                return df[col].astype(str).tolist()
        except Exception as e:
            logger.warning(f"efinance成分股失败(index={index_code}): {type(e).__name__}: {e}")
        return []

    def get_stock_info(self, code: str) -> Dict:
        """个股基本信息"""
        if not _EF_AVAILABLE:
            return {}
        try:
            df = ef.stock.get_base_info(code)
            if df is None:
                return {}
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df.iloc[0].to_dict()
            if isinstance(df, pd.Series):
                return df.to_dict()
        except Exception as e:
            logger.warning(f"efinance个股信息失败(code={code}): {type(e).__name__}: {e}")
        return {}

    def get_financial_data(self, code: str) -> Dict:
        """财务数据 - efinance无独立财务API，返回空留给akshare/baostock"""
        logger.info(f"efinance无独立财务接口，get_financial_data返回空(code={code})")
        return {}

    def health_check(self) -> bool:
        """健康检查：调get_realtime_quotes('沪深A股')"""
        if not _EF_AVAILABLE:
            return False
        try:
            df = ef.stock.get_realtime_quotes()
            return df is not None and len(df) > 0
        except Exception as e:
            logger.warning(f"efinance健康检查失败: {type(e).__name__}: {e}")
            return False

    # ---------- P0-A2 新增能力 ----------

    def get_minute_kline(self, code: str, klt: int = 1, count: int = 240) -> pd.DataFrame:
        """分钟K线

        Args:
            code: 股票代码 如 000001
            klt: K线周期分钟 {1,5,15,30,60}, 默认1分钟
            count: 返回最近条数，取尾部count根（efinance无原生count，取尾切）
        Returns:
            DataFrame[code,name,date,open,close,high,low,volume,amount,...]
        """
        if not _EF_AVAILABLE:
            logger.warning("efinance未就绪，get_minute_kline返回空DF")
            return pd.DataFrame()
        if klt not in _VALID_KLT:
            logger.warning(f"非法klt={klt}，合法值{_VALID_KLT}，回退klt=1")
            klt = 1
        try:
            df = ef.stock.get_quote_history(code, klt=klt, fqt=1)
            df = self._rename(df, _KLINE_FIELD_MAP)
            if count and len(df) > count:
                df = df.tail(count).reset_index(drop=True)
            return df
        except Exception as e:
            logger.warning(f"efinance分钟线失败(code={code},klt={klt}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_top_list(self, start: str, end: str) -> pd.DataFrame:
        """龙虎榜（efinance实际API名 get_daily_billboard）

        Args:
            start: 起始日期 YYYYMMDD 或 YYYY-MM-DD
            end: 结束日期
        Returns:
            DataFrame[code,name,list_date,net_buy,buy_amount,sell_amount,reason,...]
        """
        if not _EF_AVAILABLE:
            logger.warning("efinance未就绪，get_top_list返回空DF")
            return pd.DataFrame()
        try:
            df = ef.stock.get_daily_billboard(
                start_date=self._norm_date(start, dash=True),
                end_date=self._norm_date(end, dash=True),
            )
            return self._rename(df, _BILLBOARD_FIELD_MAP)
        except Exception as e:
            logger.warning(f"efinance龙虎榜失败({start}~{end}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_margin_trading(self, code: str) -> pd.DataFrame:
        """融资融券 - efinance无此API。保留签名供调度统一，实际由akshare兜底

        调度层：fallback_manager应将此调用转发到 AkshareAdapter.stock_margin_detail
        """
        logger.info(
            f"efinance无融资融券API(get_margin_schedule不存在)，"
            f"get_margin_trading返回空DF(code={code})，请走akshare兜底"
        )
        return pd.DataFrame()

    def get_realtime_quotes(self, codes: Optional[List[str]] = None) -> pd.DataFrame:
        """实时行情

        Args:
            codes: 股票代码列表；None/空→返回全市场快照
        Returns:
            DataFrame[code,name,price,change_percent,volume,amount,...]
        """
        if not _EF_AVAILABLE:
            logger.warning("efinance未就绪，get_realtime_quotes返回空DF")
            return pd.DataFrame()
        try:
            if codes:
                # efinance get_realtime_quotes的fs参数是市场名，不是代码
                # 按代码过滤需先全市场拉再filter
                df = ef.stock.get_realtime_quotes()
                df = self._rename(df, _REALTIME_FIELD_MAP)
                if 'code' in df.columns:
                    codes_str = [str(c).zfill(6) for c in codes]
                    df = df[df['code'].astype(str).isin(codes_str)].reset_index(drop=True)
                return df
            df = ef.stock.get_realtime_quotes()
            return self._rename(df, _REALTIME_FIELD_MAP)
        except Exception as e:
            logger.warning(f"efinance实时行情失败: {type(e).__name__}: {e}")
            return pd.DataFrame()

    # ---------- J1 alias: 个股资金流 ----------
    def get_individual_fund_flow(self, code: str) -> pd.DataFrame:
        """J1 [NEW-FILE:#20260415-43] 个股资金流 alias。

        策略:
          1) efinance 优先使用 stock.get_today_bill(code) (官方个股分时资金接口)
          2) 失败则从实时行情重组主要字段(price/change/amount)供降级

        Returns:
            pd.DataFrame — 资金流数据或实时快照降级DF。
        """
        if not _EF_AVAILABLE:
            return pd.DataFrame()
        # 1) 官方真实接口
        try:
            get_bill = getattr(ef.stock, "get_today_bill", None)
            if callable(get_bill):
                df = get_bill(str(code))
                if isinstance(df, pd.DataFrame) and not df.empty:
                    return df
        except Exception as e:
            logger.info(f"[EfinanceAdapter] get_today_bill({code}) 不可用: {type(e).__name__}: {e}")
        # 2) 实时快照降级
        try:
            df = self.get_realtime_quotes(codes=[code])
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
        except Exception as e:
            logger.warning(f"[EfinanceAdapter] get_individual_fund_flow 降级失败: {type(e).__name__}: {e}")
        return pd.DataFrame()

    # ---------- 工具方法 ----------

    @staticmethod
    def _norm_date(d: str, dash: bool = False) -> str:
        """日期归一化：20240101 ↔ 2024-01-01。efinance龙虎榜要带'-'，K线不带。"""
        if not d:
            return d
        s = str(d).replace('-', '').replace('/', '')
        if dash and len(s) == 8:
            return f"{s[:4]}-{s[4:6]}-{s[6:]}"
        return s

    @staticmethod
    def _rename(df: Optional[pd.DataFrame], mapping: Dict[str, str]) -> pd.DataFrame:
        """按mapping只rename存在的列；df为空/None→空DF"""
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame()
        m = {k: v for k, v in mapping.items() if k in df.columns}
        return df.rename(columns=m) if m else df
