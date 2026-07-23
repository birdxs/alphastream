# -*- coding: utf-8 -*-
"""
智能分析系统（股票） - 股票市场数据分析系统
开发者：熊猫大侠
版本：v2.1.0
许可证：MIT License
"""
# risk_monitor.py
# Input: StockAnalyzer + 持仓列表
# Output: 单票/组合风险 + 组合诊断（行业集中度/同质化/防御占比；缺行业=unknown）
# Pos: app/analysis/risk_monitor.py — 风险分析与组合诊断
# 一旦我被修改，请更新本头注释与所属目录 README。
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

# 防御型行业关键词（仅匹配真实行业文案；无行业永不发明）
_DEFENSIVE_INDUSTRY_KEYWORDS = (
    "银行", "保险", "公用", "电力", "水务", "燃气",
    "高速公路", "铁路", "港口", "机场", "通信运营", "运营商",
    "食品", "饮料", "白酒", "乳品", "制药", "医药", "中药",
    "超市", "零售", "公用事业", "交通运输",
    "bank", "utility", "utilities", "insurance", "telecom", "pharma",
    "consumer staples",
)

# 名称/主题同质化关键词（简单规则，非 AI 分类）
_NAME_HOMOGENY_KEYWORDS = (
    "银行", "证券", "保险", "白酒", "光伏", "锂电", "芯片", "半导体",
    "医药", "地产", "信托", "券商", "煤炭", "钢铁", "石油", "新能源",
    "军工", "机器人", "汽车",
)


def _normalize_industry_label(raw) -> str:
    """缺行业 → unknown；禁止伪造行业。'未知'/空/None 统一 unknown。"""
    if raw is None:
        return "unknown"
    s = str(raw).strip()
    if not s or s in ("未知", "N/A", "n/a", "None", "null", "-", "—"):
        return "unknown"
    return s


def _is_defensive_industry(industry: str) -> bool:
    if not industry or industry == "unknown":
        return False
    low = industry.lower()
    for kw in _DEFENSIVE_INDUSTRY_KEYWORDS:
        if kw.lower() in low:
            return True
    return False


