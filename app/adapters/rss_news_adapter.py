# -*- coding: utf-8 -*-
"""
RSS 新闻聚合适配器 — 华尔街见闻 / 财联社 / 雪球头条 / 新浪财经 / 金融界 / 央视财经
Input: source(源名) / limit(条数) / keyword(关键词) / sources(源列表)
Output: pd.DataFrame[source, title, link, published, summary, author, tags]
Pos: app/adapters层 — 新闻情绪/事件驱动Agent的资讯底座；feedparser软依赖，未装降级空DF；只研究用途

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

权威源（≥3交叉验证, 检索时间 2026-04-15 12:30 +08:00）：
  1) feedparser 官方库 https://github.com/kurtmckee/feedparser (MIT, 2k+⭐, v6.0.11)
     https://pypi.org/project/feedparser/ — Atom/RSS 0.9x–2.0/RDF 统一解析
  2) 新浪财经 RSS 官方入口 https://rss.sina.com.cn/news/allnews/finance.xml
     https://roll.finance.sina.com.cn/ (滚动新闻源)
  3) RSShub 公共路由 https://docs.rsshub.app/ (MIT, 32k+⭐)
     - 华尔街见闻: https://rsshub.app/wallstreetcn/news/global
     - 财联社电报: https://rsshub.app/cls/telegraph
     - 雪球头条:   https://rsshub.app/xueqiu/hots
     - 金融界:     https://rsshub.app/jrj/news/list
     - 央视财经:   https://rsshub.app/cctv/caijing
  4) 华尔街见闻官网 https://wallstreetcn.com/ — 官方无RSS，RSShub代理
  5) 金融界 https://www.jrj.com.cn/ — 旧版 rss.jrj.com.cn 已下线，统一走RSShub
  6) 雪球 https://xueqiu.com/ — 官方无公开RSS，RSShub代理 xqtl

合规：仅研究用途；UA伪装；超时10s + 3次重试；并发≤4；去重基于 title_hash。
"""
import time
import hashlib
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import pandas as pd

from .base_adapter import BaseAdapter
from ._retry_utils import UA_POOL as _SHARED_UA_POOL, random_ua

logger = logging.getLogger(__name__)

try:
    import feedparser  # type: ignore
    _HAS_FEEDPARSER = True
except ImportError:
    feedparser = None  # type: ignore
    _HAS_FEEDPARSER = False
    logger.warning("feedparser 未安装，RSSNewsAdapter 降级为空DF；pip install feedparser")


# 内置 FEED_SOURCES 映射：官方优先 + RSShub备选
FEED_SOURCES: Dict[str, Dict[str, str]] = {
    "wallstreetcn": {
        "name": "华尔街见闻",
        "url": "https://rsshub.app/wallstreetcn/news/global",
        "fallback": "https://rsshub.rssforever.com/wallstreetcn/news/global",
    },
    "cls": {
        "name": "财联社",
        "url": "https://rsshub.app/cls/telegraph",
        "fallback": "https://rsshub.rssforever.com/cls/telegraph",
    },
    "xueqiu": {
        "name": "雪球头条",
        "url": "https://rsshub.app/xueqiu/hots",
        "fallback": "https://rsshub.rssforever.com/xueqiu/hots",
    },
    "sina_finance": {
        "name": "新浪财经",
        "url": "https://rss.sina.com.cn/news/allnews/finance.xml",
        "fallback": "https://rsshub.app/sina/finance",
    },
    "jrj": {
        "name": "金融界",
        "url": "https://rsshub.app/jrj/news/list",
        "fallback": "https://rsshub.rssforever.com/jrj/news/list",
    },
    "cctv_finance": {
        "name": "央视财经",
        "url": "https://rsshub.app/cctv/caijing",
        "fallback": "https://rsshub.rssforever.com/cctv/caijing",
    },
}

# K1: 复用 _retry_utils.UA_POOL (8+ UA) 提升反爬对抗
_UA_POOL = list(_SHARED_UA_POOL)

_EMPTY_COLUMNS = ["source", "title", "link", "published", "summary", "author", "tags"]


