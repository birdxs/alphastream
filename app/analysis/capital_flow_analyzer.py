# Input  : AkShare 资金流向 DataFrame 与股票代码/周期参数（含北向 hsgt）
# Output : 个股/板块资金流向结构化 dict/list，金额字段单位保持 yuan；北向 history
# Pos    : 金融数据单位契约边界，供 API 与前端图表消费；上游网络降级走受控 WARNING 日志
import logging
import re
import traceback
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

_ASIA_SHANGHAI = timezone(timedelta(hours=8))
now_cn = lambda: datetime.now(_ASIA_SHANGHAI)

# 市场级北向 symbol（非 6 位 A 股代码时走 hist 汇总）
_NORTH_MARKET_SYMBOLS = frozenset({
    '', '北向资金', '沪股通', '深股通', '南向资金', '港股通沪', '港股通深',
    'north', 'northbound', 'hsgt', 'HSGT',
})


def a_share_market_tag(stock_code: str) -> str:
    """A 股代码 → akshare market：sh / sz / bj。

    规则：6→sh；0/3→sz；4/8 及 92 开头（北交）→bj；其余默认 sh。
    """
    code = (stock_code or '').strip().split('.')[0]
    if not code:
        return 'sh'
    if code.startswith('6'):
        return 'sh'
    if code.startswith(('0', '3')):
        return 'sz'
    if code.startswith(('4', '8', '92')):
        return 'bj'
    return 'sh'


