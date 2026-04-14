"""
Input: 搜索关键词
Output: 搜索结果列表
Pos: app/core/search.py - 搜索门面(Facade)，代理到 search_engines.multi_search（17引擎）

一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。
"""
import logging
from typing import List, Dict

from app.core.search_engines import multi_search, search_one, list_engines

logger = logging.getLogger(__name__)


def search_web(query: str, max_results: int = 5, engine: str = "auto") -> List[Dict]:
    """
    统一搜索接口（自动降级 fallback 链）

    Args:
        query: 查询关键词
        max_results: 返回结果数
        engine: 引擎名（'auto'默认，或 'baidu'/'duckduckgo'/'wikipedia'/'wolframalpha'/...）
                也可 'concurrent' 触发并发多引擎去重合并
    Returns:
        [{title, content, url, source}, ...]
    """
    try:
        return multi_search(query, engine=engine, n_results=max_results)
    except Exception as e:
        logger.warning(f"search_web 失败: {e}")
        return []


def search_stock_news_unified(stock_code: str, stock_name: str = '', max_results: int = 5) -> List[Dict]:
    """搜索股票相关新闻（中文优化，news fallback 链）"""
    queries = [
        f"{stock_code} {stock_name} 股票 最新消息",
        f"{stock_name} 行业分析 投资",
    ]
    all_results: List[Dict] = []
    seen_urls = set()
    for q in queries:
        try:
            results = multi_search(q, engine="auto", n_results=3, chain="news")
        except Exception as e:
            logger.debug(f"search_stock_news_unified 分支失败 {q}: {e}")
            results = []
        for r in results:
            u = r.get("url")
            if u and u not in seen_urls:
                seen_urls.add(u)
                all_results.append(r)
    return all_results[:max_results]


# 保留旧符号，便于 tools.py 仍能 import 到
__all__ = ["search_web", "search_stock_news_unified", "multi_search", "search_one", "list_engines"]
