# -*- coding: utf-8 -*-
"""
yfinance适配器 - 港美股+ETF+期权覆盖 [NEW-FILE:#20260415-05]
Input: 符号(A股6位/港股5位/美股Ticker)、period/interval、expiry
Output: pd.DataFrame (K线) 或 Dict (info/financials/options_chain)
Pos: app/adapters层，跨市场数据补全 (yfinance官方API v0.2+，Apache-2.0)

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

联网调研权威源 (2026-04-15 11:30 +08:00)：
  1. https://github.com/ranaroussi/yfinance - 官方仓库 README
  2. https://ranaroussi.github.io/yfinance/ - API文档 Ticker/history/info/option_chain
  3. https://pypi.org/project/yfinance/ - PyPI release与依赖
  4. Yahoo Finance符号后缀规则：.HK(港) .T(东京) .SS(沪) .SZ(深) .L(伦敦)，美股原样
"""
import logging
from typing import List, Dict, Optional
import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

# 软依赖：yfinance未安装时整模块可用，方法降级返回空结构
try:
    import yfinance as yf  # type: ignore
    _YF_AVAILABLE = True
except ImportError:
    yf = None  # type: ignore
    _YF_AVAILABLE = False
    logger.warning("yfinance未安装，YFinanceAdapter将返回空结构。pip install yfinance 启用")


