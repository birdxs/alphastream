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
    artifact = {
        "type": "artifact",
        "artifact_type": artifact_type,
        "title": f"{stock_code} {ARTIFACT_TITLE_MAP.get(artifact_type, tool_name)}",
        "data": structured_data,
        "metadata": {
            "source_tool": tool_name,
            "stock_code": stock_code,
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
    """获取新闻数据的结构化结果

    调用 NewsFetcher.get_latest_news() 获取list[dict]，
    返回结构: {items: [{title, content, datetime, source}, ...]}
    """
    try:
        from app.analysis.news_fetcher import news_fetcher

        limit = arguments.get("limit", 5)
        news = news_fetcher.get_latest_news(days=1, limit=limit)
        if not news:
            return None

        items = []
        for item in news[:limit]:
            items.append({
                "title": item.get("title", ""),
                "content": item.get("content", "")[:200],
                "datetime": item.get("datetime", ""),
                "time": item.get("time", ""),
            })

        return {"items": items}
    except Exception as e:
        logger.warning(f"获取新闻结构化数据失败: {e}")
        return None


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
        return {
            "total_risk_score": result.get("total_risk_score", 0),
            "risk_level": result.get("risk_level", "未知"),
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
