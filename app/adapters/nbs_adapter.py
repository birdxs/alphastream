# -*- coding: utf-8 -*-
"""
国家统计局 (NBS) 开放接口适配器 — GDP/CPI/PMI/工业增加值 等宏观指标
Input: dbcode(数据库代码 hgjd/hgyd/hgnd) / rowcode(指标zb树代码) / sj(时期编码 LAST10/LAST13/2023)
Output: pd.DataFrame[date, indicator, value, unit, code]  统一的"时期×指标×值"长表
Pos: app/adapters层 — 宏观/宏观研究Agent的基础数据源；无需Key；未通降级为空DF
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

权威源（≥3交叉验证, 检索时间 2026-04-15 12:00 +08:00）：
  1) 国家统计局-国家数据 https://data.stats.gov.cn/
     - easyquery.htm 接口：m=QueryData & dbcode & rowcode & colcode=sj & wds=[] & k1=<ms_ts>
     - 数据库代码体系：hgjd=季度 / hgyd=月度 / hgnd=年度 / fsyd=分省月度
  2) 指标树接口 easyquery.htm?id=<parentId>&dbcode=<db>&wdcode=zb&m=getTree
     — GDP根节点 A01 / 价格指数 A09 / PMI A0B / 工业 A02
  3) 开源实现 GitHub awolfly9/tushare + PyStat (stats.gov.cn爬虫), 5k+⭐
     https://github.com/awolfly9/stats-gov-cn
  4) sj时期编码规则: LAST10 最近10期 / LAST13 最近13期 / 2023 指定单年

合规：仅研究用途；UA伪装普通浏览器；带重试+超时；官方无明确QPS限制但推荐≤1QPS。
"""
import time
import random
import logging
from typing import Dict, List, Optional

import requests
import pandas as pd

from .base_adapter import BaseAdapter
from ._retry_utils import get_thread_local_session, random_ua, retry_with_backoff, rotate_ua
from ._proxy_utils import get_proxies

logger = logging.getLogger(__name__)


# 国家统计局指标树：常用宏观指标 rowcode (zb代码)
# 来源：easyquery.htm?id=A01&dbcode=hgjd&wdcode=zb&m=getTree 递归展开
_KNOWN_INDICATORS = {
    # GDP 季度 hgjd
    "gdp_total":          ("hgjd", "A010101"),   # GDP当季值(亿元)
    "gdp_yoy":            ("hgjd", "A010102"),   # GDP当季同比(%)
    # CPI 月度 hgyd
    "cpi_yoy":            ("hgyd", "A01010G01"), # CPI同比(上年同月=100)
    "cpi_mom":            ("hgyd", "A01010G02"), # CPI环比
    # PMI 月度 hgyd
    "pmi_manufacturing":  ("hgyd", "A0B0101"),   # 制造业PMI
    "pmi_nonmanufacturing": ("hgyd", "A0B0201"), # 非制造业PMI
    # 工业增加值 月度 hgyd
    "industrial_yoy":     ("hgyd", "A020102"),   # 规模以上工业增加值同比
    "industrial_accum":   ("hgyd", "A020103"),   # 累计同比
}


