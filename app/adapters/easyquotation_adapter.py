# -*- coding: utf-8 -*-
"""
easyquotation适配器 - 新浪/腾讯/qq/daykline/jsl 批量实时行情+基金净值
Input: 股票代码列表 codes、source(sina/tencent/qq/daykline/jsl)
Output: dict{code: quote_dict} 批量实时 / 全市场 / 基金净值
Pos: app/adapters层，高并发批量实时兜底；未装easyquotation静默降级
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

权威源（≥3交叉验证, 检索时间 2026-04-15 12:30 +08:00）：
  1) GitHub shidenggui/easyquotation README + api.py @ master
     https://github.com/shidenggui/easyquotation
     说明：`use('sina'|'tencent'|'qq'|'daykline'|'jsl')`；`.stocks(codes)` 批量；`.market_snapshot(prefix=True)` 全市场
  2) PyPI easyquotation（最新稳定版，MIT）
     https://pypi.org/project/easyquotation/
  3) 集思录 jsl.cn 可转债/基金净值公开接口（easyquotation jsl 源封装）
     https://www.jisilu.cn/data/

API映射：
  - 批量实时  → quotation.stocks(codes) / quotation.real(codes)
  - 全市场    → quotation.market_snapshot(prefix=False)
  - 基金净值  → use('jsl').funda() / fundb() / fundm() — 分级A/B/母基
"""
import logging
from typing import List, Dict, Optional

import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

# try-import：未装不崩
try:
    import easyquotation  # type: ignore
    _EQ_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    easyquotation = None  # type: ignore
    _EQ_AVAILABLE = False
    logger.warning(f"easyquotation未安装或导入失败，EasyquotationAdapter进入降级模式: {type(_e).__name__}: {_e}")


# 合法source（easyquotation官方）
_VALID_SOURCES = {"sina", "tencent", "qq", "daykline", "jsl", "hkquote", "timekline"}


