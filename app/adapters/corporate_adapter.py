# -*- coding: utf-8 -*-
"""
产业链/工商适配器 [NEW-FILE:#20260415-25]
Input: 公司名称/jurisdiction/company_id 等查询参数
Output: pd.DataFrame(search_company) / dict(get_company_details/get_company_network)
Pos: app/adapters层, 另类数据——企业注册与股权关系, 由Registry按 domain=corporate_entity 路由

OpenCorporates REST API 官方规范 (已交叉验证 ≥4 权威源, 检索时间 2026-04-15 12:16 +08:00)：
- https://api.opencorporates.com/documentation/API-Reference (官方API参考)
- https://opencorporates.com/info/our-data (数据覆盖: 140+司法辖区, 2亿+公司)
- https://api.opencorporates.com/v0.4/companies/search?q=... (搜索端点)
- https://api.opencorporates.com/v0.4/companies/{jurisdiction_code}/{company_number} (详情端点)
- 国家企业信用信息公示系统 https://www.gsxt.gov.cn/ (中国工商交叉来源, 公开查询无API)
- EU European Business Registers https://e-justice.europa.eu/content_business_registers-104-en.do (欧盟交叉源)

关键约束：
1. 免费层速率 500 calls/month (匿名) - 建议本地缓存
2. API Key 三级回退: 参数 > env OPENCORPORATES_API_KEY > 匿名
3. 无Key时端点仍可用但字段有限 & 速率更严, 必须优雅降级
4. 端点使用 HTTPS, UA 建议标识应用

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import os
import time
import logging
import threading
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class CorporateAdapter(BaseAdapter):
    """OpenCorporates 产业链/工商数据适配器

    端点：
    - GET /v0.4/companies/search?q={name}&jurisdiction_code={code}
    - GET /v0.4/companies/{jurisdiction_code}/{company_number}
    - GET /v0.4/companies/{jurisdiction_code}/{company_number}/network
    """

    BASE_URL = "https://api.opencorporates.com/v0.4"

    # 免费匿名层建议自限流：≥0.5s/req 以避免触发全局限额
    _MIN_INTERVAL = 0.5

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 15,
        user_agent: Optional[str] = None,
    ):
        """初始化

        Args:
            api_key: OpenCorporates API Token; 缺省从 env OPENCORPORATES_API_KEY 读取, 最后回退匿名
            timeout: 单次请求超时秒数
            user_agent: UA 标识, 缺省使用项目兜底
        """
        self.api_key = api_key or os.environ.get("OPENCORPORATES_API_KEY") or ""
        self.timeout = timeout
        self.user_agent = (
            user_agent
            or os.environ.get("OPENCORPORATES_UA")
            or "StockAnalSys/1.0 (+research@example.com)"
        )

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        })

        self._lock = threading.Lock()
        self._last_request_ts = 0.0

        if not self.api_key:
            logger.info(
                "CorporateAdapter 运行在匿名模式 (无OPENCORPORATES_API_KEY)，速率 500/月"
            )

    @property
    def name(self) -> str:
        return "opencorporates"

    # ----------------------------- 限流 -----------------------------

    def _throttle(self) -> None:
        """免费层最小间隔保护"""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_ts
            if elapsed < self._MIN_INTERVAL:
                time.sleep(self._MIN_INTERVAL - elapsed)
            self._last_request_ts = time.monotonic()

    def _get_json(self, path: str, params: Optional[dict] = None) -> dict:
        """统一GET。无Key降级, 失败返回空dict"""
        self._throttle()
        params = dict(params or {})
        if self.api_key:
            params["api_token"] = self.api_key
        url = f"{self.BASE_URL}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 401:
                logger.warning(
                    f"OpenCorporates 401 未授权, 可能 api_key 无效: {url}"
                )
                return {}
            if resp.status_code == 403:
                logger.warning(
                    f"OpenCorporates 403 禁止/免费层耗尽: {url}"
                )
                return {}
            if resp.status_code == 429:
                logger.warning(f"OpenCorporates 429 限流: {url}, 退避2s")
                time.sleep(2.0)
                return {}
            if resp.status_code != 200:
                logger.warning(
                    f"OpenCorporates HTTP {resp.status_code}: {url}"
                )
                return {}
            return resp.json() or {}
        except Exception as e:
            logger.warning(
                f"OpenCorporates 请求失败 {url}: {type(e).__name__}: {e}"
            )
            return {}

    # --------------------------- 核心端点 ---------------------------

    def search_company(
        self,
        name: str,
        jurisdiction: Optional[str] = None,
        per_page: int = 30,
    ) -> pd.DataFrame:
        """按名称搜索公司

        Args:
            name: 公司名称关键词 (必填, 空返回空DF)
            jurisdiction: 司法辖区代码 (如 us_ca, gb, cn); None 搜索全球
            per_page: 单页条数 (OpenCorporates 免费层上限 30)

        Returns:
            DataFrame columns: name, company_number, jurisdiction_code,
                               incorporation_date, company_type, current_status,
                               opencorporates_url
        """
        if not name or not str(name).strip():
            return pd.DataFrame()

        params: Dict = {"q": name.strip(), "per_page": int(per_page)}
        if jurisdiction:
            params["jurisdiction_code"] = jurisdiction.strip().lower()

        data = self._get_json("/companies/search", params=params)
        results = (data.get("results") or {}).get("companies") or []
        if not results:
            return pd.DataFrame()

        rows: List[Dict] = []
        for item in results:
            c = (item or {}).get("company") or {}
            rows.append({
                "name": c.get("name"),
                "company_number": c.get("company_number"),
                "jurisdiction_code": c.get("jurisdiction_code"),
                "incorporation_date": c.get("incorporation_date"),
                "company_type": c.get("company_type"),
                "current_status": c.get("current_status"),
                "opencorporates_url": c.get("opencorporates_url"),
            })
        return pd.DataFrame(rows)

    def get_company_details(self, company_id: str) -> dict:
        """公司详情

        Args:
            company_id: 格式 "{jurisdiction_code}/{company_number}",
                        如 "us_ca/C0806592" 或 "gb/01234567"

        Returns:
            dict: company 字段快照, 若失败返回空dict
        """
        if not company_id or "/" not in company_id:
            logger.debug(f"CorporateAdapter.get_company_details 非法id: {company_id!r}")
            return {}
        jurisdiction, number = company_id.split("/", 1)
        path = f"/companies/{quote(jurisdiction)}/{quote(number)}"
        data = self._get_json(path)
        return ((data.get("results") or {}).get("company") or {})

    def get_company_network(self, company_id: str) -> dict:
        """公司股权关系网络 (父/子/关联实体)

        Args:
            company_id: 同 get_company_details 格式

        Returns:
            dict: {"company_id": ..., "parents": [...], "children": [...], "officers": [...]}
                  失败时返回空字段的完整结构, 不抛异常
        """
        result = {
            "company_id": company_id or "",
            "parents": [],
            "children": [],
            "officers": [],
        }
        if not company_id or "/" not in company_id:
            return result

        details = self.get_company_details(company_id)
        if not details:
            return result

        # parents: controlling_entity 字段 (OpenCorporates schema)
        ce = details.get("controlling_entity") or {}
        if ce:
            result["parents"].append({
                "name": ce.get("name"),
                "jurisdiction_code": ce.get("jurisdiction_code"),
                "company_number": ce.get("company_number"),
            })

        # children: subsidiaries (OpenCorporates premium may omit; 空列表即可)
        for sub in (details.get("subsidiaries") or []):
            s = sub.get("subsidiary") or sub
            result["children"].append({
                "name": s.get("name"),
                "jurisdiction_code": s.get("jurisdiction_code"),
                "company_number": s.get("company_number"),
            })

        # officers: 董监高
        for off in (details.get("officers") or []):
            o = off.get("officer") or off
            result["officers"].append({
                "name": o.get("name"),
                "position": o.get("position"),
                "start_date": o.get("start_date"),
                "end_date": o.get("end_date"),
            })
        return result

    # ------------------------- Base 抽象方法 -------------------------

    def get_stock_history(
        self, code: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """OpenCorporates 不提供行情数据"""
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        """OpenCorporates 不提供指数成分股"""
        return []

    def get_stock_info(self, code: str) -> Dict:
        """以 code 作为 "{jurisdiction}/{number}" 查询公司简介"""
        if not code or "/" not in code:
            return {}
        d = self.get_company_details(code)
        if not d:
            return {}
        keys = [
            "name", "company_number", "jurisdiction_code",
            "incorporation_date", "dissolution_date", "company_type",
            "current_status", "registered_address_in_full",
            "opencorporates_url",
        ]
        return {k: d.get(k) for k in keys if k in d}

    def get_financial_data(self, code: str) -> Dict:
        """OpenCorporates 免费层不提供结构化财务数据"""
        return {}

    def health_check(self) -> bool:
        """轻量探活: 搜索一个常见关键词"""
        try:
            df = self.search_company("apple", per_page=1)
            return isinstance(df, pd.DataFrame) and not df.empty
        except Exception as e:
            logger.warning(
                f"CorporateAdapter 健康检查失败: {type(e).__name__}: {e}"
            )
            return False