class CapitalFlowAnalyzer:
    def __init__(self):
        self.data_cache = {}

        # 设置日志记录
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        # 初始化统一数据层
        from app.core.data_provider import get_data_provider
        self.data_provider = get_data_provider()

    @staticmethod
    def market_tag_for_code(stock_code: str) -> str:
        """对外暴露的 market 映射（与 a_share_market_tag 一致）。"""
        return a_share_market_tag(stock_code)

    def _parse_ymd(self, value):
        """宽松解析 YYYYMMDD / YYYY-MM-DD / Timestamp → date 或 None。"""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if hasattr(value, 'date') and not isinstance(value, str):
            try:
                return value.date()
            except Exception:
                pass
        s = str(value).strip()
        if not s or s.lower() in ('nan', 'none', 'nat', '--'):
            return None
        s = s.replace('/', '-').replace('.', '-')
        digits = re.sub(r'\D', '', s)
        try:
            if len(digits) >= 8:
                return datetime.strptime(digits[:8], '%Y%m%d').date()
            if len(s) >= 10:
                return datetime.strptime(s[:10], '%Y-%m-%d').date()
        except ValueError:
            return None
        return None

    def _filter_history_by_dates(self, history, start_date=None, end_date=None):
        """客户端按日期过滤 history 列表。"""
        if not history:
            return history
        start_d = self._parse_ymd(start_date) if start_date else None
        end_d = self._parse_ymd(end_date) if end_date else None
        if start_d is None and end_d is None:
            return history
        out = []
        for item in history:
            d = self._parse_ymd(item.get('date'))
            if d is None:
                continue
            if start_d and d < start_d:
                continue
            if end_d and d > end_d:
                continue
            out.append(item)
        return out

    def _rows_from_hsgt_df(self, df):
        """将 hsgt hist/individual DataFrame 规范为 history 列表。"""
        if df is None or (hasattr(df, 'empty') and df.empty):
            return []
        date_cols = ['日期', '持股日期', '交易日期', 'date', 'Date']
        amount_cols = [
            '当日成交净买额', '当日资金流入', '北向资金净流入', '净买额',
            '净流入', '持股数量', '持股数量(股)', '今日持股股数',
            '持股市值', '今日持股市值',
        ]
        date_col = next((c for c in date_cols if c in df.columns), df.columns[0])
        amount_col = next((c for c in amount_cols if c in df.columns), None)
        if amount_col is None:
            for c in df.columns:
                if c == date_col:
                    continue
                if pd.api.types.is_numeric_dtype(df[c]):
                    amount_col = c
                    break
        history = []
        for _, row in df.iterrows():
            try:
                d_raw = row.get(date_col, '')
                d_parsed = self._parse_ymd(d_raw)
                date_str = d_parsed.isoformat() if d_parsed else str(d_raw)
                net_amount = None
                if amount_col is not None:
                    val = row.get(amount_col)
                    if val is not None and str(val) not in ('', 'nan', 'None', '--'):
                        try:
                            net_amount = float(val)
                        except (ValueError, TypeError):
                            net_amount = None
                item = {'date': date_str, 'net_amount': net_amount}
                for extra in ('持股数量', '持股市值', '持股数量占A股百分比', '当日收盘价', '当日涨跌幅'):
                    if extra in df.columns:
                        try:
                            v = row.get(extra)
                            if v is not None and str(v) not in ('', 'nan', 'None'):
                                item[extra] = (
                                    float(v)
                                    if isinstance(v, (int, float, np.floating, np.integer))
                                    else v
                                )
                        except Exception:
                            pass
                history.append(item)
            except Exception as e:
                self.logger.warning(f"north flow row parse skip: {e}")
                continue
        return history

    def _merge_hsgt_hist_sh_sz(self):
        """北向资金失败：沪股通+深股通按日期加总净额。"""
        frames = []
        for sym in ('沪股通', '深股通'):
            try:
                part = ak.stock_hsgt_hist_em(symbol=sym)
                if part is not None and not part.empty:
                    frames.append(part)
            except Exception as e:
                self.logger.warning(f"stock_hsgt_hist_em({sym}) fallback failed: {e}")
        if not frames:
            return None
        if len(frames) == 1:
            return frames[0]
        df_a, df_b = frames[0].copy(), frames[1].copy()
        date_cols = ['日期', '持股日期', '交易日期']
        dcol_a = next((c for c in date_cols if c in df_a.columns), df_a.columns[0])
        dcol_b = next((c for c in date_cols if c in df_b.columns), df_b.columns[0])
        num_candidates = ['当日成交净买额', '当日资金流入', '净买额', '净流入']
        ncol_a = next((c for c in num_candidates if c in df_a.columns), None)
        ncol_b = next((c for c in num_candidates if c in df_b.columns), None)
        if ncol_a is None or ncol_b is None:
            return df_a if len(df_a) >= len(df_b) else df_b
        a = df_a[[dcol_a, ncol_a]].rename(columns={dcol_a: '日期', ncol_a: 'net_a'})
        b = df_b[[dcol_b, ncol_b]].rename(columns={dcol_b: '日期', ncol_b: 'net_b'})
        a['日期'] = pd.to_datetime(a['日期'], errors='coerce')
        b['日期'] = pd.to_datetime(b['日期'], errors='coerce')
        merged = pd.merge(a, b, on='日期', how='outer')
        merged['当日成交净买额'] = merged['net_a'].fillna(0) + merged['net_b'].fillna(0)
        return merged[['日期', '当日成交净买额']].sort_values('日期', ascending=False)

    def get_north_flow_history(self, stock_code, start_date=None, end_date=None):
        """北向资金历史（C1/C2/H3 契约）。

        - 空代码/市场标识：stock_hsgt_hist_em(symbol="北向资金")，无 start/end kwargs
        - 6 位 A 股：优先 stock_hsgt_individual_detail_em(start/end)；失败退 individual_em
        - 严禁 stock_hsgt_hist_em(股票代码)
        - 失败返回 {'history': []}，不抛未捕获异常
        """
        code = (stock_code or '').strip()
        pure = code.split('.')[0] if code else ''
        try:
            is_market = (not pure) or pure in _NORTH_MARKET_SYMBOLS or not re.fullmatch(r'\d{6}', pure)

            if is_market:
                symbol = pure if pure in _NORTH_MARKET_SYMBOLS and pure not in (
                    '', 'north', 'northbound', 'hsgt', 'HSGT'
                ) else '北向资金'
                if symbol in ('', 'north', 'northbound', 'hsgt', 'HSGT'):
                    symbol = '北向资金'
                self.logger.info(f"north flow market hist symbol={symbol}")
                df = None
                try:
                    df = ak.stock_hsgt_hist_em(symbol=symbol)
                except Exception as e1:
                    self.logger.warning(f"stock_hsgt_hist_em({symbol}) failed: {e1}")
                if df is None or (hasattr(df, 'empty') and df.empty):
                    if symbol == '北向资金':
                        df = self._merge_hsgt_hist_sh_sz()
                if df is None or (hasattr(df, 'empty') and df.empty):
                    try:
                        # 第三备：summary（无参）
                        df = ak.stock_hsgt_fund_flow_summary_em()
                    except Exception as e3:
                        self.logger.warning(f"stock_hsgt_fund_flow_summary_em failed: {e3}")
                history = self._rows_from_hsgt_df(df)
            else:
                self.logger.info(f"north flow individual symbol={pure}")
                df = None
                # 默认日期：近 1 年（detail API 需要 YYYYMMDD）
                sd = start_date or (now_cn() - timedelta(days=365)).strftime('%Y%m%d')
                ed = end_date or now_cn().strftime('%Y%m%d')
                # 规范化为 YYYYMMDD
                sd_d = self._parse_ymd(sd)
                ed_d = self._parse_ymd(ed)
                sd_s = sd_d.strftime('%Y%m%d') if sd_d else str(re.sub(r'\D', '', str(sd)))[:8]
                ed_s = ed_d.strftime('%Y%m%d') if ed_d else str(re.sub(r'\D', '', str(ed)))[:8]
                try:
                    df = ak.stock_hsgt_individual_detail_em(
                        symbol=pure, start_date=sd_s, end_date=ed_s
                    )
                except Exception as e:
                    self.logger.warning(
                        f"stock_hsgt_individual_detail_em({pure}) failed: {e}; fallback individual_em"
                    )
                    try:
                        df = ak.stock_hsgt_individual_em(symbol=pure)
                    except Exception as e2:
                        self.logger.warning(f"stock_hsgt_individual_em({pure}) failed: {e2}")
                        return {'history': [], 'source': 'degraded', 'error': str(e2)}
                history = self._rows_from_hsgt_df(df)

            history = self._filter_history_by_dates(history, start_date, end_date)
            return {'history': history, 'stock_code': pure or code, 'source': 'akshare'}
        except Exception as e:
            self._log_upstream_failure(f"north_flow_history code={stock_code}", e)
            return {'history': [], 'source': 'degraded', 'error': str(e)}

    def _log_upstream_failure(self, context, exc):
        """统一记录上游数据源失败日志。

        预期的网络层降级（Eastmoney ProxyError / RemoteDisconnected /
        ConnectionError / Timeout 等）属于受控降级，仅以 WARNING 级输出精简
        消息，不打印完整 Traceback，避免污染日志；非网络类异常仍按 ERROR 级
        输出完整堆栈，便于排查真实 bug。
        """
        is_network = self._is_upstream_network_error(exc)

        if is_network:
            self.logger.warning(
                f"资金流上游降级: {context} <{type(exc).__name__}: {str(exc)[:120]}>"
            )
        else:
            self.logger.error(f"Error {context}: {str(exc)}")
            self.logger.error(traceback.format_exc())

    @staticmethod
    def _is_upstream_network_error(exc):
        """判定异常是否为上游网络层降级（受控、可预期）。

        以 isinstance 为主（覆盖 requests.ProxyError 等子类），辅以
        network_resilience 的名称/关键字分类作为兜底。
        """
        network_types = []
        try:
            import requests.exceptions as _req_exc
            network_types.extend([
                _req_exc.ConnectionError,   # 含 ProxyError 子类
                _req_exc.Timeout,
                _req_exc.SSLError,
                _req_exc.ChunkedEncodingError,
            ])
        except Exception:
            pass
        try:
            import http.client as _http_client
            network_types.append(_http_client.RemoteDisconnected)
        except Exception:
            pass
        try:
            import urllib3.exceptions as _u3_exc
            network_types.extend([_u3_exc.ProtocolError, _u3_exc.NewConnectionError])
        except Exception:
            pass
        network_types.extend([
            ConnectionError, ConnectionResetError,
            ConnectionAbortedError, ConnectionRefusedError, TimeoutError,
        ])
        if network_types and isinstance(exc, tuple(network_types)):
            return True
        # 兜底：复用 network_resilience 的名称/关键字分类
        try:
            from app.core.network_resilience import _is_retryable_exception
            return _is_retryable_exception(exc)
        except Exception:
            return False

    def get_concept_fund_flow(self, period="10日排行"):
        """获取概念/行业资金流向数据"""
        try:
            self.logger.info(f"Getting concept fund flow for period: {period}")

            # 检查缓存
            cache_key = f"concept_fund_flow_{period}"
            if cache_key in self.data_cache:
                cache_time, cached_data = self.data_cache[cache_key]
                # 如果在最近一小时内有缓存数据，则返回缓存数据
                if (now_cn() - cache_time).total_seconds() < 3600:
                    return cached_data

            # 从akshare获取数据
            concept_data = ak.stock_fund_flow_concept(symbol=period)

            # 处理数据
            result = []
            for _, row in concept_data.iterrows():
                try:
                    # 列名可能有所不同，所以我们使用灵活的方法
                    item = {
                        "rank": int(row.get("序号", 0)),
                        "sector": row.get("行业", ""),
                        "company_count": int(row.get("公司家数", 0)),
                        "sector_index": float(row.get("行业指数", 0)),
                        "change_percent": self._parse_percent(row.get("阶段涨跌幅", "0%")),
                        "inflow": float(row.get("流入资金", 0)),
                        "outflow": float(row.get("流出资金", 0)),
                        "net_flow": float(row.get("净额", 0))
                    }
                    result.append(item)
                except Exception as e:
                    # self.logger.warning(f"Error processing row in concept fund flow: {str(e)}")
                    continue

            # 缓存结果
            self.data_cache[cache_key] = (now_cn(), result)

            return result
        except Exception as e:
            self._log_upstream_failure("getting concept fund flow", e)
            return {'data': [], 'source': 'degraded', 'reason': str(e)}

    def get_individual_fund_flow_rank(self, period="10日"):
        """获取个股资金流向排名。

        返回统一结构（H2-4 修复）：
            {'data': list[dict], 'error': str | None, 'count': int, 'amount_unit': 'yuan'}
        调用方通过 result['error'] is not None 判断失败，通过 result['data'] 取列表。
        AkShare 净额字段单位为元，后端保持原始数值不缩放。
        """
        try:
            self.logger.info(f"Getting individual fund flow ranking for period: {period}")

            # 检查缓存
            cache_key = f"individual_fund_flow_rank_{period}"
            if cache_key in self.data_cache:
                cache_time, cached_data = self.data_cache[cache_key]
                # 如果在最近一小时内有缓存数据，则返回缓存数据
                if (now_cn() - cache_time).total_seconds() < 3600:
                    return cached_data

            # 从akshare获取数据
            stock_data = ak.stock_individual_fund_flow_rank(indicator=period)

            # 处理数据
            items = []
            for _, row in stock_data.iterrows():
                try:
                    # 根据不同时间段设置列名前缀
                    period_prefix = "" if period == "今日" else f"{period}"

                    item = {
                        "rank": int(row.get("序号", 0)),
                        "code": row.get("代码", ""),
                        "name": row.get("名称", ""),
                        "price": float(row.get("最新价", 0)),
                        "change_percent": float(row.get(f"{period_prefix}涨跌幅", 0)),
                        "main_net_inflow": float(row.get(f"{period_prefix}主力净流入-净额", 0)),
                        "main_net_inflow_percent": float(row.get(f"{period_prefix}主力净流入-净占比", 0)),
                        "super_large_net_inflow": float(row.get(f"{period_prefix}超大单净流入-净额", 0)),
                        "super_large_net_inflow_percent": float(row.get(f"{period_prefix}超大单净流入-净占比", 0)),
                        "large_net_inflow": float(row.get(f"{period_prefix}大单净流入-净额", 0)),
                        "large_net_inflow_percent": float(row.get(f"{period_prefix}大单净流入-净占比", 0)),
                        "medium_net_inflow": float(row.get(f"{period_prefix}中单净流入-净额", 0)),
                        "medium_net_inflow_percent": float(row.get(f"{period_prefix}中单净流入-净占比", 0)),
                        "small_net_inflow": float(row.get(f"{period_prefix}小单净流入-净额", 0)),
                        "small_net_inflow_percent": float(row.get(f"{period_prefix}小单净流入-净占比", 0))
                    }
                    items.append(item)
                except Exception as e:
                    self.logger.warning(f"Error processing row in individual fund flow rank: {str(e)}")
                    continue

            result = {'data': items, 'error': None, 'count': len(items), 'amount_unit': 'yuan'}
            # 缓存结果
            self.data_cache[cache_key] = (now_cn(), result)

            return result
        except Exception as e:
            self._log_upstream_failure("getting individual fund flow ranking", e)
            return {'data': [], 'error': str(e), 'count': 0, 'amount_unit': 'yuan'}

    def get_individual_fund_flow(self, stock_code, market_type="", re_date="10日"):
        """获取个股资金流向数据"""
        try:
            self.logger.info(f"Getting fund flow for stock: {stock_code}, market: {market_type}")

            # [I2-2026-04-15] 美股/港股短路: akshare stock_individual_fund_flow 仅支持A股,
            # 对美股symbol(如AAPL)会返回None或抛异常, 导致下游 None.iterrows() NoneType.
            # 非A股直接返回mock, 避免触底爬网.
            if market_type in ('US', 'us', 'HK', 'hk'):
                self.logger.info(f"非A股市场 {market_type}, 资金流向接口不支持, 返回空数据")
                return {'data': [], 'source': 'unsupported', 'reason': 'market_type not supported', 'amount_unit': 'yuan'}

            # 转换 market 为 akshare 期望的 sh/sz/bj（H2：4/8/92→bj）
            if market_type in ('A', 'a', None, '', 'SH', 'SZ', 'BJ'):
                if market_type in ('SH',):
                    market_type = 'sh'
                elif market_type in ('SZ',):
                    market_type = 'sz'
                elif market_type in ('BJ',):
                    market_type = 'bj'
                else:
                    market_type = a_share_market_tag(stock_code)
            elif market_type not in ('sh', 'sz', 'bj'):
                market_type = a_share_market_tag(stock_code)

            # 检查缓存
            cache_key = f"individual_fund_flow_{stock_code}_{market_type}"
            if cache_key in self.data_cache:
                cache_time, cached_data = self.data_cache[cache_key]
                # 如果在一小时内有缓存数据，则返回缓存数据
                if (now_cn() - cache_time).total_seconds() < 3600:
                    return cached_data

            # 从akshare获取数据
            flow_data = ak.stock_individual_fund_flow(stock=stock_code, market=market_type)

            # [I2-2026-04-15] None/空 guard: 某些股票/市场组合akshare会返回None而非抛异常
            if flow_data is None or (hasattr(flow_data, 'empty') and flow_data.empty):
                self.logger.warning(f"akshare 返回空数据 stock={stock_code} market={market_type}, 降级为空数据")
                return {'data': [], 'source': 'degraded', 'reason': 'akshare_empty', 'amount_unit': 'yuan'}

            # 处理数据
            result = {
                "stock_code": stock_code,
                "amount_unit": "yuan",
                "data": []
            }

            for _, row in flow_data.iterrows():
                try:
                    item = {
                        "date": row.get("日期", ""),
                        "price": float(row.get("收盘价", 0)),
                        "change_percent": float(row.get("涨跌幅", 0)),
                        "main_net_inflow": float(row.get("主力净流入-净额", 0)),
                        "main_net_inflow_percent": float(row.get("主力净流入-净占比", 0)),
                        "super_large_net_inflow": float(row.get("超大单净流入-净额", 0)),
                        "super_large_net_inflow_percent": float(row.get("超大单净流入-净占比", 0)),
                        "large_net_inflow": float(row.get("大单净流入-净额", 0)),
                        "large_net_inflow_percent": float(row.get("大单净流入-净占比", 0)),
                        "medium_net_inflow": float(row.get("中单净流入-净额", 0)),
                        "medium_net_inflow_percent": float(row.get("中单净流入-净占比", 0)),
                        "small_net_inflow": float(row.get("小单净流入-净额", 0)),
                        "small_net_inflow_percent": float(row.get("小单净流入-净占比", 0))
                    }
                    result["data"].append(item)
                except Exception as e:
                    self.logger.warning(f"Error processing row in individual fund flow: {str(e)}")
                    continue

            # 计算汇总统计数据
            if result["data"]:
                # 最近数据 (最近10天)
                recent_data = result["data"][:min(10, len(result["data"]))]

                result["summary"] = {
                    "recent_days": len(recent_data),
                    "total_main_net_inflow": sum(item["main_net_inflow"] for item in recent_data),
                    "avg_main_net_inflow_percent": np.mean(
                        [item["main_net_inflow_percent"] for item in recent_data]),
                    "positive_days": sum(1 for item in recent_data if item["main_net_inflow"] > 0),
                    "negative_days": sum(1 for item in recent_data if item["main_net_inflow"] <= 0),
                    "amount_unit": "yuan"
                }

            # Cache the result
            self.data_cache[cache_key] = (now_cn(), result)

            return result
        except Exception as e:
            self._log_upstream_failure("getting individual fund flow", e)
            return {'data': [], 'source': 'degraded', 'reason': str(e), 'amount_unit': 'yuan'}

    def get_sector_stocks(self, sector):
        """获取特定行业的股票"""
        try:
            self.logger.info(f"Getting stocks for sector: {sector}")

            # 检查缓存
            cache_key = f"sector_stocks_{sector}"
            if cache_key in self.data_cache:
                cache_time, cached_data = self.data_cache[cache_key]
                # 如果在一小时内有缓存数据，则返回缓存数据
                if (now_cn() - cache_time).total_seconds() < 3600:
                    return cached_data

            # 使用DataProvider获取概念/行业成分股详细信息
            result = self.data_provider.get_concept_stocks_detail(sector)
            if result:
                self.data_cache[cache_key] = (now_cn(), result)
            return result  # 没数据就返回空，不用mock

        except Exception as e:
            self.logger.error(f"Error getting sector stocks: {str(e)}")
            return []  # 出错返回空数组，不用mock

    def calculate_capital_flow_score(self, stock_code, market_type=""):
        """计算股票资金流向评分"""
        try:
            self.logger.info(f"Calculating capital flow score for stock: {stock_code}")

            # 获取个股资金流向数据
            fund_flow = self.get_individual_fund_flow(stock_code, market_type)

            if not fund_flow or not fund_flow.get("data") or not fund_flow.get("summary"):
                return {
                    "total": 0,
                    "main_force": 0,
                    "large_order": 0,
                    "small_order": 0,
                    "details": {}
                }

            # Extract summary statistics
            summary = fund_flow["summary"]
            recent_days = summary["recent_days"]
            total_main_net_inflow = summary["total_main_net_inflow"]
            avg_main_net_inflow_percent = summary["avg_main_net_inflow_percent"]
            positive_days = summary["positive_days"]

            # Calculate main force score (0-40)
            main_force_score = 0

            # 基于净流入百分比的评分
            if avg_main_net_inflow_percent > 3:
                main_force_score += 20
            elif avg_main_net_inflow_percent > 1:
                main_force_score += 15
            elif avg_main_net_inflow_percent > 0:
                main_force_score += 10

            # 基于上涨天数的评分
            positive_ratio = positive_days / recent_days if recent_days > 0 else 0
            if positive_ratio > 0.7:
                main_force_score += 20
            elif positive_ratio > 0.5:
                main_force_score += 15
            elif positive_ratio > 0.3:
                main_force_score += 10

            # 计算大单评分（0-30分）
            large_order_score = 0

            # 分析超大单和大单交易
            recent_super_large = [item["super_large_net_inflow"] for item in
                                   fund_flow["data"][:recent_days]]
            recent_large = [item["large_net_inflow"] for item in fund_flow["data"][:recent_days]]

            super_large_positive = sum(1 for x in recent_super_large if x > 0)
            large_positive = sum(1 for x in recent_large if x > 0)

            # 基于超大单的评分
            super_large_ratio = super_large_positive / recent_days if recent_days > 0 else 0
            if super_large_ratio > 0.7:
                large_order_score += 15
            elif super_large_ratio > 0.5:
                large_order_score += 10
            elif super_large_ratio > 0.3:
                large_order_score += 5

            # 基于大单的评分
            large_ratio = large_positive / recent_days if recent_days > 0 else 0
            if large_ratio > 0.7:
                large_order_score += 15
            elif large_ratio > 0.5:
                large_order_score += 10
            elif large_ratio > 0.3:
                large_order_score += 5

            # 计算小单评分（0-30分）
            small_order_score = 0

            # 分析中单和小单交易
            recent_medium = [item["medium_net_inflow"] for item in fund_flow["data"][:recent_days]]
            recent_small = [item["small_net_inflow"] for item in fund_flow["data"][:recent_days]]

            medium_positive = sum(1 for x in recent_medium if x > 0)
            small_positive = sum(1 for x in recent_small if x > 0)

            # 基于中单的评分
            medium_ratio = medium_positive / recent_days if recent_days > 0 else 0
            if medium_ratio > 0.7:
                small_order_score += 15
            elif medium_ratio > 0.5:
                small_order_score += 10
            elif medium_ratio > 0.3:
                small_order_score += 5

            # 基于小单的评分
            small_ratio = small_positive / recent_days if recent_days > 0 else 0
            if small_ratio > 0.7:
                small_order_score += 15
            elif small_ratio > 0.5:
                small_order_score += 10
            elif small_ratio > 0.3:
                small_order_score += 5

            # 计算总评分
            total_score = main_force_score + large_order_score + small_order_score

            return {
                "total": total_score,
                "main_force": main_force_score,
                "large_order": large_order_score,
                "small_order": small_order_score,
                "details": fund_flow
            }
        except Exception as e:
            self.logger.error(f"Error calculating capital flow score: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {
                "total": 0,
                "main_force": 0,
                "large_order": 0,
                "small_order": 0,
                "details": {},
                "error": str(e)
            }

    def _parse_percent(self, percent_str):
        """将百分比字符串转换为浮点数"""
        try:
            if isinstance(percent_str, str) and '%' in percent_str:
                return float(percent_str.replace('%', ''))
            return float(percent_str)
        except (ValueError, TypeError):
            return 0.0