class YFinanceAdapter(BaseAdapter):
    """yfinance数据源适配器，覆盖美股/港股/日股/A股(via .SS/.SZ)/ETF/期权。

    符号归一化规则：
      - A股6位数字：6开头→.SS(沪)，其余→.SZ(深)
      - 港股4-5位数字：左补0至4位 + .HK
      - 美股/ETF：原样大写
      - 已含后缀(.SS/.SZ/.HK/.T/.L等)：原样
    """

    # period/interval 合法值 (yfinance官方文档)
    VALID_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
    VALID_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h",
                       "1d", "5d", "1wk", "1mo", "3mo"}

    @property
    def name(self) -> str:
        return "yfinance"

    # ==================== 符号归一化 ====================
    def normalize_symbol(self, code: str, market: str = "auto") -> str:
        """将内部代码转为Yahoo Finance符号。

        Args:
            code: 原始代码，如 "000001" / "00700" / "AAPL" / "600519.SS"
            market: "A"/"HK"/"US"/"JP"/"auto"；auto根据字符规则推断

        Returns:
            Yahoo符号，如 "000001.SZ" / "0700.HK" / "AAPL"
        """
        if not code:
            return ""
        code = str(code).strip().upper()

        # 已含后缀直接返回
        for suf in (".SS", ".SZ", ".HK", ".T", ".L", ".TO", ".AX", ".PA", ".DE"):
            if code.endswith(suf):
                return code

        m = market.upper() if market else "AUTO"

        if m == "A" or (m == "AUTO" and code.isdigit() and len(code) == 6):
            return f"{code}.SS" if code.startswith("6") else f"{code}.SZ"

        if m == "HK" or (m == "AUTO" and code.isdigit() and len(code) <= 5):
            return f"{code.zfill(4)}.HK"

        if m == "JP":
            return f"{code}.T"

        # 美股/ETF/默认
        return code

    # ==================== 核心业务接口 ====================
    def get_kline(self, symbol: str, period: str = "1y",
                  interval: str = "1d") -> pd.DataFrame:
        """获取K线 (yfinance Ticker.history)。

        Returns:
            DataFrame columns: date, open, high, low, close, volume, amount
        """
        if not _YF_AVAILABLE:
            logger.warning(f"yfinance不可用，get_kline({symbol})返回空")
            return pd.DataFrame()

        if period not in self.VALID_PERIODS:
            logger.warning(f"非法period={period}，降级为1y")
            period = "1y"
        if interval not in self.VALID_INTERVALS:
            logger.warning(f"非法interval={interval}，降级为1d")
            interval = "1d"

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval, auto_adjust=False)
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.reset_index()
            date_col = "Date" if "Date" in df.columns else ("Datetime" if "Datetime" in df.columns else df.columns[0])
            df = df.rename(columns={
                date_col: "date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })
            # yfinance无amount字段，用close*volume近似
            if "close" in df.columns and "volume" in df.columns:
                df["amount"] = df["close"] * df["volume"]
            keep = [c for c in ["date", "open", "high", "low", "close", "volume", "amount"] if c in df.columns]
            return df[keep]
        except Exception as e:
            logger.warning(f"yfinance get_kline失败(symbol={symbol}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_info(self, symbol: str) -> Dict:
        """获取基本面信息 (Ticker.info)。"""
        if not _YF_AVAILABLE:
            return {}
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return dict(info) if info else {}
        except Exception as e:
            logger.warning(f"yfinance get_info失败(symbol={symbol}): {type(e).__name__}: {e}")
            return {}

    def get_financials(self, symbol: str) -> Dict:
        """获取三大报表 (income_stmt/balance_sheet/cashflow)。"""
        if not _YF_AVAILABLE:
            return {"income_stmt": [], "balance_sheet": [], "cashflow": []}
        result = {"income_stmt": [], "balance_sheet": [], "cashflow": []}
        try:
            ticker = yf.Ticker(symbol)
            for key, attr in (("income_stmt", "income_stmt"),
                              ("balance_sheet", "balance_sheet"),
                              ("cashflow", "cashflow")):
                try:
                    df = getattr(ticker, attr, None)
                    if df is not None and hasattr(df, "empty") and not df.empty:
                        # 行=科目、列=财报期；转为 [{'item':..., 'YYYY-MM-DD': value, ...}]
                        result[key] = df.reset_index().to_dict("records")
                except Exception as sub_e:
                    logger.warning(f"yfinance {attr}子表失败(symbol={symbol}): {type(sub_e).__name__}: {sub_e}")
        except Exception as e:
            logger.warning(f"yfinance get_financials失败(symbol={symbol}): {type(e).__name__}: {e}")
        return result

    def get_options_chain(self, symbol: str, expiry: Optional[str] = None) -> Dict:
        """获取期权链 (Ticker.option_chain)。

        Args:
            symbol: 标的
            expiry: 到期日 YYYY-MM-DD，None则取最近一期

        Returns:
            {"expiry": str, "expirations": [...], "calls": [...], "puts": [...]}
        """
        if not _YF_AVAILABLE:
            return {"expiry": None, "expirations": [], "calls": [], "puts": []}
        try:
            ticker = yf.Ticker(symbol)
            expirations = list(ticker.options) if ticker.options else []
            if not expirations:
                return {"expiry": None, "expirations": [], "calls": [], "puts": []}
            target = expiry if expiry in expirations else expirations[0]
            chain = ticker.option_chain(target)
            calls = chain.calls.to_dict("records") if chain.calls is not None and not chain.calls.empty else []
            puts = chain.puts.to_dict("records") if chain.puts is not None and not chain.puts.empty else []
            return {"expiry": target, "expirations": expirations, "calls": calls, "puts": puts}
        except Exception as e:
            logger.warning(f"yfinance get_options_chain失败(symbol={symbol}): {type(e).__name__}: {e}")
            return {"expiry": None, "expirations": [], "calls": [], "puts": []}

    # ==================== BaseAdapter契约 ====================
    def get_stock_history(self, code: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> pd.DataFrame:
        """BaseAdapter接口：按日期区间获取K线。

        将A股6位代码归一化为Yahoo符号后调用history(start,end)。
        """
        if not _YF_AVAILABLE:
            return pd.DataFrame()
        symbol = self.normalize_symbol(code)
        try:
            # 兼容 20240101 / 2024-01-01 两种入参
            def _fmt(d: str) -> str:
                d = str(d).strip()
                return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d
            auto_adjust = adjust in ("qfq", "hfq")
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=_fmt(start_date), end=_fmt(end_date),
                                interval="1d", auto_adjust=auto_adjust)
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.reset_index().rename(columns={
                "Date": "date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })
            if "close" in df.columns and "volume" in df.columns:
                df["amount"] = df["close"] * df["volume"]
            keep = [c for c in ["date", "open", "high", "low", "close", "volume", "amount"] if c in df.columns]
            return df[keep]
        except Exception as e:
            logger.warning(f"yfinance get_stock_history失败(code={code}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        """yfinance不提供指数成分股，返回空列表（由akshare/baostock负责）。"""
        logger.info(f"yfinance不支持指数成分股({index_code})，应由akshare/baostock提供")
        return []

    def get_stock_info(self, code: str) -> Dict:
        """BaseAdapter契约：委托 get_info。"""
        return self.get_info(self.normalize_symbol(code))

    def get_financial_data(self, code: str) -> Dict:
        """BaseAdapter契约：委托 get_financials。"""
        return self.get_financials(self.normalize_symbol(code))

    def health_check(self) -> bool:
        """健康检查：拉 AAPL 1d K线。"""
        if not _YF_AVAILABLE:
            return False
        try:
            df = yf.Ticker("AAPL").history(period="5d", interval="1d")
            return df is not None and not df.empty
        except Exception as e:
            logger.warning(f"yfinance健康检查失败: {type(e).__name__}: {e}")
            return False
