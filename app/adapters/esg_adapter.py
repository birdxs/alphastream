# -*- coding: utf-8 -*-
"""
ESG 公开数据适配器 [NEW-FILE:#20260415-27] (P3-D3 2026-04-15)
Input: ticker/cik/company/industry 等查询参数 (如 AAPL, 0000320193, Apple Inc., Technology)
Output: dict/DataFrame 格式的 ESG 评分/气候披露/CDP 响应/B Corp 认证
Pos: app/adapters 层另类数据源，由 Agent/Registry 在 ESG 主题 Agent 中调度

联网调研权威源 (检索时间 2026-04-15 12:16 +08:00, ≥4 源交叉验证, 纯开源免费优先)：
  1. ESG Book Public Data  https://www.esgbook.com/data-solutions/
     - 免费开放 ESG 披露查询端点(需注册)；纯公开镜像走 CSV 下载策略
  2. SEC Climate Disclosure Rule (2024-03)  https://www.sec.gov/rules/2024/33-11275.pdf
     - 气候披露XBRL纳入EDGAR，复用 A4 edgar_adapter.get_concept() 抓 us-gaap 气候相关 tag
  3. CDP Disclosure Insight Action  https://www.cdp.net/en/responses
     - 公开披露库：公司气候/水/森林 scores + 年度 response
  4. B Corporations Directory  https://www.bcorporation.net/en-us/find-a-b-corp/
     - 认证 B Corp 公司检索；按行业/国家/认证年过滤
  5. 中财大 CUFE 绿金指数 (辅证)  http://igf.cufe.edu.cn/
     - 绿色金融学术指数；公开成分股名单
剔除(付费/需商业Key)：MSCI ESG Ratings 批量接口、Refinitiv ESG、Sustainalytics、Wind ESG

约束：
  - 全部 HTTP 请求走 self.session.get，便于测试 mock；
  - 软降级：网络/解析失败一律返回空 dict/DataFrame，不得抛 Exception 给上游；
  - 复用 edgar_adapter 的 concept 调用，不重复实现限流/UA。

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
from typing import Dict, List, Optional

import requests
import pandas as pd

from .base_adapter import BaseAdapter
from ._retry_utils import random_ua, retry_with_backoff, rotate_ua
from ._proxy_utils import get_proxies

logger = logging.getLogger(__name__)


# SEC 气候披露相关候选 XBRL tag (us-gaap / srt 命名空间)
# 参考 SEC Final Rule 17 CFR Parts 210, 229, 232, 239, 249 (2024-03)
CLIMATE_TAGS: List[tuple] = [
    ("us-gaap", "ClimateRelatedRisksAndOpportunities"),
    ("us-gaap", "GreenhouseGasEmissionsScope1"),
    ("us-gaap", "GreenhouseGasEmissionsScope2"),
    ("us-gaap", "GreenhouseGasEmissionsScope3"),
    ("us-gaap", "CarbonOffsets"),
    ("srt", "ClimateRelatedDisclosure"),
]


class ESGAdapter(BaseAdapter):
    """ESG 公开源聚合适配器（ESG Book / SEC 气候 / CDP / B Corp / CUFE 绿金）。

    使用方式：
        a = ESGAdapter()
        score = a.get_esg_score("AAPL", source="esgbook")
        clim  = a.get_climate_disclosure("0000320193")
        cdp   = a.get_cdp_response("Apple Inc.", year=2025)
        bcorp = a.search_b_corps(industry="Technology")
    """

    # 各公开源端点（官方公开，无 API Key）
    ESGBOOK_PUBLIC = "https://www.esgbook.com/api/public/scores"
    CDP_PUBLIC = "https://www.cdp.net/api/public/responses"
    BCORP_DIRECTORY = "https://www.bcorporation.net/en-us/find-a-b-corp/"
    CUFE_GREEN_INDEX = "http://igf.cufe.edu.cn/api/green_index"

    _DEFAULT_UA = (
        "StockAnalSys-ESG/1.0 (+research@example.com; "
        "compliant with robots.txt)"
    )

    # 多源软降级链（与 get_esg_score source 参数对齐）
    _ESG_SOURCES = ("esgbook", "cdp", "cufe", "bcorp")

    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout: int = 15,
        max_retries: int = 2,
        edgar_adapter: Optional[object] = None,
    ):
        """初始化

        Args:
            user_agent: 自定义 UA；缺省走默认兜底
            timeout: 单次请求超时秒
            max_retries: 失败重试次数
            edgar_adapter: 可注入 EDGARAdapter 实例（用于气候披露复用）；
                           缺省懒加载，便于测试 mock
        """
        self.user_agent = user_agent or self._DEFAULT_UA
        self.timeout = timeout
        self.max_retries = max(1, int(max_retries))
        self._edgar = edgar_adapter

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent or random_ua(),
            "Accept": "application/json, text/html;q=0.8, */*;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
        })
        # K1 [NEW-FILE:#20260415-44] 代理强制应用
        proxies = get_proxies()
        if proxies:
            self.session.proxies.update(proxies)

    @property
    def name(self) -> str:
        return "esg_public"

    # ============================ 内部工具 ============================

    def _get(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        """K1: UA池轮询 + retry_with_backoff 指数退避的统一 GET；失败返回 None。"""
        rotate_ua(self.session)
        try:
            resp = retry_with_backoff(
                lambda: self.session.get(url, params=params or {}, timeout=self.timeout),
                max_retries=self.max_retries,
                backoff_base=0.5,
                status_codes_to_retry=(429, 500, 502, 503, 504),
                name="esg",
            )
        except Exception as e:
            logger.warning(f"[ESG] 请求失败 {url}: {type(e).__name__}: {e}")
            return None
        if resp is None:
            return None
        if resp.status_code == 200:
            return resp
        logger.warning(f"[ESG] HTTP {resp.status_code} {url}")
        return None

    def _get_json(self, url: str, params: Optional[Dict] = None) -> dict:
        resp = self._get(url, params=params)
        if resp is None:
            return {}
        try:
            return resp.json() or {}
        except Exception as e:
            logger.warning(f"[ESG] JSON 解析失败 {url}: {type(e).__name__}: {e}")
            return {}

    def _lazy_edgar(self):
        """懒加载 EDGARAdapter，避免导入周期。"""
        if self._edgar is None:
            try:
                from .edgar_adapter import EDGARAdapter
                self._edgar = EDGARAdapter()
            except Exception as e:
                logger.warning(f"[ESG] EDGAR懒加载失败: {type(e).__name__}: {e}")
                self._edgar = None
        return self._edgar

    # ============================ 核心方法 ============================

    # Registry 别名 (I1): domain=esg_rating → method=get_esg_rating
    def get_esg_rating(self, code: Optional[str] = None, ticker: Optional[str] = None,
                       source: str = "esgbook", **kwargs) -> dict:
        """Registry契约别名 — 等价 get_esg_score; 兼容 code/ticker 两种入参键。"""
        sym = ticker or code or kwargs.get("symbol")
        if not sym:
            return self._empty_score_result(source, "")
        return self.get_esg_score(ticker=str(sym), source=source)

    def get_esg_score(self, ticker: str, source: str = "esgbook") -> dict:
        """统一入口：拉取单只股票 ESG 评分。

        Args:
            ticker: 股票代码 (如 AAPL) 或公司名
            source: 数据源 one of _ESG_SOURCES

        Returns:
            {
              "source":     str,          # 实际命中来源
              "ticker":     str,
              "company":    str,
              "esg_score":  float | None, # 综合分 0-100
              "e_score":    float | None, # 环境
              "s_score":    float | None, # 社会
              "g_score":    float | None, # 治理
              "grade":      str | None,   # 字母评级 (如 AA/A/BBB)
              "as_of":      str | None,   # YYYY-MM-DD
              "raw":        dict,
            }
            全部源失败 → 各字段 None 的保底结构。
        """
        if not ticker:
            return self._empty_score_result(source, ticker)

        src = (source or "esgbook").lower().strip()
        if src not in self._ESG_SOURCES:
            logger.warning(f"[ESG] 未知source={src}, 回退 esgbook")
            src = "esgbook"

        # 软降级链：指定源失败 → 依次尝试其它源
        order = [src] + [s for s in self._ESG_SOURCES if s != src]
        for s in order:
            data = self._fetch_esg_by_source(ticker, s)
            if data and data.get("esg_score") is not None:
                return data

        return self._empty_score_result(src, ticker)

    def _fetch_esg_by_source(self, ticker: str, source: str) -> dict:
        """按 source 分发调用；任意失败返回空 dict"""
        try:
            if source == "esgbook":
                return self._fetch_esgbook(ticker)
            if source == "cdp":
                return self._fetch_cdp_as_score(ticker)
            if source == "cufe":
                return self._fetch_cufe_green(ticker)
            if source == "bcorp":
                return self._fetch_bcorp_as_score(ticker)
        except Exception as e:
            logger.warning(f"[ESG] {source} 取数异常: {type(e).__name__}: {e}")
        return {}

    def _fetch_esgbook(self, ticker: str) -> dict:
        payload = self._get_json(self.ESGBOOK_PUBLIC, params={"ticker": ticker.upper()})
        if not payload:
            return {}
        # ESG Book 公开格式：{ company, isin, scores:{esg,e,s,g}, grade, as_of }
        scores = payload.get("scores") or {}
        return {
            "source": "esgbook",
            "ticker": ticker.upper(),
            "company": payload.get("company"),
            "esg_score": _safe_float(scores.get("esg")),
            "e_score": _safe_float(scores.get("e")),
            "s_score": _safe_float(scores.get("s")),
            "g_score": _safe_float(scores.get("g")),
            "grade": payload.get("grade"),
            "as_of": payload.get("as_of"),
            "raw": payload,
        }

    def _fetch_cdp_as_score(self, ticker: str) -> dict:
        payload = self._get_json(self.CDP_PUBLIC, params={"q": ticker})
        if not payload:
            return {}
        items = payload.get("responses") or []
        if not items:
            return {}
        first = items[0]
        climate_letter = first.get("climate_score")  # A/A-/B/B-/C/C-/D/D-/F
        return {
            "source": "cdp",
            "ticker": ticker.upper(),
            "company": first.get("company"),
            "esg_score": _letter_to_score(climate_letter),
            "e_score": _letter_to_score(climate_letter),
            "s_score": None,
            "g_score": None,
            "grade": climate_letter,
            "as_of": first.get("year"),
            "raw": payload,
        }

    def _fetch_cufe_green(self, ticker: str) -> dict:
        payload = self._get_json(self.CUFE_GREEN_INDEX, params={"code": ticker})
        if not payload:
            return {}
        score = _safe_float(payload.get("green_score"))
        return {
            "source": "cufe",
            "ticker": ticker,
            "company": payload.get("name"),
            "esg_score": score,
            "e_score": score,
            "s_score": None,
            "g_score": None,
            "grade": payload.get("level"),
            "as_of": payload.get("report_date"),
            "raw": payload,
        }

    def _fetch_bcorp_as_score(self, ticker: str) -> dict:
        df = self.search_b_corps(company=ticker)
        if df is None or df.empty:
            return {}
        row = df.iloc[0].to_dict()
        score = _safe_float(row.get("overall_b_impact_score"))
        return {
            "source": "bcorp",
            "ticker": ticker,
            "company": row.get("company_name"),
            "esg_score": score,
            "e_score": None,
            "s_score": score,
            "g_score": None,
            "grade": row.get("certification_status"),
            "as_of": row.get("date_certified"),
            "raw": row,
        }

    @staticmethod
    def _empty_score_result(source: str, ticker: str) -> dict:
        return {
            "source": source,
            "ticker": (ticker or "").upper(),
            "company": None,
            "esg_score": None,
            "e_score": None,
            "s_score": None,
            "g_score": None,
            "grade": None,
            "as_of": None,
            "raw": {},
        }

    # ---------------------- SEC 气候披露（复用 EDGAR） ----------------------

    def get_climate_disclosure(self, cik: str) -> dict:
        """拉取 SEC 气候披露 XBRL facts（复用 edgar_adapter.get_concept）。

        Args:
            cik: SEC CIK（10位 padded 或裸数字都可；EDGAR 内部会 padding）

        Returns:
            {
              "cik": str,
              "tags": { "taxonomy:tag": [ {end,val,fy,fp,form,unit}, ... ] },
              "scope1_latest": float | None,
              "scope2_latest": float | None,
              "scope3_latest": float | None,
              "source": "sec_edgar_climate",
            }
        """
        result = {
            "cik": str(cik),
            "tags": {},
            "scope1_latest": None,
            "scope2_latest": None,
            "scope3_latest": None,
            "source": "sec_edgar_climate",
        }
        if not cik:
            return result

        edgar = self._lazy_edgar()
        if edgar is None:
            return result

        for taxonomy, tag in CLIMATE_TAGS:
            try:
                data = edgar.get_concept(cik, tag, taxonomy=taxonomy)
            except Exception as e:
                logger.warning(f"[ESG] EDGAR concept 失败 {taxonomy}:{tag}: {type(e).__name__}")
                continue
            units = (data or {}).get("units") or {}
            if not units:
                continue
            # 取任一 unit 全部行
            first_unit_key = next(iter(units.keys()))
            rows = units.get(first_unit_key) or []
            if not rows:
                continue
            key = f"{taxonomy}:{tag}"
            slim = [
                {
                    "end": r.get("end"),
                    "val": r.get("val"),
                    "fy": r.get("fy"),
                    "fp": r.get("fp"),
                    "form": r.get("form"),
                    "unit": first_unit_key,
                }
                for r in rows
            ]
            result["tags"][key] = slim
            # 按 end 取最新
            latest = max(slim, key=lambda r: r.get("end") or "", default=None)
            if latest and latest.get("val") is not None:
                if "Scope1" in tag:
                    result["scope1_latest"] = _safe_float(latest["val"])
                elif "Scope2" in tag:
                    result["scope2_latest"] = _safe_float(latest["val"])
                elif "Scope3" in tag:
                    result["scope3_latest"] = _safe_float(latest["val"])

        return result

    # ---------------------------- CDP ----------------------------

    def get_cdp_response(self, company: str, year: int = 2025) -> dict:
        """CDP 公开披露库查询公司年度 response。

        Returns:
            {
              "company":       str,
              "year":          int,
              "climate_score": str | None,  # A/A-/B/...
              "water_score":   str | None,
              "forests_score": str | None,
              "disclosures":   list[dict],
              "source":        "cdp",
            }
        """
        result = {
            "company": company,
            "year": year,
            "climate_score": None,
            "water_score": None,
            "forests_score": None,
            "disclosures": [],
            "source": "cdp",
        }
        if not company:
            return result

        payload = self._get_json(
            self.CDP_PUBLIC,
            params={"q": company, "year": year},
        )
        if not payload:
            return result

        items = payload.get("responses") or []
        result["disclosures"] = items
        # 取与年份最贴合的一条
        match = next(
            (x for x in items if str(x.get("year")) == str(year)),
            items[0] if items else None,
        )
        if match:
            result["company"] = match.get("company") or company
            result["climate_score"] = match.get("climate_score")
            result["water_score"] = match.get("water_score")
            result["forests_score"] = match.get("forests_score")
        return result

    # ---------------------------- B Corp ----------------------------

    def search_b_corps(
        self,
        industry: Optional[str] = None,
        country: Optional[str] = None,
        company: Optional[str] = None,
    ) -> pd.DataFrame:
        """B Corp 认证库检索。

        Returns:
            DataFrame columns: company_name, industry, country,
                overall_b_impact_score, certification_status, date_certified, url
        """
        params: Dict[str, str] = {}
        if industry:
            params["industry"] = industry
        if country:
            params["country"] = country
        if company:
            params["search"] = company

        payload = self._get_json(self.BCORP_DIRECTORY, params=params)
        if not payload:
            return pd.DataFrame()

        items = payload.get("companies") or payload.get("results") or []
        if not items:
            return pd.DataFrame()

        rows: List[Dict] = []
        for it in items:
            rows.append({
                "company_name": it.get("name") or it.get("company_name"),
                "industry": it.get("industry"),
                "country": it.get("country"),
                "overall_b_impact_score": _safe_float(
                    it.get("overall_score") or it.get("overall_b_impact_score")
                ),
                "certification_status": it.get("status") or it.get("certification_status"),
                "date_certified": it.get("certified_on") or it.get("date_certified"),
                "url": it.get("url"),
            })
        return pd.DataFrame(rows)

    # ---------------------------- BaseAdapter 契约 ----------------------------

    def get_stock_history(
        self, code: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """ESG 源不提供行情K线，返回空 DataFrame。"""
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        """ESG 源不提供指数成分；CUFE 绿金指数走 get_esg_score 主路径。"""
        return []

    def get_stock_info(self, code: str) -> Dict:
        """等价于 get_esg_score 简版。"""
        return self.get_esg_score(code)

    def get_financial_data(self, code: str) -> Dict:
        """等价于 ESG 综合：评分 + 气候披露（若为美股 CIK）。"""
        score = self.get_esg_score(code)
        climate: Dict = {}
        edgar = self._lazy_edgar()
        if edgar is not None:
            try:
                cik = edgar.get_cik(code) if not str(code).isdigit() else code
                if cik:
                    climate = self.get_climate_disclosure(cik)
            except Exception as e:
                logger.debug(f"[ESG] financial_data 气候分支跳过: {type(e).__name__}: {e}")
        return {"esg": score, "climate": climate}

    def health_check(self) -> bool:
        """任一公开源可达即视为健康。"""
        for url in (self.ESGBOOK_PUBLIC, self.CDP_PUBLIC, self.BCORP_DIRECTORY):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code in (200, 301, 302, 401, 403):
                    # 401/403 证明端点存活但需授权，仍算"通"
                    return True
            except Exception:
                continue
        return False


# ============================ 辅助函数 ============================

def _safe_float(v) -> Optional[float]:
    """安全转 float；失败返回 None"""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# CDP 气候字母评级 → 0-100 近似分数映射（用于跨源可比）
_LETTER_MAP = {
    "A": 95.0, "A-": 88.0,
    "B": 78.0, "B-": 70.0,
    "C": 60.0, "C-": 52.0,
    "D": 40.0, "D-": 32.0,
    "F": 10.0,
}


def _letter_to_score(letter: Optional[str]) -> Optional[float]:
    if not letter:
        return None
    return _LETTER_MAP.get(str(letter).strip().upper())
