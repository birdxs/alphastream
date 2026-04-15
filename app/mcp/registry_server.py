"""
Input: MCP 协议请求 (tool_name, arguments dict)
Output: MCP 协议响应 (dict/JSON), 失败返回 {'error': ...}
Pos: app/mcp/registry_server.py - Registry 16 domain MCP Tools Server

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

L2 扩展: 将 AdapterRegistry 16 domain 的关键能力暴露为 MCP tools,
    供 Claude Desktop / Cursor 等 AI 客户端通过 Model Context Protocol 调用.

架构说明:
    现有 stock_data_server.py 采用 dict+handler 模式 (未依赖 mcp SDK),
    本文件保持相同风格, 不引入 pip 新依赖 (mcp 库未在 requirements.txt);
    每个 tool 内部调用 AdapterRegistry.default().call_with_fallback(domain, method, **kw),
    利用既有多源降级与重试能力.

核心 16 domain 对应的 10+ tools 清单见 REGISTRY_TOOLS 与 app/mcp/README.md.

MCP 规范参考 (2026-04 时点, Asia/Singapore 2026-04-15 14:49 +08:00):
  - 官方站点: https://modelcontextprotocol.io/
  - Python SDK: https://github.com/modelcontextprotocol/python-sdk
  - Claude Desktop config: ~/Library/Application Support/Claude/claude_desktop_config.json
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ====================================================================
# REGISTRY_TOOLS: MCP 发现 (discovery) 用 schema 清单
# ====================================================================
REGISTRY_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "a_stock_kline",
        "description": "获取 A 股历史 K 线 (domain=a_stock_kline, Akshare/Baostock/Efinance 三源降级)",
        "parameters": {
            "code":       {"type": "string",  "description": "6 位 A 股代码, 如 000001"},
            "start_date": {"type": "string",  "description": "起始 YYYYMMDD"},
            "end_date":   {"type": "string",  "description": "结束 YYYYMMDD"},
            "adjust":     {"type": "string",  "description": "复权类型: qfq/hfq/none", "default": "qfq"},
        },
    },
    {
        "name": "a_stock_realtime",
        "description": "获取 A 股实时报价 (domain=a_stock_realtime, Efinance/Easyquotation/Akshare)",
        "parameters": {
            "codes": {"type": "array", "description": "6 位 A 股代码列表 (可空, 空返回全市场快照)"},
        },
    },
    {
        "name": "us_stock_quote",
        "description": "获取美股历史价格 (domain=us_stock, YFinance/OpenBB/EDGAR)",
        "parameters": {
            "symbol":     {"type": "string", "description": "美股代码, 如 AAPL"},
            "start_date": {"type": "string", "description": "起始 YYYY-MM-DD"},
            "end_date":   {"type": "string", "description": "结束 YYYY-MM-DD"},
        },
    },
    {
        "name": "hk_stock_quote",
        "description": "获取港股历史价格 (domain=hk_stock, YFinance/Akshare)",
        "parameters": {
            "code":       {"type": "string", "description": "港股代码, 如 00700"},
            "start_date": {"type": "string", "description": "起始 YYYYMMDD"},
            "end_date":   {"type": "string", "description": "结束 YYYYMMDD"},
        },
    },
    {
        "name": "crypto_ticker",
        "description": "获取加密货币实时报价 (domain=crypto, CCXT/CoinGecko/YFinance)",
        "parameters": {
            "symbol": {"type": "string", "description": "交易对, 如 BTC/USDT", "default": "BTC/USDT"},
        },
    },
    {
        "name": "macro_us",
        "description": "获取美国宏观指标 (domain=macro_us, FRED/OpenBB/WorldBank)",
        "parameters": {
            "indicator": {"type": "string", "description": "FRED 指标 ID, 如 GDP, CPIAUCSL, UNRATE"},
        },
    },
    {
        "name": "macro_cn",
        "description": "获取中国宏观指标 (domain=macro_cn, NBS/Akshare)",
        "parameters": {
            "indicator": {"type": "string", "description": "指标名: gdp/cpi/pmi/industrial_output"},
        },
    },
    {
        "name": "macro_global",
        "description": "获取全球宏观指标 (domain=macro_global, WorldBank/IMF/OpenBB)",
        "parameters": {
            "indicator": {"type": "string", "description": "WorldBank 指标 ID, 如 NY.GDP.MKTP.CD"},
            "country":   {"type": "string", "description": "ISO 三位国家码", "default": "USA"},
        },
    },
    {
        "name": "xbrl_financials",
        "description": "获取 SEC XBRL 财务数据 (domain=xbrl_financials, EDGAR/YFinance/OpenBB)",
        "parameters": {
            "ticker": {"type": "string", "description": "美股代码, 如 AAPL"},
        },
    },
    {
        "name": "news_feed",
        "description": "获取 RSS 新闻流 (domain=news, RSSNews/OpenCLI/Akshare)",
        "parameters": {
            "source": {"type": "string", "description": "来源: wallstreetcn/cls/xueqiu/sina", "default": "wallstreetcn"},
            "limit":  {"type": "integer", "description": "最大条数", "default": 20},
        },
    },
    {
        "name": "esg_rating",
        "description": "获取 ESG 评级 (domain=esg_rating, ESGAdapter)",
        "parameters": {
            "ticker": {"type": "string", "description": "股票代码, 如 AAPL / 000001"},
            "source": {"type": "string", "description": "来源: esgbook/sustainalytics/msci", "default": "esgbook"},
        },
    },
    {
        "name": "corporate_search",
        "description": "企业实体搜索 (domain=corporate_entity, OpenCorporates)",
        "parameters": {
            "query":        {"type": "string",  "description": "公司名关键词"},
            "jurisdiction": {"type": "string",  "description": "司法辖区 (可空), 如 us_ca/gb/cn"},
            "per_page":     {"type": "integer", "description": "每页条数 (免费层 ≤30)", "default": 30},
        },
    },
    {
        "name": "jobs_search",
        "description": "招聘信号搜索 (domain=hiring_signal, JobsAdapter)",
        "parameters": {
            "query":   {"type": "string", "description": "职位/技能关键词 (可空)"},
            "company": {"type": "string", "description": "公司名 (可空)"},
        },
    },
    {
        "name": "shipping_bdi",
        "description": "波罗的海干散货指数 BDI (domain=commodity_shipping, ShippingAdapter)",
        "parameters": {
            "days": {"type": "integer", "description": "回溯天数", "default": 30},
        },
    },
    {
        "name": "satellite_search",
        "description": "卫星遥感数据集搜索 (domain=earth_observation, SatelliteAdapter)",
        "parameters": {
            "keyword": {"type": "string",  "description": "数据集关键词, 如 landsat/modis/sentinel"},
            "limit":   {"type": "integer", "description": "最大结果数", "default": 20},
        },
    },
    {
        "name": "registry_status",
        "description": "查询 AdapterRegistry 当前注册状态 (domain→adapters 映射 + 失败计数)",
        "parameters": {},
    },
]


# ====================================================================
# 序列化工具: DataFrame / 非 JSON 对象 → dict
# ====================================================================
def _to_jsonable(obj: Any, limit: int = 200) -> Any:
    """把 Registry 返回值(常见 DataFrame/list/dict) 归一为 MCP 可返回的 JSON 结构."""
    try:
        import pandas as pd  # 延迟导入
        if isinstance(obj, pd.DataFrame):
            if obj.empty:
                return {"data": [], "total_rows": 0}
            # 时间戳类安全转字符串
            df = obj.copy()
            for col in df.columns:
                if str(df[col].dtype).startswith("datetime"):
                    df[col] = df[col].astype(str)
            return {
                "data": df.head(limit).to_dict("records"),
                "total_rows": int(len(obj)),
                "truncated": bool(len(obj) > limit),
            }
    except ImportError:
        pass
    if isinstance(obj, (dict, list, str, int, float, bool)) or obj is None:
        return obj
    # 兜底
    return {"value": str(obj)}


def _call_registry(domain: str, method: str, **kwargs) -> Any:
    """统一的 Registry 调用入口 (可被 monkeypatch 做 mock 测试)."""
    from app.adapters.adapter_registry import AdapterRegistry
    reg = AdapterRegistry.default()
    return reg.call_with_fallback(domain, method, **kwargs)


# ====================================================================
# Tool Handlers
# ====================================================================
def _h_a_stock_kline(code: str, start_date: str, end_date: str, adjust: str = "qfq") -> Any:
    return _to_jsonable(_call_registry(
        "a_stock_kline", "get_stock_history",
        code=code, start_date=start_date, end_date=end_date, adjust=adjust,
    ))


def _h_a_stock_realtime(codes: Optional[List[str]] = None) -> Any:
    return _to_jsonable(_call_registry("a_stock_realtime", "get_realtime_quotes", codes=codes))


def _h_us_stock_quote(symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Any:
    # yfinance_adapter 统一方法 get_stock_history(code, start_date, end_date)
    kw = {"code": symbol}
    if start_date: kw["start_date"] = start_date
    if end_date:   kw["end_date"] = end_date
    return _to_jsonable(_call_registry("us_stock", "get_stock_history", **kw))


def _h_hk_stock_quote(code: str, start_date: str, end_date: str) -> Any:
    return _to_jsonable(_call_registry(
        "hk_stock", "get_stock_history",
        code=code, start_date=start_date, end_date=end_date,
    ))


def _h_crypto_ticker(symbol: str = "BTC/USDT") -> Any:
    return _to_jsonable(_call_registry("crypto", "get_ticker", symbol=symbol))


def _h_macro_us(indicator: str) -> Any:
    # FREDAdapter 方法名 get_series
    return _to_jsonable(_call_registry("macro_us", "get_series", series_id=indicator))


def _h_macro_cn(indicator: str) -> Any:
    method_map = {
        "gdp":               "get_gdp",
        "cpi":               "get_cpi",
        "pmi":               "get_pmi",
        "industrial_output": "get_industrial_output",
    }
    method = method_map.get(indicator.lower())
    if not method:
        return {"error": f"不支持的中国宏观指标: {indicator}; 支持: {list(method_map.keys())}"}
    return _to_jsonable(_call_registry("macro_cn", method))


def _h_macro_global(indicator: str, country: str = "USA") -> Any:
    return _to_jsonable(_call_registry(
        "macro_global", "get_indicator",
        indicator=indicator, country=country,
    ))


def _h_xbrl_financials(ticker: str) -> Any:
    return _to_jsonable(_call_registry("xbrl_financials", "get_financial_data", code=ticker))


def _h_news_feed(source: str = "wallstreetcn", limit: int = 20) -> Any:
    return _to_jsonable(_call_registry("news", "get_feed", source=source, limit=limit))


def _h_esg_rating(ticker: str, source: str = "esgbook") -> Any:
    return _to_jsonable(_call_registry("esg_rating", "get_esg_score", ticker=ticker, source=source))


def _h_corporate_search(query: str, jurisdiction: Optional[str] = None, per_page: int = 30) -> Any:
    return _to_jsonable(_call_registry(
        "corporate_entity", "search_company",
        name=query, jurisdiction=jurisdiction, per_page=per_page,
    ))


def _h_jobs_search(query: Optional[str] = None, company: Optional[str] = None) -> Any:
    return _to_jsonable(_call_registry(
        "hiring_signal", "get_hiring_trend",
        query=query, company=company,
    ))


def _h_shipping_bdi(days: int = 30) -> Any:
    return _to_jsonable(_call_registry("commodity_shipping", "get_bdi_index", days=days))


def _h_satellite_search(keyword: str, limit: int = 20) -> Any:
    return _to_jsonable(_call_registry(
        "earth_observation", "search_datasets",
        keyword=keyword, limit=limit,
    ))


def _h_registry_status() -> Any:
    from app.adapters.adapter_registry import AdapterRegistry
    return AdapterRegistry.default().get_status()


HANDLERS: Dict[str, Callable[..., Any]] = {
    "a_stock_kline":     _h_a_stock_kline,
    "a_stock_realtime":  _h_a_stock_realtime,
    "us_stock_quote":    _h_us_stock_quote,
    "hk_stock_quote":    _h_hk_stock_quote,
    "crypto_ticker":     _h_crypto_ticker,
    "macro_us":          _h_macro_us,
    "macro_cn":          _h_macro_cn,
    "macro_global":      _h_macro_global,
    "xbrl_financials":   _h_xbrl_financials,
    "news_feed":         _h_news_feed,
    "esg_rating":        _h_esg_rating,
    "corporate_search":  _h_corporate_search,
    "jobs_search":       _h_jobs_search,
    "shipping_bdi":      _h_shipping_bdi,
    "satellite_search":  _h_satellite_search,
    "registry_status":   _h_registry_status,
}


# ====================================================================
# MCP 入口
# ====================================================================
MCP_REGISTRY_CONFIG: Dict[str, Any] = {
    "name":        "stockanal-registry-server",
    "version":     "1.0.0",
    "description": "StockAnal_Sys AdapterRegistry 16 domain MCP 工具服务器 (L2 扩展)",
    "tools":       REGISTRY_TOOLS,
}


def list_tools() -> List[Dict[str, Any]]:
    """MCP discovery: 列出所有可用工具 schema."""
    return list(REGISTRY_TOOLS)


def handle_mcp_tool_call(tool_name: str, arguments: Optional[dict] = None) -> Any:
    """MCP tools/call: 路由到对应 handler, 异常统一返回 {'error': ...}."""
    arguments = arguments or {}
    handler = HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"未知 Registry 工具: {tool_name}"}
    try:
        return handler(**arguments)
    except TypeError as e:
        logger.error(f"[MCP-Registry] 参数不匹配 {tool_name}: {e}")
        return {"error": f"参数错误: {e}"}
    except Exception as e:
        logger.error(f"[MCP-Registry] 调用失败 {tool_name}: {type(e).__name__}: {e}")
        return {"error": f"{type(e).__name__}: {e}"}


def as_json(tool_name: str, arguments: Optional[dict] = None) -> str:
    """便捷: 返回 JSON 字符串形式, 用于直接 stdout 协议帧."""
    return json.dumps(handle_mcp_tool_call(tool_name, arguments), ensure_ascii=False, default=str)
