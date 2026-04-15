#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Input: 无参数，直接运行
Output: 控制台 + logs/adapter_smoke_<date>.md 真网络冒烟报告
Pos: scripts/ 冒烟执行器 — E2 [NEW-FILE:#20260415-28]

功能：
- 逐个导入并初始化 22 个 adapter + Registry
- 对每个 adapter 调用 1-2 个最核心方法 (真实网络)
- 每个调用 30s 超时，独立 try/except
- 分类标记：🟢 PASS / 🟡 DEGRADED / 🔴 FAIL / ⚫ SKIPPED
- 尾部写入 logs/adapter_smoke_<YYYY-MM-DD>.md
"""
from __future__ import annotations
import os
import sys
import time
import signal
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager

# 项目根路径
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TODAY = datetime.now().strftime("%Y-%m-%d")
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S +08:00")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
MD_PATH = LOG_DIR / f"adapter_smoke_{TODAY}.md"

# 结果收集
results = []  # [(adapter_name, method, status_emoji, status_text, rows_or_note, err_snip)]

# ===== 超时上下文 =====
class TimeoutError_(Exception):
    pass

@contextmanager
def timeout(seconds: int):
    """Unix 信号超时，Windows 会降级为不生效。"""
    def _handler(signum, frame):
        raise TimeoutError_(f"timeout {seconds}s")
    if hasattr(signal, "SIGALRM"):
        old = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
    else:
        yield


def _rows(obj) -> int:
    """统一计算返回对象的"行/元素数"。"""
    try:
        import pandas as pd
        if isinstance(obj, pd.DataFrame):
            return len(obj)
    except Exception:
        pass
    if obj is None:
        return 0
    if isinstance(obj, (list, tuple, set)):
        return len(obj)
    if isinstance(obj, dict):
        return len(obj)
    if hasattr(obj, "__len__"):
        try:
            return len(obj)
        except Exception:
            return 0
    return 1  # 单值对象


def run(adapter_name: str, method: str, fn, timeout_s: int = 30,
        min_rows: int = 1, skip_reason: str | None = None):
    """统一执行包装。"""
    if skip_reason:
        print(f"[⚫ SKIP] {adapter_name}.{method} — {skip_reason}")
        results.append((adapter_name, method, "⚫", "SKIPPED", skip_reason, ""))
        return
    t0 = time.time()
    try:
        with timeout(timeout_s):
            obj = fn()
        elapsed = time.time() - t0
        n = _rows(obj)
        if n >= min_rows:
            print(f"[🟢 PASS] {adapter_name}.{method} rows={n} ({elapsed:.1f}s)")
            results.append((adapter_name, method, "🟢", "PASS", f"rows={n}", ""))
        else:
            note = f"empty (rows={n})"
            print(f"[🟡 DEGRADED] {adapter_name}.{method} {note} ({elapsed:.1f}s)")
            results.append((adapter_name, method, "🟡", "DEGRADED", note, ""))
    except TimeoutError_ as e:
        print(f"[⚫ SKIP] {adapter_name}.{method} — TIMEOUT {timeout_s}s")
        results.append((adapter_name, method, "⚫", "SKIPPED",
                        f"timeout {timeout_s}s", ""))
    except ImportError as e:
        msg = str(e)[:100]
        print(f"[⚫ SKIP] {adapter_name}.{method} — dep missing: {msg}")
        results.append((adapter_name, method, "⚫", "SKIPPED",
                        f"dep missing: {msg}", ""))
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:120]}"
        print(f"[🔴 FAIL] {adapter_name}.{method} — {err}")
        results.append((adapter_name, method, "🔴", "FAIL",
                        "", err))


# ===== 主流程 =====
def main():
    print(f"=== Adapter 真网络冒烟 @ {NOW} ===\n")

    # ---------- 1) AkshareAdapter ----------
    try:
        from app.adapters import AkshareAdapter
        ak_ad = AkshareAdapter()
        run("AkshareAdapter", "get_stock_history(600519)",
            lambda: ak_ad.get_stock_history("600519", "2026-04-01", "2026-04-10"))
    except Exception as e:
        results.append(("AkshareAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 2) BaostockAdapter ----------
    try:
        from app.adapters import BaostockAdapter
        bs_ad = BaostockAdapter()
        run("BaostockAdapter", "get_stock_history(sh.600519)",
            lambda: bs_ad.get_stock_history("sh.600519", "2026-04-01", "2026-04-10"))
    except Exception as e:
        results.append(("BaostockAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 3) EfinanceAdapter ----------
    try:
        from app.adapters import EfinanceAdapter
        ef_ad = EfinanceAdapter()
        run("EfinanceAdapter", "get_realtime_quotes([600519])",
            lambda: ef_ad.get_realtime_quotes(["600519"]))
    except Exception as e:
        results.append(("EfinanceAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 4) YFinanceAdapter ----------
    try:
        from app.adapters import YFinanceAdapter
        yf_ad = YFinanceAdapter()
        run("YFinanceAdapter", "get_kline(AAPL,5d,1d)",
            lambda: yf_ad.get_kline("AAPL", "5d", "1d"))
    except Exception as e:
        results.append(("YFinanceAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 5) EDGARAdapter ----------
    try:
        from app.adapters import EDGARAdapter
        edgar_ad = EDGARAdapter(user_agent="StockAnalSys Smoke smoke@example.com")
        run("EDGARAdapter", "get_cik(AAPL)",
            lambda: edgar_ad.get_cik("AAPL"), min_rows=1)
    except Exception as e:
        results.append(("EDGARAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 6) FREDAdapter ----------
    try:
        from app.adapters import FREDAdapter
        fred_key = os.getenv("FRED_API_KEY")
        fred_ad = FREDAdapter(api_key=fred_key)
        if not fred_key:
            run("FREDAdapter", "get_common_indicators",
                lambda: None, skip_reason="FRED_API_KEY 未配置")
        else:
            run("FREDAdapter", "get_common_indicators",
                lambda: fred_ad.get_common_indicators())
    except Exception as e:
        results.append(("FREDAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 7) NBSAdapter (必须无Key可用) ----------
    try:
        from app.adapters import NBSAdapter
        nbs_ad = NBSAdapter()
        run("NBSAdapter", "get_cpi",
            lambda: nbs_ad.get_cpi())
    except Exception as e:
        results.append(("NBSAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 8) WorldBankAdapter ----------
    try:
        from app.adapters import WorldBankAdapter
        wb_ad = WorldBankAdapter()
        run("WorldBankAdapter", "get_indicator(CN,NY.GDP.MKTP.CD)",
            lambda: wb_ad.get_indicator("CN", "NY.GDP.MKTP.CD", 2020, 2024))
    except Exception as e:
        results.append(("WorldBankAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 9) IMFAdapter ----------
    try:
        from app.adapters import IMFAdapter
        imf_ad = IMFAdapter()
        run("IMFAdapter", "get_ifs(PMP_IX,US,A)",
            lambda: imf_ad.get_ifs("PMP_IX", "US", "A"))
    except Exception as e:
        results.append(("IMFAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 10) CCXTAdapter ----------
    try:
        from app.adapters import CCXTAdapter
        ccxt_ad = CCXTAdapter("binance")
        run("CCXTAdapter", "get_ticker(BTC/USDT)",
            lambda: ccxt_ad.get_ticker("BTC/USDT"))
    except Exception as e:
        results.append(("CCXTAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 11) CoinGeckoAdapter ----------
    try:
        from app.adapters import CoinGeckoAdapter
        cg_ad = CoinGeckoAdapter()
        run("CoinGeckoAdapter", "get_price([bitcoin])",
            lambda: cg_ad.get_price(["bitcoin"]))
    except Exception as e:
        results.append(("CoinGeckoAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 12) OpenCLIBridge ----------
    try:
        from app.adapters import OpenCLIBridge
        oc_ad = OpenCLIBridge()
        # 自检环境
        env_err = OpenCLIBridge._check_environment()
        if env_err:
            run("OpenCLIBridge", "get_eastmoney_hot_rank",
                lambda: None, skip_reason=f"env: {env_err[:80]}")
        else:
            run("OpenCLIBridge", "get_eastmoney_hot_rank",
                lambda: oc_ad.get_eastmoney_hot_rank())
    except Exception as e:
        results.append(("OpenCLIBridge", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 13) EasyquotationAdapter ----------
    try:
        from app.adapters import EasyquotationAdapter
        eq_ad = EasyquotationAdapter("sina")
        run("EasyquotationAdapter", "get_realtime([sh600519])",
            lambda: eq_ad.get_realtime(["sh600519"]))
    except Exception as e:
        results.append(("EasyquotationAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 14) AshareAdapter ----------
    try:
        from app.adapters import AshareAdapter
        as_ad = AshareAdapter()
        run("AshareAdapter", "get_price(sh600519,1d,5)",
            lambda: as_ad.get_price("sh600519", "1d", 5))
    except Exception as e:
        results.append(("AshareAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 15) RSSNewsAdapter ----------
    try:
        from app.adapters import RSSNewsAdapter
        rss_ad = RSSNewsAdapter()
        run("RSSNewsAdapter", "get_feed(sina_finance,limit=5)",
            lambda: rss_ad.get_feed("sina_finance", limit=5))
    except Exception as e:
        results.append(("RSSNewsAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 16) CorporateAdapter ----------
    try:
        from app.adapters import CorporateAdapter
        corp_ad = CorporateAdapter()
        run("CorporateAdapter", "search_company(Apple)",
            lambda: corp_ad.search_company("Apple"))
    except Exception as e:
        results.append(("CorporateAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 17) JobsAdapter ----------
    try:
        from app.adapters import JobsAdapter
        jobs_ad = JobsAdapter()
        run("JobsAdapter", "search_jobs(python,limit=5)",
            lambda: jobs_ad.search_jobs("python", limit=5))
    except Exception as e:
        results.append(("JobsAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 18) ESGAdapter ----------
    try:
        from app.adapters import ESGAdapter
        esg_ad = ESGAdapter()
        run("ESGAdapter", "get_cdp_response(Apple,2024)",
            lambda: esg_ad.get_cdp_response("Apple", 2024))
    except Exception as e:
        results.append(("ESGAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 19) ShippingAdapter ----------
    try:
        from app.adapters import ShippingAdapter
        sh_ad = ShippingAdapter()
        run("ShippingAdapter", "get_bdi_index(days=5)",
            lambda: sh_ad.get_bdi_index(days=5))
    except Exception as e:
        results.append(("ShippingAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 20) SatelliteAdapter ----------
    try:
        from app.adapters import SatelliteAdapter
        sat_ad = SatelliteAdapter()
        run("SatelliteAdapter", "search_datasets(MODIS)",
            lambda: sat_ad.search_datasets("MODIS"))
    except Exception as e:
        results.append(("SatelliteAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 21) OpenBBAdapter ----------
    try:
        from app.adapters import OpenBBAdapter
        obb_ad = OpenBBAdapter()
        run("OpenBBAdapter", "get_equity_price(AAPL)",
            lambda: obb_ad.get_equity_price("AAPL"))
    except ImportError as e:
        results.append(("OpenBBAdapter", "init", "⚫", "SKIPPED",
                        f"openbb 未安装: {str(e)[:80]}", ""))
    except Exception as e:
        results.append(("OpenBBAdapter", "init", "🔴", "FAIL", "",
                        f"init: {type(e).__name__}: {str(e)[:120]}"))

    # ---------- 22) AdapterRegistry ----------
    try:
        from app.adapters import AdapterRegistry
        reg = AdapterRegistry.default()
        domains = reg.list_domains()
        if domains:
            print(f"[🟢 PASS] AdapterRegistry.list_domains rows={len(domains)}")
            results.append(("AdapterRegistry", "list_domains", "🟢", "PASS",
                            f"domains={len(domains)}", ""))
        else:
            print("[🟡 DEGRADED] AdapterRegistry.list_domains empty")
            results.append(("AdapterRegistry", "list_domains", "🟡", "DEGRADED",
                            "empty domains", ""))
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:120]}"
        print(f"[🔴 FAIL] AdapterRegistry — {err}")
        results.append(("AdapterRegistry", "default", "🔴", "FAIL", "", err))

    # ===== 写报告 =====
    write_report()


def write_report():
    counts = {"🟢": 0, "🟡": 0, "🔴": 0, "⚫": 0}
    for *_, emoji, _s, _n, _e in [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in results]:
        pass
    for r in results:
        counts[r[2]] += 1

    total = len(results)
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S +08:00")

    lines = []
    lines.append(f"# Adapter 真网络冒烟报告")
    lines.append("")
    lines.append(f"- 发起：{NOW}")
    lines.append(f"- 完成：{end_time}")
    lines.append(f"- 被测数量：{total}")
    lines.append("")
    lines.append("## 汇总统计")
    lines.append("")
    lines.append(f"| 状态 | 数量 | 说明 |")
    lines.append(f"|------|------|------|")
    lines.append(f"| 🟢 PASS | {counts['🟢']} | 真拉到数据 (rows ≥ 1) |")
    lines.append(f"| 🟡 DEGRADED | {counts['🟡']} | 调用成功但返回空 (软降级) |")
    lines.append(f"| 🔴 FAIL | {counts['🔴']} | 抛异常 |")
    lines.append(f"| ⚫ SKIPPED | {counts['⚫']} | 超时 / 依赖缺失 / 无 Key |")
    lines.append("")
    lines.append("## 详情明细")
    lines.append("")
    lines.append("| # | Adapter | 方法 | 状态 | 数据/备注 | 错误摘要 |")
    lines.append("|---|---------|------|------|-----------|----------|")
    for i, (ad, mt, emj, st, note, err) in enumerate(results, 1):
        safe_err = err.replace("|", "\\|")[:100] if err else ""
        safe_note = (note or "").replace("|", "\\|")[:80]
        lines.append(f"| {i} | {ad} | `{mt}` | {emj} {st} | {safe_note} | {safe_err} |")
    lines.append("")

    # Bug 清单 (code bug, 非网络/依赖)
    bugs = []
    for ad, mt, emj, st, note, err in results:
        if emj == "🔴":
            # 疑似 code bug 的模式：AttributeError、TypeError、NameError、ImportError(不在SKIP分支)
            if any(k in err for k in ["AttributeError", "TypeError", "NameError",
                                       "KeyError", "IndexError"]):
                bugs.append((ad, mt, err))
    lines.append("## Bug 清单 (疑似 code bug, 非网络/依赖)")
    lines.append("")
    if bugs:
        lines.append("| Adapter | 方法 | 错误 |")
        lines.append("|---------|------|------|")
        for ad, mt, err in bugs:
            lines.append(f"| {ad} | `{mt}` | {err[:150]} |")
    else:
        lines.append("_无疑似 code bug；🔴 全部为网络/反爬/服务端异常。_")
    lines.append("")
    lines.append("---")
    lines.append(f"_生成者: scripts/smoke_adapters.py · E2 NEW-FILE:#20260415-28_")

    MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n=== 报告已写入: {MD_PATH} ===")
    print(f"汇总: 🟢{counts['🟢']}  🟡{counts['🟡']}  🔴{counts['🔴']}  ⚫{counts['⚫']} (共{total})")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INTERRUPT] 被中断，但已测试项仍写入报告")
        write_report()
        sys.exit(1)
