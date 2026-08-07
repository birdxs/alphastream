"""
Input: 搜索关键词 query + engine名 + max_results
Output: 统一格式的搜索结果 List[Dict(title, content, url, source)]
Pos: app/core/search_engines.py - 17引擎多源搜索层（移植自 yanran_digital_life/search_skill）

一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。
设计：
- 17个引擎（8中文域 + 9全球/知识域），全部无需API key，纯 HTML 抓取 + 官方API(Wikipedia) + 可选 Tavily/SERP/Brave API key。
- 统一 `multi_search(query, engine='auto', n_results=5)` 入口。
- `engine='auto'` 走 fallback 链；可明确指定 `engine='wolframalpha'`/`'wikipedia'`/`'baidu'` 等。
- 并发多引擎 `multi_search(..., engine='concurrent')` → 聚合去重。
- 所有引擎失败容错，不抛出异常；通过日志记录。
"""
from __future__ import annotations
import os
import re
import logging
import time
import concurrent.futures
from typing import List, Dict, Optional, Callable
from urllib.parse import quote, urlparse, parse_qs, unquote

logger = logging.getLogger(__name__)

# 默认UA
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_DEFAULT_TIMEOUT = 12


# ====== 17 引擎配置（源自 yanran_digital_life/config/skills/search_engines.json 20260410实测）======
ENGINES_CONFIG: Dict[str, Dict] = {
    # 中文域
    "baidu": {
        "url": "https://www.baidu.com/s?wd={q}&rn={n}",
        "container": "div.result.c-container",
        "title_sel": "h3 a",
        "snippet_sel": ".content-right_8Zs40, .c-abstract, .c-span-last",
        "region": "cn",
    },
    "sogou": {
        "url": "https://www.sogou.com/web?query={q}",
        "container": ".results .vrwrap, .results .rb",
        "title_sel": "h3 a, a.tit",
        "snippet_sel": ".fz-mid, .str-info, .str_info",
        "region": "cn",
    },
    "so360": {
        "url": "https://www.so.com/s?q={q}",
        "container": "li.res-list, div.result",
        "title_sel": "h3.res-title a, .result-title",
        "snippet_sel": ".res-desc, .result-desc",
        "region": "cn",
    },
    "wechat": {   # 微信搜一搜(搜狗入口)
        "url": "https://weixin.sogou.com/weixin?type=2&query={q}",
        "container": ".news-list li, .txt-box",
        "title_sel": "h3 a, h4 a",
        "snippet_sel": ".txt-info, .abstract",
        "region": "cn",
    },
    "toutiao": {
        "url": "https://so.toutiao.com/search?keyword={q}",
        "container": ".result-content, .cs-view, div[data-testid='result-item']",
        "title_sel": ".title a, .cs-title, h3",
        "snippet_sel": ".abstract, .cs-abstract, .ttp-text",
        "region": "cn",
    },
    "jisilu": {  # 集思录 投资社区站内
        "url": "https://www.jisilu.cn/explore/?keyword={q}",
        "container": ".topic-item, .article-item",
        "title_sel": "h3 a, .title a",
        "snippet_sel": ".content, .abstract",
        "region": "cn",
    },
    "bing_cn": {
        "url": "https://cn.bing.com/search?q={q}&ensearch=0",
        "container": "li.b_algo",
        "title_sel": "h2 a",
        "snippet_sel": ".b_caption p, .b_snippet",
        "region": "cn",
    },
    "zhihu": {  # 知乎站内（用搜狗引流最可靠）
        "url": "https://www.sogou.com/web?query={q}+site:zhihu.com",
        "container": ".results .vrwrap, .results .rb",
        "title_sel": "h3 a, a.tit",
        "snippet_sel": ".fz-mid, .str-info, .str_info",
        "region": "cn",
    },
    # 全球域
    "duckduckgo_html": {
        "url": "https://duckduckgo.com/html/?q={q}",
        "container": "div.result.results_links, div.result",
        "title_sel": "a.result__a",
        "snippet_sel": "a.result__snippet, .result__snippet",
        "region": "global",
    },
    "bing": {
        "url": "https://cn.bing.com/search?q={q}&ensearch=1",
        "container": "li.b_algo",
        "title_sel": "h2 a",
        "snippet_sel": ".b_caption p, .b_snippet",
        "region": "global",
    },
    "brave": {
        "url": "https://search.brave.com/search?q={q}",
        "container": "div.snippet, div[data-type='web']",
        "title_sel": "a.h, .title, h3 a",
        "snippet_sel": ".snippet-description, .snippet-content",
        "region": "global",
    },
    "qwant": {
        "url": "https://www.qwant.com/?q={q}",
        "container": "article, div[data-testid='webResult']",
        "title_sel": "a[data-testid='serTitle'], h2 a",
        "snippet_sel": "span[data-testid='serDesc'], .description",
        "region": "global",
    },
    "startpage": {
        "url": "https://www.startpage.com/sp/search?query={q}",
        "container": "div.w-gl__result, section.w-gl",
        "title_sel": "a.w-gl__result-title, h3 a",
        "snippet_sel": ".w-gl__description, p.w-gl__description",
        "region": "global",
    },
    "ecosia": {
        "url": "https://www.ecosia.org/search?q={q}",
        "container": "div.result, article.result",
        "title_sel": "a.result-title, a.title",
        "snippet_sel": ".result-snippet, .description",
        "region": "global",
    },
    # 特殊 / API 类
    "duckduckgo": {"special": "ddgs_api", "region": "global"},           # 通过 ddgs/duckduckgo_search pypi
    "wikipedia": {"special": "wikipedia_api", "region": "knowledge"},     # MediaWiki REST API
    "wolframalpha": {"special": "wolframalpha", "region": "knowledge"},  # HTML 抓取
}