class RSSNewsAdapter(BaseAdapter):
    """RSS 新闻聚合适配器

    - 并发抓取 (ThreadPoolExecutor, max_workers=4)
    - 超时 10s + 3 次重试 (含主URL→fallback切换)
    - 去重基于 sha1(title)
    - 输出统一 schema: source/title/link/published/summary/author/tags
    """

    TIMEOUT = 10
    MAX_RETRIES = 3
    MAX_WORKERS = 4

    def __init__(self, timeout: int = 10, max_retries: int = 3, max_workers: int = 4):
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_workers = max_workers

    # ------------------------------------------------------------
    # BaseAdapter 契约 (新闻源对K线/财务不适用，均返回空)
    # ------------------------------------------------------------
    @property
    def name(self) -> str:
        return "rss_news"

    def get_stock_history(self, code, start_date, end_date, adjust="qfq"):
        return pd.DataFrame()

    def get_index_stocks(self, index_code):
        return []

    def get_stock_info(self, code):
        return {}

    def get_financial_data(self, code):
        return {}

    def health_check(self) -> bool:
        return _HAS_FEEDPARSER

    # ------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------
    def _ua(self) -> str:
        return random.choice(_UA_POOL)

    def _parse_feed(self, url: str) -> Optional[object]:
        """K1: UA池轮询 + 指数退避 + Referer伪造；失败返回 None。"""
        if not _HAS_FEEDPARSER:
            return None
        last_err: Optional[Exception] = None
        # 反爬Referer: rsshub站点伪造主页来源
        headers_base = {
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        }
        if "rsshub" in url:
            headers_base["Referer"] = "https://docs.rsshub.app/"
        elif "sina" in url:
            headers_base["Referer"] = "https://finance.sina.com.cn/"
        for attempt in range(1, self.max_retries + 1):
            try:
                req_headers = dict(headers_base)
                req_headers["User-Agent"] = self._ua()
                parsed = feedparser.parse(url, request_headers=req_headers)
                entries = getattr(parsed, "entries", []) or []
                bozo = getattr(parsed, "bozo", 0)
                if not entries and bozo:
                    raise RuntimeError(f"feedparser bozo: {getattr(parsed, 'bozo_exception', None)}")
                return parsed
            except Exception as e:  # pragma: no cover
                last_err = e
                logger.debug("feedparser 第%d次失败 url=%s err=%s", attempt, url, e)
                # K1: 指数退避 + jitter
                time.sleep(min(4.0, 0.5 * (2 ** (attempt - 1))) + random.random() * 0.3)
        logger.warning("feedparser 解析失败 url=%s err=%s", url, last_err)
        return None

    def _entry_to_row(self, entry, source_key: str) -> Dict:
        tags_raw = getattr(entry, "tags", None) or []
        tags: List[str] = []
        try:
            tags = [t.get("term") if isinstance(t, dict) else getattr(t, "term", "") for t in tags_raw]
            tags = [t for t in tags if t]
        except Exception:
            tags = []
        return {
            "source": source_key,
            "title": (getattr(entry, "title", "") or "").strip(),
            "link": getattr(entry, "link", "") or "",
            "published": getattr(entry, "published", "") or getattr(entry, "updated", "") or "",
            "summary": (getattr(entry, "summary", "") or "").strip(),
            "author": getattr(entry, "author", "") or "",
            "tags": ",".join(tags) if tags else "",
        }

    def get_feed(self, source: str, limit: int = 50) -> pd.DataFrame:
        """拉取单个源的 RSS 新闻。

        Args:
            source: FEED_SOURCES 的 key, 如 wallstreetcn
            limit: 最多返回条数
        """
        if source not in FEED_SOURCES:
            logger.warning("未知RSS源 source=%s; 合法值=%s", source, list(FEED_SOURCES.keys()))
            return pd.DataFrame(columns=_EMPTY_COLUMNS)
        if not _HAS_FEEDPARSER:
            return pd.DataFrame(columns=_EMPTY_COLUMNS)

        cfg = FEED_SOURCES[source]
        parsed = self._parse_feed(cfg["url"])
        if parsed is None or not getattr(parsed, "entries", None):
            # 主URL失败 → fallback
            fb = cfg.get("fallback")
            if fb:
                parsed = self._parse_feed(fb)
        if parsed is None or not getattr(parsed, "entries", None):
            return pd.DataFrame(columns=_EMPTY_COLUMNS)

        rows = [self._entry_to_row(e, source) for e in parsed.entries[:limit]]
        df = pd.DataFrame(rows, columns=_EMPTY_COLUMNS)
        return df

    def get_all_feeds(
        self,
        sources: Optional[List[str]] = None,
        limit_per_source: int = 50,
    ) -> pd.DataFrame:
        """并发拉取多源并聚合去重。

        Args:
            sources: 限定拉取的源 key 列表；None = 全部
            limit_per_source: 每源最多条数
        """
        if not _HAS_FEEDPARSER:
            return pd.DataFrame(columns=_EMPTY_COLUMNS)

        targets = sources if sources else list(FEED_SOURCES.keys())
        targets = [s for s in targets if s in FEED_SOURCES]
        if not targets:
            return pd.DataFrame(columns=_EMPTY_COLUMNS)

        results: List[pd.DataFrame] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(targets))) as ex:
            fut_map = {ex.submit(self.get_feed, s, limit_per_source): s for s in targets}
            for fut in as_completed(fut_map):
                src = fut_map[fut]
                try:
                    df = fut.result()
                    if df is not None and not df.empty:
                        results.append(df)
                except Exception as e:  # pragma: no cover
                    logger.warning("并发拉取 %s 异常: %s", src, e)

        if not results:
            return pd.DataFrame(columns=_EMPTY_COLUMNS)

        merged = pd.concat(results, ignore_index=True)

        # 去重：title 的 sha1
        def _hash(t: str) -> str:
            return hashlib.sha1((t or "").strip().encode("utf-8", errors="ignore")).hexdigest()

        merged["_h"] = merged["title"].map(_hash)
        merged = merged.drop_duplicates(subset=["_h"], keep="first").drop(columns=["_h"])
        merged = merged.reset_index(drop=True)
        return merged

    def search_news(
        self,
        keyword: str,
        sources: Optional[List[str]] = None,
        limit_per_source: int = 50,
    ) -> pd.DataFrame:
        """关键词过滤（title / summary / tags 任一命中即保留，大小写不敏感）。"""
        df = self.get_all_feeds(sources=sources, limit_per_source=limit_per_source)
        if df.empty or not keyword:
            return df
        kw = str(keyword).strip().lower()
        if not kw:
            return df

        def _hit(row) -> bool:
            for col in ("title", "summary", "tags"):
                v = str(row.get(col, "") or "").lower()
                if kw in v:
                    return True
            return False

        mask = df.apply(_hit, axis=1)
        return df[mask].reset_index(drop=True)

    # ============================ Registry 别名 (I1) ============================
    # domain="news" → agent 调用统一 method "get_latest_news"
    # 签名对齐 app/agents/*.py _registry_fetch('news','get_latest_news', code=..., days=..., limit=...)
    def get_latest_news(
        self,
        code: Optional[str] = None,
        days: int = 7,
        limit: int = 20,
        sources: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict]:
        """统一新闻入口 — Registry domain=news.get_latest_news 契约。

        Args:
            code: 个股代码 (可选) — 有则做关键词过滤
            days: 时间窗 (目前仅作为提示, RSS源已是近期)
            limit: 返回上限
            sources: 限定源; None=全部
        Returns:
            List[Dict] (records格式); 空降级 []
        """
        try:
            if code:
                df = self.search_news(keyword=str(code), sources=sources, limit_per_source=limit)
            else:
                df = self.get_all_feeds(sources=sources, limit_per_source=limit)
            if df is None or df.empty:
                return []
            df = df.head(int(max(1, limit)))
            return df.to_dict(orient="records")
        except Exception as e:
            logger.warning("[RSSNews] get_latest_news 失败 code=%s: %s", code, e)
            return []
