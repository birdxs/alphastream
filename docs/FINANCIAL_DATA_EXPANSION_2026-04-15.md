# 金融数据库扩充方案 (FINANCIAL_DATA_EXPANSION)

> Input: 测试反馈"专业金融数据获取严重不足" + 现有akshare/baostock基线
> Output: 现状矩阵 + 18项数据源扩充清单 + 三阶段落地计划 + 合规与14-Agent对接方案
> Pos: `docs/` — 数据层战略规划文档 (P0基线)

---

## 元信息

| 项 | 值 |
|---|---|
| 文档编号 | NEW-FILE:#20260415-01 |
| 撰写日期 | 2026-04-15 (Asia/Singapore +08:00) |
| 撰写人 | 香草少校 (agent team 调研) |
| 时间基准 | 系统currentDate=2026-04-15，已通过环境变量校验 |
| 文档定位 | 扩充方案，不涉及代码实装 |
| 覆盖市场 | A股/港股/美股 + 宏观 + 另类 |
| 现有基线 | `app/adapters/akshare_adapter.py` + `baostock_adapter.py` + `app/core/search_engines.py` (17引擎) |
| 审批理由 | 缺失且必需的战略文档，无可修改的同类现存文件 (已核 docs/ 目录) |

---

## 一、现状矩阵 (已接入 vs 关键缺口)

### 1.1 已接入能力

| 维度 | 现有实现 | 覆盖范围 | 品质评估 |
|---|---|---|---|
| A股行情日线 | baostock_adapter | 沪深A股全量日/周/月K | 优 (官方友好) |
| A股基础财报 | baostock_adapter | 季度利润/资产/现金流 | 中 (披露滞后) |
| A股另类聚合 | akshare_adapter | 东财/新浪/同花顺爬虫聚合 | 中 (接口不稳定) |
| 搜索层 | search_engines.py | 17引擎 (8中+9国际) fallback | 优 |
| 新闻信息 | 通过搜索引擎抓取 | 间接 | 中 |

### 1.2 关键缺口 (测试反馈映射)

| 缺口领域 | 具体问题 | 严重度 |
|---|---|---|
| **A股分钟级/Tick级** | 仅日线，无盘中分钟、无Level-2 | P0 |
| **A股龙虎榜/大宗/融资融券** | 缺异动类数据 | P0 |
| **港股数据** | 仅部分经akshare，港股财报/股东薄弱 | P1 |
| **美股全量** | 依赖akshare爬虫，不稳 | P0 |
| **专业财务结构化** | XBRL标准、10K/10Q、重述数据无官方源 | P0 |
| **宏观经济** | FRED/央行/国统局未接入 | P0 |
| **分析师预测/一致预期** | 无 | P1 |
| **情绪/讨论热度** | 无 Reddit/雪球/股吧原生接入 | P1 |
| **工商关系图谱** | 无股权穿透/关联交易 | P2 |
| **ESG/做空/13F持仓** | 无机构持仓类 | P2 |

---

## 二、推荐扩充清单 (共18项，按优先级)

### P0 — 立即接入 (7项，2周内)