# fallback 链
FALLBACK_CHAINS = {
    "auto": ["duckduckgo", "baidu", "bing_cn", "sogou", "so360", "wechat", "brave"],
    "cn":   ["baidu", "sogou", "so360", "wechat", "toutiao", "bing_cn"],
    "global": ["duckduckgo", "brave", "bing", "qwant", "duckduckgo_html"],
    "news": ["wechat", "toutiao", "baidu", "sogou", "so360"],
    "knowledge": ["wikipedia", "wolframalpha", "brave", "baidu"],
    "privacy": ["duckduckgo", "brave", "qwant", "startpage"],
}


def _disabled_engines() -> set:
    """读取环境变量 SEARCH_DISABLED_ENGINES=baidu,brave 禁用特定引擎"""
    raw = os.getenv("SEARCH_DISABLED_ENGINES", "")
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


# ====== 公用抓取层 ======
def _http_get(url: str, timeout: int = _DEFAULT_TIMEOUT) -> Optional[str]:
    try:
        import requests
        headers = {
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        proxy = os.getenv("DUCKDUCKGO_PROXY") or os.getenv("HTTPS_PROXY") or ""
        proxies = {"http": proxy, "https": proxy} if proxy else None
        r = requests.get(url, headers=headers, timeout=timeout, proxies=proxies)
        if r.status_code != 200:
            logger.debug(f"[search_engines] GET {url} → {r.status_code}")
            return None
        return r.text
    except Exception as e:
        logger.debug(f"[search_engines] GET失败 {url}: {e}")
        return None


def _parse_generic(html: str, cfg: Dict, engine: str, max_results: int) -> List[Dict]:
    """通用 CSS 选择器 HTML 解析"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("[search_engines] bs4 未安装，无法HTML解析；请 pip install beautifulsoup4")
        return []
    try:
        soup = BeautifulSoup(html, "html.parser")
        results: List[Dict] = []
        for item in soup.select(cfg["container"])[: max_results * 2]:
            title_el = item.select_one(cfg["title_sel"])
            snip_el = item.select_one(cfg["snippet_sel"])
            if not title_el:
                continue
            title = title_el.get_text(" ", strip=True)
            url = title_el.get("href", "") or ""
            snippet = snip_el.get_text(" ", strip=True) if snip_el else ""
            if not title or not url:
                continue
            results.append({
                "title": title[:200],
                "content": snippet[:400],
                "url": url,
                "source": engine,
            })
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        logger.debug(f"[search_engines] 解析{engine}失败: {e}")
        return []


# ====== 特殊引擎 ======
def _search_ddgs_api(query: str, max_results: int) -> List[Dict]:
    """ddgs/duckduckgo_search pypi 包"""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        proxy = os.getenv("DUCKDUCKGO_PROXY") or None
        with DDGS(timeout=15, proxy=proxy) if proxy else DDGS(timeout=15) as ddgs:
            results = []
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "content": r.get("body", ""),
                    "url": r.get("href", ""),
                    "source": "duckduckgo",
                })
            return results
    except Exception as e:
        logger.debug(f"[search_engines] ddgs 失败: {e}")
        return []


def _search_wikipedia(query: str, max_results: int) -> List[Dict]:
    """Wikipedia REST / MediaWiki API，中文优先再降级英文"""
    import requests
    out: List[Dict] = []
    for lang in ("zh", "en"):
        try:
            url = (
                f"https://{lang}.wikipedia.org/w/api.php"
                f"?action=query&list=search&srsearch={quote(query)}"
                f"&format=json&srlimit={max_results}"
            )
            # Wikimedia 要求具体UA(项目名+联系方式) https://meta.wikimedia.org/wiki/User-Agent_policy
            wiki_ua = "StockAnalSys/1.0 (https://github.com/lc2panda/alphastream; contact via GitHub) python-requests"
            r = requests.get(url, headers={"User-Agent": wiki_ua, "Accept": "application/json"}, timeout=8)
            try:
                data = r.json()
            except Exception:
                logger.debug(f"[search_engines] wikipedia 非JSON响应: {r.status_code} {r.text[:120]}")
                continue
            for item in data.get("query", {}).get("search", [])[:max_results]:
                page_title = item.get("title", "")
                snippet_raw = item.get("snippet", "")
                snippet = re.sub(r"<[^>]+>", "", snippet_raw)
                page_url = f"https://{lang}.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'))}"
                out.append({
                    "title": page_title,
                    "content": snippet[:400],
                    "url": page_url,
                    "source": f"wikipedia_{lang}",
                })
            if out:
                return out
        except Exception as e:
            logger.debug(f"[search_engines] wikipedia {lang} 失败: {e}")
    return out


def _search_wolframalpha(query: str, max_results: int) -> List[Dict]:
    """WolframAlpha 结构化答案（HTML抓取meta description）"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []
    url = f"https://www.wolframalpha.com/input?i={quote(query)}"
    html = _http_get(url, timeout=20)
    if not html:
        return []
    try:
        soup = BeautifulSoup(html, "html.parser")
        title_el = soup.select_one("title")
        title = title_el.get_text(strip=True) if title_el else f"WolframAlpha: {query}"
        meta = soup.select_one('meta[name="description"]')
        desc = meta.get("content", "") if meta else ""
        answers = []
        for img in soup.select("img[alt]")[:6]:
            alt = (img.get("alt") or "").strip()
            if alt and len(alt) > 5 and alt.lower() not in ("logo", "image"):
                answers.append(alt)
        snippet = desc or " | ".join(answers[:3]) or f"WolframAlpha 查询: {query}"
        return [{
            "title": title[:200],
            "content": snippet[:500],
            "url": url,
            "source": "wolframalpha",
        }]
    except Exception as e:
        logger.debug(f"[search_engines] wolframalpha 异常: {e}")
        return []


def _search_tavily_api(query: str, max_results: int) -> List[Dict]:
    """Tavily API(可选 key)"""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        resp = client.search(query, max_results=max_results, search_depth="basic")
        return [{
            "title": r.get("title", ""),
            "content": r.get("content", ""),
            "url": r.get("url", ""),
            "source": "tavily",
        } for r in resp.get("results", [])]
    except Exception as e:
        logger.debug(f"[search_engines] tavily 失败: {e}")
        return []


def _search_serp_api(query: str, max_results: int) -> List[Dict]:
    """Serper/SERP API(可选 key)"""
    api_key = os.getenv("SERP_API_KEY")
    if not api_key:
        return []
    try:
        import requests
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=10,
        )
        data = r.json()
        return [{
            "title": it.get("title", ""),
            "content": it.get("snippet", ""),
            "url": it.get("link", ""),
            "source": "serp",
        } for it in data.get("organic", [])[:max_results]]
    except Exception as e:
        logger.debug(f"[search_engines] serp 失败: {e}")
        return []