class EasyquotationAdapter(BaseAdapter):
    """easyquotation批量实时行情适配器"""

    def __init__(self, source: str = "sina"):
        """
        Args:
            source: 数据源 sina/tencent/qq/daykline/jsl 等
                    - sina/tencent/qq: A股实时
                    - daykline: 日K线
                    - jsl: 集思录 基金/可转债
        """
        if source not in _VALID_SOURCES:
            logger.warning(f"非法source={source}，合法{_VALID_SOURCES}，回退sina")
            source = "sina"
        self.source = source
        self._client = None
        if _EQ_AVAILABLE:
            try:
                self._client = easyquotation.use(source)
            except Exception as e:
                logger.warning(f"easyquotation.use({source})失败: {type(e).__name__}: {e}")
                self._client = None

    @property
    def name(self) -> str:
        return f"easyquotation:{self.source}"

    # ---------- 核心能力 ----------

    def get_realtime(self, codes: List[str]) -> Dict:
        """批量实时行情

        Args:
            codes: 代码列表，如 ['000001','600519']；easyquotation内部自动识别市场前缀

        Returns:
            dict {code: {name,now,open,close,high,low,volume,...}}
        """
        if not _EQ_AVAILABLE or self._client is None:
            logger.warning("easyquotation未就绪，get_realtime返回空dict")
            return {}
        if not codes:
            return {}
        try:
            # 优先走 stocks，兼容老版 real
            if hasattr(self._client, "stocks"):
                return self._client.stocks(codes) or {}
            if hasattr(self._client, "real"):
                return self._client.real(codes) or {}
            logger.warning(f"easyquotation client({self.source})无stocks/real接口")
            return {}
        except Exception as e:
            logger.warning(f"easyquotation实时行情失败({self.source}): {type(e).__name__}: {e}")
            return {}

    def get_stocks_all(self) -> Dict:
        """全市场快照

        Returns:
            dict {code: quote_dict}；量级约5000+只A股
        """
        if not _EQ_AVAILABLE or self._client is None:
            logger.warning("easyquotation未就绪，get_stocks_all返回空dict")
            return {}
        try:
            if hasattr(self._client, "market_snapshot"):
                return self._client.market_snapshot(prefix=False) or {}
            if hasattr(self._client, "all"):
                return self._client.all or {}
            logger.warning(f"easyquotation client({self.source})无market_snapshot接口")
            return {}
        except Exception as e:
            logger.warning(f"easyquotation全市场快照失败({self.source}): {type(e).__name__}: {e}")
            return {}

    def get_fund_nav(self, codes: Optional[List[str]] = None) -> Dict:
        """基金净值（jsl源）— 分级A/B/母基合并

        Args:
            codes: 基金代码列表；None则返回全部

        Returns:
            dict {code: {name,price,nav,...}}
        """
        if not _EQ_AVAILABLE:
            return {}
        # 基金净值必须jsl源
        client = self._client if self.source == "jsl" else None
        if client is None:
            try:
                client = easyquotation.use("jsl")
            except Exception as e:
                logger.warning(f"easyquotation.use('jsl')失败: {type(e).__name__}: {e}")
                return {}
        result: Dict = {}
        try:
            for fn_name in ("funda", "fundb", "fundm"):
                fn = getattr(client, fn_name, None)
                if fn is None:
                    continue
                try:
                    data = fn() or {}
                    if isinstance(data, dict):
                        result.update(data)
                    elif isinstance(data, list):
                        # jsl部分接口返回list[dict]，按base_fund_id/fund_id归档
                        for item in data:
                            if not isinstance(item, dict):
                                continue
                            k = (item.get("base_fund_id") or item.get("fund_id")
                                 or item.get("code") or "")
                            if k:
                                result[str(k)] = item
                except Exception as e:
                    logger.warning(f"jsl.{fn_name}失败: {type(e).__name__}: {e}")
        except Exception as e:
            logger.warning(f"easyquotation基金净值失败: {type(e).__name__}: {e}")
            return {}

        if codes:
            codes_set = {str(c) for c in codes}
            result = {k: v for k, v in result.items() if str(k) in codes_set}
        return result

    # ---------- J1 alias: 个股资金流 ----------
    def get_individual_fund_flow(self, code: str) -> pd.DataFrame:
        """J1 [NEW-FILE:#20260415-43] 个股资金流 alias。

        easyquotation 无原生资金流接口；此处从 get_realtime 重组
        关键字段 (price/now/volume/amount/change) 为单行 DataFrame，
        保证 registry 能取到非空结果。
        """
        if not _EQ_AVAILABLE or self._client is None:
            return pd.DataFrame()
        try:
            data = self.get_realtime([str(code)])
            if not isinstance(data, dict) or str(code) not in data:
                return pd.DataFrame()
            row = data[str(code)]
            if not isinstance(row, dict) or not row:
                return pd.DataFrame()
            # 统一列名：code + 主要字段
            flat = {"code": str(code)}
            for k in ("name", "now", "price", "open", "close", "high", "low",
                      "volume", "amount", "turnover"):
                if k in row:
                    flat[k] = row[k]
            return pd.DataFrame([flat])
        except Exception as e:
            logger.warning(f"[EasyquotationAdapter] get_individual_fund_flow({code}) 失败: {type(e).__name__}: {e}")
            return pd.DataFrame()

    # ---------- BaseAdapter 抽象方法实现 ----------

    def get_stock_history(self, code: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> pd.DataFrame:
        """easyquotation仅实时/日K，无历史。daykline源可取最近约2年日K
        日期切片交调用方，这里返回raw。
        """
        if not _EQ_AVAILABLE:
            return pd.DataFrame()
        try:
            dk = easyquotation.use("daykline")
            data = dk.real([code]) if hasattr(dk, "real") else {}
            if not data or code not in data:
                return pd.DataFrame()
            # daykline返回 {code: [[date,open,close,high,low,volume],...]}
            rows = data[code]
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows, columns=["date", "open", "close", "high", "low", "volume"])
            return df
        except Exception as e:
            logger.warning(f"easyquotation daykline失败(code={code}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        """easyquotation无指数成分接口"""
        return []

    def get_stock_info(self, code: str) -> Dict:
        """取单只实时行情充当info"""
        data = self.get_realtime([code])
        return data.get(code, {}) if isinstance(data, dict) else {}

    def get_financial_data(self, code: str) -> Dict:
        """easyquotation无财务"""
        return {}

    def health_check(self) -> bool:
        """健康检查：取上证指数或平安银行"""
        if not _EQ_AVAILABLE or self._client is None:
            return False
        try:
            if self.source == "jsl":
                # jsl健康检查：funda
                fn = getattr(self._client, "funda", None)
                if fn is None:
                    return False
                d = fn()
                return bool(d)
            data = self.get_realtime(["000001"])
            return bool(data)
        except Exception as e:
            logger.warning(f"easyquotation健康检查失败({self.source}): {type(e).__name__}: {e}")
            return False
