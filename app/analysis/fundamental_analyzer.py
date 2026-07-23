# -*- coding: utf-8 -*-
# Input  : AkShare 财务摘要数据 / DataProvider 财务指标
# Output : 基本面指标、成长性 CAGR 与综合评分
# Pos    : app/analysis/fundamental_analyzer.py 金融正确性敏感分析模块
"""
智能分析系统（股票） - 股票市场数据分析系统
开发者：熊猫大侠
版本：v2.1.0
许可证：MIT License
"""
# fundamental_analyzer.py
import re
import akshare as ak
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class FundamentalAnalyzer:
    def __init__(self):
        """初始化基础分析类"""
        self.data_cache = {}
        # 初始化统一数据层
        from app.core.data_provider import get_data_provider
        self.data_provider = get_data_provider()

    def _safe_get_column(self, df, col_options, row_idx=0, default=None):
        """安全获取DataFrame列值，支持多个候选列名。
        默认返回 None（铁律 #1：财务指标缺失时不应以 0 充当真实值）。
        """
        if df is None or df.empty:
            return default
        for col in col_options if isinstance(col_options, list) else [col_options]:
            if col in df.columns:
                try:
                    val = df[col].iloc[row_idx]
                    if val is None or str(val) == '' or (isinstance(val, float) and pd.isna(val)):
                        return default
                    fval = float(val)
                    return default if pd.isna(fval) else fval
                except (IndexError, ValueError, TypeError):
                    continue
        return default

    def get_financial_indicators(self, stock_code, progress_callback=None):
        """获取财务指标数据 - 使用DataProvider统一数据层"""
        if progress_callback:
            progress_callback(5, "正在获取财务指标...")
        try:
            # 使用DataProvider获取财务数据（自动故障转移）
            fin_result = self.data_provider.get_financial_data(stock_code)
            financial_data = fin_result.get('indicator', [])
            if isinstance(financial_data, list) and len(financial_data) > 0:
                financial_data = pd.DataFrame(financial_data)
            else:
                financial_data = pd.DataFrame()

            # 获取最新估值指标（暂保留akshare直接调用，DataProvider暂不支持）
            valuation = None
            try:
                valuation = ak.stock_value_em(symbol=stock_code)
            except Exception as e:
                logger.warning(f"获取估值指标失败: {e}")

            # 整合数据（使用安全列名访问）
            # H3-1 修复：各字段候选列名严格按语义边界定义，禁止交叉污染。
            # H3-2 修复：default=None（铁律 #1），缺失 / NaN → None，前端显示 "—"。
            indicators = {
                # 估值指标 —— 来自 akshare stock_value_em
                'pe_ttm': self._safe_get_column(valuation, ['PE(TTM)', 'PE-TTM', 'pe_ttm']),
                'pb': self._safe_get_column(valuation, ['市净率', 'PB', 'pb']),
                'ps_ttm': self._safe_get_column(valuation, ['市销率', 'PS(TTM)', 'ps_ttm']),
                # ROE（净资产收益率）—— 仅包含 ROE 相关列名，不得混入净利率列
                'roe': self._safe_get_column(financial_data, ['加权净资产收益率(%)', '加权ROE(%)', 'ROE(%)', 'ROE', 'roe']),
                # 毛利率 —— 仅包含毛利率/销售毛利率列名
                'gross_margin': self._safe_get_column(financial_data, ['销售毛利率(%)', '毛利率(%)', 'gross_margin']),
                # H3-1 核心修复：净利率候选列名中移除 ROE 列（'净资产收益率(%)' 是 ROE，不是净利率）
                'net_profit_margin': self._safe_get_column(financial_data, ['销售净利率(%)', '净利润率(%)', '总资产净利润率(%)', 'net_profit_margin']),
                # 负债率 —— 仅包含负债/资产负债率列名
                'debt_ratio': self._safe_get_column(financial_data, ['资产负债率(%)', '负债率(%)', 'debt_ratio']),
            }
            if progress_callback:
                progress_callback(10, "财务指标获取成功")
            return indicators
        except Exception as e:
            print(f"获取财务指标出错: {str(e)}")
            if progress_callback:
                progress_callback(10, f"财务指标获取失败: {e}")
            return {}

    def _is_long_form_financial(self, df):
        """stock_financial_abstract 长表：含「指标」列 + 多个报告期列。"""
        if df is None or getattr(df, 'empty', True):
            return False
        cols = [str(c) for c in df.columns]
        return '指标' in cols and sum(
            1 for c in cols if re.fullmatch(r'\d{4}[-/]?\d{0,2}[-/]?\d{0,2}', str(c).strip())
            or re.fullmatch(r'\d{8}', str(c).strip())
            or re.fullmatch(r'\d{4}年', str(c).strip())
            or re.search(r'20\d{2}', str(c))
        ) >= 2 or (
            '指标' in cols and len(cols) > 3
        )

    def _series_from_long_form(self, df, indicator_keywords):
        """从 long-form 按「指标」行筛关键字，报告期列 → 降序 Series(index=日期)。"""
        if df is None or df.empty or '指标' not in df.columns:
            return None
        # 排除元数据列
        meta = {'选项', '指标', '选项名', '指标名称'}
        period_cols = [c for c in df.columns if str(c) not in meta]
        if not period_cols:
            return None
        # 匹配指标行
        ind = df['指标'].astype(str)
        mask = pd.Series(False, index=df.index)
        for kw in indicator_keywords:
            mask = mask | ind.str.contains(kw, na=False, regex=False)
        rows = df.loc[mask]
        if rows.empty:
            return None
        # 优先精确/更短匹配（营业收入 优于 营业总收入同比增长）
        def _score(name):
            name = str(name)
            # 排除含「同比」「环比」「增长」等比率行，只要绝对额
            if any(x in name for x in ('同比', '环比', '增长率', '增速')):
                return -1
            for i, kw in enumerate(indicator_keywords):
                if kw == name:
                    return 100 - i
                if kw in name:
                    return 50 - i
            return 0
        rows = rows.copy()
        rows['_score'] = rows['指标'].map(_score)
        rows = rows[rows['_score'] > 0]
        if rows.empty:
            return None
        best = rows.sort_values('_score', ascending=False).iloc[0]
        values = []
        dates = []
        for c in period_cols:
            raw = best.get(c)
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                continue
            s = str(raw).strip().replace(',', '').replace('%', '')
            if not s or s in ('--', 'None', 'nan', '-'):
                continue
            try:
                val = float(s)
            except (ValueError, TypeError):
                continue
            # 解析列名为日期
            cs = str(c).strip()
            dt = pd.to_datetime(cs, errors='coerce')
            if pd.isna(dt):
                digits = re.sub(r'\D', '', cs)
                if len(digits) >= 8:
                    dt = pd.to_datetime(digits[:8], format='%Y%m%d', errors='coerce')
                elif len(digits) >= 4:
                    dt = pd.to_datetime(digits[:4] + '1231', format='%Y%m%d', errors='coerce')
            if pd.isna(dt):
                continue
            dates.append(dt)
            values.append(val)
        if len(values) < 2:
            return None
        series = pd.Series(values, index=pd.DatetimeIndex(dates))
        series = series.sort_index(ascending=False)  # 最新在前
        return series

    def _series_from_wide_form(self, df, col_candidates):
        """宽表：列为指标名，行为报告期。"""
        col = None
        for c in col_candidates:
            if c in df.columns:
                col = c
                break
        if col is None:
            return None
        # 若有日期列，用其作 index
        date_col = next((c for c in ('报告期', '截止日期', '日期', '报告日期') if c in df.columns), None)
        s = pd.to_numeric(df[col], errors='coerce')
        if date_col:
            idx = pd.to_datetime(df[date_col], errors='coerce')
            s = pd.Series(s.values, index=idx)
            s = s[s.index.notna()].sort_index(ascending=False)
        return s.dropna()

    def _series_from_ths_or_indicator(self, stock_code):
        """备用链：stock_financial_abstract_ths / stock_financial_analysis_indicator。

        注意：sina stock_financial_abstract 对深市 paperCode 写死 sh，深市勿仅依赖该源。
        """
        code = (stock_code or '').strip().split('.')[0]
        # 1) ths
        try:
            ths = ak.stock_financial_abstract_ths(symbol=code)
            if ths is not None and not ths.empty:
                # ths 通常为宽表，列含 营业总收入 / 净利润 等
                rev = self._series_from_wide_form(
                    ths, ['营业总收入', '营业收入', 'total_revenue']
                )
                prof = self._series_from_wide_form(
                    ths,
                    ['归属母公司股东的净利润', '净利润', 'net_profit', '归母净利润'],
                )
                if rev is not None or prof is not None:
                    return rev, prof
        except Exception as e:
            logger.warning(f"stock_financial_abstract_ths({code}) 失败: {e}")
        # 2) analysis_indicator
        try:
            start_year = str(int(pd.Timestamp.now().year) - 6)
            ind = ak.stock_financial_analysis_indicator(symbol=code, start_year=start_year)
            if ind is not None and not ind.empty:
                # 指标表常有 日期 + 主营业务收入 / 净利润
                rev = self._series_from_wide_form(
                    ind, ['主营业务收入', '营业总收入', '营业收入']
                )
                prof = self._series_from_wide_form(
                    ind, ['净利润', '归属母公司股东的净利润']
                )
                if rev is not None or prof is not None:
                    return rev, prof
        except Exception as e:
            logger.warning(f"stock_financial_analysis_indicator({code}) 失败: {e}")
        return None, None

    def get_growth_data(self, stock_code, progress_callback=None):
        """获取成长性数据（C3：long-form 按指标行；失败备 ths/indicator；禁止 0 假 CAGR）。"""
        if progress_callback:
            progress_callback(15, "正在获取成长性数据...")
        try:
            revenue = None
            net_profit = None
            financial_data = None

            # 主路径：sina abstract（深市可能不可靠，失败走备用）
            try:
                financial_data = ak.stock_financial_abstract(symbol=stock_code)
            except Exception as e:
                logger.warning(f"获取财务摘要数据失败: {e}")

            if financial_data is not None and not financial_data.empty:
                # 标准化报告期顺序（宽表）
                for date_col in ['报告期', '截止日期', '日期', '报告日期']:
                    if date_col in financial_data.columns:
                        parsed_dates = pd.to_datetime(financial_data[date_col], errors='coerce')
                        if parsed_dates.notna().any():
                            financial_data = (
                                financial_data.assign(_parsed_report_date=parsed_dates)
                                .sort_values('_parsed_report_date', ascending=False, kind='mergesort')
                                .drop(columns=['_parsed_report_date'])
                                .reset_index(drop=True)
                            )
                        break

                if self._is_long_form_financial(financial_data):
                    revenue = self._series_from_long_form(
                        financial_data, ['营业总收入', '营业收入']
                    )
                    net_profit = self._series_from_long_form(
                        financial_data, ['归属母公司股东的净利润', '归母净利润', '净利润']
                    )
                else:
                    revenue = self._series_from_wide_form(
                        financial_data, ['营业总收入', '营业收入']
                    )
                    net_profit = self._series_from_wide_form(
                        financial_data, ['归属母公司股东的净利润', '净利润']
                    )

            # 备用链：主源失败或抽不出序列
            if revenue is None and net_profit is None:
                logger.warning(
                    f"股票 {stock_code} 主财务摘要无法解析成长序列，尝试 ths/indicator 备用链"
                )
                revenue, net_profit = self._series_from_ths_or_indicator(stock_code)

            growth = {}
            if revenue is not None and len(revenue.dropna()) >= 2:
                growth['revenue_growth_3y'] = self._calculate_cagr(revenue, 3)
                growth['revenue_growth_5y'] = self._calculate_cagr(revenue, 5)
            else:
                logger.warning(f"股票 {stock_code} 未找到可用营收序列（不填 0）")

            if net_profit is not None and len(net_profit.dropna()) >= 2:
                growth['profit_growth_3y'] = self._calculate_cagr(net_profit, 3)
                growth['profit_growth_5y'] = self._calculate_cagr(net_profit, 5)
            else:
                logger.warning(f"股票 {stock_code} 未找到可用净利润序列（不填 0）")

            if progress_callback:
                msg = "成长性数据获取成功" if growth else "成长性数据为空"
                progress_callback(20, msg)
            return growth
        except Exception as e:
            logger.warning(f"获取成长数据出错: {str(e)}")
            if progress_callback:
                progress_callback(20, f"成长性数据获取失败: {e}")
            return {}

    def _calculate_cagr(self, series, years):
        """计算复合年增长率。失败返回 None（铁律 #1：禁止 0 伪装增长率）。"""
        try:
            is_plain_range = isinstance(series.index, pd.RangeIndex)
            series = series.dropna()
            if len(series) < years:
                return None

            if not is_plain_range:
                parsed_index = pd.to_datetime(series.index, errors='coerce')
                if parsed_index.notna().any():
                    series = series.iloc[parsed_index.argsort()[::-1]]

            latest = float(series.iloc[0])
            earlier = float(series.iloc[min(years, len(series) - 1)])

            if earlier <= 0 or latest <= 0:
                return None

            return ((latest / earlier) ** (1 / years) - 1) * 100
        except (IndexError, ValueError, TypeError, ZeroDivisionError) as e:
            logger.warning(f"计算CAGR失败: {e}")
            return None

    def calculate_fundamental_score(self, stock_code, progress_callback=None):
        """计算基本面综合评分"""
        if progress_callback:
            progress_callback(0, "启动基本面分析模块...")

        try:
            indicators = self.get_financial_indicators(stock_code, progress_callback=progress_callback)
        except Exception as e:
            logger.error(f"获取财务指标异常: {e}")
            indicators = {}

        try:
            growth = self.get_growth_data(stock_code, progress_callback=progress_callback)
        except Exception as e:
            logger.error(f"获取成长数据异常: {e}")
            growth = {}

        if progress_callback:
            progress_callback(25, "计算基本面综合评分...")

        # 估值评分 (30分)
        valuation_score = 0
        if 'pe_ttm' in indicators and indicators['pe_ttm'] > 0:
            pe = indicators['pe_ttm']
            if pe < 15:
                valuation_score += 25
            elif pe < 25:
                valuation_score += 20
            elif pe < 35:
                valuation_score += 15
            elif pe < 50:
                valuation_score += 10
            else:
                valuation_score += 5

        # 财务健康评分 (40分)
        financial_score = 0
        if 'roe' in indicators:
            roe = indicators['roe']
            if roe > 20:
                financial_score += 15
            elif roe > 15:
                financial_score += 12
            elif roe > 10:
                financial_score += 8
            elif roe > 5:
                financial_score += 4

        if 'debt_ratio' in indicators:
            debt_ratio = indicators['debt_ratio']
            if debt_ratio < 30:
                financial_score += 15
            elif debt_ratio < 50:
                financial_score += 10
            elif debt_ratio < 70:
                financial_score += 5

        # 成长性评分 (30分)
        growth_score = 0
        if 'revenue_growth_3y' in growth and growth['revenue_growth_3y']:
            rev_growth = growth['revenue_growth_3y']
            if rev_growth > 30:
                growth_score += 15
            elif rev_growth > 20:
                growth_score += 12
            elif rev_growth > 10:
                growth_score += 8
            elif rev_growth > 0:
                growth_score += 4

        if 'profit_growth_3y' in growth and growth['profit_growth_3y']:
            profit_growth = growth['profit_growth_3y']
            if profit_growth > 30:
                growth_score += 15
            elif profit_growth > 20:
                growth_score += 12
            elif profit_growth > 10:
                growth_score += 8
            elif profit_growth > 0:
                growth_score += 4

        # 计算总分
        total_score = valuation_score + financial_score + growth_score
        
        if progress_callback:
            progress_callback(30, "基本面分析完成")

        return {
            'total': total_score,
            'valuation': valuation_score,
            'financial_health': financial_score,
            'growth': growth_score,
            'details': {
                'indicators': indicators,
                'growth': growth
            }
        }