SPECIAL_HANDLERS: Dict[str, Callable[[str, int], List[Dict]]] = {
    "ddgs_api": _search_ddgs_api,
    "wikipedia_api": _search_wikipedia,
    "wolframalpha": _search_wolframalpha,
    "tavily": _search_tavily_api,
    "serp": _search_serp_api,
}


# ====== 统一引擎调度 ======
def search_one(engine: str, query: str, max_results: int = 5) -> List[Dict]:
    """执行单个引擎搜索，返回归一化结果 list"""
    engine = engine.lower()
    if engine in _disabled_engines():
        logger.debug(f"[search_engines] 引擎 {engine} 已被 SEARCH_DISABLED_ENGINES 禁用")
        return []
    cfg = ENGINES_CONFIG.get(engine)
    if not cfg:
        # 允许动态的 tavily/serp 作为补充
        if engine in SPECIAL_HANDLERS:
            return SPECIAL_HANDLERS[engine](query, max_results)
        logger.debug(f"[search_engines] 未知引擎: {engine}")
        return []
    if "special" in cfg:
        handler = SPECIAL_HANDLERS.get(cfg["special"])
        return handler(query, max_results) if handler else []
    # 通用 HTML 抓取
    url = cfg["url"].format(q=quote(query), n=max_results)
    html = _http_get(url)
    if not html or len(html) < 200:
        return []
    return _parse_generic(html, cfg, engine, max_results)


