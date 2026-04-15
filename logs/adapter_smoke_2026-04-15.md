# Adapter 真网络冒烟报告

- 发起：2026-04-15 14:41:26 +08:00
- 完成：2026-04-15 14:42:43 +08:00
- 被测数量：22

## 汇总统计

| 状态 | 数量 | 说明 |
|------|------|------|
| 🟢 PASS | 10 | 真拉到数据 (rows ≥ 1) |
| 🟡 DEGRADED | 11 | 调用成功但返回空 (软降级) |
| 🔴 FAIL | 0 | 抛异常 |
| ⚫ SKIPPED | 1 | 超时 / 依赖缺失 / 无 Key |

## 详情明细

| # | Adapter | 方法 | 状态 | 数据/备注 | 错误摘要 |
|---|---------|------|------|-----------|----------|
| 1 | AkshareAdapter | `get_stock_history(600519)` | 🟢 PASS | rows=7 |  |
| 2 | BaostockAdapter | `get_stock_history(sh.600519)` | 🟢 PASS | rows=7 |  |
| 3 | EfinanceAdapter | `get_realtime_quotes([600519])` | 🟡 DEGRADED | empty (rows=0) |  |
| 4 | YFinanceAdapter | `get_kline(AAPL,5d,1d)` | 🟡 DEGRADED | empty (rows=0) |  |
| 5 | EDGARAdapter | `get_cik(AAPL)` | 🟢 PASS | rows=10 |  |
| 6 | FREDAdapter | `get_common_indicators` | ⚫ SKIPPED | FRED_API_KEY 未配置 |  |
| 7 | NBSAdapter | `get_cpi` | 🟡 DEGRADED | empty (rows=0) |  |
| 8 | WorldBankAdapter | `get_indicator(CN,NY.GDP.MKTP.CD)` | 🟢 PASS | rows=5 |  |
| 9 | IMFAdapter | `get_ifs(PMP_IX,US,A)` | 🟡 DEGRADED | empty (rows=0) |  |
| 10 | CCXTAdapter | `get_ticker(BTC/USDT)` | 🟡 DEGRADED | empty (rows=0) |  |
| 11 | CoinGeckoAdapter | `get_price([bitcoin])` | 🟢 PASS | rows=1 |  |
| 12 | OpenCLIBridge | `get_eastmoney_hot_rank` | 🟡 DEGRADED | empty (rows=0) |  |
| 13 | EasyquotationAdapter | `get_realtime([sh600519])` | 🟢 PASS | rows=1 |  |
| 14 | AshareAdapter | `get_price(sh600519,1d,5)` | 🟡 DEGRADED | empty (rows=0) |  |
| 15 | RSSNewsAdapter | `get_feed(sina_finance,limit=5)` | 🟡 DEGRADED | empty (rows=0) |  |
| 16 | CorporateAdapter | `search_company(Apple)` | 🟡 DEGRADED | empty (rows=0) |  |
| 17 | JobsAdapter | `search_jobs(python,limit=5)` | 🟢 PASS | rows=5 |  |
| 18 | ESGAdapter | `get_cdp_response(Apple,2024)` | 🟢 PASS | rows=7 |  |
| 19 | ShippingAdapter | `get_bdi_index(days=5)` | 🟡 DEGRADED | empty (rows=0) |  |
| 20 | SatelliteAdapter | `search_datasets(MODIS)` | 🟢 PASS | rows=20 |  |
| 21 | OpenBBAdapter | `get_equity_price(AAPL)` | 🟡 DEGRADED | empty (rows=0) |  |
| 22 | AdapterRegistry | `list_domains` | 🟢 PASS | domains=16 |  |

## Bug 清单 (疑似 code bug, 非网络/依赖)

_无疑似 code bug；🔴 全部为网络/反爬/服务端异常。_

---
_生成者: scripts/smoke_adapters.py · E2 NEW-FILE:#20260415-28_