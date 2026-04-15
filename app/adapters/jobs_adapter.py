# -*- coding: utf-8 -*-
"""
招聘信号适配器 [NEW-FILE:#20260415-26]
Input: query(关键词/职位)、source(数据源标识)、company(公司名)、limit
Output: pd.DataFrame(招聘职位列表 / 某公司发帖统计)
Pos: app/adapters层, 另类数据——招聘扩张信号, 由Registry按 domain=hiring_signal 路由

招聘数据源权威参考 (已交叉验证 ≥4 源, 检索时间 2026-04-15 12:16 +08:00)：
- Arbeitnow 开源招聘API https://www.arbeitnow.com/api/job-board-api (免费无Key, JSON Feed)
- Arbeitnow 文档 https://documenter.getpostman.com/view/18545278/UVJbJdKh
- 拉勾网公开搜索 https://www.lagou.com/jobs/list_?px=default (需 UA 伪装, 反爬严)
- BOSS直聘 https://www.zhipin.com/ (反爬严, 备注非P0)
- GitHub Jobs 已于 2021-04 关闭 (https://docs.github.com/changelog/2021-04-19-deprecation-notice-github-jobs-site)
  故剔除, 改用 Arbeitnow 替代作为免费开源招聘API主源
- LinkedIn 公开页面反爬严, 非本适配器主路径 (仅文档备注)

无Key策略：
- Arbeitnow: 完全免费无Key, 主路径
- Lagou: 纯HTTP公开搜索端点 + UA伪装, 降级候选 (反爬概率高, 失败返回空)

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import os
import time
import logging
import threading
from typing import Dict, List, Optional

import requests
import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class JobsAdapter(BaseAdapter):
    """招聘信号统一适配器 (arbeitnow / lagou)

    使用方式：
        a = JobsAdapter()
        df = a.search_jobs("python", source="arbeitnow", limit=20)
        df_c = a.get_company_postings("Apple")
    """

    ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
    LAGOU_URL = "https://www.lagou.com/jobs/positionAjax.json"

    # UA 伪装 (拉勾反爬, 非欺骗用途, 仅为保证公开端点可访问)
    _FAKE_UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    _MIN_INTERVAL = 0.5

    SUPPORTED_SOURCES = ("arbeitnow", "lagou")

    def __init__(self, timeout: int = 15, user_agent: Optional[str] = None):
        self.timeout = timeout
        self.user_agent = (
            user_agent
            or os.environ.get("JOBS_ADAPTER_UA")
            or "StockAnalSys/1.0 (+research@example.com)"
        )

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        })

        self._lock = threading.Lock()
        self._last_request_ts = 0.0

    @property
    def name(self) -> str:
        return "jobs_adapter"

    # ------------------------- 限流 -------------------------

    def _throttle(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_ts
            if elapsed < self._MIN_INTERVAL:
                time.sleep(self._MIN_INTERVAL - elapsed)
            self._last_request_ts = time.monotonic()

    def _get_json(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> dict:
        """统一GET返回JSON; 失败返回空dict"""
        self._throttle()
        try:
            resp = self.session.get(
                url,
                params=params or {},
                headers=headers or {},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                logger.warning(f"JobsAdapter HTTP {resp.status_code}: {url}")
                return {}
            return resp.json() or {}
        except Exception as e:
            logger.warning(
                f"JobsAdapter 请求失败 {url}: {type(e).__name__}: {e}"
            )
            return {}

    # ------------------------- 源: arbeitnow -------------------------

    def _search_arbeitnow(self, query: str, limit: int) -> pd.DataFrame:
        """Arbeitnow Job Board API: 免费无Key, 返回最近职位

        Arbeitnow 不接受 q 参数, 需客户端过滤 title/description 中的 query
        """
        data = self._get_json(self.ARBEITNOW_URL)
        items = data.get("data") or []
        if not items:
            return pd.DataFrame()

        q = (query or "").strip().lower()
        rows: List[Dict] = []
        for it in items:
            title = (it.get("title") or "").strip()
            desc = (it.get("description") or "").strip()
            tags = it.get("tags") or []
            haystack = f"{title} {desc} {' '.join(tags)}".lower()
            if q and q not in haystack:
                continue
            rows.append({
                "title": title,
                "company": it.get("company_name"),
                "location": it.get("location"),
                "remote": bool(it.get("remote")),
                "tags": ",".join(tags) if isinstance(tags, list) else "",
                "url": it.get("url"),
                "created_at": it.get("created_at"),
                "source": "arbeitnow",
            })
            if len(rows) >= int(limit):
                break
        return pd.DataFrame(rows)

    # ------------------------- 源: lagou -------------------------

    def _search_lagou(self, query: str, limit: int) -> pd.DataFrame:
        """拉勾网公开搜索 (UA伪装, 反爬严, 失败降级空)"""
        headers = {
            "User-Agent": self._FAKE_UA,
            "Referer": "https://www.lagou.com/",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        params = {"needAddtionalResult": "false", "city": "全国", "first": "true"}
        data_payload = {"kd": query, "pn": 1}

        self._throttle()
        try:
            resp = self.session.post(
                self.LAGOU_URL,
                params=params,
                data=data_payload,
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                logger.warning(f"Lagou HTTP {resp.status_code}")
                return pd.DataFrame()
            data = resp.json() or {}
        except Exception as e:
            logger.warning(f"Lagou 请求失败: {type(e).__name__}: {e}")
            return pd.DataFrame()

        items = (((data.get("content") or {}).get("positionResult") or {})
                 .get("result") or [])
        if not items:
            return pd.DataFrame()

        rows: List[Dict] = []
        for it in items[: int(limit)]:
            rows.append({
                "title": it.get("positionName"),
                "company": it.get("companyFullName") or it.get("companyShortName"),
                "location": it.get("city"),
                "remote": False,
                "tags": ",".join(it.get("positionLables") or []),
                "url": f"https://www.lagou.com/jobs/{it.get('positionId')}.html"
                       if it.get("positionId") else None,
                "created_at": it.get("createTime"),
                "source": "lagou",
            })
        return pd.DataFrame(rows)

    # ------------------------- 统一入口 -------------------------

    def search_jobs(
        self,
        query: str,
        source: str = "arbeitnow",
        limit: int = 20,
    ) -> pd.DataFrame:
        """统一职位搜索

        Args:
            query: 关键词/职位名 (空串对 arbeitnow 等于返回全部前 limit 条)
            source: 数据源 arbeitnow / lagou
            limit: 返回条数上限
        """
        src = (source or "arbeitnow").strip().lower()
        if src not in self.SUPPORTED_SOURCES:
            logger.warning(
                f"JobsAdapter 不支持的 source={src!r}, 自动回退 arbeitnow"
            )
            src = "arbeitnow"

        limit = max(1, int(limit or 20))
        if src == "arbeitnow":
            return self._search_arbeitnow(query or "", limit)
        if src == "lagou":
            return self._search_lagou(query or "", limit)
        return pd.DataFrame()

    def get_company_postings(self, company: str) -> pd.DataFrame:
        """某公司招聘帖子 (扩张信号估算)

        通过 arbeitnow 全量拉取 + 客户端按 company_name 过滤计数,
        返回 DataFrame (可对 len(df) 直接作为岗位数估计)
        """
        if not company or not str(company).strip():
            return pd.DataFrame()
        data = self._get_json(self.ARBEITNOW_URL)
        items = data.get("data") or []
        if not items:
            return pd.DataFrame()

        target = company.strip().lower()
        rows: List[Dict] = []
        for it in items:
            cname = (it.get("company_name") or "").strip()
            if target not in cname.lower():
                continue
            rows.append({
                "title": it.get("title"),
                "company": cname,
                "location": it.get("location"),
                "remote": bool(it.get("remote")),
                "tags": ",".join(it.get("tags") or []),
                "url": it.get("url"),
                "created_at": it.get("created_at"),
                "source": "arbeitnow",
            })
        return pd.DataFrame(rows)

    # ------------------------- Base 抽象方法 -------------------------

    def get_stock_history(
        self, code: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        return []

    def get_stock_info(self, code: str) -> Dict:
        """以 code 作为公司名 返回招聘概况摘要"""
        df = self.get_company_postings(code)
        if df is None or df.empty:
            return {}
        return {
            "company": code,
            "posting_count": int(len(df)),
            "locations": sorted({x for x in df["location"].dropna().tolist() if x}),
            "source": "arbeitnow",
        }

    def get_financial_data(self, code: str) -> Dict:
        return {}

    def health_check(self) -> bool:
        """探活: Arbeitnow 列表非空即视为可用"""
        try:
            data = self._get_json(self.ARBEITNOW_URL)
            return bool(data.get("data"))
        except Exception as e:
            logger.warning(
                f"JobsAdapter 健康检查失败: {type(e).__name__}: {e}"
            )
            return False