def multi_search(
    query: str,
    engine: str = "auto",
    n_results: int = 5,
    chain: str = "auto",
) -> List[Dict]:
    """
    统一搜索入口 - 供 LLM tool 调用

    Args:
        query: 搜索关键词
        engine: 引擎名，或 'auto' 走 fallback 链，或 'concurrent' 并发多引擎合并
        n_results: 返回结果数
        chain: 当 engine='auto'/'concurrent' 时，指定使用的 fallback 链名
               (auto/cn/global/news/knowledge/privacy)

    Returns:
        [{title, content, url, source}, ...]
    """
    engine = (engine or "auto").lower()

    # 指定单引擎
    if engine not in ("auto", "concurrent"):
        results = search_one(engine, query, n_results)
        if results:
            return results
        logger.debug(f"[search_engines] {engine} 无结果，启用 auto 兜底")
        engine = "auto"

    # 拿 fallback 链
    chain_name = chain if chain in FALLBACK_CHAINS else "auto"
    engines_chain = FALLBACK_CHAINS[chain_name]
    # 附加可选 API 引擎
    if os.getenv("TAVILY_API_KEY"):
        engines_chain = engines_chain + ["tavily"]
    if os.getenv("SERP_API_KEY"):
        engines_chain = engines_chain + ["serp"]

    if engine == "concurrent":
        return _concurrent_search(query, engines_chain, n_results)

    # auto - 串行 fallback
    for eng in engines_chain:
        try:
            results = search_one(eng, query, n_results)
            if results:
                logger.info(f"[search_engines] 命中引擎: {eng} ({len(results)}条)")
                return results
        except Exception as e:
            logger.debug(f"[search_engines] 引擎 {eng} 异常: {e}")
    logger.warning(f"[search_engines] 所有引擎失败: {query}")
    return []


def _concurrent_search(query: str, engines: List[str], n_results: int) -> List[Dict]:
    """并发多引擎 + 去重合并（URL为key）。返回前 n_results 条（按出现次数加权排序）"""
    all_results: List[Dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(engines))) as ex:
        future_map = {ex.submit(search_one, eng, query, n_results): eng for eng in engines[:6]}
        for fut in concurrent.futures.as_completed(future_map, timeout=20):
            try:
                all_results.extend(fut.result() or [])
            except Exception as e:
                logger.debug(f"[search_engines] 并发分支 {future_map[fut]} 异常: {e}")

    # URL去重 + score
    seen: Dict[str, Dict] = {}
    for r in all_results:
        url = (r.get("url") or "").split("#")[0]
        if not url:
            continue
        if url in seen:
            seen[url]["_score"] = seen[url].get("_score", 1) + 1
            seen[url]["source"] = seen[url]["source"] + "+" + r["source"]
        else:
            r["_score"] = 1
            seen[url] = r
    merged = sorted(seen.values(), key=lambda x: -x.get("_score", 0))
    for r in merged:
        r.pop("_score", None)
    return merged[:n_results]


# ====== 列出可用引擎（便于运维/诊断）======
def list_engines() -> List[str]:
    disabled = _disabled_engines()
    return [name for name in ENGINES_CONFIG.keys() if name not in disabled]
