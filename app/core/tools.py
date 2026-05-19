"""
Input: 各分析模块的方法调用、OpenAI Function Calling工具调用请求
Output: LangChain @tool 包装的标准工具函数 + OpenAI Function Calling格式schema + 工具执行分发
Pos: app/core/tools.py - 所有Agent共享的工具函数注册表，支持LangChain和OpenAI双格式

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
from langchain_core.tools import tool
from app.core.data_provider import get_data_provider

logger = logging.getLogger(__name__)


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


# === LangChain工具注册表（保持向后兼容） ===
ALL_TOOLS = [
    get_stock_data,
    get_technical_indicators,
    get_fundamental_data,
    get_capital_flow,
    get_stock_news,
    search_web_tool,
    get_risk_assessment,
]

# LangChain按职能分组
TECHNICAL_TOOLS = [get_stock_data, get_technical_indicators]
FUNDAMENTAL_TOOLS = [get_fundamental_data]
CAPITAL_FLOW_TOOLS = [get_capital_flow]
SENTIMENT_TOOLS = [get_stock_news, search_web_tool]
RISK_TOOLS = [get_risk_assessment]


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
    if s['function']['name'] == 'get_risk_assessment'
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
}


def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    执行指定工具并返回结果字符串。

    通过LangChain工具的 .invoke() 方法调用，兼容 @tool 装饰器的调用约定。

    Args:
        tool_name: 工具名称（需与TOOL_EXECUTORS中的key匹配）
        arguments: 工具参数字典

    Returns:
        str: 工具执行结果的字符串表示

    Raises:
        ValueError: 未知的工具名称
    """
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