def build_portfolio_diagnosis(stock_entries):
    """组合诊断字段（纯结构，可离线单测）。

    stock_entries: list of dict，至少含 weight；可选 industry/stock_name/stock_code。
    缺行业一律 industry='unknown'，不填假行业。
    """
    if not stock_entries:
        return {
            "sector_concentration": {
                "by_sector": {},
                "max_sector": None,
                "max_sector_weight": None,
                "hhi": None,
                "unknown_weight": None,
                "unknown_share": None,
            },
            "name_overlap": {
                "groups": [],
                "homogenized": False,
                "hints": [],
            },
            "defensive_weight": None,
            "unknown_industry_weight": None,
            "unknown_industry_share": None,
            "weight_sum": 0.0,
        }

    total_w = 0.0
    sector_w = defaultdict(float)
    unknown_w = 0.0
    defensive_w = 0.0
    cleaned = []

    for s in stock_entries:
        try:
            w = float(s.get("weight") or 0)
        except (TypeError, ValueError):
            w = 0.0
        if w <= 0:
            continue
        ind = _normalize_industry_label(s.get("industry") or s.get("行业"))
        name = (s.get("stock_name") or s.get("name") or "").strip()
        code = str(s.get("stock_code") or s.get("code") or "")
        sector_w[ind] += w
        if ind == "unknown":
            unknown_w += w
        elif _is_defensive_industry(ind):
            defensive_w += w
        total_w += w
        cleaned.append({"code": code, "name": name, "weight": w, "industry": ind})

    by_sector = {k: round(v, 6) for k, v in sorted(sector_w.items(), key=lambda x: -x[1])}
    max_sector = None
    max_sector_weight = None
    hhi = None
    unknown_share = None
    defensive_share = None
    if total_w > 0:
        norms = {k: v / total_w for k, v in sector_w.items()}
        hhi = sum(x * x for x in norms.values())
        max_sector, max_raw = max(sector_w.items(), key=lambda x: x[1])
        max_sector_weight = max_raw / total_w
        unknown_share = unknown_w / total_w
        defensive_share = defensive_w / total_w

    groups = []
    hints = []
    by_ind = defaultdict(list)
    for c in cleaned:
        if c["industry"] != "unknown":
            by_ind[c["industry"]].append(c)
    for ind, members in by_ind.items():
        if len(members) >= 2:
            groups.append({
                "type": "same_industry",
                "key": ind,
                "codes": [m["code"] for m in members if m["code"]],
                "names": [m["name"] for m in members if m["name"]],
                "count": len(members),
            })
            hints.append(f"行业「{ind}」持有 {len(members)} 只，存在同质化敞口")

    for kw in _NAME_HOMOGENY_KEYWORDS:
        matched = [
            c for c in cleaned
            if kw in (c["name"] or "") or kw in (c["industry"] if c["industry"] != "unknown" else "")
        ]
        if len(matched) >= 2 and any(kw in (c["name"] or "") for c in matched):
            groups.append({
                "type": "name_keyword",
                "key": kw,
                "codes": [m["code"] for m in matched if m["code"]],
                "names": [m["name"] for m in matched if m["name"]],
                "count": len(matched),
            })
            hints.append(f"名称/主题「{kw}」相关持仓 {len(matched)} 只")

    prefix_map = defaultdict(list)
    for c in cleaned:
        code = c["code"]
        if len(code) >= 3 and code.isdigit():
            prefix_map[code[:3]].append(c)
    for pref, members in prefix_map.items():
        if len(members) >= 3:
            groups.append({
                "type": "code_prefix",
                "key": pref,
                "codes": [m["code"] for m in members],
                "names": [m["name"] for m in members if m["name"]],
                "count": len(members),
            })
            hints.append(f"代码前缀 {pref}* 共 {len(members)} 只，请核对板块集中度")

    seen_h = set()
    uniq_hints = []
    for h in hints:
        if h not in seen_h:
            seen_h.add(h)
            uniq_hints.append(h)

    homogenized = any(g["count"] >= 2 for g in groups)

    return {
        "sector_concentration": {
            "by_sector": by_sector,
            "max_sector": max_sector,
            "max_sector_weight": max_sector_weight,
            "hhi": hhi,
            "unknown_weight": unknown_w if total_w > 0 else None,
            "unknown_share": unknown_share,
        },
        "name_overlap": {
            "groups": groups,
            "homogenized": homogenized,
            "hints": uniq_hints,
        },
        "defensive_weight": defensive_share,
        "unknown_industry_weight": unknown_w if total_w > 0 else None,
        "unknown_industry_share": unknown_share,
        "weight_sum": total_w,
    }