class NBSAdapter(BaseAdapter):
    """国家统计局开放接口适配器

    端点：
      - https://data.stats.gov.cn/easyquery.htm?m=QueryData&... (通用查询)
      - https://data.stats.gov.cn/easyquery.htm?m=getTree&...  (指标树，本类未暴露)
    """

    BASE_URL = "https://data.stats.gov.cn/easyquery.htm"
    DEFAULT_TIMEOUT = 15
    MAX_RETRIES = 4  # K1: 403 反爬需更多尝试
    # 推荐 ≤1 QPS，两次请求间隔
    _MIN_INTERVAL = 1.0

    # K1 [NEW-FILE:#20260415-44] UA 改为 UA_POOL 轮询

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        # S3-A3 2026-05-20: 改用 thread-local session，每线程独立，避免并发竞态
        self._last_request_ts = 0.0

    @property
    def _session(self) -> requests.Session:
        """thread-local session，每线程独立，避免并发竞态（S3-A3）"""
        sess = get_thread_local_session(
            referer="https://data.stats.gov.cn/",
            extra_headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            namespace="nbs",
        )
        proxies = get_proxies()
        if proxies:
            sess.proxies.update(proxies)
        return sess

    @property
    def name(self) -> str:
        return "nbs"

    # ---------- 通用 easyquery ----------

    def query(self, dbcode: str, rowcode: str, colcode: str = "sj",
              sj: str = "LAST10") -> pd.DataFrame:
        """通用 easyquery 查询

        Args:
            dbcode: 数据库代码 hgjd/hgyd/hgnd/fsyd
            rowcode: 指标zb代码 如 A010101
            colcode: 列维度，默认 sj (时期)
            sj: 时期编码 LAST10 / LAST13 / 2023 / 2020-2023 等

        Returns:
            DataFrame[date, code, value, unit] — 统一扁平长表；失败返回空DF
        """
        params = {
            "m": "QueryData",
            "dbcode": dbcode,
            "rowcode": rowcode,
            "colcode": colcode,
            "wds": "[]",
            "dfwds": f'[{{"wdcode":"{colcode}","valuecode":"{sj}"}}]',
            "k1": str(int(time.time() * 1000)),
            "h": "1",
        }
        raw = self._get_json(self.BASE_URL, params)
        if not raw:
            return pd.DataFrame()
        return self._parse_easyquery(raw)

    # ---------- 快捷封装 ----------

    def get_gdp(self, freq: str = "quarterly") -> pd.DataFrame:
        """GDP — freq: quarterly(hgjd,默认)/yearly(hgnd)"""
        dbcode = "hgnd" if freq == "yearly" else "hgjd"
        # GDP 当季值 A010101；年度使用 A020101（GDP总量年度）
        rowcode = "A020101" if dbcode == "hgnd" else "A010101"
        df = self.query(dbcode=dbcode, rowcode=rowcode,
                        sj="LAST13" if dbcode == "hgjd" else "LAST10")
        if not df.empty:
            df["indicator"] = "GDP"
            df["freq"] = freq
        return df

    def get_cpi(self, freq: str = "monthly") -> pd.DataFrame:
        """CPI — freq: monthly(hgyd,默认)/yearly(hgnd)"""
        dbcode = "hgnd" if freq == "yearly" else "hgyd"
        rowcode = "A01010G01"  # CPI 同比
        df = self.query(dbcode=dbcode, rowcode=rowcode, sj="LAST13")
        if not df.empty:
            df["indicator"] = "CPI_YoY"
            df["freq"] = freq
        return df

    def get_pmi(self) -> pd.DataFrame:
        """制造业 PMI (月度)"""
        df = self.query(dbcode="hgyd", rowcode="A0B0101", sj="LAST13")
        if not df.empty:
            df["indicator"] = "PMI_Manufacturing"
            df["freq"] = "monthly"
        return df

    def get_industrial_output(self) -> pd.DataFrame:
        """规模以上工业增加值同比 (月度)"""
        df = self.query(dbcode="hgyd", rowcode="A020102", sj="LAST13")
        if not df.empty:
            df["indicator"] = "IndustrialOutput_YoY"
            df["freq"] = "monthly"
        return df

    def get_macro_indicators(
        self, indicators: Optional[List[str]] = None
    ) -> Dict[str, pd.DataFrame]:
        """J1 [NEW-FILE:#20260415-43] 中国宏观指标 alias — agent 统一入口。

        Args:
            indicators: 可选列表，支持 "GDP"/"CPI"/"PMI"/"IndustrialOutput"；
                        None→ 返回全部四项。

        Returns:
            Dict[key, DataFrame]；失败的 key 跳过，全失败返回空 dict。
        """
        mapping = {
            "GDP": self.get_gdp,
            "CPI": self.get_cpi,
            "PMI": self.get_pmi,
            "IndustrialOutput": self.get_industrial_output,
        }
        keys = indicators or list(mapping.keys())
        out: Dict[str, pd.DataFrame] = {}
        for k in keys:
            fn = mapping.get(k)
            if fn is None:
                continue
            try:
                df = fn()
                if isinstance(df, pd.DataFrame) and not df.empty:
                    out[k] = df
            except Exception as e:
                logger.warning(f"[NBSAdapter] get_macro_indicators({k}) 失败: {type(e).__name__}: {e}")
        return out

    # ---------- BaseAdapter 抽象方法 (宏观源不提供个股) ----------

    def get_stock_history(self, code, start_date, end_date, adjust="qfq") -> pd.DataFrame:
        logger.info("NBS为宏观源，不提供个股K线")
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        return []

    def get_stock_info(self, code: str) -> Dict:
        return {}

    def get_financial_data(self, code: str) -> Dict:
        return {}

    def health_check(self) -> bool:
        """健康检查：拉一条CPI短序列"""
        try:
            df = self.query(dbcode="hgyd", rowcode="A01010G01", sj="LAST3")
            return not df.empty
        except Exception as e:
            logger.warning(f"NBS健康检查失败: {type(e).__name__}: {e}")
            return False

    # ---------- 内部 ----------

    def _get_json(self, url: str, params: Dict) -> Optional[Dict]:
        """K1: UA池轮询 + retry_with_backoff (429/5xx/403指数退避)，失败返回None"""
        # 限流
        elapsed = time.time() - self._last_request_ts
        if elapsed < self._MIN_INTERVAL:
            time.sleep(self._MIN_INTERVAL - elapsed)

        # 每请求轮换UA，增强反爬
        rotate_ua(self._session)

        try:
            resp = retry_with_backoff(
                lambda: self._session.get(url, params=params,
                                          timeout=self.timeout, verify=False),
                max_retries=self.MAX_RETRIES,
                backoff_base=0.8,
                # 国统局偶现 403 伪 Not-Found，加入重试码尝试 UA 轮换
                status_codes_to_retry=(403, 429, 500, 502, 503, 504),
                name="nbs",
            )
            self._last_request_ts = time.time()
            if resp is None or resp.status_code != 200:
                logger.warning(f"NBS最终失败 status={getattr(resp,'status_code',None)}")
                return None
            try:
                data = resp.json()
            except Exception as je:
                logger.warning(f"NBS JSON解析失败: {je}")
                return None
            if data.get("returncode") == 200:
                return data
            logger.warning(f"NBS业务错误 returncode={data.get('returncode')}")
            return None
        except Exception as e:
            logger.error(f"NBS请求最终失败: {type(e).__name__}: {e}")
            return None

    @staticmethod
    def _parse_easyquery(raw: Dict) -> pd.DataFrame:
        """将NBS easyquery JSON 扁平化为长表

        NBS 返回结构：
          returndata:
            datanodes: [{code:"zbcode_sjcode", data:{data:val,strdata:..}, wds:[...]}]
            wdnodes:   [{wdcode:"zb"/"sj", nodes:[{code,cname,unit}]}]
        """
        try:
            rd = raw.get("returndata", {})
            datanodes = rd.get("datanodes", [])
            wdnodes = rd.get("wdnodes", [])

            # 构建 code → {cname, unit} 映射
            meta: Dict[str, Dict] = {}
            for wd in wdnodes:
                for node in wd.get("nodes", []):
                    meta[node.get("code", "")] = {
                        "cname": node.get("cname", ""),
                        "unit": node.get("unit", ""),
                        "wdcode": wd.get("wdcode", ""),
                    }

            rows: List[Dict] = []
            for dn in datanodes:
                wds = dn.get("wds", [])
                zb_code = ""
                sj_code = ""
                for w in wds:
                    if w.get("wdcode") == "zb":
                        zb_code = w.get("valuecode", "")
                    elif w.get("wdcode") == "sj":
                        sj_code = w.get("valuecode", "")
                val = dn.get("data", {}).get("data")
                strdata = dn.get("data", {}).get("strdata", "")
                rows.append({
                    "date": sj_code,
                    "code": zb_code,
                    "cname": meta.get(zb_code, {}).get("cname", ""),
                    "unit": meta.get(zb_code, {}).get("unit", ""),
                    "value": val if val is not None else strdata,
                })
            return pd.DataFrame(rows)
        except Exception as e:
            logger.warning(f"NBS解析异常: {type(e).__name__}: {e}")
            return pd.DataFrame()
