"""
Input: MCP协议请求(stock_code, date_range等)
Output: MCP协议响应(股票数据、技术指标等)
Pos: app/mcp/stock_data_server.py - 股票数据MCP Server

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# MCP Server 配置
MCP_SERVER_CONFIG = {
    'name': 'stockanal-data-server',
    'version': '1.0.0',
    'description': 'StockAnal_Sys 股票数据MCP服务器',
    'tools': [
        {
            'name': 'get_stock_history',
            'description': '获取A股历史K线数据',
            'parameters': {
                'stock_code': {'type': 'string', 'description': '6位股票代码'},
                'days': {'type': 'integer', 'description': '获取天数', 'default': 120},
            }
        },
        {
            'name': 'get_technical_analysis',
            'description': '获取股票技术分析(MA/RSI/MACD/评分)',
            'parameters': {
                'stock_code': {'type': 'string', 'description': '6位股票代码'},
                'market_type': {'type': 'string', 'description': '市场类型', 'default': 'A'},
            }
        },
        {
            'name': 'get_financial_data',
            'description': '获取股票基本面财务数据',
            'parameters': {
                'stock_code': {'type': 'string', 'description': '6位股票代码'},
            }
        },
        {
            'name': 'get_capital_flow',
            'description': '获取个股资金流向',
            'parameters': {
                'stock_code': {'type': 'string', 'description': '6位股票代码'},
            }
        },
        {
            'name': 'search_news',
            'description': '搜索股票相关新闻',
            'parameters': {
                'query': {'type': 'string', 'description': '搜索关键词'},
                'max_results': {'type': 'integer', 'description': '最大结果数', 'default': 5},
            }
        },
    ]
}


def handle_mcp_tool_call(tool_name: str, arguments: dict) -> Any:
    """处理MCP工具调用"""
    handlers = {
        'get_stock_history': _handle_stock_history,
        'get_technical_analysis': _handle_technical_analysis,
        'get_financial_data': _handle_financial_data,
        'get_capital_flow': _handle_capital_flow,
        'search_news': _handle_search_news,
    }

    handler = handlers.get(tool_name)
    if not handler:
        return {'error': f'未知工具: {tool_name}'}

    try:
        return handler(**arguments)
    except Exception as e:
        logger.error(f"MCP工具调用失败({tool_name}): {e}")
        return {'error': str(e)}


def _handle_stock_history(stock_code: str, days: int = 120) -> dict:
    """获取股票历史K线数据"""
    from datetime import datetime, timedelta
    from app.core.data_provider import get_data_provider
    dp = get_data_provider()
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    df = dp.get_stock_history(stock_code, start_date, end_date)
    if df is None or df.empty:
        return {'error': f'未获取到{stock_code}数据'}
    return {'data': df.tail(20).to_dict('records'), 'total_rows': len(df)}


def _handle_technical_analysis(stock_code: str, market_type: str = 'A') -> dict:
    """获取股票技术分析结果"""
    from app.analysis.stock_analyzer import StockAnalyzer
    analyzer = StockAnalyzer()
    result = analyzer.quick_analyze_stock(stock_code, market_type)
    return result


def _handle_financial_data(stock_code: str) -> dict:
    """获取股票基本面财务数据"""
    from app.analysis.fundamental_analyzer import FundamentalAnalyzer
    fa = FundamentalAnalyzer()
    return fa.get_financial_indicators(stock_code)


def _handle_capital_flow(stock_code: str) -> dict:
    """获取个股资金流向数据"""
    from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
    cfa = CapitalFlowAnalyzer()
    return cfa.get_individual_fund_flow(stock_code)


def _handle_search_news(query: str, max_results: int = 5) -> dict:
    """搜索股票相关新闻"""
    try:
        from app.core.search import search_web
        return {'results': search_web(query, max_results)}
    except ImportError:
        from app.analysis.news_fetcher import news_fetcher
        return {'results': news_fetcher.get_latest_news(days=1, limit=max_results)}
