# -*- coding: utf-8 -*-
"""
Input: adapter名(如eastmoney/hot-rank) + 可选args列表 + 超时
Output: list[dict] 结构化热股/爬取数据；异常时返回[]并log.warning
Pos: app/adapters/opencli_bridge.py — OpenCLI浏览器爬取桥，作为第二支柱数据源
     覆盖三大热股榜(东财/通达信/同花顺)及后续雪球/股吧/1688等爬取适配器
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

权威源（2026-04-15 11:30 +08:00 检索）：
- https://github.com/jackwener/OpenCLI   README.md (Strategy.COOKIE / --format=json)
- https://github.com/jackwener/OpenCLI/pull/1025   eastmoney/tdx/ths hot-rank 适配器
- https://docs.python.org/3.12/library/subprocess.html  subprocess.run 最佳实践

[NEW-FILE:#20260415-02]
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from functools import lru_cache
from typing import List, Dict, Optional

import pandas as pd

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

# 缓存TTL：5分钟（热股榜刷新频率足够）
_CACHE_TTL_SECONDS = 300


def _ttl_bucket() -> int:
    """把时间切为5分钟桶，用于 lru_cache 参数实现 TTL 效果"""
    return int(time.time() // _CACHE_TTL_SECONDS)


class OpenCLIBridge(BaseAdapter):
    """OpenCLI 子进程桥接器

    通过 `opencli <adapter> --format=json` 调用底层浏览器爬取能力。
    Node/opencli 未安装 -> 降级返回空列表 + log.warning，绝不抛异常影响上游。
    """

    OPENCLI_BIN = "opencli"
    NODE_BIN = "node"

    @property
    def name(self) -> str:
        return "opencli"

    # -------------------- 环境探测 --------------------
    @staticmethod
    def _check_environment() -> Optional[str]:
        """返回 None 表示环境OK；否则返回失败原因字符串"""
        if shutil.which(OpenCLIBridge.NODE_BIN) is None:
            return "node_not_installed"
        if shutil.which(OpenCLIBridge.OPENCLI_BIN) is None:
            return "opencli_not_installed"
        return None

    # -------------------- 通用调用 --------------------
    def opencli_call(
        self,
        adapter: str,
        args: Optional[List[str]] = None,
        timeout: int = 30,
    ) -> List[Dict]:
        """通用 OpenCLI 调用入口

        Args:
            adapter: OpenCLI 适配器路径，如 "eastmoney/hot-rank"
            args: 额外命令行参数
            timeout: 子进程超时（秒），默认30，对齐文档 §七 回滚阈值

        Returns:
            list[dict]：失败/异常时返回空列表
        """
        reason = self._check_environment()
        if reason:
            logger.warning(
                "[OpenCLI] 环境未就绪(%s)，降级返回空列表 adapter=%s",
                reason, adapter,
            )
            return []

        cmd = [self.OPENCLI_BIN, adapter, "--format=json"]
        if args:
            cmd.extend(args)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.warning("[OpenCLI] 超时(%ss) adapter=%s", timeout, adapter)
            return []
        except (OSError, FileNotFoundError) as exc:
            logger.warning("[OpenCLI] 调用失败 adapter=%s err=%s", adapter, exc)
            return []

        if proc.returncode != 0:
            logger.warning(
                "[OpenCLI] 非零退出码 adapter=%s rc=%s stderr=%s",
                adapter, proc.returncode, (proc.stderr or "")[:200],
            )
            return []

        stdout = (proc.stdout or "").strip()
        if not stdout:
            logger.warning("[OpenCLI] 空stdout adapter=%s", adapter)
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.warning(
                "[OpenCLI] JSON解析失败 adapter=%s err=%s raw=%s",
                adapter, exc, stdout[:200],
            )
            return []

        # 兼容两种schema：{"data":[...]} 或 [...]
        if isinstance(data, dict):
            data = data.get("data") or data.get("items") or []
        if not isinstance(data, list):
            logger.warning("[OpenCLI] schema异常 adapter=%s type=%s", adapter, type(data))
            return []

        return data

    # -------------------- 三大热股榜 --------------------
    def get_eastmoney_hot_rank(self) -> List[Dict]:
        """东方财富热股榜"""
        return _cached_hot_rank("eastmoney/hot-rank", _ttl_bucket())

    def get_tdx_hot_rank(self) -> List[Dict]:
        """通达信热股榜"""
        return _cached_hot_rank("tdx/hot-rank", _ttl_bucket())

    def get_ths_hot_rank(self) -> List[Dict]:
        """同花顺热股榜"""
        return _cached_hot_rank("ths/hot-rank", _ttl_bucket())

    # -------------------- P2-B1 自建社交/舆情适配器 --------------------
    # 对应 clis/xueqiu/discuss.js / clis/eastmoney/guba.js / clis/cls/telegraph.js
    # 权威源 (2026-04-15 12:30 +08:00)：
    #   https://github.com/jackwener/OpenCLI/pull/1025 (hot-rank 模板)
    #   https://xueqiu.com/S/{symbol}/TIMELINE
    #   https://guba.eastmoney.com/list,{code}.html
    #   https://www.cls.cn/telegraph
    def get_xueqiu_discuss(self, symbol: str, limit: int = 30) -> List[Dict]:
        """雪球个股讨论流

        Args:
            symbol: 雪球股票代码，含交易所前缀 (如 ``SZ000001`` / ``SH600519``)
            limit: 返回条数上限，默认30

        Returns:
            list[dict]：[{user,time,content,likes,comments,reposts}]；异常降级 []
        """
        if not symbol:
            logger.warning("[OpenCLI] xueqiu/discuss symbol必填")
            return []
        return self.opencli_call(
            "xueqiu/discuss",
            args=[f"--symbol={symbol}", f"--limit={int(limit)}"],
            timeout=45,
        )

    def get_eastmoney_guba(self, code: str, pages: int = 1) -> List[Dict]:
        """东方财富股吧帖子列表

        Args:
            code: 6位A股代码
            pages: 抓取页数，默认1（每页约80条）

        Returns:
            list[dict]：[{rank,title,author,time,reads,replies,url}]；异常降级 []
        """
        if not code or not code.isdigit() or len(code) != 6:
            logger.warning("[OpenCLI] eastmoney/guba code必须为6位数字 got=%s", code)
            return []
        return self.opencli_call(
            "eastmoney/guba",
            args=[f"--code={code}", f"--pages={max(1, int(pages))}"],
            timeout=60,
        )

    def get_cls_telegraph(self, limit: int = 50) -> List[Dict]:
        """财联社电报实时流

        Args:
            limit: 返回条数上限，默认50

        Returns:
            list[dict]：[{time,title,content,tags,isImportant}]；异常降级 []
        """
        return self.opencli_call(
            "cls/telegraph",
            args=[f"--limit={int(limit)}"],
            timeout=30,
        )

    # -------------------- BaseAdapter抽象方法占位 --------------------
    # OpenCLI 主职责是爬取/热榜，K线/财务/指数成分非其能力范围，
    # 统一返回空对象以满足抽象接口契约，供 fallback_manager 跳过。
    def get_stock_history(self, code: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> pd.DataFrame:
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str) -> List[str]:
        return []

    def get_stock_info(self, code: str) -> Dict:
        return {}

    def get_financial_data(self, code: str) -> Dict:
        return {}

    def health_check(self) -> bool:
        return self._check_environment() is None


# -------------------- 模块级 TTL 缓存 --------------------
# lru_cache 结合 _ttl_bucket 实现 5min 自动过期
@lru_cache(maxsize=32)
def _cached_hot_rank(adapter: str, bucket: int) -> List[Dict]:
    """TTL缓存包装：同一 (adapter, bucket) 命中缓存，bucket跨越即自然失效"""
    bridge = OpenCLIBridge()
    return bridge.opencli_call(adapter)
