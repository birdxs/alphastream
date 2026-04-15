# app/adapters — 数据源适配器

此文件夹收纳所有数据源适配器；一旦这里的结构发生变化，请务必更新我……就像重新标记领地一样。

## 文件清单

| 文件 | 地位 | 功能 |
|---|---|---|
| `base_adapter.py` | 契约层 | `BaseAdapter` 抽象基类：K线/成分股/信息/财务/健康检查 |
| `akshare_adapter.py` | 主数据源 | akshare 多数据源冗余（东财/同花顺/新浪/腾讯） |
| `baostock_adapter.py` | 备援数据源 | baostock 日线/周线/月线兜底 |
| `opencli_bridge.py` | 爬取桥(P0-A1 2026-04-15) | OpenCLI 子进程桥：三大热股榜+浏览器爬取；Node/opencli未装降级为空 |
| `efinance_adapter.py` | 高频补充(P0-A2 2026-04-15) | efinance东财反向接口：分钟K/龙虎榜/实时；融资融券由akshare兜底；未装efinance降级为空 [NEW-FILE:#20260415-04] |
| `yfinance_adapter.py` | 跨市场(P0-A3 2026-04-15) | yfinance港美股+日股+ETF+期权链；未装yfinance降级为空 [NEW-FILE:#20260415-05] |
| `edgar_adapter.py` | 美股基本面(P0-A4 2026-04-15) | SEC EDGAR官方XBRL：申报历史/companyfacts/concept；10req/s限流+UA规范 |
| `nbs_adapter.py` | 国内宏观(P1-A6 2026-04-15) | 国家统计局easyquery：GDP/CPI/PMI/工业；无Key+UA伪装+3重试 [NEW-FILE:#20260415-08] |
| `fred_adapter.py` | 全球宏观(P1-A5 2026-04-15) | FRED St.Louis Fed 80万+序列：get_series/search/release/common_indicators；免费Key+fredapi软依赖降级 [NEW-FILE:#20260415-07] |
| `ccxt_adapter.py` | 加密货币(P1-A9 2026-04-15) | ccxt 100+交易所统一接口：ticker/ohlcv/order_book/markets；未装ccxt降级为空 [NEW-FILE:#20260415-11] |
| `coingecko_adapter.py` | 加密市场概览(P1-A10 2026-04-15) | CoinGecko公开API：价格/市值图/趋势/全球总览；限流≤30/min无需Key [NEW-FILE:#20260415-12] |
| `worldbank_adapter.py` | 世界银行(P1-A7 2026-04-15) | World Bank Open Data：get_indicator时序/list_indicators搜索/compare_countries横向对比；无Key免费 [NEW-FILE:#20260415-09] |
| `imf_adapter.py` | 国际货币基金(P1-A8 2026-04-15) | IMF SDMX-JSON REST：get_dataset/get_ifs/get_data_structure，支持IFS/WEO/DOT；无Key免费 [NEW-FILE:#20260415-10] |
| `rss_news_adapter.py` | RSS新闻聚合(P2-B3 2026-04-15) | 华尔街见闻/财联社/雪球/新浪财经/金融界/央视财经 6源 RSS 并发聚合 + 去重 + 关键词过滤；feedparser软依赖 [NEW-FILE:#20260415-19] |
| `ashare_adapter.py` | A股轻量兜底(P2-B2 2026-04-15) | Ashare 单文件库直调：新浪/腾讯 日/周/月/分钟K线；code规范sh/sz前缀；未装Ashare降级为空 [NEW-FILE:#20260415-17] |
| `easyquotation_adapter.py` | 批量实时(P2-B2 2026-04-15) | easyquotation sina/tencent/qq/daykline/jsl：批量实时+全市场快照+jsl基金净值；未装降级为空 [NEW-FILE:#20260415-18] |
| `openbb_adapter.py` | OpenBB桥(P2-B4 2026-04-15) | OpenBB Platform SDK：equity/crypto/economy 路由；免费provider白名单(yfinance/fred/sec/intrinio/fmp)；软依赖降级 [NEW-FILE:#20260415-20] |
| `adapter_registry.py` | 注册中心(P2-B4 2026-04-15) | 统一 domain→adapters 映射 + call_with_fallback 自动降级；覆盖11业务域(a_stock_kline/realtime/us/hk/macro_us/cn/global/crypto/news/sentiment_social/xbrl_financials) [NEW-FILE:#20260415-21] |
| `__init__.py` | 导出 | 统一入口 |

## 约定

- 所有新适配器必须继承 `BaseAdapter`，实现 6 个抽象方法（不支持的能力返回空对象）
- 头部 3 行铭牌 `Input/Output/Pos` 必填
- 爬取/外部进程类适配器必须对环境缺失做降级，不得向上游抛异常