class RiskMonitor:
    def __init__(self, analyzer):
        self.analyzer = analyzer

    def analyze_stock_risk(self, stock_code, market_type='A'):
        """分析单只股票的风险"""
        try:
            # 获取股票数据和技术指标
            df = self.analyzer.get_stock_data(stock_code, market_type)
            df = self.analyzer.calculate_indicators(df)

            # 计算各类风险指标
            volatility_risk = self._analyze_volatility_risk(df)
            trend_risk = self._analyze_trend_risk(df)
            reversal_risk = self._analyze_reversal_risk(df)
            volume_risk = self._analyze_volume_risk(df)

            # 综合评估总体风险
            total_risk_score = (
                    volatility_risk['score'] * 0.3 +
                    trend_risk['score'] * 0.3 +
                    reversal_risk['score'] * 0.25 +
                    volume_risk['score'] * 0.15
            )

            # 确定风险等级
            if total_risk_score >= 80:
                risk_level = "极高"
            elif total_risk_score >= 60:
                risk_level = "高"
            elif total_risk_score >= 40:
                risk_level = "中等"
            elif total_risk_score >= 20:
                risk_level = "低"
            else:
                risk_level = "极低"

            # 生成风险警报
            alerts = []

            if volatility_risk['score'] >= 70:
                alerts.append({
                    "type": "volatility",
                    "level": "高",
                    "message": f"波动率风险较高 ({volatility_risk['value']:.2f}%)，可能面临大幅波动"
                })

            if trend_risk['score'] >= 70:
                alerts.append({
                    "type": "trend",
                    "level": "高",
                    "message": f"趋势风险较高，当前处于{trend_risk['trend']}趋势，可能面临加速下跌"
                })

            if reversal_risk['score'] >= 70:
                alerts.append({
                    "type": "reversal",
                    "level": "高",
                    "message": f"趋势反转风险较高，技术指标显示可能{reversal_risk['direction']}反转"
                })

            if volume_risk['score'] >= 70:
                alerts.append({
                    "type": "volume",
                    "level": "高",
                    "message": f"成交量异常，{volume_risk['pattern']}，可能预示价格波动"
                })

            return {
                "total_risk_score": total_risk_score,
                "risk_level": risk_level,
                "volatility_risk": volatility_risk,
                "trend_risk": trend_risk,
                "reversal_risk": reversal_risk,
                "volume_risk": volume_risk,
                "alerts": alerts
            }

        except Exception as e:
            print(f"分析股票风险出错: {str(e)}")
            return {
                "error": f"分析风险时出错: {str(e)}"
            }

    def _analyze_volatility_risk(self, df):
        """分析波动率风险"""
        # 计算近期波动率
        recent_volatility = df.iloc[-1]['Volatility']

        # 计算波动率变化
        avg_volatility = df['Volatility'].mean()
        volatility_change = recent_volatility / avg_volatility - 1

        # 评估风险分数
        if recent_volatility > 5 and volatility_change > 0.5:
            score = 90  # 极高风险
        elif recent_volatility > 4 and volatility_change > 0.3:
            score = 75  # 高风险
        elif recent_volatility > 3 and volatility_change > 0.1:
            score = 60  # 中高风险
        elif recent_volatility > 2:
            score = 40  # 中等风险
        elif recent_volatility > 1:
            score = 20  # 低风险
        else:
            score = 0  # 极低风险

        return {
            "score": score,
            "value": recent_volatility,
            "change": volatility_change * 100,
            "risk_level": "高" if score >= 60 else "中" if score >= 30 else "低"
        }

    def _analyze_trend_risk(self, df):
        """分析趋势风险"""
        # 获取均线数据
        ma5 = df.iloc[-1]['MA5']
        ma20 = df.iloc[-1]['MA20']
        ma60 = df.iloc[-1]['MA60']

        # 判断当前趋势
        if ma5 < ma20 < ma60:
            trend = "下降"

            # 判断下跌加速程度
            ma5_ma20_gap = (ma20 - ma5) / ma20 * 100

            if ma5_ma20_gap > 5:
                score = 90  # 极高风险
            elif ma5_ma20_gap > 3:
                score = 75  # 高风险
            elif ma5_ma20_gap > 1:
                score = 60  # 中高风险
            else:
                score = 50  # 中等风险

        elif ma5 > ma20 > ma60:
            trend = "上升"
            score = 20  # 低风险
        else:
            trend = "盘整"
            score = 40  # 中等风险

        return {
            "score": score,
            "trend": trend,
            "risk_level": "高" if score >= 60 else "中" if score >= 30 else "低"
        }

    def _analyze_reversal_risk(self, df):
        """分析趋势反转风险"""
        # 获取最新指标
        rsi = df.iloc[-1]['RSI']
        macd = df.iloc[-1]['MACD']
        signal = df.iloc[-1]['Signal']
        price = df.iloc[-1]['close']
        ma20 = df.iloc[-1]['MA20']

        # 判断潜在趋势反转信号
        reversal_signals = 0

        # RSI超买/超卖
        if rsi > 75:
            reversal_signals += 1
            direction = "向下"
        elif rsi < 25:
            reversal_signals += 1
            direction = "向上"
        else:
            direction = "无明确方向"

        # MACD死叉/金叉
        if macd > signal and df.iloc[-2]['MACD'] <= df.iloc[-2]['Signal']:
            reversal_signals += 1
            direction = "向上"
        elif macd < signal and df.iloc[-2]['MACD'] >= df.iloc[-2]['Signal']:
            reversal_signals += 1
            direction = "向下"

        # 价格与均线关系
        if price > ma20 * 1.1:
            reversal_signals += 1
            direction = "向下"
        elif price < ma20 * 0.9:
            reversal_signals += 1
            direction = "向上"

        # 评估风险分数
        if reversal_signals >= 3:
            score = 90  # 极高风险
        elif reversal_signals == 2:
            score = 70  # 高风险
        elif reversal_signals == 1:
            score = 40  # 中等风险
        else:
            score = 10  # 低风险

        return {
            "score": score,
            "reversal_signals": reversal_signals,
            "direction": direction,
            "risk_level": "高" if score >= 60 else "中" if score >= 30 else "低"
        }

    def _analyze_volume_risk(self, df):
        """分析成交量风险"""
        # 计算成交量变化
        recent_volume = df.iloc[-1]['volume']
        avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
        volume_ratio = recent_volume / avg_volume

        # 判断成交量模式
        if volume_ratio > 3:
            pattern = "成交量暴增"
            score = 90  # 极高风险
        elif volume_ratio > 2:
            pattern = "成交量显著放大"
            score = 70  # 高风险
        elif volume_ratio > 1.5:
            pattern = "成交量温和放大"
            score = 50  # 中等风险
        elif volume_ratio < 0.5:
            pattern = "成交量萎缩"
            score = 40  # 中低风险
        else:
            pattern = "成交量正常"
            score = 20  # 低风险

        # 价格与成交量背离分析
        price_change = (df.iloc[-1]['close'] - df.iloc[-5]['close']) / df.iloc[-5]['close']
        volume_change = (recent_volume - df.iloc[-5]['volume']) / df.iloc[-5]['volume']

        if price_change > 0.05 and volume_change < -0.3:
            pattern = "价量背离(价格上涨但量能萎缩)"
            score = max(score, 80)  # 提高风险评分
        elif price_change < -0.05 and volume_change < -0.3:
            pattern = "价量同向(价格下跌且量能萎缩)"
            score = max(score, 70)  # 提高风险评分
        elif price_change < -0.05 and volume_change > 0.5:
            pattern = "价量同向(价格下跌且量能放大)"
            score = max(score, 85)  # 提高风险评分

        return {
            "score": score,
            "volume_ratio": volume_ratio,
            "pattern": pattern,
            "risk_level": "高" if score >= 60 else "中" if score >= 30 else "低"
        }

    def analyze_portfolio_risk(self, portfolio):
        """分析投资组合整体风险。

        扩展返回（Sprint3）：
        - sector_concentration / name_overlap / defensive_weight / unknown_industry_*
        - 缺行业 → industry='unknown'，禁止假行业
        """
        try:
            if not portfolio or len(portfolio) == 0:
                return {"error": "投资组合为空"}

            # 分析每只股票的风险
            stock_risks = {}
            total_weight = 0
            weighted_risk_score = 0
            diagnosis_entries = []

            for stock in portfolio:
                stock_code = stock.get('stock_code')
                weight = stock.get('weight', 1)
                market_type = stock.get('market_type', 'A')

                if not stock_code:
                    continue

                try:
                    weight = float(weight)
                except (TypeError, ValueError):
                    weight = 0
                if weight <= 0:
                    continue

                # 行业：优先请求体 industry；否则 get_stock_info；失败/空 → unknown
                industry_raw = stock.get("industry") or stock.get("行业")
                stock_name = stock.get("stock_name") or stock.get("name")
                try:
                    info = self.analyzer.get_stock_info(stock_code) or {}
                    if not stock_name:
                        stock_name = info.get("股票名称") or info.get("name") or stock_code
                    if not industry_raw:
                        industry_raw = info.get("行业") or info.get("industry")
                except Exception:
                    info = {}
                    if not stock_name:
                        stock_name = stock_code
                industry = _normalize_industry_label(industry_raw)

                diagnosis_entries.append({
                    "stock_code": stock_code,
                    "stock_name": stock_name or "",
                    "weight": weight,
                    "industry": industry,
                })

                # 分析股票风险
                risk = self.analyze_stock_risk(stock_code, market_type)
                if not isinstance(risk, dict):
                    risk = {"error": "invalid_risk_result"}
                stock_risks[stock_code] = {
                    **risk,
                    "industry": industry,
                    "stock_name": stock_name or stock_code,
                }

                # 计算加权风险分数
                total_weight += weight
                weighted_risk_score += risk.get('total_risk_score', 50) * weight

            # 计算组合总风险分数
            if total_weight > 0:
                portfolio_risk_score = weighted_risk_score / total_weight
            else:
                portfolio_risk_score = 0

            # 确定风险等级
            if portfolio_risk_score >= 80:
                risk_level = "极高"
            elif portfolio_risk_score >= 60:
                risk_level = "高"
            elif portfolio_risk_score >= 40:
                risk_level = "中等"
            elif portfolio_risk_score >= 20:
                risk_level = "低"
            else:
                risk_level = "极低"

            # 收集高风险股票
            high_risk_stocks = [
                {
                    "stock_code": code,
                    "risk_score": risk.get('total_risk_score', 0),
                    "risk_level": risk.get('risk_level', '未知'),
                    "industry": risk.get("industry", "unknown"),
                }
                for code, risk in stock_risks.items()
                if risk.get('total_risk_score', 0) >= 60
            ]

            # 收集所有风险警报
            all_alerts = []
            for code, risk in stock_risks.items():
                for alert in risk.get('alerts', []) or []:
                    all_alerts.append({
                        "stock_code": code,
                        **alert
                    })

            # 分析风险集中度（兼容旧字段 + 诊断）
            risk_concentration = self._analyze_risk_concentration(portfolio, stock_risks)
            diagnosis = build_portfolio_diagnosis(diagnosis_entries)

            return {
                "portfolio_risk_score": portfolio_risk_score,
                "risk_level": risk_level,
                "high_risk_stocks": high_risk_stocks,
                "alerts": all_alerts,
                "risk_concentration": risk_concentration,
                "stock_risks": stock_risks,
                # Sprint3 诊断字段
                "sector_concentration": diagnosis["sector_concentration"],
                "name_overlap": diagnosis["name_overlap"],
                "defensive_weight": diagnosis["defensive_weight"],
                "unknown_industry_weight": diagnosis["unknown_industry_weight"],
                "unknown_industry_share": diagnosis["unknown_industry_share"],
                "diagnosis": diagnosis,
            }

        except Exception as e:
            print(f"分析投资组合风险出错: {str(e)}")
            return {
                "error": f"分析投资组合风险时出错: {str(e)}"
            }

    def _analyze_risk_concentration(self, portfolio, stock_risks):
        """分析风险集中度（旧字段兼容；行业缺省 unknown 不发明假行业）"""
        industries = {}
        for stock in portfolio:
            stock_code = stock.get('stock_code')
            industry_raw = stock.get("industry") or stock.get("行业")
            if not industry_raw:
                try:
                    stock_info = self.analyzer.get_stock_info(stock_code) or {}
                    industry_raw = stock_info.get('行业') or stock_info.get('industry')
                except Exception:
                    industry_raw = None
            industry = _normalize_industry_label(industry_raw)
            try:
                weight = float(stock.get('weight', 1) or 0)
            except (TypeError, ValueError):
                weight = 0
            if weight <= 0:
                continue
            industries[industry] = industries.get(industry, 0) + weight

        max_industry = max(industries.items(), key=lambda x: x[1]) if industries else ('unknown', 0)

        high_risk_weight = 0
        for stock in portfolio:
            stock_code = stock.get('stock_code')
            if stock_code in stock_risks and stock_risks[stock_code].get('total_risk_score', 0) >= 60:
                try:
                    high_risk_weight += float(stock.get('weight', 1) or 0)
                except (TypeError, ValueError):
                    pass

        return {
            "max_industry": max_industry[0],
            "max_industry_weight": max_industry[1],
            "high_risk_weight": high_risk_weight,
            "by_industry": industries,
        }