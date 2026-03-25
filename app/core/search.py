"""
Input: 搜索关键词
Output: 搜索结果列表
Pos: app/core/search.py - 统一搜索引擎接口(多源降级: DuckDuckGo -> Tavily -> SERP)

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """统一搜索接口，自动降级：DuckDuckGo -> Tavily -> SERP -> 空结果"""
    results = []

    # 优先使用 DuckDuckGo（免费无限制，无需API key）
    results = _search_duckduckgo(query, max_results)
    if results:
        return results

    # 降级到 Tavily
    results = _search_tavily(query, max_results)
    if results:
        return results

    # 降级到 SERP
    results = _search_serp(query, max_results)
    if results:
        return results

    logger.warning(f"所有搜索引擎均失败: {query}")
    return []


def _search_duckduckgo(query: str, max_results: int = 5) -> List[Dict]:
    """DuckDuckGo搜索（免费，无需API key）"""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    'title': r.get('title', ''),
                    'content': r.get('body', ''),
                    'url': r.get('href', ''),
                    'source': 'duckduckgo'
                })
            return results
    except ImportError:
        logger.debug("duckduckgo-search 未安装，跳过")
        return []
    except Exception as e:
        logger.warning(f"DuckDuckGo搜索失败: {e}")
        return []


def _search_tavily(query: str, max_results: int = 5) -> List[Dict]:
    """Tavily搜索（需API key）"""
    api_key = os.getenv('TAVILY_API_KEY')
    if not api_key:
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=max_results, search_depth="basic")
        results = []
        for r in response.get('results', []):
            results.append({
                'title': r.get('title', ''),
                'content': r.get('content', ''),
                'url': r.get('url', ''),
                'source': 'tavily'
            })
        return results
    except Exception as e:
        logger.warning(f"Tavily搜索失败: {e}")
        return []


def _search_serp(query: str, max_results: int = 5) -> List[Dict]:
    """SERP API搜索（需API key）"""
    api_key = os.getenv('SERP_API_KEY')
    if not api_key:
        return []
    try:
        import requests
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": max_results}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        data = response.json()
        results = []
        for r in data.get('organic', [])[:max_results]:
            results.append({
                'title': r.get('title', ''),
                'content': r.get('snippet', ''),
                'url': r.get('link', ''),
                'source': 'serp'
            })
        return results
    except Exception as e:
        logger.warning(f"SERP搜索失败: {e}")
        return []


def search_stock_news_unified(stock_code: str, stock_name: str = '', max_results: int = 5) -> List[Dict]:
    """搜索股票相关新闻（中文优化查询）"""
    queries = [
        f"{stock_code} {stock_name} 股票 最新消息",
        f"{stock_name} 行业分析 投资"
    ]
    all_results = []
    seen_urls = set()
    for q in queries:
        results = search_web(q, max_results=3)
        for r in results:
            if r.get('url') not in seen_urls:
                seen_urls.add(r.get('url'))
                all_results.append(r)
    return all_results[:max_results]
