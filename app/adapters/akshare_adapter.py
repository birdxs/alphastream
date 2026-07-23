# -*- coding: utf-8 -*-
"""
akshare适配器 - 老王说：内部多数据源自动切换！
东财挂了切同花顺，同花顺挂了切新浪，新浪挂了切腾讯...
Input: 股票代码、日期范围等查询参数
Output: DataFrame或Dict格式的股票/财务/板块数据
Pos: app/adapters层，作为主数据源适配器被fallback_manager调度；含 A 股 code/market helper
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import akshare as ak
import pandas as pd
import logging
import os
import re
import time
import threading
from typing import List, Dict, Optional, Tuple
from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# A 股代码 / 市场 helper（akshare 1.18.75 契约；与 CapitalFlowAnalyzer.a_share_market_tag 对齐）
# 资金流 market：6→sh，0/3→sz，4/8→bj（含 92 开头北交所）
# 雪球：SH/SZ+代码；BJ 雪球多数端点不稳 → None 文档化降级
# 东财 hist：纯 6 位；tx/sina：sh/sz/bj 前缀（BJ 勿强绑 sz）
# ---------------------------------------------------------------------------


def to_em_pure_code(code: str) -> str:
    """东财 hist 用纯 6 位代码；清洗 SH/SZ/BJ 前缀与后缀。"""
    if code is None:
        return ''
    s = str(code).strip().upper()
    s = s.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
    s = re.sub(r'^(SH|SZ|BJ)', '', s)
    digits = re.sub(r'\D', '', s)
    if len(digits) >= 6:
        return digits[-6:]
    return digits


def to_flow_market(code: str) -> str:
    """个股资金流 market 标签（ak.stock_individual_fund_flow 的 market）。

    契约：6→sh，0/3→sz，4/8→bj（含 92xxxx）。无法识别时默认 sz（保守降级，不造假数）。
    """
    pure = to_em_pure_code(code)
    if not pure:
        return 'sz'
    if pure.startswith('6'):
        return 'sh'
    if pure.startswith(('0', '3')):
        return 'sz'
    if pure.startswith(('4', '8')) or pure.startswith('92'):
        return 'bj'
    if pure.startswith('9'):
        return 'sh'
    return 'sz'


def to_xq_symbol(code: str) -> Optional[str]:
    """雪球 symbol：SH600519 / SZ000001。

    北交所（4/8/92）在 akshare 1.18.75 无稳定雪球契约 → 返回 None，调用方跳过雪球路径。
    """
    pure = to_em_pure_code(code)
    if not pure or len(pure) != 6:
        return None
    if pure.startswith('6'):
        return f'SH{pure}'
    if pure.startswith(('0', '3')):
        return f'SZ{pure}'
    return None


def to_tx_sina_symbol(code: str) -> Optional[str]:
    """腾讯/新浪日 K：sh600519 / sz000001 / bj8xxxxx。BJ 用 bj 前缀，勿强绑 sz。"""
    pure = to_em_pure_code(code)
    if not pure:
        return None
    if pure.startswith(('6', '9')):
        return f'sh{pure}'
    if pure.startswith(('0', '3')):
        return f'sz{pure}'
    if pure.startswith(('4', '8')) or pure.startswith('92'):
        return f'bj{pure}'
    return f'sz{pure}'


# 同花顺概念/行业资金流合法 period
FUND_FLOW_BOARD_PERIODS = frozenset({
    '即时', '3日排行', '5日排行', '10日排行', '20日排行',
})
# 个股 rank indicator（勿与「10日排行」混用）
FUND_FLOW_RANK_INDICATORS = frozenset({'今日', '3日', '5日', '10日'})

_BOARD_PERIOD_ALIASES = {
    '即时': '即时', '今日': '即时', 'today': '即时', '1日': '即时',
    '3日': '3日排行', '3日排行': '3日排行',
    '5日': '5日排行', '5日排行': '5日排行',
    '10日': '10日排行', '10日排行': '10日排行',
    '20日': '20日排行', '20日排行': '20日排行',
}

_RANK_INDICATOR_ALIASES = {
    '今日': '今日', '即时': '今日', 'today': '今日',
    '3日': '3日', '3日排行': '3日',
    '5日': '5日', '5日排行': '5日',
    '10日': '10日', '10日排行': '10日',
}


def normalize_fund_flow_board_period(period: Optional[str]) -> Tuple[str, bool]:
    """归一概念/行业资金流 period → (normalized, ok)。

    ok=False：非法枚举已映射到默认「即时」；调用方应在响应中标注 degraded/mapped，勿盲传非法值。
    """
    if period is None or str(period).strip() == '':
        return '即时', True
    raw = str(period).strip()
    if raw in FUND_FLOW_BOARD_PERIODS:
        return raw, True
    mapped = _BOARD_PERIOD_ALIASES.get(raw) or _BOARD_PERIOD_ALIASES.get(raw.lower())
    if mapped:
        return mapped, True
    return '即时', False


def normalize_fund_flow_rank_indicator(indicator: Optional[str]) -> Tuple[str, bool]:
    """归一个股资金流 rank indicator（今日|3日|5日|10日）→ (normalized, ok)。"""
    if indicator is None or str(indicator).strip() == '':
        return '今日', True
    raw = str(indicator).strip()
    if raw in FUND_FLOW_RANK_INDICATORS:
        return raw, True
    mapped = _RANK_INDICATOR_ALIASES.get(raw) or _RANK_INDICATOR_ALIASES.get(raw.lower())
    if mapped:
        return mapped, True
    return '今日', False


# B16 AkshareAdapter 探针缓存常量（S1-C5: RLock 保护并发双字段写）
_AKSHARE_HC_CACHE = {'ok': None, 'ts': 0.0}
_AKSHARE_HC_CACHE_LOCK = threading.RLock()
_AKSHARE_HC_TTL = float(os.getenv('AKSHARE_HC_CACHE_TTL', '60'))
_AKSHARE_HC_PROBE_SYMBOL = os.getenv('AKSHARE_HC_PROBE_SYMBOL', 'SH600519')

# ── S3-C2 交易日历缓存（Hunt6-Major 2026-05-20）──────────────────────────────
# 缓存 A 股交易日集合，TTL 24h，DISABLE_NETWORK=1 时跳过（避免 CI 网络依赖）
_TRADE_DATE_CACHE: Optional[set] = None
_TRADE_DATE_CACHE_TS: float = 0.0
_TRADE_DATE_CACHE_TTL: float = float(os.getenv('TRADE_DATE_CACHE_TTL_S', str(86400)))
_TRADE_DATE_CACHE_LOCK = threading.RLock()


def _get_trade_date_set() -> Optional[set]:
    """获取 A 股交易日集合（datetime.date 对象）。

    - 数据来源：ak.tool_trade_date_hist_sina()（新浪交易日历，全量历史）
    - TTL：24h（TRADE_DATE_CACHE_TTL_S env 可覆盖）
    - DISABLE_NETWORK=1 时直接返回 None（CI 环境不调外网）
    - 失败时返回 None（允许降级，不抛异常）
    """
    if os.getenv('DISABLE_NETWORK', '0') == '1':
        return None

    global _TRADE_DATE_CACHE, _TRADE_DATE_CACHE_TS
    now = time.time()
    with _TRADE_DATE_CACHE_LOCK:
        if _TRADE_DATE_CACHE is not None and (now - _TRADE_DATE_CACHE_TS) < _TRADE_DATE_CACHE_TTL:
            return _TRADE_DATE_CACHE
        # 缓存过期 / 首次加载
        try:
            df = ak.tool_trade_date_hist_sina()
            if df is not None and not df.empty:
                import datetime as _dt
                col = df.columns[0]
                dates: set = set()
                for v in df[col]:
                    try:
                        if isinstance(v, _dt.date):
                            dates.add(v)
                        else:
                            dates.add(pd.to_datetime(str(v)).date())
                    except Exception:
                        pass
                _TRADE_DATE_CACHE = dates
                _TRADE_DATE_CACHE_TS = now
                logger.info(f"[S3-C2] 交易日历加载成功，共 {len(dates)} 个交易日")
                return _TRADE_DATE_CACHE
        except Exception as e:
            logger.warning(f"[S3-C2] 交易日历加载失败（降级，不过滤）: {type(e).__name__}: {e}")
        return None


def filter_kline_by_trade_dates(df: pd.DataFrame, date_col: str = 'date') -> pd.DataFrame:
    """过滤 K 线 DataFrame，只保留 A 股交易日数据行。

    - 若无法获取交易日历（DISABLE_NETWORK=1 / 网络失败），原样返回 df（降级）
    - 非交易日行（节假日/周末）会被剔除，前端渲染时不再出现 0 值/断点混淆
    - date_col 支持 'date'（string YYYYMMDD / YYYY-MM-DD）或 datetime64 列

    Args:
        df: K 线 DataFrame，含 date_col 列
        date_col: 日期列名

    Returns:
        过滤后的 DataFrame（trading days only），或原始 df（降级）
    """
    if df is None or df.empty:
        return df
    if date_col not in df.columns:
        return df

    trade_dates = _get_trade_date_set()
    if trade_dates is None:
        return df  # 降级：不过滤

    import datetime as _dt
    try:
        def _to_date(v) -> Optional[_dt.date]:
            if isinstance(v, _dt.date):
                return v
            try:
                return pd.to_datetime(str(v)).date()
            except Exception:
                return None

        mask = df[date_col].apply(lambda v: (_to_date(v) in trade_dates))
        filtered = df[mask].copy()
        dropped = len(df) - len(filtered)
        if dropped > 0:
            logger.debug(f"[S3-C2] 过滤非交易日 {dropped} 行 / 原始 {len(df)} 行")
        return filtered
    except Exception as e:
        logger.warning(f"[S3-C2] 交易日过滤异常（降级）: {e}")
        return df


class AkshareAdapter(BaseAdapter):
    """akshare数据源适配器，支持内部多数据源冗余"""

    # 字段映射：统一不同数据源的返回格式
    FIELD_MAPPING = {
        'stock_zh_a_hist': {
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume', '成交额': 'amount'
        },
        'stock_zh_a_hist_tx': {},  # 腾讯接口字段已是英文
    }

    @property
    def name(self) -> str:
        return "akshare"

    def _format_code_for_tx(self, code: str) -> str:
        """转换股票代码为腾讯格式；委托 to_tx_sina_symbol（BJ 用 bj 前缀，勿强绑 sz）。"""
        sym = to_tx_sina_symbol(code)
        return sym if sym else f"sz{to_em_pure_code(code)}"

    def _format_code_for_sina(self, code: str) -> str:
        """转换股票代码为新浪格式；与 to_tx_sina_symbol 一致。"""
        sym = to_tx_sina_symbol(code)
        return sym if sym else f"sz{to_em_pure_code(code)}"

    @staticmethod
    def _normalize_sina_daily(df: pd.DataFrame) -> pd.DataFrame:
        """归一化新浪 stock_zh_a_daily 返回的列名 -> 与东财对齐
        新浪列：date open high low close volume amount outstanding_share turnover
        东财列（经 FIELD_MAPPING 后）：date open close high low volume amount
        新浪已是英文，只需保证 amount/turnover_rate 存在即可。
        """
        if df is None or df.empty:
            return df
        # 新浪日 K 已英文化，core 字段 date/open/close/high/low/volume/amount 命中
        # 若缺 amount，用 close*volume 估算（避免下游 KeyError）
        if 'amount' not in df.columns:
            if 'close' in df.columns and 'volume' in df.columns:
                df = df.copy()
                df['amount'] = df['close'] * df['volume']
        return df

    def get_stock_history(self, code: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> pd.DataFrame:
        """获取股票历史K线 - 东财挂了自动切腾讯"""
        # 清洗并验证股票代码
        code = str(code).strip()
        for prefix in ['.SH', '.SZ', '.sh', '.sz', 'SH', 'SZ', 'sh', 'sz']:
            code = code.replace(prefix, '')
        if not code or not code.isdigit() or len(code) != 6:
            logger.error(f"无效的股票代码: {code}")
            return pd.DataFrame()

        # 2026-05-18 调优：调用顺序改为新浪第一 → 腾讯第二 → 东财第三（兜底）
        # 依据：akshare GitHub issues #7274/#6987/#6954，东财 JSONDecodeError 频发；
        # 新浪 daily 实测 1.1s 稳定，优先使用；腾讯作第二道保险；东财降为最终兜底。

        # 第一位：新浪 daily（最快最稳定）
        try:
            sina_code = self._format_code_for_sina(code)
            df = ak.stock_zh_a_daily(symbol=sina_code, start_date=start_date,
                                     end_date=end_date, adjust=adjust)
            if df is not None and not df.empty:
                df = self._normalize_sina_daily(df)
                df = filter_kline_by_trade_dates(df)  # S3-C2: 交易日历过滤
                logger.info(f"akshare新浪 daily 成功(symbol={sina_code}, rows={len(df)})")
                return df
        except Exception as e:
            logger.warning(f"akshare新浪 daily 失败(symbol={code}): {type(e).__name__}: {e}")

        # 第二位：腾讯接口
        try:
            tx_code = self._format_code_for_tx(code)
            df = ak.stock_zh_a_hist_tx(symbol=tx_code, start_date=start_date,
                                       end_date=end_date, adjust=adjust)
            if df is not None and not df.empty:
                df = filter_kline_by_trade_dates(df)  # S3-C2: 交易日历过滤
                logger.info(f"akshare腾讯接口成功兜底(symbol={tx_code}, rows={len(df)})")
                return df
        except Exception as e:
            logger.warning(f"akshare腾讯接口失败(symbol={code}): {type(e).__name__}: {e}")

        # 第三位（最终兜底）：东财接口
        try:
            df = ak.stock_zh_a_hist(symbol=code, start_date=start_date,
                                    end_date=end_date, adjust=adjust)
            if df is not None and not df.empty:
                # 只 rename 存在的列
                mapping = {k: v for k, v in self.FIELD_MAPPING['stock_zh_a_hist'].items() if k in df.columns}
                if mapping:
                    df = df.rename(columns=mapping)
                df = filter_kline_by_trade_dates(df)  # S3-C2: 交易日历过滤
                logger.info(f"akshare东财接口最终兜底成功(symbol={code}, rows={len(df)})")
                return df
        except Exception as e:
            logger.warning(f"akshare东财接口失败(symbol={code}): {type(e).__name__}: {e}")

        # 2026-05-18 兜底：未知 symbol 或格式异常时返回空 DF，由上层 web_server.py:1198 走 404 友好路径
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        """获取指数成分股"""
        try:
            df = ak.index_stock_cons_weight_csindex(symbol=index_code)
            if df is not None and not df.empty:
                col = '成分券代码' if '成分券代码' in df.columns else df.columns[0]
                return df[col].tolist()
        except Exception as e:
            logger.warning(f"获取指数成分股失败(index={index_code}): {type(e).__name__}: {e}")
        return []

    def get_stock_info(self, code: str) -> Dict:
        """获取股票基本信息 - 东财→雪球"""
        code = code.replace('.SH', '').replace('.SZ', '').replace('sh', '').replace('sz', '')

        # 东财
        try:
            df = ak.stock_individual_info_em(symbol=code)
            if df is not None and not df.empty:
                return dict(zip(df['item'], df['value']))
        except Exception as e:
            logger.warning(f"akshare东财个股信息失败(symbol={code}): {type(e).__name__}: {e}")

        # 雪球
        # [2026-05-29 schema 守卫] 雪球上游 schema 变化时，ak.stock_individual_basic_info_xq
        # 内部解析会抛 KeyError: 'data'（缺 'data' 键）；外层 try/except 已兜住该异常，
        # 此处对返回结果再做结构校验（DataFrame 非空且形如表格），缺失/异常时受控降级返回 {} + WARNING，
        # 不让任何 KeyError/结构异常冒泡，契约不变。
        try:
            df = ak.stock_individual_basic_info_xq(symbol=code)
            records = df.to_dict('records') if (df is not None and not df.empty) else []
            if records:
                first = records[0]
                if isinstance(first, dict):
                    return first
                logger.warning(f"akshare雪球个股信息结构异常(symbol={code}): 首行非映射类型")
        except Exception as e:
            logger.warning(f"akshare雪球个股信息失败(symbol={code}): {type(e).__name__}: {e}")

        return {}

    def get_financial_data(self, code: str) -> Dict:
        """获取财务数据 - 东财→同花顺"""
        code = code.replace('.SH', '').replace('.SZ', '').replace('sh', '').replace('sz', '')

        # 东财财务分析指标
        try:
            df = ak.stock_financial_analysis_indicator(symbol=code, start_year="2023")
            if df is not None and not df.empty:
                return {'indicator': df.to_dict('records')}
        except Exception as e:
            logger.warning(f"akshare东财财务指标失败(symbol={code}): {type(e).__name__}: {e}")

        # 同花顺财务摘要
        try:
            df = ak.stock_financial_abstract_ths(symbol=code)
            if df is not None and not df.empty:
                return {'abstract': df.to_dict('records')}
        except Exception as e:
            logger.warning(f"akshare同花顺财务摘要失败(symbol={code}): {type(e).__name__}: {e}")

        return {}

    def get_board_stocks(self, board: str) -> List[str]:
        """获取板块股票列表"""
        board_map = {
            'all': 'stock_zh_a_spot_em',
            'sh': 'stock_sh_a_spot_em',
            'sz': 'stock_sz_a_spot_em',
            'bj': 'stock_bj_a_spot_em',
            'cyb': 'stock_cy_a_spot_em',
            'kcb': 'stock_kc_a_spot_em',
        }
        func_name = board_map.get(board)
        if not func_name:
            return []

        try:
            func = getattr(ak, func_name)
            df = func()
            if df is not None and not df.empty:
                col = '代码' if '代码' in df.columns else df.columns[0]
                return df[col].tolist()
        except Exception as e:
            logger.warning(f"获取板块股票列表失败(board={board}): {type(e).__name__}: {e}")
        return []

    def get_industry_list(self) -> pd.DataFrame:
        """获取行业板块列表 - 东财→同花顺"""
        # 东财
        try:
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.warning(f"akshare东财行业列表失败: {type(e).__name__}: {e}")

        # 同花顺
        try:
            df = ak.stock_board_industry_summary_ths()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.warning(f"akshare同花顺行业列表失败: {type(e).__name__}: {e}")

        return pd.DataFrame()

    def get_industry_stocks(self, industry: str) -> List[str]:
        """获取行业成分股"""
        try:
            df = ak.stock_board_industry_cons_em(symbol=industry)
            if df is not None and not df.empty:
                col = '代码' if '代码' in df.columns else df.columns[0]
                return df[col].tolist()
        except Exception as e:
            logger.warning(f"获取行业成分股失败(industry={industry}): {type(e).__name__}: {e}")
        return []

    def get_concept_stocks(self, concept: str) -> List[str]:
        """获取概念板块成分股代码列表"""
        # 先尝试概念板块
        try:
            df = ak.stock_board_concept_cons_em(symbol=concept)
            if df is not None and not df.empty:
                col = '代码' if '代码' in df.columns else df.columns[0]
                return df[col].tolist()
        except Exception as e:
            logger.warning(f"获取概念成分股失败(concept={concept}): {type(e).__name__}: {e}")

        # 概念失败，尝试行业板块
        try:
            df = ak.stock_board_industry_cons_em(symbol=concept)
            if df is not None and not df.empty:
                col = '代码' if '代码' in df.columns else df.columns[0]
                return df[col].tolist()
        except Exception as e:
            logger.warning(f"获取行业成分股失败(concept={concept}): {type(e).__name__}: {e}")

        return []

    def get_concept_stocks_detail(self, concept: str) -> List[Dict]:
        """获取概念板块成分股详细信息（含名称、价格等）"""
        # 先尝试概念板块
        try:
            df = ak.stock_board_concept_cons_em(symbol=concept)
            if df is not None and not df.empty:
                return self._parse_board_stocks_df(df)
        except Exception as e:
            logger.warning(f"获取概念成分股详情失败(concept={concept}): {type(e).__name__}: {e}")

        # 概念失败，尝试行业板块
        try:
            df = ak.stock_board_industry_cons_em(symbol=concept)
            if df is not None and not df.empty:
                return self._parse_board_stocks_df(df)
        except Exception as e:
            logger.warning(f"获取行业成分股详情失败(concept={concept}): {type(e).__name__}: {e}")

        return []

    def _parse_board_stocks_df(self, df) -> List[Dict]:
        """解析板块成分股DataFrame为字典列表"""
        import math
        result = []
        for _, row in df.iterrows():
            price = row.get("最新价", 0)
            change = row.get("涨跌幅", 0)
            # 处理NaN值
            price = 0 if (price is None or (isinstance(price, float) and math.isnan(price))) else float(price)
            change = 0 if (change is None or (isinstance(change, float) and math.isnan(change))) else float(change)
            item = {
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "price": price,
                "change_percent": change,
                "main_net_inflow": 0,
                "main_net_inflow_percent": 0
            }
            result.append(item)
        return result

    @staticmethod
    def _a_share_market_tag(code: str) -> str:
        """6→sh；0/3→sz；4/8/92→bj（与 capital_flow_analyzer.a_share_market_tag 一致）。"""
        c = (code or '').strip().split('.')[0]
        if c.startswith('6'):
            return 'sh'
        if c.startswith(('0', '3')):
            return 'sz'
        if c.startswith(('4', '8', '92')):
            return 'bj'
        return 'sh'

    def get_capital_flow(self, code: str) -> Dict:
        """获取资金流向"""
        try:
            market = self._a_share_market_tag(str(code))
            df = ak.stock_individual_fund_flow(stock=code, market=market)
            if df is not None and not df.empty:
                return {'flow': df.to_dict('records')}
        except Exception as e:
            logger.warning(f"获取资金流向失败(code={code}): {type(e).__name__}: {e}")
        return {}

    def get_individual_fund_flow(self, code: str) -> pd.DataFrame:
        """J1 [NEW-FILE:#20260415-43] 个股资金流 alias — 转发真实接口。

        使用 akshare.stock_individual_fund_flow 返回原始 DataFrame
        (不转 dict, 保持 registry 统一返回类型)。
        """
        try:
            import akshare as ak
            market = self._a_share_market_tag(str(code))
            df = ak.stock_individual_fund_flow(stock=str(code), market=market)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.warning(f"[AkshareAdapter] get_individual_fund_flow({code}) 失败: {type(e).__name__}: {e}")
        return pd.DataFrame()

    def get_north_flow(self) -> pd.DataFrame:
        """获取北向资金（H3：优先「北向资金」；失败则沪+深合并；再备 summary）。"""
        try:
            df = ak.stock_hsgt_hist_em(symbol="北向资金")
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.warning(f"获取北向资金(北向资金)失败: {type(e).__name__}: {e}")
        # fallback: 沪股通 + 深股通
        frames = []
        for sym in ("沪股通", "深股通"):
            try:
                part = ak.stock_hsgt_hist_em(symbol=sym)
                if part is not None and not part.empty:
                    frames.append(part)
            except Exception as e:
                logger.warning(f"获取北向资金({sym})失败: {type(e).__name__}: {e}")
        if len(frames) == 1:
            return frames[0]
        if len(frames) == 2:
            try:
                date_cols = ['日期', '持股日期', '交易日期']
                num_candidates = ['当日成交净买额', '当日资金流入', '净买额', '净流入']
                df_a, df_b = frames[0], frames[1]
                dcol_a = next((c for c in date_cols if c in df_a.columns), df_a.columns[0])
                dcol_b = next((c for c in date_cols if c in df_b.columns), df_b.columns[0])
                ncol_a = next((c for c in num_candidates if c in df_a.columns), None)
                ncol_b = next((c for c in num_candidates if c in df_b.columns), None)
                if ncol_a and ncol_b:
                    a = df_a[[dcol_a, ncol_a]].rename(columns={dcol_a: '日期', ncol_a: 'net_a'})
                    b = df_b[[dcol_b, ncol_b]].rename(columns={dcol_b: '日期', ncol_b: 'net_b'})
                    a['日期'] = pd.to_datetime(a['日期'], errors='coerce')
                    b['日期'] = pd.to_datetime(b['日期'], errors='coerce')
                    merged = pd.merge(a, b, on='日期', how='outer')
                    merged['当日成交净买额'] = merged['net_a'].fillna(0) + merged['net_b'].fillna(0)
                    return merged[['日期', '当日成交净买额']].sort_values('日期', ascending=False)
                return df_a if len(df_a) >= len(df_b) else df_b
            except Exception as e:
                logger.warning(f"北向资金沪深合并失败: {type(e).__name__}: {e}")
                return frames[0]
        try:
            df = ak.stock_hsgt_fund_flow_summary_em()
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.warning(f"获取北向资金(summary)失败: {type(e).__name__}: {e}")
            return pd.DataFrame()

    def health_check(self) -> bool:
        """轻量探针：雪球单股快照 + 60s 缓存

        - 命中缓存：<1ms
        - 冷启动：~3.5s（雪球，独立于东财上游）
        - 与 ADAPTERS_STATUS_PER_CALL_TIMEOUT=5s 兼容
        """
        now = time.time()
        # S1-C5: 读缓存加锁，防止并发下双字段非原子读
        with _AKSHARE_HC_CACHE_LOCK:
            if _AKSHARE_HC_CACHE['ok'] is not None and (now - _AKSHARE_HC_CACHE['ts']) < _AKSHARE_HC_TTL:
                return _AKSHARE_HC_CACHE['ok']
        try:
            df = ak.stock_individual_spot_xq(symbol=_AKSHARE_HC_PROBE_SYMBOL)
            ok = df is not None and len(df) > 0
        except Exception as e:
            logger.warning(f"akshare健康检查失败: {type(e).__name__}: {e}")
            ok = False
        # S1-C5: 写缓存加锁，保证 ok 和 ts 同时更新的原子性
        with _AKSHARE_HC_CACHE_LOCK:
            _AKSHARE_HC_CACHE['ok'] = ok
            _AKSHARE_HC_CACHE['ts'] = now
        return ok