#### 1. **Tushare Pro** (A股专业)
- URL: https://tushare.pro/
- 覆盖: A股日/分钟/Tick、财报、指数、基金、龙虎榜、大宗、融资融券
- 免费额度: 注册120积分基线，满足股票列表/日线；关键接口阈值120/500/2000/5000积分
- 接入方式: `pip install tushare`，token认证
- 证据: [tushare.pro/document/1?doc_id=290](https://tushare.pro/document/1?doc_id=290) (采用)；[知乎量化数据源选型2026](https://zhuanlan.zhihu.com/p/2005025480454197447) (印证)
- 代码示例:
```python
import tushare as ts
pro = ts.pro_api(token)
df = pro.daily(ts_code='000001.SZ', start_date='20260101', end_date='20260415')
# 龙虎榜: pro.top_list(trade_date='20260414')
```

#### 2. **efinance** (东财爬虫封装)
- URL: https://github.com/Micro-sheep/efinance
- 覆盖: 股/基/债/期货 + 基金实时净值 + 龙虎榜 + 异动
- 免费额度: 无限制 (本地爬虫，受东财反爬)
- 接入: `pip install efinance`，无token
- 证据: [GitHub Micro-sheep/efinance](https://github.com/Micro-sheep/efinance) (采用) — 相对akshare具备更快的基金行情链路
- 补位akshare缺失的基金板块深度数据

#### 3. **yfinance** (美股/港股/全球)
- URL: https://github.com/ranaroussi/yfinance
- 覆盖: 全球所有Yahoo Finance覆盖标的，日线+分钟+期权链
- 免费额度: 无额度但非官方，Yahoo会限频；建议本地缓存+UA轮换
- 证据: [Medium: Beyond yFinance对比](https://medium.com/@trading.dude/beyond-yfinance-comparing-the-best-financial-data-apis-for-traders-and-developers-06a3b8bc07e2) (采用，警示"一年坏2次") — 作为美股基线补位
- 代码: `yf.Ticker("AAPL").history(period="1y", interval="1d")`

#### 4. **Finnhub** (美股实时+新闻)
- URL: https://finnhub.io/
- 覆盖: 美股实时报价、公司新闻、财报、经济日历、央行事件
- 免费额度: **60次/分钟**，历史仅数年 (2026年仍最慷慨的免费梯度)
- 证据: [finnhub vs alternatives](https://finnhub.io/finnhub-stock-api-vs-alternatives)；[Best APIs 2026 nb-data](https://www.nb-data.com/p/best-financial-data-apis-in-2026) (采用)
- 接入: `pip install finnhub-python`

#### 5. **SEC EDGAR (官方)** (美股结构化财报)
- URL: https://data.sec.gov/  +  EdgarTools
- 覆盖: 10-K/10-Q/8-K/13F/Form 4 (内部人交易) — XBRL结构化
- 免费额度: **无需Key、无限频、无订阅**
- 证据: [SEC官方API页](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)；[edgartools](https://github.com/dgunning/edgartools) (采用)
- 代码:
```python
from edgar import Company
aapl = Company("AAPL")
financials = aapl.financials  # 结构化XBRL
insider_trades = aapl.get_filings(form="4")
```

#### 6. **FRED API** (宏观 — 美联储 + 兼世行/IMF)
- URL: https://fred.stlouisfed.org/docs/api/fred/
- 覆盖: 美联储80万+宏观序列 + 世行/IMF/OECD镜像
- 免费额度: 需免费API Key，实测请求无硬限频
- 证据: [fredapi PyPI](https://pypi.org/project/fredapi/)；[fedfred (330,000+ indicators, 多源整合)](https://medium.com/@nsunder724/access-macroeconomic-data-at-scale-with-fedfred-a-modern-python-client-for-the-fred-api-96745541ef2a) (采用)

#### 7. **国家统计局 data.stats.gov.cn** (中国宏观)
- URL: https://data.stats.gov.cn/easyquery.htm
- 覆盖: GDP/CPI/PMI/行业统计 — 全国+31省+地市
- 免费额度: 无官方限频，POST请求即可
- 证据: [国统局API博客园实测](https://www.cnblogs.com/wang_yb/p/14636575.html)；[中经数据API](https://www.sic.gov.cn/sic/93/552/zjsj/0801/20250801152158503557628_pc.html) (采用) — 作为补充
- 注意: 非官方文档化API，需UA伪装、慢频率

---

### P1 — 2周内接入 (7项)

#### 8. **Alpha Vantage** (美股备援)
- URL: https://www.alphavantage.co/
- 免费额度: **25次/天** (2026年继续收紧) — 仅做Finnhub备援
- 证据: [AlphaVantage 2026 Guide](https://alphalog.ai/blog/alphavantage-api-complete-guide)

#### 9. **Polygon.io** (美股Level-1)
- 免费额度: 5次/分钟
- 证据: [Polygon vs IEX vs AV 2026](https://www.ksred.com/the-complete-guide-to-financial-data-apis-building-your-own-stock-market-data-pipeline-in-2025/)
- 定位: 美股盘中分钟备援

#### 10. **Financial Modeling Prep (FMP)**
- URL: https://site.financialmodelingprep.com/
- 覆盖: 全球财报比率、DCF、分析师一致预期 — **直连NASDAQ/LSEG/CBOE/TMX**
- 免费额度: 每日250次
- 证据: [FMP developer docs](https://site.financialmodelingprep.com/developer/docs) (采用) — 填补"分析师预测/一致预期"缺口

#### 11. **NASDAQ Data Link (原Quandl)**
- URL: https://data.nasdaq.com/
- 覆盖: 另类数据、商品、宏观、ESG、基金流
- 免费额度: 50次/天(匿名) / 300次/10秒(注册)
- 证据: [Stock Analysis Financial Sources](https://stockanalysis.com/financial-sources/) — 对标产品也在使用

#### 12. **easyquotation** (A股实时盘口)
- URL: https://github.com/shidenggui/easyquotation
- 覆盖: 新浪/腾讯实时盘口/集思录
- 用途: 盘中Level-1报价 + 5档买卖盘 (akshare不稳定时fallback)

#### 13. **Ashare** (双源实时K线自动fallback)
- URL: https://github.com/mpquant/Ashare
- 亮点: **新浪+腾讯双核采集自动故障切换**，填补akshare实时分钟线空隙

#### 14. **pysnowball** (雪球社区+组合)
- URL: https://github.com/uname-yang/pysnowball
- 覆盖: 雪球组合、讨论、关注者数 — **情绪维度首选**
- 合规: 需登录态cookie，非商用

---

### P2 — 1月内接入 (4项)

#### 15. **ApeWisdom Reddit/WSB 情绪**
- URL: https://apewisdom.io/api/
- 覆盖: r/wallstreetbets + r/stocks + r/cryptocurrency 的股票代码提及热度
- 免费: 无Key，速率限制宽松
- 证据: [ApeWisdom官方API](https://apewisdom.io/api/) (采用)

#### 16. **OpenEcon (多源宏观聚合)**
- 覆盖: FRED+世行+IMF+Comtrade+StatsCan+Eurostat+BIS 330,000+指标
- 用途: 作为FRED扩展，跨境贸易/汇率/商品

#### 17. **天眼查/企查查 开放平台** (工商图谱)
- URL: https://open.tianyancha.com/ / https://openapi.qcc.com/
- 覆盖: 1.8亿企业、股东/投资/变更/法律风险
- 免费: **无明确免费额度**，需按次计费；建议注册试用
- 合规: 商用必须授权；P2是因为成本不透明

#### 18. **东方财富股吧讨论 + 同花顺问财** (情绪补位)
- 通过现有search_engines.py搜索引擎辐射，暂不独立适配器

---

## 三、分阶段落地计划

### 阶段一 (P0, D+0 ~ D+14)
1. 新建 `app/adapters/tushare_adapter.py` (继承base_adapter) — 龙虎榜/融资融券
2. 新建 `app/adapters/yfinance_adapter.py` — 美股基线
3. 新建 `app/adapters/finnhub_adapter.py` — 美股新闻+实时
4. 新建 `app/adapters/edgar_adapter.py` — 美股官方财报
5. 新建 `app/adapters/fred_adapter.py` — 宏观
6. 新建 `app/adapters/stats_gov_cn_adapter.py` — 中国宏观
7. 新建 `app/adapters/efinance_adapter.py` — 基金
- 提交: 每适配器独立commit，标签 `[NEW-FILE:#20260415-01]`
- 验证: 三重验证 (单元+集成+端到端)

### 阶段二 (P1, D+14 ~ D+28)
8. FMP/Polygon/Alpha Vantage 统一封装到 `app/adapters/global_backup_adapter.py` (三合一fallback链)
9. `easyquotation_adapter.py` + `ashare_adapter.py` 合并为 `app/adapters/realtime_quote_adapter.py` (A股实时双源fallback)
10. `pysnowball_adapter.py` + NASDAQ Data Link

### 阶段三 (P2, D+28 ~ D+45)
11. ApeWisdom + OpenEcon 接入 `app/adapters/sentiment_adapter.py` + `macro_multi_adapter.py`
12. 天眼查/企查查视预算决策

---

## 四、合规/限频/缓存建议

### 4.1 合规清单
| 数据源 | 合规风险 | 措施 |
|---|---|---|
| Tushare Pro | 低 (官方) | 遵守积分阈值 |
| yfinance/easyquotation/Ashare | 中 (非官方爬虫) | **仅内部研究，禁止对外商业API转售** |
| pysnowball | 中 | 需用户自备cookie，使用条款声明 |
| 天眼查/企查查 | 高 | 必须付费商用授权 |
| SEC EDGAR/FRED/国统局 | 极低 | 官方免费 |

### 4.2 统一限频网关
新增 `app/core/rate_limiter.py` (已有cache.py可扩展)：
- 基于 `token-bucket` 算法，每源独立桶
- Finnhub 60/min, FMP 250/day, AV 25/day
- 全局降级: 超限自动切fallback_manager (现有)

### 4.3 缓存策略
- Tick/分钟: Redis 30秒
- 日线: Redis 12小时
- 财报: Redis 24小时
- 宏观: Redis 24小时
- XBRL/10-K: 本地parquet永久

---

## 五、与14-Agent对接方案

| Agent | 新增数据入口 | 关键接口 |
|---|---|---|
| **行情Agent** | Tushare/yfinance/easyquotation | 分钟K + 实时盘口 |
| **财报Agent** | EDGAR + FMP + Tushare | XBRL结构化 + 一致预期 |
| **宏观Agent** (新) | FRED + 国统局 + OpenEcon | GDP/CPI/PMI/利率 |
| **新闻Agent** | Finnhub + search_engines | 事件驱动 |
| **情绪Agent** (新) | ApeWisdom + pysnowball | WSB提及 + 雪球讨论 |
| **风险Agent** | Tushare龙虎榜/融资融券 + EDGAR Form4 | 异动监测 |
| **基金Agent** | efinance + FMP | 基金净值/持仓 |
| **产业链Agent** (P2新) | 天眼查/企查查 | 股权穿透 |
| **技术分析/量化/事件/估值/合规/对标/研报/投顾** 8个现有Agent | 通过统一DataProvider消费 | 无需改动 |

### 统一接入点
`app/core/data_provider.py` 现有类扩展 provider registry：
```python
PROVIDERS = {
    "tushare": TushareAdapter,
    "yfinance": YFinanceAdapter,
    "finnhub": FinnhubAdapter,
    "edgar": EdgarAdapter,
    "fred": FredAdapter,
    ...
}
# Agent侧调用: data_provider.fetch("daily", symbol="AAPL", source="yfinance")
# fallback_manager自动按优先级链路重试
```

---

## 六、对标产品反推验证

| 产品 | 数据源 | 启示 |
|---|---|---|
| **stockanalysis.com** | S&P Global (默认) + NASDAQ Data Link + **Fiscal.ai** | 三源交叉校验架构可借鉴 |
| **simplywall.st** | S&P Global Market Intelligence | 单源重型 |
| **tikr.com** | S&P Global CapitalIQ | 国际92国136所 |
| **fiscal.ai** | 自采集 — 为Perplexity Finance供数据 | "分钟级披露"是核心指标 |
| **我们的策略** | Tushare+EDGAR+FMP+FRED 四柱 + akshare/efinance 爬虫补位 | **多源+fallback** 替代 S&P Global付费路径 |

证据:
- [Stock Analysis Financial Sources声明](https://stockanalysis.com/financial-sources/)
- [Simply Wall St data sources](https://simplywall.st/analysis-and-financial-data-sources)
- [TIKR / Simply Wall St对比](https://slashdot.org/software/comparison/Simply-Wall-St-vs-TIKR/)
- [fiscal.ai平台](https://fiscal.ai/)

---

## 七、风险与回滚

- **Tushare积分不够**: 保留akshare+baostock主链，Tushare仅覆盖新接口
- **yfinance断供**: Finnhub+FMP双备援
- **爬虫类(easyquotation/efinance)反爬**: 通过 fallback_manager 降级，不影响主流程
- **回滚**: 每适配器为独立文件，移除即回滚；`data_provider.PROVIDERS` 注册表摘除即可

---

## 八、证据清单 (检索时间 2026-04-15 +08:00)

| # | 来源 | 类型 | 采纳 |
|---|---|---|---|
| 1 | https://tushare.pro/document/1?doc_id=290 | 官方 | 是 |
| 2 | https://github.com/Micro-sheep/efinance | 主仓库 | 是 |
| 3 | https://github.com/shidenggui/easyquotation | 主仓库 | 是 |
| 4 | https://github.com/mpquant/Ashare | 主仓库 | 是 |
| 5 | https://finnhub.io/finnhub-stock-api-vs-alternatives | 官方 | 是 |
| 6 | https://www.sec.gov/search-filings/edgar-application-programming-interfaces | 官方 | 是 |
| 7 | https://pypi.org/project/fredapi/ | 官方Python包 | 是 |
| 8 | https://www.cnblogs.com/wang_yb/p/14636575.html | 社区实证 | 是 |
| 9 | https://site.financialmodelingprep.com/developer/docs | 官方 | 是 |
| 10 | https://stockanalysis.com/financial-sources/ | 对标声明 | 是 |
| 11 | https://simplywall.st/analysis-and-financial-data-sources | 对标声明 | 是 |
| 12 | https://fiscal.ai/ | 对标产品 | 是 |
| 13 | https://www.nb-data.com/p/best-financial-data-apis-in-2026 | 行业评测2026 | 是 |
| 14 | https://www.ksred.com/the-complete-guide-to-financial-data-apis-building-your-own-stock-market-data-pipeline-in-2025/ | 行业评测 | 是 |
| 15 | https://apewisdom.io/api/ | 官方 | 是 |
| 16 | https://open.tianyancha.com/api_list | 官方 | 部分 |
| 17 | https://openapi.qcc.com/ | 官方 | 部分 |
| 18 | https://zhuanlan.zhihu.com/p/2005025480454197447 | 2026选型深度文 | 是 |
| 19 | https://alphalog.ai/blog/alphavantage-api-complete-guide | 行业评测2026 | 是 |
| 20 | https://github.com/dgunning/edgartools | 主仓库 | 是 |

---

## 九、下一步执行指令

1. **即刻**: Comdr审批本方案 → 分配子agent起稿 7 个 P0 适配器
2. **D+1**: `app/adapters/` 下开 7 个feature分支并行
3. **D+7**: 首轮集成测试，三重验证
4. **D+14**: P0验收，进入P1
5. **持续**: 每次适配器并入更新 `app/adapters/README.md` 与本文档"现状矩阵"

---

**文档完结** | 撰写时间 2026-04-15 +08:00 | [NEW-FILE:#20260415-01]
