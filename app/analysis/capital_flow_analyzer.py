# Input  : AkShare 资金流向 DataFrame 与股票代码/周期参数
# Output : 个股/板块资金流向结构化 dict/list，金额字段单位保持 yuan
# Pos    : 金融数据单位契约边界，供 API 与前端图表消费
import logging
import traceback
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

_ASIA_SHANGHAI = timezone(timedelta(hours=8))
now_cn = lambda: datetime.now(_ASIA_SHANGHAI)


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
            self.logger.error(f"Error getting concept fund flow: {str(e)}")
            self.logger.error(traceback.format_exc())
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
            self.logger.error(f"Error getting individual fund flow ranking: {str(e)}")
            self.logger.error(traceback.format_exc())
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

            # 转换market参数为akshare期望的 'sh'/'sz' 格式
            # 'A'/'a'/None/空字符串 均需根据股票代码自动判断
            if market_type in ('A', 'a', None, ''):
                if stock_code.startswith('6'):
                    market_type = "sh"
                elif stock_code.startswith('0') or stock_code.startswith('3'):
                    market_type = "sz"
                else:
                    market_type = "sh"  # 默认上海

            # 检查缓存
            cache_key = f"individual_fund_flow_{stock_code}_{market_type}"
            if cache_key in self.data_cache:
                cache_time, cached_data = self.data_cache[cache_key]
                # 如果在一小时内有缓存数据，则返回缓存数据
                if (now_cn() - cache_time).total_seconds() < 3600:
                    return cached_data

            # 以下分支已被上面的统一转换覆盖，保留作为防御性兜底
            if not market_type:
                if stock_code.startswith('6'):
                    market_type = "sh"
                elif stock_code.startswith('0') or stock_code.startswith('3'):
                    market_type = "sz"
                else:
                    market_type = "sh"  # Default to Shanghai

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
            self.logger.error(f"Error getting individual fund flow: {str(e)}")
            self.logger.error(traceback.format_exc())
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

