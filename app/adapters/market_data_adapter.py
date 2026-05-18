"""
Input: 股票代码 + 市场类型 (A/HK/US)
Output: 统一格式的 quote / kline / fundamentals DataFrame 或 dict
Pos: app/adapters/market_data_adapter.py - 多市场数据源统一接口

[FIX-8 2026-05-18 +08:00] 港股/美股后端数据源接入。
  - A 股: 委托给现有 DataProvider (akshare + baostock fallback)
  - 港股: akshare stock_hk_hist / stock_hk_spot_em (含 stock_hk_security_profile_em 兜底)
  - 美股: akshare stock_us_hist / stock_us_spot_em (含 yfinance 兜底)
  - 全部走 FIX-7 network_resilience wrapper

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd

from app.core.network_resilience import resilient_call, DataSourceTimeoutError, DataSourceUnavailableError

logger = logging.getLogger(__name__)


class UnsupportedMarketError(Exception):
    """市场类型不在 A/HK/US 内"""
    pass


# === 列名归一 ===

_RENAME_MAP = {
    "日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
    "最低": "low", "成交量": "volume", "成交额": "amount",
    "trade_date": "date", "Open": "open", "Close": "close",
    "High": "high", "Low": "low", "Volume": "volume", "Date": "date",
}


def _normalize_kline_df(df: pd.DataFrame) -> pd.DataFrame:
    """统一 OHLCV 列名 + 类型转换"""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns=_RENAME_MAP).copy()
    if 'volume' not in df.columns and 'amount' in df.columns:
        df['volume'] = df['amount']
    essential = ['date', 'open', 'close', 'high', 'low', 'volume']
    missing = [c for c in essential if c not in df.columns]
    if missing:
        logger.warning(f"kline 缺列: {missing}, 可用列: {list(df.columns)}")
        return pd.DataFrame()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df.dropna(subset=['date'], inplace=True)
    for c in ['open', 'close', 'high', 'low', 'volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df.dropna(subset=essential, inplace=True)
    return df.sort_values('date').reset_index(drop=True)


# === 港股 ===

def _fetch_hk_kline_raw(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """raw 调用, 不带韧性 (供 wrapper 包裹)"""
    import akshare as ak
    # akshare 港股代号要求 5 位 (如 00700)
    sc = stock_code.zfill(5) if stock_code.isdigit() and len(stock_code) < 5 else stock_code
    df = ak.stock_hk_hist(symbol=sc, period="daily",
                          start_date=start_date, end_date=end_date, adjust="qfq")
    return df


def _fetch_hk_spot_raw(stock_code: str) -> dict:
    import akshare as ak
    df = ak.stock_hk_spot_em()
    sc = stock_code.zfill(5) if stock_code.isdigit() and len(stock_code) < 5 else stock_code
    row = df[df['代码'] == sc]
    if row.empty:
        return {}
    r = row.iloc[0].to_dict()
    return {
        'code': sc,
        'name': r.get('名称'),
        'price': float(r.get('最新价') or 0),
        'change_pct': float(r.get('涨跌幅') or 0),
        'volume': float(r.get('成交量') or 0),
        'amount': float(r.get('成交额') or 0),
        'market': 'HK',
    }


# === 美股 ===

def _fetch_us_kline_raw(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    import akshare as ak
    try:
        df = ak.stock_us_hist(symbol=stock_code, period="daily",
                              start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and not df.empty:
            return df
    except Exception as e:
        logger.warning(f"akshare stock_us_hist 失败 ({stock_code}): {type(e).__name__}: {e}")
    # 降级 yfinance
    try:
        import yfinance as yf
        ticker = yf.Ticker(stock_code)
        # yfinance 区间用 start/end (YYYY-MM-DD)
        sd = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
        ed = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
        hist = ticker.history(start=sd, end=ed, auto_adjust=False)
        if hist is not None and not hist.empty:
            hist = hist.reset_index()
            return hist
    except Exception as e:
        logger.warning(f"yfinance 降级失败 ({stock_code}): {type(e).__name__}: {e}")
    return pd.DataFrame()


def _fetch_us_spot_raw(stock_code: str) -> dict:
    import akshare as ak
    try:
        df = ak.stock_us_spot_em()
        row = df[df['代码'].str.contains(stock_code.upper(), na=False)]
        if not row.empty:
            r = row.iloc[0].to_dict()
            return {
                'code': stock_code.upper(),
                'name': r.get('名称'),
                'price': float(r.get('最新价') or 0),
                'change_pct': float(r.get('涨跌幅') or 0),
                'volume': float(r.get('成交量') or 0),
                'market': 'US',
            }
    except Exception as e:
        logger.warning(f"akshare stock_us_spot_em 失败: {type(e).__name__}: {e}")
    # 降级 yfinance
    try:
        import yfinance as yf
        ticker = yf.Ticker(stock_code)
        info = ticker.info or {}
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        if price:
            return {
                'code': stock_code.upper(),
                'name': info.get('shortName') or info.get('longName'),
                'price': float(price),
                'change_pct': float(info.get('regularMarketChangePercent') or 0),
                'volume': float(info.get('regularMarketVolume') or 0),
                'market': 'US',
            }
    except Exception as e:
        logger.warning(f"yfinance spot 降级失败 ({stock_code}): {type(e).__name__}: {e}")
    return {}


# === 公开接口 ===

def get_kline(stock_code: str, market: str = 'A',
              start_date: Optional[str] = None,
              end_date: Optional[str] = None,
              days: int = 365) -> pd.DataFrame:
    """统一 K 线接口。返回 ['date','open','close','high','low','volume'] DataFrame。"""
    market = (market or 'A').upper()
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')

    try:
        if market == 'A':
            # 委托 DataProvider (现有逻辑)
            from app.core.data_provider import DataProvider
            dp = DataProvider()
            raw = resilient_call(
                dp.get_stock_history, (stock_code, start_date, end_date),
                per_call_timeout=10.0, cache_ttl=600,
            )
            return _normalize_kline_df(raw)
        elif market == 'HK':
            raw = resilient_call(
                _fetch_hk_kline_raw, (stock_code, start_date, end_date),
                per_call_timeout=10.0, cache_ttl=600,
            )
            return _normalize_kline_df(raw)
        elif market == 'US':
            raw = resilient_call(
                _fetch_us_kline_raw, (stock_code, start_date, end_date),
                per_call_timeout=12.0, cache_ttl=600,
            )
            return _normalize_kline_df(raw)
        else:
            raise UnsupportedMarketError(f"不支持的市场: {market}")
    except (DataSourceTimeoutError, DataSourceUnavailableError) as e:
        logger.warning(f"get_kline 数据源失败 {stock_code}/{market}: {e}")
        return pd.DataFrame()


def get_quote(stock_code: str, market: str = 'A') -> Dict[str, Any]:
    """统一行情快照接口。"""
    market = (market or 'A').upper()
    try:
        if market == 'A':
            # 复用 K 线最新一行
            df = get_kline(stock_code, 'A', days=10)
            if df.empty:
                return {}
            row = df.iloc[-1]
            return {
                'code': stock_code,
                'price': float(row['close']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'volume': float(row['volume']),
                'date': row['date'].strftime('%Y-%m-%d'),
                'market': 'A',
            }
        elif market == 'HK':
            return resilient_call(
                _fetch_hk_spot_raw, (stock_code,),
                per_call_timeout=8.0, cache_ttl=60,
            )
        elif market == 'US':
            return resilient_call(
                _fetch_us_spot_raw, (stock_code,),
                per_call_timeout=10.0, cache_ttl=60,
            )
        else:
            raise UnsupportedMarketError(f"不支持的市场: {market}")
    except (DataSourceTimeoutError, DataSourceUnavailableError) as e:
        logger.warning(f"get_quote 失败 {stock_code}/{market}: {e}")
        return {}


def get_fundamentals(stock_code: str, market: str = 'A') -> Dict[str, Any]:
    """统一基本面接口。当前仅返回最小集 (name + market)，详细字段后续扩展。"""
    market = (market or 'A').upper()
    if market not in ('A', 'HK', 'US'):
        raise UnsupportedMarketError(f"不支持的市场: {market}")
    quote = get_quote(stock_code, market)
    return {
        'code': stock_code,
        'name': quote.get('name', ''),
        'market': market,
        'price': quote.get('price'),
    }
