"""
Input: 各分析模块的方法调用、OpenAI Function Calling工具调用请求；可选请求级 portfolio_snapshot（ContextVar）
Output: LangChain @tool 包装的标准工具函数 + OpenAI Function Calling格式schema + 工具执行分发
Pos: app/core/tools.py - 所有Agent共享的工具函数注册表；execute_tool 挂 P0-1 turn 护栏（tool_guardrails）；Sprint2 持仓只读工具

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.tools import tool
from app.core.data_provider import get_data_provider

logger = logging.getLogger(__name__)

# Sprint2：请求级持仓上下文（前端 body.portfolio_snapshot → chat 路由 set → 工具读）
# 禁止在工具内编造持仓；无上下文时返回明确空结构。
_portfolio_ctx: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "portfolio_snapshot_ctx", default=None
)
_ASIA_SHANGHAI = timezone(timedelta(hours=8))


def _now_cn_iso() -> str:
    return datetime.now(_ASIA_SHANGHAI).isoformat()


def set_portfolio_context(snapshot: Optional[Dict[str, Any]]) -> None:
    """绑定当前请求/turn 的持仓快照（应在 reset 前 set）。"""
    _portfolio_ctx.set(snapshot if isinstance(snapshot, dict) else None)


def get_portfolio_context() -> Optional[Dict[str, Any]]:
    return _portfolio_ctx.get()


def clear_portfolio_context() -> None:
    _portfolio_ctx.set(None)


@contextmanager
def portfolio_context(snapshot: Optional[Dict[str, Any]]) -> Iterator[None]:
    """with portfolio_context(snap): 自动清理。"""
    token = _portfolio_ctx.set(snapshot if isinstance(snapshot, dict) else None)
    try:
        yield
    finally:
        _portfolio_ctx.reset(token)


def normalize_portfolio_snapshot(raw: Any) -> Dict[str, Any]:
    """
    规范化前端/API 传入的持仓快照。
    - 无假持仓：非法项丢弃；name 等于 code 时 name 置空串
    - 返回结构恒含 holdings(list)/source(str)/as_of(str)
    """
    as_of = _now_cn_iso()
    if raw is None:
        return {"holdings": [], "source": "none", "as_of": as_of}
    if not isinstance(raw, dict):
        return {"holdings": [], "source": "invalid", "as_of": as_of}

    src = raw.get("source") or "client"
    if not isinstance(src, str) or not src.strip():
        src = "client"
    if isinstance(raw.get("as_of"), str) and raw.get("as_of").strip():
        as_of = raw["as_of"].strip()

    items = raw.get("holdings")
    if items is None and isinstance(raw.get("positions"), list):
        items = raw.get("positions")
    if not isinstance(items, list):
        return {"holdings": [], "source": src, "as_of": as_of}

    holdings: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        code = (
            it.get("code")
            or it.get("stock_code")
            or it.get("symbol")
            or ""
        )
        if not isinstance(code, str):
            code = str(code) if code is not None else ""
        code = code.strip()
        if not code or len(code) > 20:
            continue
        name = it.get("name")
        if not isinstance(name, str):
            name = ""
        name = name.strip()
        # 铁律 #1：禁止把 code 当 name
        if name == code:
            name = ""
        weight = it.get("weight")
        try:
            weight_f = float(weight) if weight is not None else None
        except (TypeError, ValueError):
            weight_f = None
        shares = it.get("shares")
        try:
            shares_f = float(shares) if shares is not None else None
        except (TypeError, ValueError):
            shares_f = None
        cost = it.get("cost")
        if cost is None:
            cost = it.get("avg_cost")
        try:
            cost_f = float(cost) if cost is not None else None
        except (TypeError, ValueError):
            cost_f = None
        market_type = it.get("market_type") or it.get("market") or "A"
        if not isinstance(market_type, str):
            market_type = "A"
        market_type = market_type.strip().upper()[:10] or "A"
        row: Dict[str, Any] = {
            "code": code,
            "name": name,
            "market_type": market_type,
        }
        if weight_f is not None:
            row["weight"] = weight_f
        if shares_f is not None:
            row["shares"] = shares_f
        if cost_f is not None:
            row["cost"] = cost_f
        holdings.append(row)

    return {"holdings": holdings, "source": src, "as_of": as_of}


# === 数据获取工具 ===

@tool
def get_stock_data(stock_code: str, market_type: str = 'A', days: int = 120) -> str:
    """获取股票历史K线数据，返回最近N天的OHLCV数据摘要"""
    from datetime import datetime, timezone, timedelta
    _tz = timezone(timedelta(hours=8))
    dp = get_data_provider()
    end_date = datetime.now(_tz).strftime('%Y%m%d')
    start_date = (datetime.now(_tz) - timedelta(days=days)).strftime('%Y%m%d')
    try:
        df = dp.get_stock_history(stock_code, start_date, end_date)
        if df is None or df.empty:
            return f"未获取到{stock_code}的数据"
        latest = df.iloc[-1]
        summary = (
            f"股票{stock_code} 最新数据({df['date'].iloc[-1]}):\n"
            f"收盘价: {latest.get('close', 'N/A')}\n"
            f"最高价: {latest.get('high', 'N/A')}\n"
            f"最低价: {latest.get('low', 'N/A')}\n"
            f"成交量: {latest.get('volume', 'N/A')}\n"
            f"数据范围: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}, 共{len(df)}条"
        )
        return summary
    except Exception as e:
        return f"获取数据失败: {str(e)}"


@tool
def get_technical_indicators(stock_code: str, market_type: str = 'A') -> str:
    """计算股票技术指标(MA/RSI/MACD/布林带等)并返回摘要"""
    from app.analysis.stock_analyzer import StockAnalyzer
    try:
        analyzer = StockAnalyzer()
        result = analyzer.quick_analyze_stock(stock_code, market_type)
        if 'error' in result:
            return f"技术分析失败: {result['error']}"
        return str(result)
    except Exception as e:
        return f"技术分析失败: {str(e)}"


@tool
def get_fundamental_data(stock_code: str) -> str:
    """获取股票基本面数据(PE/PB/ROE/净利润等财务指标)"""
    from app.analysis.fundamental_analyzer import FundamentalAnalyzer
    # P2a：Wind 优先源——需请求级 use_wind=true（或 WIND_USE_DEFAULT）+ 已配 key + 非空结果；
    # 否则静默回落 FundamentalAnalyzer。不改工具签名与返回契约。
    try:
        from app.adapters.wind_adapter import WindAdapter, is_use_wind_enabled
        if is_use_wind_enabled():
            _wind = WindAdapter()
            if _wind.health_check():  # 仅查 key，不连网
                _wind_data = _wind.get_financial_data(stock_code)
                if _wind_data:
                    return str(_wind_data)
    except Exception:
        pass  # Wind 任何异常都不影响原路径
    try:
        fa = FundamentalAnalyzer()
        result = fa.get_financial_indicators(stock_code)
        if not result:
            return f"未获取到{stock_code}的基本面数据"
        return str(result)
    except Exception as e:
        return f"基本面数据获取失败: {str(e)}"


@tool
def get_capital_flow(stock_code: str) -> str:
    """获取股票资金流向数据(主力/北向/机构资金)"""
    from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
    try:
        cfa = CapitalFlowAnalyzer()
        result = cfa.get_individual_fund_flow(stock_code)
        if not result:
            return f"未获取到{stock_code}的资金流向数据"
        return str(result)
    except Exception as e:
        return f"资金流向获取失败: {str(e)}"


@tool
def get_stock_news(stock_code: str, limit: int = 5) -> str:
    """获取股票相关的最新新闻和舆情信息"""
    from app.analysis.news_fetcher import news_fetcher
    try:
        news = news_fetcher.get_latest_news(days=1, limit=limit)
        if not news:
            return "暂无最新新闻"
        result = []
        for item in news[:limit]:
            result.append(f"[{item.get('time', '')}] {item.get('content', '')[:100]}")
        return '\n'.join(result)
    except Exception as e:
        return f"新闻获取失败: {str(e)}"


@tool
def search_web_tool(query: str, max_results: int = 5, engine: str = "auto") -> str:
    """搜索互联网获取最新信息。

    支持17种引擎(engine参数):
      - 'auto' 默认走 fallback 链: duckduckgo→baidu→bing_cn→sogou→so360→wechat→brave
      - 中文域: 'baidu' / 'sogou' / 'so360' / 'wechat' / 'toutiao' / 'bing_cn' / 'jisilu' / 'zhihu'
      - 全球域: 'duckduckgo' / 'duckduckgo_html' / 'bing' / 'brave' / 'qwant' / 'startpage' / 'ecosia'
      - 知识域: 'wikipedia'(百科事实), 'wolframalpha'(数学/单位/货币换算)
      - 'concurrent' 并发多引擎 + 去重合并
    """
    from app.core.search import search_web
    try:
        results = search_web(query, max_results, engine=engine)
        if not results:
            return "未找到相关搜索结果"
        output = []
        for r in results:
            output.append(f"[{r.get('source', '')}] {r.get('title', '')}: {r.get('content', '')[:150]}")
        return '\n'.join(output)
    except Exception as e:
        return f"搜索失败: {str(e)}"


@tool
def get_risk_assessment(stock_code: str, market_type: str = 'A') -> str:
    """评估股票的多维度风险(波动率/趋势/反转/成交量风险)"""
    from app.analysis.risk_monitor import RiskMonitor
    from app.analysis.stock_analyzer import StockAnalyzer
    try:
        analyzer = StockAnalyzer()
        rm = RiskMonitor(analyzer)
        result = rm.analyze_stock_risk(stock_code, market_type)
        if not result:
            return f"未获取到{stock_code}的风险数据"
        return str(result)
    except Exception as e:
        return f"风险评估失败: {str(e)}"


@tool
def get_portfolio_snapshot() -> str:
    """读取当前用户真实持仓快照（只读）。

    数据来自请求上下文 portfolio_snapshot（前端 portfolio-store 真值注入）。
    无持仓时返回明确空结构 holdings=[]，绝不编造持仓或权重。
    """
    snap = normalize_portfolio_snapshot(get_portfolio_context())
    payload = {
        "holdings": snap.get("holdings") or [],
        "source": snap.get("source") or "none",
        "as_of": snap.get("as_of") or _now_cn_iso(),
        "count": len(snap.get("holdings") or []),
        "empty": not bool(snap.get("holdings")),
    }
    if payload["empty"]:
        payload["message"] = "当前无持仓快照；请用户在组合页维护持仓，或于对话附带 portfolio_snapshot。"
    return json.dumps(payload, ensure_ascii=False)


def _structural_portfolio_risk(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """仅基于权重的结构摘要（可离线、不造假市价风险分）。"""
    if not holdings:
        return {
            "mode": "structural",
            "empty": True,
            "message": "持仓为空，无风险结构可汇总",
            "count": 0,
        }
    weights = []
    for h in holdings:
        w = h.get("weight")
        if w is None:
            continue
        try:
            wf = float(w)
        except (TypeError, ValueError):
            continue
        if wf < 0:
            continue
        weights.append((h.get("code") or "", h.get("name") or "", wf))
    n = len(holdings)
    if not weights:
        return {
            "mode": "structural",
            "empty": False,
            "count": n,
            "weight_sum": None,
            "message": "持仓存在但无可用 weight 字段；仅返回 count，不发明权重",
        }
    w_sum = sum(w for _, _, w in weights)
    # 归一用于集中度（若 sum≈0 则跳过 HHI）
    max_item = max(weights, key=lambda x: x[2])
    hhi = None
    top_share = None
    if w_sum > 0:
        norms = [w / w_sum for _, _, w in weights]
        hhi = sum(x * x for x in norms)
        top_share = max_item[2] / w_sum
    # Sprint3：在只读结构摘要中附带组合诊断（行业未知=unknown，不造假）
    diagnosis = None
    try:
        from app.analysis.risk_monitor import build_portfolio_diagnosis
        diagnosis_entries = []
        for h in holdings:
            diagnosis_entries.append({
                "stock_code": h.get("code") or h.get("stock_code") or "",
                "stock_name": h.get("name") or h.get("stock_name") or "",
                "weight": h.get("weight"),
                "industry": h.get("industry") or h.get("sector"),
            })
        diagnosis = build_portfolio_diagnosis(diagnosis_entries)
    except Exception:
        diagnosis = None
    out = {
        "mode": "structural",
        "empty": False,
        "count": n,
        "weighted_names_count": len(weights),
        "weight_sum": w_sum,
        "max_weight_code": max_item[0],
        "max_weight_name": max_item[1],
        "max_weight": max_item[2],
        "top_weight_share": top_share,
        "hhi": hhi,
        "message": "结构摘要来自用户 weight 真值；未调用行情接口，不产生假风险分",
    }
    if diagnosis is not None:
        out["sector_concentration"] = diagnosis.get("sector_concentration")
        out["name_overlap"] = diagnosis.get("name_overlap")
        out["defensive_weight"] = diagnosis.get("defensive_weight")
        out["unknown_industry_share"] = diagnosis.get("unknown_industry_share")
        out["diagnosis"] = diagnosis
    return out


@tool
def get_portfolio_risk_summary(include_market_risk: bool = False) -> str:
    """基于真实持仓快照的组合风险结构摘要（只读）。

    默认仅做权重结构摘要（离线安全、零假数）。
    include_market_risk=true 且未 DISABLE_NETWORK 时，才尝试调用 RiskMonitor.analyze_portfolio_risk；
    上游失败则降级为结构摘要并标明 degraded，不编造风险分。
    """
    snap = normalize_portfolio_snapshot(get_portfolio_context())
    holdings = list(snap.get("holdings") or [])
    base = {
        "source": snap.get("source") or "none",
        "as_of": snap.get("as_of") or _now_cn_iso(),
        "structural": _structural_portfolio_risk(holdings),
        "market_risk": None,
        "degraded": False,
    }
    if not holdings:
        base["message"] = "无持仓，跳过市场风险分析"
        return json.dumps(base, ensure_ascii=False)

    if not include_market_risk:
        base["message"] = "仅结构摘要；如需市价风险分析请设 include_market_risk=true"
        return json.dumps(base, ensure_ascii=False)

    if os.environ.get("DISABLE_NETWORK", "").strip() in ("1", "true", "True", "YES", "yes"):
        base["degraded"] = True
        base["message"] = "DISABLE_NETWORK=1，跳过市场风险分析，仅返回结构摘要"
        return json.dumps(base, ensure_ascii=False)

    try:
        from app.analysis.risk_monitor import RiskMonitor
        from app.analysis.stock_analyzer import StockAnalyzer

        portfolio = []
        for h in holdings:
            portfolio.append(
                {
                    "stock_code": h.get("code"),
                    "weight": h.get("weight") if h.get("weight") is not None else 1.0,
                    "market_type": h.get("market_type") or "A",
                }
            )
        rm = RiskMonitor(StockAnalyzer())
        risk = rm.analyze_portfolio_risk(portfolio)
        if isinstance(risk, dict) and risk.get("error"):
            base["degraded"] = True
            base["message"] = f"市场风险分析降级: {risk.get('error')}"
            base["market_risk"] = None
        else:
            base["market_risk"] = risk
            base["message"] = "结构摘要 + 市场风险分析"
    except Exception as e:
        logger.warning("get_portfolio_risk_summary market path failed: %s", e)
        base["degraded"] = True
        base["message"] = f"市场风险分析异常降级: {e}"
        base["market_risk"] = None
    return json.dumps(base, ensure_ascii=False, default=str)


# === LangChain工具注册表（保持向后兼容） ===
ALL_TOOLS = [
    get_stock_data,
    get_technical_indicators,
    get_fundamental_data,
    get_capital_flow,
    get_stock_news,
    search_web_tool,
    get_risk_assessment,
    get_portfolio_snapshot,
    get_portfolio_risk_summary,
]

# LangChain按职能分组
TECHNICAL_TOOLS = [get_stock_data, get_technical_indicators]
FUNDAMENTAL_TOOLS = [get_fundamental_data]
CAPITAL_FLOW_TOOLS = [get_capital_flow]
SENTIMENT_TOOLS = [get_stock_news, search_web_tool]
RISK_TOOLS = [get_risk_assessment, get_portfolio_snapshot, get_portfolio_risk_summary]
PORTFOLIO_TOOLS = [get_portfolio_snapshot, get_portfolio_risk_summary]


# === OpenAI Function Calling 格式工具定义 ===

OPENAI_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_data",
            "description": "获取股票历史K线数据，返回最近N天的OHLCV数据摘要",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码，如 '600519'、'000001'"
                    },
                    "market_type": {
                        "type": "string",
                        "description": "市场类型，'A'为A股，'HK'为港股，'US'为美股",
                        "default": "A"
                    },
                    "days": {
                        "type": "integer",
                        "description": "获取最近多少天的数据",
                        "default": 120
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_technical_indicators",
            "description": "计算股票技术指标(MA/RSI/MACD/布林带等)并返回摘要",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "market_type": {
                        "type": "string",
                        "description": "市场类型，'A'为A股，'HK'为港股，'US'为美股",
                        "default": "A"
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_fundamental_data",
            "description": "获取股票基本面数据(PE/PB/ROE/净利润等财务指标)",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码"
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_capital_flow",
            "description": "获取股票资金流向数据(主力/北向/机构资金)",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码"
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_news",
            "description": "获取股票相关的最新新闻和舆情信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回新闻条数上限",
                        "default": 5
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索互联网获取最新信息。17引擎多源聚合：auto自动降级(DDG→百度→Bing→搜狗→360→微信→Brave)；可明确指定 baidu/sogou/so360/wechat/toutiao/bing_cn/bing/duckduckgo/brave/qwant/startpage/ecosia/jisilu/zhihu/wikipedia/wolframalpha/concurrent",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回结果数",
                        "default": 5
                    },
                    "engine": {
                        "type": "string",
                        "description": "引擎名。auto默认；数学/换算用wolframalpha；百科事实用wikipedia；中文新闻可用wechat/toutiao；隐私偏好用duckduckgo/brave/qwant；多源聚合用concurrent",
                        "default": "auto"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk_assessment",
            "description": "评估股票的多维度风险(波动率/趋势/反转/成交量风险)",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "market_type": {
                        "type": "string",
                        "description": "市场类型，'A'为A股，'HK'为港股，'US'为美股",
                        "default": "A"
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_snapshot",
            "description": (
                "读取当前用户真实持仓快照（只读）。"
                "无持仓时返回 holdings=[] 空结构，禁止编造持仓。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_risk_summary",
            "description": (
                "基于真实持仓快照的组合风险结构摘要（只读）。"
                "默认仅权重结构；include_market_risk=true 才尝试市价风险分析。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "include_market_risk": {
                        "type": "boolean",
                        "description": "是否尝试调用行情路径做组合市场风险（可能较重）",
                        "default": False
                    }
                },
                "required": []
            }
        }
    }
]


# === OpenAI工具按职能分组的schema ===

TECHNICAL_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] in ('get_stock_data', 'get_technical_indicators')
]

FUNDAMENTAL_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] == 'get_fundamental_data'
]

CAPITAL_FLOW_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] == 'get_capital_flow'
]

SENTIMENT_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] in ('get_stock_news', 'search_web')
]

RISK_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] in (
        'get_risk_assessment',
        'get_portfolio_snapshot',
        'get_portfolio_risk_summary',
    )
]

PORTFOLIO_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] in (
        'get_portfolio_snapshot',
        'get_portfolio_risk_summary',
    )
]

# 全量schema（排除搜索工具，用于股票分析场景）
STOCK_ANALYSIS_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] != 'search_web'
]


# === 工具执行分发 ===

# 工具名称到LangChain工具实例的映射
TOOL_EXECUTORS = {
    "get_stock_data": get_stock_data,
    "get_technical_indicators": get_technical_indicators,
    "get_fundamental_data": get_fundamental_data,
    "get_capital_flow": get_capital_flow,
    "get_stock_news": get_stock_news,
    "search_web": search_web_tool,
    "get_risk_assessment": get_risk_assessment,
    "get_portfolio_snapshot": get_portfolio_snapshot,
    "get_portfolio_risk_summary": get_portfolio_risk_summary,
}


def _raw_execute_tool(tool_name: str, arguments: dict) -> str:
    """底层工具执行（无护栏）。未知工具抛 ValueError（保持既有契约）。"""
    executor = TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        available = ', '.join(TOOL_EXECUTORS.keys())
        raise ValueError(f"未知工具: {tool_name}，可用工具: {available}")

    logger.info(f"执行工具 {tool_name}，参数: {arguments}")
    try:
        result = executor.invoke(arguments)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        error_msg = f"工具 {tool_name} 执行失败: {str(e)}"
        logger.error(error_msg)
        return error_msg


def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    执行指定工具并返回结果字符串。

    通过LangChain工具的 .invoke() 方法调用，兼容 @tool 装饰器的调用约定。
    P0-1：若当前 ContextVar 绑定了 turn 护栏，则同 tool+归一化 args 连续失败
    达阈值时返回结构化 JSON（guardrail=block|halt|warn），不造假金融数据。

    Args:
        tool_name: 工具名称（需与TOOL_EXECUTORS中的key匹配）
        arguments: 工具参数字典

    Returns:
        str: 工具执行结果的字符串表示；被护栏拦截时为含 guardrail 字段的 JSON

    Raises:
        ValueError: 未知的工具名称（仅裸路径；护栏开启时未知工具仍 raise，由调用方捕获）
    """
    try:
        from app.core.tool_guardrails import get_turn_guardrails, guarded_execute

        if get_turn_guardrails() is not None:
            # 未知工具仍 raise，与既有契约一致（ai_client 已 try/except 包装）
            return guarded_execute(
                tool_name,
                arguments or {},
                lambda n, a: _raw_execute_tool(n, a),
            )
    except ValueError:
        raise
    except Exception as e:
        logger.warning("tool_guardrails unavailable, fallback raw execute: %s", e)

    return _raw_execute_tool(tool_name, arguments or {})
