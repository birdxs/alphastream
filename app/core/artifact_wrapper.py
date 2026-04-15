"""
Input: 工具名称、工具参数、工具执行结果（原始数据或字符串）
Output: 标准化Artifact JSON（artifact_type + structured data + metadata）
Pos: app/core/artifact_wrapper.py - Generative UI后端数据协议层，将工具结果包装为前端可渲染的Artifact

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Artifact类型注册表：工具名称 → artifact_type
ARTIFACT_TYPE_MAP = {
    "get_stock_data": "candlestick_chart",
    "get_technical_indicators": "technical_indicators",
    "get_fundamental_data": "fundamental_metrics",
    "get_capital_flow": "capital_flow_chart",
    "get_stock_news": "news_feed",
    "search_web": "search_results",
    "get_risk_assessment": "risk_gauge",
}

# 数据溯源映射：工具名称 → 数据来源列表
ARTIFACT_SOURCE_MAP = {
    "get_stock_data": [{"name": "东方财富", "type": "行情数据"}],
    "get_technical_indicators": [{"name": "akshare", "type": "技术分析"}],
    "get_fundamental_data": [{"name": "东方财富", "type": "财务数据"}, {"name": "巨潮资讯", "type": "年报"}],
    "get_capital_flow": [{"name": "东方财富", "type": "资金流向"}],
    "get_stock_news": [{"name": "财联社", "type": "新闻"}, {"name": "东方财富", "type": "新闻"}],
    "get_risk_assessment": [{"name": "akshare", "type": "风险模型"}],
    "search_web": [{"name": "Bing", "type": "网络搜索"}],
}

# AI置信度映射：工具名称 → 默认置信度 (0.0-1.0)
ARTIFACT_CONFIDENCE_MAP = {
    "get_stock_data": 0.95,        # 数据类，高置信度
    "get_technical_indicators": 0.75,  # 模型计算
    "get_fundamental_data": 0.90,  # 财务数据
    "get_capital_flow": 0.85,      # 资金数据
    "get_stock_news": 0.80,        # 新闻
    "get_risk_assessment": 0.70,   # 风险模型
    "search_web": 0.60,            # 网络搜索
}

# 中文标题映射
ARTIFACT_TITLE_MAP = {
    "candlestick_chart": "K线走势图",
    "technical_indicators": "技术指标分析",
    "fundamental_metrics": "基本面指标",
    "capital_flow_chart": "资金流向分析",
    "news_feed": "相关新闻",
    "search_results": "搜索结果",
    "risk_gauge": "风险评估",
}


def execute_tool_with_artifact(tool_name: str, arguments: dict) -> Tuple[str, Optional[Dict]]:
    """执行工具并包装为artifact格式

    Args:
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        (raw_result_str, artifact_dict) 元组
        - raw_result_str: 工具原始字符串结果（给AI继续推理用）
        - artifact_dict: 标准化artifact数据（给前端渲染用），无法生成时为None
    """
    from app.core.tools import execute_tool

    # 执行工具获取字符串结果
    raw_result = execute_tool(tool_name, arguments)

    # 尝试获取结构化数据
    structured_data = _get_structured_data(tool_name, arguments)

    artifact_type = ARTIFACT_TYPE_MAP.get(tool_name)
    if not artifact_type or structured_data is None:
        return raw_result, None

    stock_code = arguments.get("stock_code", arguments.get("query", ""))

    # 反查股票名称（用于卡片标题显示"688111 金山办公 ..."）
    stock_name = ""
    if stock_code and artifact_type != "search_results":
        # structured_data里已有stock_name优先用
        if isinstance(structured_data, dict) and structured_data.get("stock_name"):
            stock_name = structured_data.get("stock_name", "")
        else:
            try:
                from app.analysis.stock_analyzer import StockAnalyzer
                info = StockAnalyzer().get_stock_info(stock_code)
                stock_name = info.get("股票名称", "") or info.get("name", "")
                if stock_name == "未知":
                    stock_name = ""
                if stock_name and isinstance(structured_data, dict):
                    structured_data.setdefault("stock_name", stock_name)
            except Exception as e:
                logger.debug(f"反查{stock_code}名称失败: {e}")

    title_prefix = f"{stock_code} {stock_name}".strip() if stock_name else stock_code
    artifact = {
        "type": "artifact",
        "artifact_type": artifact_type,
        "title": f"{title_prefix} {ARTIFACT_TITLE_MAP.get(artifact_type, tool_name)}".strip(),
        "data": structured_data,
        "confidence": ARTIFACT_CONFIDENCE_MAP.get(tool_name, 0.5),
        "sources": ARTIFACT_SOURCE_MAP.get(tool_name, []),
        "metadata": {
            "source_tool": tool_name,
            "stock_code": stock_code,
            "stock_name": stock_name,
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    }

    return raw_result, artifact


def _get_structured_data(tool_name: str, arguments: dict) -> Optional[Dict]:
    """直接调用底层分析器获取结构化数据（绕过tools.py的str序列化）"""
    try:
        if tool_name == "get_stock_data":
            return _get_stock_data_structured(arguments)
        elif tool_name == "get_technical_indicators":
            return _get_technical_structured(arguments)
        elif tool_name == "get_fundamental_data":
            return _get_fundamental_structured(arguments)
        elif tool_name == "get_capital_flow":
            return _get_capital_flow_structured(arguments)
        elif tool_name == "get_stock_news":
            return _get_news_structured(arguments)
        elif tool_name == "get_risk_assessment":
            return _get_risk_structured(arguments)
        elif tool_name == "search_web":
            return _get_search_structured(arguments)
    except Exception as e:
        logger.warning(f"获取{tool_name}结构化数据失败: {e}")
    return None


def _get_stock_data_structured(arguments: dict) -> Optional[Dict]:
    """获取K线数据的结构化结果

    调用 DataProvider.get_stock_history() 获取DataFrame，
    返回结构: {ohlcv: [{date, open, high, low, close, volume}, ...], summary: {...}}
    """
    try:
        from app.core.data_provider import get_data_provider

        stock_code = arguments.get("stock_code", "")
        days = arguments.get("days", 120)

        dp = get_data_provider()
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        df = dp.get_stock_history(stock_code, start_date, end_date)
        if df is None or df.empty:
            return None

        # 转换DataFrame为OHLCV列表（取最近60条供前端图表渲染）
        display_df = df.tail(60)
        ohlcv = []
        for _, row in display_df.iterrows():
            ohlcv.append({
                "date": str(row.get("date", "")),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
            })

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        price_change = float((latest.get("close", 0) - prev.get("close", 1)) / prev.get("close", 1) * 100)

        return {
            "ohlcv": ohlcv,
            "summary": {
                "latest_close": float(latest.get("close", 0)),
                "latest_high": float(latest.get("high", 0)),
                "latest_low": float(latest.get("low", 0)),
                "latest_volume": float(latest.get("volume", 0)),
                "price_change_pct": round(price_change, 2),
                "total_records": len(df),
                "date_range": f"{df['date'].iloc[0]} ~ {df['date'].iloc[-1]}",
            }
        }
    except Exception as e:
        logger.warning(f"获取K线结构化数据失败: {e}")
        return None


def _get_technical_structured(arguments: dict) -> Optional[Dict]:
    """获取技术指标的结构化结果

    调用 StockAnalyzer.quick_analyze_stock() 获取dict，
    返回结构: {stock_code, stock_name, price, score, rsi, macd_signal, ma_trend, ...}
    """
    try:
        from app.analysis.stock_analyzer import StockAnalyzer

        stock_code = arguments.get("stock_code", "")
        market_type = arguments.get("market_type", "A")

        analyzer = StockAnalyzer()
        result = analyzer.quick_analyze_stock(stock_code, market_type)
        if not result or "error" in result:
            return None

        # result已是dict，包含:
        # stock_code, stock_name, industry, analysis_date, score,
        # price, price_change, ma_trend, rsi, macd_signal, volume_status, recommendation
        return {
            "stock_code": result.get("stock_code", stock_code),
            "stock_name": result.get("stock_name", ""),
            "industry": result.get("industry", ""),
            "analysis_date": result.get("analysis_date", ""),
            "score": result.get("score", 0),
            "price": result.get("price", 0),
            "price_change": result.get("price_change", 0),
            "ma_trend": result.get("ma_trend", ""),
            "rsi": result.get("rsi", 0),
            "macd_signal": result.get("macd_signal", ""),
            "volume_status": result.get("volume_status", ""),
            "recommendation": result.get("recommendation", ""),
        }
    except Exception as e:
        logger.warning(f"获取技术指标结构化数据失败: {e}")
        return None


def _get_fundamental_structured(arguments: dict) -> Optional[Dict]:
    """获取基本面指标的结构化结果

    调用 FundamentalAnalyzer.get_financial_indicators() 获取dict，
    返回结构: {pe_ttm, pb, ps_ttm, roe, gross_margin, net_profit_margin, debt_ratio}
    """
    try:
        from app.analysis.fundamental_analyzer import FundamentalAnalyzer

        stock_code = arguments.get("stock_code", "")
        fa = FundamentalAnalyzer()
        result = fa.get_financial_indicators(stock_code)
        if not result:
            return None

        # result已是dict: {pe_ttm, pb, ps_ttm, roe, gross_margin, net_profit_margin, debt_ratio}
        return {
            "pe_ttm": result.get("pe_ttm", 0),
            "pb": result.get("pb", 0),
            "ps_ttm": result.get("ps_ttm", 0),
            "roe": result.get("roe", 0),
            "gross_margin": result.get("gross_margin", 0),
            "net_profit_margin": result.get("net_profit_margin", 0),
            "debt_ratio": result.get("debt_ratio", 0),
        }
    except Exception as e:
        logger.warning(f"获取基本面结构化数据失败: {e}")
        return None


def _get_capital_flow_structured(arguments: dict) -> Optional[Dict]:
    """获取资金流向的结构化结果

    调用 CapitalFlowAnalyzer.get_individual_fund_flow() 获取dict，
    返回结构: {stock_code, daily_flow: [{date, price, main_net_inflow, ...}], summary: {...}}
    """
    try:
        from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer

        stock_code = arguments.get("stock_code", "")
        cfa = CapitalFlowAnalyzer()
        result = cfa.get_individual_fund_flow(stock_code)
        if not result or not result.get("data"):
            return None

        # 取最近20条数据供前端图表
        daily_flow = []
        for item in result["data"][:20]:
            daily_flow.append({
                "date": str(item.get("date", "")),
                "price": item.get("price", 0),
                "change_percent": item.get("change_percent", 0),
                "main_net_inflow": item.get("main_net_inflow", 0),
                "main_net_inflow_percent": item.get("main_net_inflow_percent", 0),
                "super_large_net_inflow": item.get("super_large_net_inflow", 0),
                "large_net_inflow": item.get("large_net_inflow", 0),
                "medium_net_inflow": item.get("medium_net_inflow", 0),
                "small_net_inflow": item.get("small_net_inflow", 0),
            })

        summary = result.get("summary", {})
        return {
            "stock_code": result.get("stock_code", stock_code),
            "daily_flow": daily_flow,
            "summary": {
                "recent_days": summary.get("recent_days", 0),
                "total_main_net_inflow": summary.get("total_main_net_inflow", 0),
                "avg_main_net_inflow_percent": summary.get("avg_main_net_inflow_percent", 0),
                "positive_days": summary.get("positive_days", 0),
                "negative_days": summary.get("negative_days", 0),
            }
        }
    except Exception as e:
        logger.warning(f"获取资金流向结构化数据失败: {e}")
        return None


def _get_news_structured(arguments: dict) -> Optional[Dict]:
    """获取个股相关新闻结构化数据

    优先级:
      1. akshare stock_news_em(symbol=code) — 东方财富按股票代码过滤的个股新闻
      2. search_stock_news_unified(code, name) — Tavily/SERP中文新闻搜索降级
      3. NewsFetcher.get_latest_news() — 最后兜底(全市场财联社电报)

    返回结构: {stock_code, stock_name, items: [{title, content, datetime, source}, ...]}
    """
    stock_code = arguments.get("stock_code", "")
    limit = arguments.get("limit", 8)

    # 反查股票名称
    stock_name = ""
    try:
        from app.analysis.stock_analyzer import StockAnalyzer
        info = StockAnalyzer().get_stock_info(stock_code) if stock_code else {}
        stock_name = info.get("股票名称", "") or info.get("name", "")
        if stock_name == "未知":
            stock_name = ""
    except Exception:
        pass

    items: List[Dict[str, Any]] = []

    # 优先级1: akshare个股新闻接口（按股票代码过滤）
    if stock_code:
        try:
            import akshare as ak
            df = ak.stock_news_em(symbol=stock_code)
            if df is not None and not df.empty:
                for _, row in df.head(limit).iterrows():
                    items.append({
                        "title": str(row.get("新闻标题", "") or row.get("title", "")),
                        "content": str(row.get("新闻内容", "") or row.get("content", ""))[:200],
                        "datetime": str(row.get("发布时间", "") or row.get("datetime", "")),
                        "time": str(row.get("发布时间", "") or row.get("time", "")),
                        "source": str(row.get("文章来源", "") or "东方财富"),
                        "url": str(row.get("新闻链接", "") or ""),
                    })
                logger.info(f"stock_news_em获取 {stock_code} 个股新闻 {len(items)} 条")
        except Exception as e:
            logger.warning(f"akshare stock_news_em({stock_code})失败: {e}")

    # 优先级2: Tavily/SERP按 code+name 联网搜索
    if not items and stock_code:
        try:
            from app.core.search import search_stock_news_unified
            results = search_stock_news_unified(stock_code, stock_name, max_results=limit)
            for r in results:
                items.append({
                    "title": r.get("title", ""),
                    "content": (r.get("content") or "")[:200],
                    "datetime": r.get("published_date", ""),
                    "time": r.get("published_date", ""),
                    "source": r.get("source", "web"),
                    "url": r.get("url", ""),
                })
            if items:
                logger.info(f"search_stock_news_unified获取 {stock_code} 新闻 {len(items)} 条")
        except Exception as e:
            logger.warning(f"search_stock_news_unified({stock_code})失败: {e}")

    # 优先级3: 兜底财联社电报(全市场非个股)
    if not items:
        try:
            from app.analysis.news_fetcher import news_fetcher
            news = news_fetcher.get_latest_news(days=1, limit=limit)
            for item in (news or [])[:limit]:
                items.append({
                    "title": item.get("title", ""),
                    "content": item.get("content", "")[:200],
                    "datetime": item.get("datetime", ""),
                    "time": item.get("time", ""),
                    "source": "财联社",
                })
        except Exception as e:
            logger.warning(f"news_fetcher兜底失败: {e}")

    if not items:
        return None

    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "items": items,
    }


def _get_risk_structured(arguments: dict) -> Optional[Dict]:
    """获取风险评估的结构化结果

    调用 RiskMonitor.analyze_stock_risk() 获取dict，
    返回结构: {total_risk_score, risk_level, volatility_risk, trend_risk, reversal_risk, volume_risk, alerts}
    """
    try:
        from app.analysis.risk_monitor import RiskMonitor
        from app.analysis.stock_analyzer import StockAnalyzer

        stock_code = arguments.get("stock_code", "")
        market_type = arguments.get("market_type", "A")

        analyzer = StockAnalyzer()
        rm = RiskMonitor(analyzer)
        result = rm.analyze_stock_risk(stock_code, market_type)
        if not result or "error" in result:
            return None

        # 提取关键字段，移除内嵌的大型DataFrame避免序列化问题
        # 注意: 同时冗余发送 risk_score / *_risk 扁平字符串, 保持与前端 risk-radar-chart.tsx 契约兼容
        vr = result.get("volatility_risk", {}) or {}
        tr = result.get("trend_risk", {}) or {}
        rr = result.get("reversal_risk", {}) or {}
        vor = result.get("volume_risk", {}) or {}
        return {
            "total_risk_score": result.get("total_risk_score", 0),
            "risk_score": round(result.get("total_risk_score", 0), 1),
            "risk_level": result.get("risk_level", "未知"),
            # 扁平字符串 — 前端radarData按'低/中/高'映射20/50/80
            "volatility_risk_level": vr.get("risk_level", "中"),
            "trend_risk_level": tr.get("risk_level", "中"),
            "reversal_risk_level": rr.get("risk_level", "中"),
            "volume_risk_level": vor.get("risk_level", "中"),
            # 详细dict结构(保持原字段)
            "volatility_risk": {
                "score": result.get("volatility_risk", {}).get("score", 0),
                "value": result.get("volatility_risk", {}).get("value", 0),
                "risk_level": result.get("volatility_risk", {}).get("risk_level", ""),
            },
            "trend_risk": {
                "score": result.get("trend_risk", {}).get("score", 0),
                "trend": result.get("trend_risk", {}).get("trend", ""),
                "risk_level": result.get("trend_risk", {}).get("risk_level", ""),
            },
            "reversal_risk": {
                "score": result.get("reversal_risk", {}).get("score", 0),
                "direction": result.get("reversal_risk", {}).get("direction", ""),
                "risk_level": result.get("reversal_risk", {}).get("risk_level", ""),
            },
            "volume_risk": {
                "score": result.get("volume_risk", {}).get("score", 0),
                "pattern": result.get("volume_risk", {}).get("pattern", ""),
                "risk_level": result.get("volume_risk", {}).get("risk_level", ""),
            },
            "alerts": result.get("alerts", []),
        }
    except Exception as e:
        logger.warning(f"获取风险评估结构化数据失败: {e}")
        return None


# ============================================================
# P3 Domain Artifact Wrappers [2026-04-15 13:08 +08:00]
# 配合 F3 Flask P3 API端点 (shipping/esg/corporate/jobs/alt_data/satellite)
# Input:  adapter原始返回(DataFrame/dict/list)
# Output: 标准化artifact dict {artifact_type, title, data, confidence, sources, metadata}
# ============================================================

P3_SOURCE_MAP = {
    "shipping": [{"name": "BDI", "type": "航运指数"}, {"name": "交通运输部/AISHub", "type": "港口AIS"}],
    "esg": [{"name": "ESG Book/CDP/B Corp/CUFE", "type": "ESG评级"}, {"name": "SEC EDGAR Climate", "type": "气候披露"}],
    "corporate": [{"name": "OpenCorporates", "type": "企业图谱"}],
    "jobs": [{"name": "Arbeitnow", "type": "招聘数据"}, {"name": "拉勾", "type": "招聘降级"}],
    "satellite": [{"name": "NASA CMR", "type": "对地观测"}],
    "alt_data": [{"name": "聚合:航运+ESG+招聘+企业", "type": "另类数据"}],
}


def _df_to_records(data: Any, max_rows: int = 60) -> list:
    """将pandas DataFrame转为JSON安全records；非DF原样返回。"""
    try:
        import pandas as _pd
        if isinstance(data, _pd.DataFrame):
            if data.empty:
                return []
            display = data.head(max_rows).copy()
            for col in display.columns:
                try:
                    if _pd.api.types.is_datetime64_any_dtype(display[col]):
                        display[col] = display[col].dt.strftime('%Y-%m-%d')
                except Exception:
                    pass
            display = display.replace({float('nan'): None})
            return display.to_dict('records')
    except Exception as e:
        logger.debug(f"_df_to_records转换失败: {e}")
    if isinstance(data, list):
        return data[:max_rows]
    return []


def _build_p3_artifact(artifact_type: str, title: str, data: Any,
                       domain: str, confidence: float = 0.75,
                       metadata: Optional[Dict] = None) -> Dict:
    meta = {"generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "domain": domain}
    if metadata:
        meta.update(metadata)
    return {
        "type": "artifact",
        "artifact_type": artifact_type,
        "title": title,
        "data": data,
        "confidence": confidence,
        "sources": P3_SOURCE_MAP.get(domain, []),
        "metadata": meta,
    }


# ============================================================
# [DEDUP 2026-04-15 13:25 +08:00] F3版 wrap_shipping/wrap_esg/wrap_corporate/
# wrap_jobs/wrap_satellite/wrap_alt_data 已删除(共6函数).
# 唯一实现: 下方 wrap_shipping_v2/wrap_esg_v2/wrap_hiring_v2/
# wrap_corporate_network_v2/wrap_alt_data_v2 (严格对齐前端 TSX 契约).
# Satellite 域无前端组件, 端点内直接使用 _build_p3_artifact 内联.
# 详见 docs/FINANCIAL_DATA_EXPANSION_2026-04-15.md F4 章节.
# ============================================================


def wrap_satellite_artifact(result: Any, keyword: str = "", **meta) -> Dict:
    """卫星对地观测 artifact (无前端组件,保留最小 artifact 层)"""
    if isinstance(result, dict):
        data = result
    elif isinstance(result, list):
        data = {"items": result, "count": len(result)}
    else:
        data = {"records": _df_to_records(result)}
    return _build_p3_artifact(
        artifact_type="satellite_datasets",
        title=f"卫星数据集: {keyword}" if keyword else "卫星数据集",
        data=data,
        domain="satellite",
        confidence=0.65,
        metadata={"keyword": keyword, **meta},
    )


def _get_search_structured(arguments: dict) -> Optional[Dict]:
    """获取搜索结果的结构化结果

    调用 search_web() 获取list[dict]，
    返回结构: {query, items: [{title, content, url, source}, ...]}
    """
    try:
        from app.core.search import search_web

        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)

        results = search_web(query, max_results)
        if not results:
            return None

        items = []
        for r in results:
            items.append({
                "title": r.get("title", ""),
                "content": r.get("content", "")[:200],
                "url": r.get("url", ""),
                "source": r.get("source", ""),
            })

        return {"query": query, "items": items}
    except Exception as e:
        logger.warning(f"获取搜索结构化数据失败: {e}")
        return None


# =====================================================================
# F2 [2026-04-15 13:08 +08:00] P3 前端Artifact契约对齐包装 (5 新类型)
# 仅追加, 不修改上方既有 wrap_shipping/wrap_esg/wrap_corporate/wrap_jobs/
# wrap_satellite/wrap_alt_data (F3 API 端点版, 签名: result+subtype).
#
# 命名说明: 因既有同名函数签名冲突 (F3端点用 result+subtype),
# 本批使用 `_v2` 后缀与之区分, 专供 Agent 回调/Generative UI 构造
# 前端 Artifact 组件 (shipping-chart/esg-scorecard/hiring-signal/
# corporate-network/alt-data-panel) 的 DataFrame → 前端字段契约.
# 建议后续按 [DEDUP] 统一收敛, 见 docs/FINANCIAL_DATA_EXPANSION_2026-04-15.md F2 章节.
# =====================================================================


def _safe_df_to_records(df, columns: Optional[List[str]] = None,
                        limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """DataFrame → list[dict] 兼容 None/空/缺列/list[dict], 不抛异常"""
    try:
        if df is None:
            return []
        if isinstance(df, list):
            rows = df[:limit] if limit else df
            return [dict(r) for r in rows if isinstance(r, dict)]
        if not hasattr(df, "empty") or df.empty:
            return []
        work = df
        if columns:
            present = [c for c in columns if c in work.columns]
            if present:
                work = work[present]
        if limit:
            work = work.head(limit)
        records: List[Dict[str, Any]] = []
        import math
        for _, row in work.iterrows():
            item: Dict[str, Any] = {}
            for k, v in row.items():
                try:
                    if v is None:
                        item[k] = None
                    elif hasattr(v, "item"):
                        val = v.item()
                        item[k] = None if (isinstance(val, float) and math.isnan(val)) else val
                    elif isinstance(v, float) and math.isnan(v):
                        item[k] = None
                    else:
                        item[k] = v
                except Exception:
                    item[k] = str(v)
            records.append(item)
        return records
    except Exception as e:
        logger.debug(f"_safe_df_to_records 失败: {e}")
        return []


def wrap_shipping_v2(stock_name: str, bdi_df=None, port_df=None, ais_df=None) -> Dict[str, Any]:
    """航运&大宗 Artifact 包装 — 对齐 shipping-chart.tsx 字段契约

    前端契约 (frontend/src/components/artifacts/shipping-chart.tsx):
      data: {
        bdi_series:     [{date, value, indicator, source}],
        port_throughput:[{date, port, value, unit, indicator}],
        ais_vessels:    [{mmsi, name, ship_type, lat, lon, sog}],
        ais_count: int, port_name: str,
      }

    后端 adapter 映射:
      shipping_adapter.get_bdi_index()        → bdi_df [date, indicator, value, source]
      shipping_adapter.get_port_throughput()  → port_df [date, port, indicator, value, unit, source]
      shipping_adapter.get_ais_vessels()      → ais_df  [mmsi, name, lat, lon, sog, ..., ship_type, ts]
    """
    bdi_series = _safe_df_to_records(
        bdi_df, columns=["date", "value", "indicator", "source"], limit=120
    )
    for p in bdi_series:
        if p.get("date") is not None:
            p["date"] = str(p["date"])
        try:
            if p.get("value") is not None:
                p["value"] = float(p["value"])
        except Exception:
            pass

    port_throughput = _safe_df_to_records(
        port_df, columns=["date", "port", "value", "unit", "indicator"], limit=60
    )
    for p in port_throughput:
        if p.get("date") is not None:
            p["date"] = str(p["date"])
        try:
            if p.get("value") is not None:
                p["value"] = float(p["value"])
        except Exception:
            pass

    ais_records = _safe_df_to_records(
        ais_df, columns=["mmsi", "name", "ship_type", "lat", "lon", "sog"], limit=50
    )
    ais_count = 0
    try:
        if ais_df is not None and hasattr(ais_df, "shape"):
            ais_count = int(ais_df.shape[0])
        elif isinstance(ais_df, list):
            ais_count = len(ais_df)
        else:
            ais_count = len(ais_records)
    except Exception:
        ais_count = len(ais_records)

    port_name = ""
    if port_throughput:
        port_name = str(port_throughput[0].get("port") or "")

    return {
        "type": "shipping",
        "title": f"{stock_name} 航运 & 大宗数据".strip() or "航运 & 大宗数据",
        "stock_name": stock_name or "",
        "data": {
            "bdi_series": bdi_series,
            "port_throughput": port_throughput,
            "ais_vessels": ais_records,
            "ais_count": ais_count,
            "port_name": port_name,
        },
    }


def wrap_esg_v2(stock_name: str, scores: Optional[Dict[str, Any]] = None,
                disclosures: Optional[Dict[str, Any]] = None,
                cdp: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """ESG Artifact 包装 — 对齐 esg-scorecard.tsx 字段契约

    前端契约 (frontend/src/components/artifacts/esg-scorecard.tsx):
      data: {ticker, company, primary{source,esg_score,e_score,s_score,g_score,grade,as_of},
             esg_score, e_score, s_score, g_score, grade, source, as_of,
             sources[{source,esg_score,grade,as_of,...}],
             climate_disclosures[{tag,label,filing_date,url}]}

    后端 adapter 映射:
      esg_adapter.get_esg_score(ticker,source)  → scores dict
      esg_adapter.get_climate_disclosure(cik)   → disclosures dict (scope1/2/3 + tags)
      esg_adapter.get_cdp_response(company, y)  → cdp dict (climate_score/disclosures...)
    """
    scores = scores or {}
    ticker = scores.get("ticker", "")
    company = scores.get("company", "") or stock_name
    primary = {
        "source": scores.get("source"),
        "ticker": ticker,
        "company": company,
        "esg_score": scores.get("esg_score"),
        "e_score": scores.get("e_score"),
        "s_score": scores.get("s_score"),
        "g_score": scores.get("g_score"),
        "grade": scores.get("grade"),
        "as_of": scores.get("as_of"),
    }

    sources_list: List[Dict[str, Any]] = [primary.copy()] if scores.get("esg_score") is not None else []

    if cdp and (cdp.get("climate_score") or cdp.get("disclosures")):
        sources_list.append({
            "source": cdp.get("source", "cdp"),
            "ticker": ticker,
            "company": cdp.get("company") or company,
            "esg_score": None,
            "grade": cdp.get("climate_score"),
            "as_of": str(cdp.get("year")) if cdp.get("year") else None,
        })

    climate: List[Dict[str, Any]] = []
    if disclosures:
        for scope_key, tag in (("scope1_latest", "Scope 1"),
                               ("scope2_latest", "Scope 2"),
                               ("scope3_latest", "Scope 3")):
            v = disclosures.get(scope_key)
            if v is not None:
                climate.append({
                    "tag": tag, "label": f"{tag} 披露",
                    "filing_date": "", "url": "",
                })
        tags_dict = disclosures.get("tags") or {}
        if isinstance(tags_dict, dict):
            for tname, facts in tags_dict.items():
                if not facts:
                    continue
                try:
                    last = facts[-1] if isinstance(facts, list) else facts
                    climate.append({
                        "tag": str(tname),
                        "label": str(tname),
                        "filing_date": str((last or {}).get("end", "")),
                        "url": "",
                    })
                except Exception:
                    continue
    if cdp and cdp.get("disclosures"):
        for d in cdp.get("disclosures") or []:
            if not isinstance(d, dict):
                continue
            climate.append({
                "tag": d.get("tag") or d.get("program") or "CDP",
                "label": d.get("label") or d.get("title") or "CDP 披露",
                "filing_date": d.get("filing_date") or d.get("date") or "",
                "url": d.get("url") or "",
            })

    return {
        "type": "esg",
        "title": f"{stock_name} ESG 评级".strip() or "ESG 评级",
        "stock_name": stock_name or "",
        "data": {
            "ticker": ticker,
            "company": company,
            "primary": primary,
            "esg_score": scores.get("esg_score"),
            "e_score": scores.get("e_score"),
            "s_score": scores.get("s_score"),
            "g_score": scores.get("g_score"),
            "grade": scores.get("grade"),
            "source": scores.get("source"),
            "as_of": scores.get("as_of"),
            "sources": sources_list,
            "climate_disclosures": climate,
        },
    }


def wrap_hiring_v2(stock_name: str, postings_df=None, trend_df=None) -> Dict[str, Any]:
    """招聘扩张 Artifact 包装 — 对齐 hiring-signal.tsx 字段契约

    前端契约 (frontend/src/components/artifacts/hiring-signal.tsx):
      data: {company, total_postings,
             items[{title,company,location,tags,url,created_at,source}],
             monthly_trend[{month,count}], skill_distribution[{name,value}],
             expansion_level: "low"|"medium"|"high", yoy_change: number}

    后端 adapter 映射:
      jobs_adapter.search_jobs() / get_company_postings()
      → DataFrame[title, company, location, remote, tags, url, created_at, source]
      trend_df 可选, DataFrame[month, count]
    """
    items = _safe_df_to_records(
        postings_df,
        columns=["title", "company", "location", "tags", "url", "created_at", "source"],
        limit=200,
    )
    for it in items:
        if it.get("created_at") is not None:
            it["created_at"] = str(it["created_at"])

    total_postings = 0
    try:
        if postings_df is not None and hasattr(postings_df, "shape"):
            total_postings = int(postings_df.shape[0])
        else:
            total_postings = len(items)
    except Exception:
        total_postings = len(items)

    monthly_trend: List[Dict[str, Any]] = _safe_df_to_records(
        trend_df, columns=["month", "count"], limit=36
    )
    if not monthly_trend and items:
        bucket: Dict[str, int] = {}
        for it in items:
            d = it.get("created_at") or ""
            m = str(d)[:7]
            if len(m) == 7 and "-" in m:
                bucket[m] = bucket.get(m, 0) + 1
        monthly_trend = [{"month": k, "count": v} for k, v in sorted(bucket.items())]

    skill_bucket: Dict[str, int] = {}
    for it in items:
        tags = it.get("tags") or ""
        for t in str(tags).split(","):
            t = t.strip()
            if t:
                skill_bucket[t] = skill_bucket.get(t, 0) + 1
    skill_distribution = [
        {"name": k, "value": v}
        for k, v in sorted(skill_bucket.items(), key=lambda x: x[1], reverse=True)[:6]
    ]

    yoy_change: Optional[float] = None
    if len(monthly_trend) >= 13:
        try:
            latest = float(monthly_trend[-1].get("count", 0))
            prev = float(monthly_trend[-13].get("count", 0))
            if prev > 0:
                yoy_change = round((latest - prev) / prev * 100, 1)
        except Exception:
            yoy_change = None

    if yoy_change is None:
        expansion_level = "medium" if total_postings >= 50 else "low"
    elif yoy_change > 30:
        expansion_level = "high"
    elif yoy_change > 10:
        expansion_level = "medium"
    else:
        expansion_level = "low"

    company = stock_name or ""
    if items and items[0].get("company"):
        company = str(items[0]["company"]) or company

    return {
        "type": "hiring",
        "title": f"{stock_name} 招聘扩张信号".strip() or "招聘扩张信号",
        "stock_name": stock_name or "",
        "data": {
            "company": company,
            "total_postings": total_postings,
            "items": items,
            "monthly_trend": monthly_trend,
            "skill_distribution": skill_distribution,
            "expansion_level": expansion_level,
            "yoy_change": yoy_change if yoy_change is not None else 0,
        },
    }


def wrap_corporate_network_v2(stock_name: str,
                              company_details: Optional[Dict[str, Any]] = None,
                              network: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """企业关联 Artifact 包装 — 对齐 corporate-network.tsx 字段契约

    前端契约 (frontend/src/components/artifacts/corporate-network.tsx):
      data: {company_id, company_name, jurisdiction_code, incorporation_date, current_status,
             parents[{name,jurisdiction_code,company_number}],
             children[{name,jurisdiction_code,company_number}],
             officers[{name,position,start_date,end_date}], opencorporates_url}

    后端 adapter 映射:
      corporate_adapter.get_company_details(company_id) → company_details dict
      corporate_adapter.get_company_network(company_id) → network dict
    """
    details = company_details or {}
    net = network or {}

    company_id = net.get("company_id") or details.get("company_id") or ""
    if not company_id:
        jc = details.get("jurisdiction_code")
        cn = details.get("company_number")
        if jc and cn:
            company_id = f"{jc}/{cn}"

    parents = [
        {
            "name": (p or {}).get("name"),
            "jurisdiction_code": (p or {}).get("jurisdiction_code"),
            "company_number": (p or {}).get("company_number"),
        }
        for p in (net.get("parents") or [])
    ]
    children = [
        {
            "name": (c or {}).get("name"),
            "jurisdiction_code": (c or {}).get("jurisdiction_code"),
            "company_number": (c or {}).get("company_number"),
        }
        for c in (net.get("children") or [])
    ]
    officers = [
        {
            "name": (o or {}).get("name"),
            "position": (o or {}).get("position"),
            "start_date": (o or {}).get("start_date"),
            "end_date": (o or {}).get("end_date"),
        }
        for o in (net.get("officers") or [])
    ]

    return {
        "type": "corporate_network",
        "title": f"{stock_name} 企业关联网络".strip() or "企业关联网络",
        "stock_name": stock_name or "",
        "data": {
            "company_id": company_id,
            "company_name": details.get("name") or stock_name or "",
            "jurisdiction_code": details.get("jurisdiction_code", ""),
            "incorporation_date": details.get("incorporation_date", ""),
            "current_status": details.get("current_status", ""),
            "parents": parents,
            "children": children,
            "officers": officers,
            "opencorporates_url": details.get("opencorporates_url", ""),
        },
    }


def wrap_alt_data_v2(stock_name: str,
                     shipping: Optional[Dict[str, Any]] = None,
                     esg: Optional[Dict[str, Any]] = None,
                     hiring: Optional[Dict[str, Any]] = None,
                     corporate: Optional[Dict[str, Any]] = None,
                     stock_code: Optional[str] = None) -> Dict[str, Any]:
    """另类数据聚合 Artifact 包装 (4子域Tab) — 对齐 alt-data-panel.tsx 字段契约

    前端契约 (frontend/src/components/artifacts/alt-data-panel.tsx):
      data: { shipping?:{...}, esg?:{...}, hiring?:{...}, corporate?:{...} }
      子域内字段对应 wrap_shipping_v2/wrap_esg_v2/wrap_hiring_v2/
      wrap_corporate_network_v2 返回 dict 的 `data` 部分.

    Args:
      shipping/esg/hiring/corporate: 可传 wrap_*_v2() 完整返回 dict (含 type/data),
      或直接传已提取的子 data dict, 自动识别.
    """
    def _extract(sub: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not sub:
            return None
        if isinstance(sub, dict) and "data" in sub and isinstance(sub.get("data"), dict):
            return sub["data"]
        return sub if isinstance(sub, dict) else None

    data: Dict[str, Any] = {}
    s = _extract(shipping)
    e = _extract(esg)
    h = _extract(hiring)
    c = _extract(corporate)
    if s is not None:
        data["shipping"] = s
    if e is not None:
        data["esg"] = e
    if h is not None:
        data["hiring"] = h
    if c is not None:
        data["corporate"] = c

    return {
        "type": "alt_data",
        "title": f"{stock_name} 另类数据聚合".strip() or "另类数据聚合",
        "stock_name": stock_name or "",
        "stock_code": stock_code or stock_name or "",  # [N1] 契约透传, 避免 None
        "data": data,
    }
