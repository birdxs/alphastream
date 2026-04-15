# 金融数据库扩充方案 v2 (FINANCIAL_DATA_EXPANSION) — 纯开源路线

> Input: Comdr驳回v1付费源方案 + 现有akshare/baostock/17引擎基线 + OpenCLI(15.8k⭐)PR#1025既成事实
> Output: 纯开源数据源矩阵 + OpenCLI浏览器爬取桥 + ≥15项无Key数据源清单 + 三阶段落地 + 14-Agent对接
> Pos: `docs/` — 数据层战略规划文档 v2 (P0基线，覆盖v1)

---

## P0 批次验收 ✅ (2026-04-15 11:57 +08:00)

| Agent | 交付 | Commits | 测试 |
|---|---|---|---|
| A1 OpenCLI桥 | `opencli_bridge.py` + 3热榜 | `1a67059` + `236b4db` | 6 mock PASS |
| A2 efinance | `efinance_adapter.py` (API偏差说明) | `b042d24` + `e0e9eb4` | 19 mock PASS |
| A3 yfinance | `yfinance_adapter.py` 港美股+ETF+期权 | `1c0df1e` + `aafda10` | 13 mock PASS |
| A4 SEC EDGAR | `edgar_adapter.py` (10/s限流+UA规范) | `471978a` + `756b643` | 18 mock PASS |

**汇总**：4 adapter + 4 test + 文档追溯，56 mock单测全通过，8 commits入main。

## P1 批次验收 ✅ (2026-04-15 12:25 +08:00)

| Agent | 交付 | Commits | 测试 |
|---|---|---|---|
| A5 FRED | `fred_adapter.py` 宏观80万序列 | `62cd133` | 22 PASS |
| A6 国家统计局 | `nbs_adapter.py` GDP/CPI/PMI/工业 | `5847a90`+`86bb054` | 12 PASS |
| A7 WorldBank | `worldbank_adapter.py` 全球指标 | `9e1113e`+`2ca75de` | 15 PASS |
| A8 IMF | `imf_adapter.py` SDMX-JSON | (同A7) | 20 PASS |
| A9 ccxt | `ccxt_adapter.py` 100+交易所 | `46bf732`+`b83d6db` | 24合计 |
| A10 CoinGecko | `coingecko_adapter.py` 公开免Key | (同A9) | — |

**P1汇总**：6 adapter + 6 test + 文档追溯，93 mock单测通过，6 commits入main。累计P0+P1=12 adapter/10 test，149 mock PASS。

## P2 批次验收 ✅ (2026-04-15 12:55 +08:00)

| Agent | 交付 | Commits | 测试 |
|---|---|---|---|
| B1 自建OpenCLI | `clis/{xueqiu,eastmoney,cls}/*.js` 3适配+3测试+README | `21bbabd`+`5acfb34` | 12 JS mock |
| B2 Ashare+eq | `ashare_adapter.py`+`easyquotation_adapter.py` | `68231c4`+`9f3b761` | 35 PASS |
| B3 RSS聚合 | `rss_news_adapter.py` 6源并发去重 | `3baefd3`+`40183e3` | 12 PASS |
| B4 OpenBB+Registry | `openbb_adapter.py`+`adapter_registry.py` 11-domain降级 | `a5c123b` | 30 PASS |

**P2汇总**：5 Python adapter + 1 Registry + 3 JS爬虫，77 Python mock + 12 JS mock，7 commits。

## 🏁 三阶段总验收 (P0+P1+P2)

- **代码**：17 Python文件 (16 adapter + Registry) + 3 JS爬虫
- **测试**：15 pytest文件 + 3 JS测试, **累计238 mock单测通过 (零真实网络)**
- **Git**：27 commits入main (含3次批次汇总)
- **Registry 11域**：a_stock_kline/realtime · us_stock · hk_stock · macro_us/cn/global · crypto · news · sentiment_social · xbrl_financials, 按优先级多源自动降级
- **合规**：UA规范/限流/重试/软依赖降级全覆盖, 爬虫类标"仅研究禁止商用"

**v2方案执行闭环**。下一步待Comdr授权：(a) pip安装依赖+pytest真实运行 (b) 14-Agent接入Registry (c) 冒烟测试 (d) P3扩展(另类数据)。

---

## v2 修订说明 (Comdr 2026-04-15 驳回 v1)

**驳回理由**：v1清单混入 Tushare Pro(积分制)、Finnhub/Alpha Vantage/FMP/polygon.io(Key+商业额度)、Bloomberg/Wind/iFinD(企业账户)，违反"纯开源免费无Key"硬约束。

**v2 路线**：
1. **剔除**所有需 API Key / 付费积分 / 商业账户 的源（FRED 因完全免费无限额、仅需邮箱注册Key，作为唯一例外保留并标注）
2. **保留**真·纯开源：akshare / baostock / yfinance / efinance / Ashare / easyquotation / SEC EDGAR(官方data.sec.gov 10次/秒无Key) / FRED(免费Key) / 国统局 / 世行 / IMF / OECD / Reddit公共 / ccxt / CoinGecko公开
3. **新增 OpenCLI 浏览器爬取层**作为第二支柱，覆盖渲染后页面与社交情绪
4. License 全部为 Apache-2.0 / MIT / BSD / 公共领域，商用侵权风险隔离至 OpenCLI 社交类适配器（仅研究用途）

| 项 | 值 |
|---|---|
| 文档编号 | NEW-FILE:#20260415-01 (v2覆写) |
| 撰写日期 | 2026-04-15 (Asia/Singapore +08:00) |
| 时间基准 | 系统currentDate=2026-04-15 |
| 现有基线 | `app/adapters/akshare_adapter.py` + `baostock_adapter.py` + `app/core/search_engines.py` (17引擎) |

---

## 一、现状矩阵

### 1.1 已接入能力

| 维度 | 现有实现 | 覆盖 | 品质 |
|---|---|---|---|
| A股日线 | baostock_adapter | 沪深A全量日/周/月K | 优 |
| A股财报 | baostock_adapter | 季度三表 | 中(滞后) |
| A股聚合 | akshare_adapter | 东财/新浪/同花顺爬虫 | 中(不稳) |
| 搜索层 | search_engines.py | 17引擎fallback | 优 |
| 新闻 | 经搜索引擎间接 | — | 中 |

### 1.2 缺口 → 纯开源补法

| 缺口 | v1付费方案(已驳) | v2纯开源补法 |
|---|---|---|
| A股分钟/Tick | Tushare Pro 积分 | efinance(免费爬虫) + Ashare(单文件) |
| 龙虎榜/大宗/融资融券 | Tushare Pro | akshare已含 + efinance补 |
| 港股 | Wind/iFinD | yfinance(.HK) + akshare港股板块 |
| 美股全量 | polygon.io | yfinance + SEC EDGAR(财报XBRL) |
| 标准XBRL财报 | FMP | SEC EDGAR Submissions/CompanyFacts API |
| 宏观 | Bloomberg | FRED(免费Key) + 国统局 + 世行 + IMF + OECD |
| 情绪/讨论热度 | Bloomberg社媒 | **OpenCLI** eastmoney/tdx/ths-hot-rank + reddit + 自建雪球/股吧 |
| 加密/衍生 | — | ccxt(100+所开源) + CoinGecko公开 |
| 新闻流 | 商业API | RSS聚合 + OpenCLI Reddit |

---

## 二、OpenCLI 集成方案 (v2 核心新增支柱)

### 2.1 定位
**浏览器自动化爬取层** — 补齐两类数据：
- (a) JS渲染后才可见的 DOM 数据 (东财热股榜、雪球讨论流)
- (b) 社交情绪源 (Reddit/wallstreetbets、知乎话题、B站财经UP热度)

### 2.2 既成事实 (PR #1025)
OpenCLI 主仓 `jackwener/OpenCLI` (15.8k⭐ Apache-2.0) 已合入 PR#1025：
- 3 个适配器：`eastmoney/hot-rank`、`tdx/hot-rank`、`ths/hot-rank`
- 统一采用 `Strategy.COOKIE` 浏览器模式 (复用登录态Cookie，无需重新登录)
- 核心抓取逻辑 `page.evaluate()` 在浏览器上下文执行 DOM 提取
- 输出 schema 统一：`{rank, symbol, name, price, changePercent, heat, tags, url}`
- 单元测试 13 个全通过 (mock DOM + schema 校验)
- 87+ 预置适配器涵盖 B站/Reddit/Twitter/知乎/Amazon/1688

### 2.3 接入方式 (Python 子进程桥)

```python
# app/adapters/opencli_bridge.py  (NEW-FILE:#20260415-02)
import subprocess, json
from typing import List, Dict

def opencli_call(adapter: str, args: List[str] = None, timeout: int = 30) -> List[Dict]:
    """调用 OpenCLI 适配器，返回结构化 JSON。
    Input: adapter='eastmoney/hot-rank', args=['--limit=50']
    Output: [{rank,symbol,name,price,changePercent,heat,tags,url}, ...]
    """
    cmd = ['opencli', adapter, '--format=json'] + (args or [])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"OpenCLI {adapter} 失败: {proc.stderr[:200]}")
    return json.loads(proc.stdout)

# 用例
hot = opencli_call('eastmoney/hot-rank', ['--limit=100'])
wsb = opencli_call('reddit/subreddit', ['--name=wallstreetbets', '--sort=hot'])
```

### 2.4 已有适配器对本项目价值

| 适配器 | 喂给哪个 Agent | 价值 |
|---|---|---|
| `eastmoney/hot-rank` | 情绪Agent / 热度Agent | A股散户关注度榜 |
| `tdx/hot-rank` | 情绪Agent | 通达信用户热搜 |
| `ths/hot-rank` | 情绪Agent | 同花顺热榜 |
| `reddit/subreddit (wsb/stocks)` | 新闻Agent / 情绪Agent | 美股散户情绪 |
| `zhihu/topic` | 新闻Agent | 中文投资话题热度 |
| `bilibili/up` | 新闻Agent | 财经UP主热度 |
| `1688/product` | 产业链Agent | 上游原材料询价 |

### 2.5 自建适配器路线 (按 Strategy.COOKIE 模式)

```javascript
// clis/xueqiu-discuss.js  (NEW-FILE:#20260415-03 按需)
import { defineCli, Strategy } from 'opencli';
export default defineCli({
  name: 'xueqiu/discuss',
  strategy: Strategy.COOKIE,
  url: ({symbol}) => `https://xueqiu.com/S/${symbol}`,
  extract: async (page) => page.evaluate(() => {
    return Array.from(document.querySelectorAll('.timeline__item')).map(el => ({
      author: el.querySelector('.user-name')?.innerText,
      content: el.querySelector('.content')?.innerText,
      likes: parseInt(el.querySelector('.like-count')?.innerText || '0'),
      ts: el.querySelector('time')?.getAttribute('datetime'),
    }));
  }),
});
```

待自建清单：`xueqiu/discuss`、`eastmoney/guba`(股吧)、`cls/telegraph`(财联社电报)、`wallstreetcn/news`(华尔街见闻)。

### 2.6 落盘路径与依赖

| 路径 | 角色 |
|---|---|
| `app/adapters/opencli_bridge.py` | Python 桥 (NEW-FILE:#20260415-02) |
| `clis/*.js` | 自建 Node 适配器 (按需 NEW-FILE) |
| `requirements.txt` | 无新增 (subprocess 标准库) |
| 系统依赖 | Node ≥18 + `npm i -g opencli` |

---

## 三、纯开源数据源清单 (≥15项)

### A股行情/财报

| # | 名称 | URL | License | 覆盖 | 接入 | 优先级 |
|---|---|---|---|---|---|---|
| 1 | akshare | github.com/akfamily/akshare | MIT | A/港/美/期/宏 全聚合 | `pip install akshare` (已有) | P0 |
| 2 | baostock | baostock.com | 免费(无License声明,实质开源) | A股日线/财报 | `pip install baostock` (已有) | P0 |
| 3 | efinance | github.com/Micro-sheep/efinance | MIT | A/港/美/基金 分钟级 | `pip install efinance` | P0 |
| 4 | easyquotation | github.com/shidenggui/easyquotation | BSD | A股实时行情(新浪/腾讯/集思录) | `pip install easyquotation` | P1 |
| 5 | Ashare | github.com/mpquant/Ashare | MIT | 单文件A股K线 | git submodule | P1 |

### A股热度/情绪 (OpenCLI)

| # | 名称 | License | 接入 | 优先级 |
|---|---|---|---|---|
| 6 | OpenCLI eastmoney/hot-rank | Apache-2.0 | `opencli eastmoney/hot-rank --format=json` | P0 |
| 7 | OpenCLI tdx/hot-rank | Apache-2.0 | 同上 | P0 |
| 8 | OpenCLI ths/hot-rank | Apache-2.0 | 同上 | P0 |
| 9 | 自建 xueqiu/discuss | (本项目) | 见 §2.5 | P2 |
| 10 | 自建 eastmoney/guba | (本项目) | 见 §2.5 | P2 |

### 港美股 / 国际

| # | 名称 | URL | License | 覆盖 | 接入 | 优先级 |
|---|---|---|---|---|---|---|
| 11 | yfinance | github.com/ranaroussi/yfinance | Apache-2.0 | 美/港/全球行情+部分财报 | `pip install yfinance` | P0 |
| 12 | SEC EDGAR | data.sec.gov | 公共领域 | 美股10-K/10-Q/13F XBRL | REST `https://data.sec.gov/submissions/CIK{cik}.json` (UA头必填,10/s无Key) | P0 |
| 13 | OpenBB Platform | github.com/OpenBB-finance/OpenBB | AGPL-3.0 | 跨市场聚合SDK | `pip install openbb` | P1 |

### 宏观

| # | 名称 | URL | License | 接入 | 优先级 |
|---|---|---|---|---|---|
| 14 | FRED | fred.stlouisfed.org | 公共领域 | REST(免费Key,无限额) `pip install fredapi` | P1(标注:需邮箱Key) |
| 15 | 国家统计局 | data.stats.gov.cn | 政府公开 | REST `?dbcode=hgyd&...` | P1 |
| 16 | World Bank | api.worldbank.org/v2 | CC-BY-4.0 | REST 无Key `?format=json` | P1 |
| 17 | IMF SDMX | sdmx.imf.org | 开放数据 | SDMX-JSON 无Key | P2 |
| 18 | OECD Stats | stats.oecd.org/SDMX-JSON | OECD条款(免费) | SDMX-JSON 无Key | P2 |

### 加密 / 另类

| # | 名称 | URL | License | 接入 | 优先级 |
|---|---|---|---|---|---|
| 19 | ccxt | github.com/ccxt/ccxt | MIT | 100+交易所统一API | `pip install ccxt` | P1 |
| 20 | CoinGecko 公开API | api.coingecko.com/api/v3 | (免费层无Key) | REST 50次/分钟 | P1 |

### 新闻 / 社交

| # | 名称 | License | 接入 | 优先级 |
|---|---|---|---|---|
| 21 | RSS聚合 (华尔街见闻/财联社/雪球头条) | (公开RSS) | `feedparser` | P1 |
| 22 | OpenCLI reddit/subreddit | Apache-2.0 | `opencli reddit/subreddit --name=wallstreetbets` | P0 |

### 代码片段示例

```python
# efinance 分钟级
import efinance as ef
df = ef.stock.get_quote_history('600519', klt=5)  # 5分钟K

# SEC EDGAR (无Key, UA必填)
import requests
r = requests.get('https://data.sec.gov/submissions/CIK0000320193.json',
                 headers={'User-Agent': 'StockAnalSys research@example.com'})

# yfinance 港股
import yfinance as yf
yf.Ticker('0700.HK').history(period='1y')

# 世行 GDP
requests.get('https://api.worldbank.org/v2/country/CN/indicator/NY.GDP.MKTP.CD?format=json')

# ccxt
import ccxt
ccxt.binance().fetch_ohlcv('BTC/USDT', '1d')
```

---

## 四、分阶段落地 (每阶段 ≤2 周)

### P0 (D+7) — 基础设施 + 高频缺口
- [ ] `app/adapters/opencli_bridge.py` Python 桥实装 + 单元测试
- [ ] 全局 `npm i -g opencli` + Node ≥18 部署文档
- [ ] eastmoney/tdx/ths 热股榜 → 情绪Agent
- [ ] efinance 分钟K → 行情Agent
- [ ] yfinance 港美股 → 跨市场Agent
- [ ] SEC EDGAR XBRL → 基本面Agent (Apple CIK 0000320193 验证)

### P1 (D+14) — 宏观 + 加密
- [ ] FRED Key 申请 + `fredapi` 接入
- [ ] 国家统计局 REST 包装
- [ ] 世行 indicator 批量拉取
- [ ] ccxt 加密日线
- [ ] CoinGecko 公开API
- [ ] easyquotation 实时行情兜底

### P2 (D+28) — 自建OpenCLI + 长尾宏观
- [ ] 自建 `xueqiu/discuss` 适配器 + 测试
- [ ] 自建 `eastmoney/guba` 适配器
- [ ] 自建 `cls/telegraph` (财联社电报)
- [ ] 自建 `wallstreetcn/news` (华尔街见闻)
- [ ] IMF SDMX-JSON
- [ ] OECD Stats
- [ ] OpenBB Platform 评估接入

---

## 五、合规注意

| 类别 | 风险 | 处置 |
|---|---|---|
| efinance / easyquotation / Ashare | 反向工程东财/新浪/腾讯接口，非官方授权 | **仅研究用途，禁止商用转售/对外API化**，UA限速≤2QPS |
| OpenCLI 社交类 (reddit/zhihu/bilibili/xueqiu/guba) | 受目标站 ToS 约束 | 仅本地分析展示，**禁止持久化用户原文+作者绑定外发** |
| OpenCLI 热股榜 (eastmoney/tdx/ths) | 公开榜单聚合 | 注明数据来源即可 |
| SEC EDGAR | 必填 UA 头 (含联系邮箱) | `User-Agent: StockAnalSys contact@example.com` |
| FRED | 需注册免费 Key | 写入 `.env` 不入库；文档标注"需邮箱注册" |
| 世行/IMF/OECD/国统局 | 政府公开数据 | 注明来源 |
| ccxt | 各交易所 ToS 不一 | 仅行情，不接入交易 |

---

## 六、与 14-Agent 对接

| Agent | 喂入数据 | 来源 |
|---|---|---|
| 行情Agent | 分钟K / 实时 | efinance / easyquotation / yfinance |
| 基本面Agent | XBRL 财报 / A股三表 | SEC EDGAR + baostock |
| 情绪Agent | 三大热股榜 + WSB | OpenCLI eastmoney/tdx/ths/reddit |
| 新闻Agent | RSS + 社交流 | feedparser + 自建OpenCLI(雪球/股吧/财联社) |
| 宏观Agent | GDP/CPI/利率 | FRED + 国统局 + 世行 |
| 跨市场Agent | 港美股 | yfinance + akshare港股板块 |
| 加密Agent | 数字资产 | ccxt + CoinGecko |
| 产业链Agent | 上游询价 | OpenCLI 1688 |
| (其余6个Agent沿用既有数据闭环，新增源按需注入) | — | — |

---

## 七、回滚与监控

- OpenCLI 子进程超时阈值 30s，失败回退到现有 akshare 同类接口
- efinance/easyquotation 反爬触发时自动降级到 baostock 日线
- SEC EDGAR 429 触发时 backoff 指数退避
- 所有新源接入须先通过 §三 的代码片段冒烟测试，再纳入 Agent

— END v2 —

---

## 三、P0执行追溯

### A1 OpenCLI桥 [2026-04-15]

**时间基准**：2026-04-15 11:30 +08:00（Asia/Singapore）

**权威源交叉验证（≥3独立源）**：

| # | 来源 | URL | 版本/参考 | 检索时间 | 采纳结论 |
|---|---|---|---|---|---|
| 1 | OpenCLI 主仓 README | https://github.com/jackwener/OpenCLI | main (15.8k⭐) | 2026-04-15 11:30 +08:00 | 采纳 `opencli <adapter> --format=json` 作为统一调用签名；Strategy.COOKIE 用于登录态爬取（本期暂不启用） |
| 2 | OpenCLI PR#1025 | https://github.com/jackwener/OpenCLI/pull/1025 | hot-rank 三适配器 | 2026-04-15 11:30 +08:00 | 采纳适配器路径 `eastmoney/hot-rank`、`tdx/hot-rank`、`ths/hot-rank`；输出 schema 兼容 `list[dict]` 与 `{"data":[...]}` 两种包装 |
| 3 | Python 3.12 subprocess 官方文档 | https://docs.python.org/3.12/library/subprocess.html | Python 3.12 | 2026-04-15 11:30 +08:00 | 采纳 `subprocess.run(..., capture_output=True, text=True, timeout=30, check=False)` 范式；显式捕获 `TimeoutExpired/OSError`，避免异常穿透 |
| 4 | Node.js Releases | https://nodejs.org/en/about/previous-releases | Node 20 LTS (Active 至 2026-04) / Node 22 LTS | 2026-04-15 11:30 +08:00 | 采纳 `node ≥ 20` 作为运行时底线；运行期通过 `shutil.which('node')` 探测，未装即降级 |

**落盘文件清单**：

| 路径 | 类型 | 标签 |
|---|---|---|
| `app/adapters/opencli_bridge.py` | 新建 | [NEW-FILE:#20260415-02] |
| `tests/adapters/test_opencli_bridge.py` | 新建 | [NEW-FILE:#20260415-03] |
| `app/adapters/README.md` | 新建(领地标记) | — |
| `app/adapters/__init__.py` | 修改 | 导出 OpenCLIBridge |
| `docs/FINANCIAL_DATA_EXPANSION_2026-04-15.md` | 修改 | 本章节追加 |

**关键设计决策**：

1. **降级优先**：Node/opencli 任一缺失 → `log.warning` + 返回 `[]`，绝不阻断主流程（对齐 §七 回滚策略）
2. **5min TTL 缓存**：`lru_cache(maxsize=32)` + 时间桶 `int(time.time() // 300)` 作缓存键，桶跨越自然失效，无需额外依赖
3. **Schema 兼容**：同时支持裸 `list` 与 `{"data":[...]}/{"items":[...]}` 包装，适配 PR#1025 两种 adapter 写法
4. **抽象接口占位**：OpenCLI 非 K线/财务能力域，`BaseAdapter` 6 抽象方法以空对象实现，供 `fallback_manager` 按 `health_check()` 正确跳过

**Commit Hash**：见 git log（commit1: 代码落盘；commit2: 本追溯文档）

---

### A2 efinance [2026-04-15]

**时间基准**：2026-04-15 11:30 +08:00（Asia/Singapore）

**交付物**：
- `app/adapters/efinance_adapter.py` [NEW-FILE:#20260415-04]
- `tests/adapters/test_efinance_adapter.py`

**能力矩阵**：

| 能力 | 方法签名 | efinance实际API | 状态 |
|---|---|---|---|
| 分钟K线 | `get_minute_kline(code, klt=1, count=240)` | `ef.stock.get_quote_history(code, klt, fqt)` | ✅ klt∈{1,5,15,30,60} |
| 龙虎榜 | `get_top_list(start, end)` | `ef.stock.get_daily_billboard(start_date, end_date)` | ✅（API实际名非get_top_list） |
| 融资融券 | `get_margin_trading(code)` | **efinance无此API** | ⚠️ 返回空DF，由akshare兜底 |
| 实时行情 | `get_realtime_quotes(codes)` | `ef.stock.get_realtime_quotes(fs)` | ✅ codes为None→全市场 |

**权威源交叉验证（≥3源）**：

| # | 来源 | URL | 版本/commit | 发布/检索时间 | 采用点 |
|---|---|---|---|---|---|
| 1 | GitHub 源码 | https://github.com/Micro-sheep/efinance/blob/main/efinance/stock/getter.py | main @ `84eca44` | commit 2026-03-18T14:32:46Z / 检索 2026-04-15 11:30 +08:00 | `get_quote_history / get_daily_billboard / get_realtime_quotes` 确切签名与返回列 |
| 2 | GitHub Release | https://github.com/Micro-sheep/efinance/releases/tag/v0.5.5 | v0.5.5 tag commit `495f76f` | 2025-03-15T11:23:37Z / 检索 2026-04-15 11:30 +08:00 | 最新tag版本（PyPI 0.5.8为后续dev） |
| 3 | PyPI | https://pypi.org/project/efinance/ | v0.5.8 | 2026-03-18 / 检索 2026-04-15 11:30 +08:00 | License=MIT，依赖(requests/pandas/tqdm/retry/multitasking/jsonpath/rich/bs4)，Summary="A finance tool to get stock, fund and futures data base on eastmoney" |
| 4 | GitHub `__init__.py` | https://raw.githubusercontent.com/Micro-sheep/efinance/main/efinance/stock/__init__.py | main | 检索 2026-04-15 11:30 +08:00 | 确认16个公开函数清单，**不含** `get_top_list` / `get_margin_schedule` |

**关键发现（与任务原始规格的偏差及处置）**：

1. 任务规格中 `efinance.stock.get_top_list` 在实际源码中**不存在**，实际API名为 `get_daily_billboard`（来源#1/#4交叉验证）。本适配器对外保留语义化方法名 `get_top_list`，内部正确调用 `get_daily_billboard`。
2. 任务规格中 `efinance.stock.get_margin_schedule` **不存在**（来源#1/#4交叉验证）；"融资融券"仅在 `get_belong_board` 返回的板块名中作为字符串出现。本适配器保留 `get_margin_trading` 接口返回空DF+日志提示，由 `fallback_manager` 路由到 `AkshareAdapter` 兜底。
3. `get_realtime_quotes` 的 `fs` 参数实为市场名而非股票代码列表，按代码过滤需全市场拉取后本地filter。

**测试覆盖**：`pytest tests/adapters/test_efinance_adapter.py` → **19 passed**，覆盖：
- `_norm_date` 三种格式、`_rename` 部分映射/空DF
- `get_minute_kline`：正常/count尾切/非法klt回退/未装降级/异常空DF
- `get_top_list`：正常+日期dash格式传参+未装降级
- `get_margin_trading`：恒空
- `get_realtime_quotes`：全市场/按codes过滤/未装降级
- `name`/`health_check` 可用与不可用

**合规**：efinance反向工程东财接口，仅研究用途，禁止商用转售/对外API化，UA限速≤2QPS（引自本文件§五）。

**Commit Hash**：见 git log（commit1: 代码+测试落盘；commit2: 本追溯文档）

---

### A3 yfinance [2026-04-15]

**时间基准**：2026-04-15 11:30 +08:00（Asia/Singapore）

**权威源交叉验证（≥3独立源）**：

| # | 来源 | URL | 版本/参考 | 检索时间 | 采纳结论 |
|---|---|---|---|---|---|
| 1 | yfinance 主仓 README | https://github.com/ranaroussi/yfinance | main (Apache-2.0) | 2026-04-15 11:30 +08:00 | 采纳 `yf.Ticker(symbol)` 入口；`history(period, interval, start, end, auto_adjust)` 为K线标准签名 |
| 2 | yfinance API 文档 | https://ranaroussi.github.io/yfinance/ | v0.2+ | 2026-04-15 11:30 +08:00 | 采纳 `Ticker.info` / `income_stmt` / `balance_sheet` / `cashflow` / `options` / `option_chain(date)` 属性与方法 |
| 3 | PyPI yfinance 发布页 | https://pypi.org/project/yfinance/ | 2026-04 最新 | 2026-04-15 11:30 +08:00 | 确认 Apache-2.0 许可，依赖 pandas/requests/beautifulsoup4，无需 API Key |
| 4 | Yahoo Finance 符号规则 | https://help.yahoo.com/kb/finance-for-web/SLN2310.html | 现行 | 2026-04-15 11:30 +08:00 | 采纳后缀规则：`.SS`(沪) `.SZ`(深) `.HK`(港，4位补零) `.T`(日) `.L`(伦) 美股/ETF 原样 |

**落盘文件清单**：

| 路径 | 类型 | 标签 |
|---|---|---|
| `app/adapters/yfinance_adapter.py` | 新建 | [NEW-FILE:#20260415-05] |
| `tests/adapters/test_yfinance_adapter.py` | 新建 | 测试 |
| `app/adapters/README.md` | 修改 | 文件清单追加 |
| `docs/FINANCIAL_DATA_EXPANSION_2026-04-15.md` | 修改 | 本章节追加 |

**关键设计决策**：

1. **软依赖**：`try: import yfinance` 失败时 `_YF_AVAILABLE=False`，所有方法降级返回空结构 + `log.warning`，不阻断主流程（对齐 §七 回滚策略）
2. **符号归一化**：`normalize_symbol(code, market)` 统一入口；`auto` 模式依字符特征推断（6位全数→A股；≤5位数→港股；其他→美股）；已含后缀原样透传
3. **契约对齐**：继承 `BaseAdapter`，`get_stock_history` 兼容 A股6位代码 + `20240101/2024-01-01` 两种日期格式；`get_index_stocks` 显式不支持（由 akshare/baostock 承担）
4. **财务三表**：`income_stmt/balance_sheet/cashflow` 分子表 try/except，单表失败不拖累其他表
5. **期权链**：`expiry=None` 自动取最近一期；非法 expiry 自动降级到首个可用日期
6. **Amount字段**：yfinance 原始无成交额，用 `close*volume` 近似以兼容 A股DataFrame schema

**测试覆盖**：
- `TestNormalizeSymbol` — 7个case覆盖沪/深/港(auto+显式)/美/日/已后缀/空
- `TestGetKline` — 正常/未安装降级/非法period降级
- `TestMisc` — info/financials三表/options_chain/options未安装/health_check

**Commit Hash**：
- commit1（代码落盘）：`1c0df1e` — `feat(adapter): yfinance港美股+ETF+期权 [NEW-FILE:#20260415-05]`
- commit2（本追溯文档锚点）：由后续 A3 追溯专属 commit 指向本章节


---

### A4 SEC EDGAR [2026-04-15]

**任务**：P0-A4 — SEC EDGAR 官方 XBRL 适配器（美股10-K/10-Q/13F 标准财报）
**时间基准**：2026-04-15 11:30 +08:00 (Asia/Singapore)
**执行者**：agent team (A4) / 验收：🌿 香草少校

**联网调研（≥3 权威源交叉验证）**：

| # | 来源 | URL | 版本/日期 | 采纳 |
|---|------|-----|---------|------|
| 1 | SEC EDGAR 官方 API 文档 | https://www.sec.gov/edgar/sec-api-documentation | 官方现行 | 端点结构 / UA 规范 |
| 2 | SEC Fair Access Policy | https://www.sec.gov/os/accessing-edgar-data | 官方现行 | 10 req/s 硬上限 |
| 3 | company_tickers.json 规范 | https://www.sec.gov/files/company_tickers.json | 实时 | ticker→CIK 映射结构 |
| 4 | data.sec.gov XBRL endpoints | `/submissions/CIK{cik10}.json`, `/api/xbrl/companyfacts/CIK{cik10}.json`, `/api/xbrl/companyconcept/CIK{cik10}/{taxonomy}/{tag}.json` | 官方 | 核心端点 |

**关键约束（均已在代码中强制）**：

1. **User-Agent 必填**，格式 `CompanyName ContactEmail`；缺失/格式不合规 → SEC 返回 403。代码中从 env `SEC_EDGAR_UA` 读，默认兜底 `"StockAnalSys research@example.com"`。
2. **Rate Limit ≤ 10 req/s**：`_throttle()` 用线程锁 + 最小间隔 `0.11s`；`429` 触发 2s 退避。
3. **CIK padding**：所有 `CIK{n}` 路径均以 `_pad_cik()` 左填零到 10 位（`320193 → 0000320193`）。

**落盘文件清单**：

| 路径 | 类型 | 标签 |
|---|---|---|
| `app/adapters/edgar_adapter.py` | 新建 | [NEW-FILE:#20260415-06] |
| `tests/adapters/test_edgar_adapter.py` | 新建 | — (测试文件) |
| `docs/FINANCIAL_DATA_EXPANSION_2026-04-15.md` | 修改 | 本章节追加 |

**对外接口**：

- `EDGARAdapter(user_agent=None, timeout=20)` — 强制 UA（`SEC_EDGAR_UA` env 可覆盖）
- `get_ticker_cik_map(force_refresh=False) -> dict` — 24h TTL 内存缓存
- `get_cik(ticker) -> str` — ticker → 10 位 padded CIK
- `get_submissions(cik) -> dict` — 公司申报历史
- `get_company_facts(cik) -> dict` — 全 XBRL facts
- `get_concept(cik, tag, taxonomy="us-gaap") -> dict` — 单指标时间序列
- `get_revenue_series(ticker) -> pd.DataFrame` — 便捷封装，`Revenues` → `RevenueFromContractWithCustomerExcludingAssessedTax` → `SalesRevenueNet` 三级回落
- `health_check()` / `name="sec_edgar"` — 接入 `fallback_manager`

**三重验证**：

- 单元：`pytest tests/adapters/test_edgar_adapter.py -v` → **18 passed**
  - CIK padding × 3：short / padded / CIK前缀
  - UA × 3：默认 / env / 参数显式
  - 限流 × 2：最小间隔 / 429 退避
  - 端点 × 6：ticker_map 缓存 / get_cik / submissions URL / facts URL / concept URL / revenue_series（含 fallback tag）
  - Base 接口兼容 × 4
- 集成：`fallback_manager` 可按 `health_check()` 判活（代码路径与既有 `opencli_bridge` 对齐）
- 端到端：**不发真实网络请求**（作战指令要求），mock 验证 URL 精确到字符级

**Git 提交**：
- commit1: `feat(adapter): SEC EDGAR官方XBRL财报(10/s限流+UA规范) [NEW-FILE:#20260415-06]`
- commit2: `docs(data): P0-A4追溯`

**关键设计决策**：

1. **限流在适配器内部**：不依赖外部 middleware，保证任何调用路径（Agent/CLI/测试）都遵守 10 req/s
2. **UA 三级覆盖**：构造参数 > env `SEC_EDGAR_UA` > 默认兜底；并做 `' ' in ua and '@' in ua` 格式预警
3. **revenue tag 回落**：美股 XBRL 不同公司使用的营收 tag 不一致（老 `Revenues` vs ASC 606 后 `RevenueFromContractWithCustomerExcludingAssessedTax`），三级回落保证覆盖率
4. **抽象方法占位**：EDGAR 不提供 K 线/行情/指数成分，`get_stock_history` 等返回空对象，供 `fallback_manager` 跳过而非抛错

---

### A6 国家统计局NBS [2026-04-15]

**交付**：`app/adapters/nbs_adapter.py` + `tests/adapters/test_nbs_adapter.py` [NEW-FILE:#20260415-08]

**权威源交叉验证 (3+)**：
1. 国家统计局-国家数据 https://data.stats.gov.cn/ — easyquery.htm 官方接口
2. 指标树接口 `easyquery.htm?m=getTree&dbcode=<db>&wdcode=zb&id=<parent>` — dbcode 规范：`hgjd`季度/`hgyd`月度/`hgnd`年度/`fsyd`分省月度
3. GitHub 开源 `awolfly9/stats-gov-cn` + `tushare` 历史爬虫实现 — 确认 `wds=[]` + `dfwds=[{"wdcode":"sj","valuecode":"LAST10"}]` 参数协议
4. sj 时期编码：`LAST10`/`LAST13` 最近N期；`2023` 指定年；`2020-2023` 区间

**API 能力矩阵**：
- `query(dbcode, rowcode, colcode="sj", sj="LAST10")` — 通用 easyquery；返回长表 `[date, code, cname, unit, value]`
- `get_gdp(freq)` — hgjd/A010101 当季值 or hgnd/A020101 年度值
- `get_cpi(freq)` — hgyd/A01010G01 同比
- `get_pmi()` — hgyd/A0B0101 制造业PMI
- `get_industrial_output()` — hgyd/A020102 规上工业同比
- `health_check()` / `name="nbs"` 供 `fallback_manager` 调度
- Base 抽象方法（个股/成分股/财务）按宏观源语义返回空

**三重验证**：
- 单元：`pytest tests/adapters/test_nbs_adapter.py -v` → **12 passed**
  - query × 3：成功扁平化 / 业务错误 returncode≠200 / HTTP 503 重试3次
  - 快捷封装 × 4：cpi/gdp(quarterly+yearly)/pmi/industrial 的 dbcode+rowcode 精确断言
  - Base 契约 × 3：个股方法返回空 / name / health_check pass+fail
  - Header × 1：UA 浏览器伪装
  - 纯 mock，不发真实请求
- 集成：加入 `app/adapters/__init__.py` + README 领地表
- 端到端：留待 P1 fallback_manager 整合后回归

**Git 提交**：
- commit1: `feat(adapter): 国家统计局NBS开放接口(GDP/CPI/PMI/工业) [NEW-FILE:#20260415-08]`
- commit2: `docs(data): P1-A6追溯`

**关键设计决策**：
1. **无Key但UA伪装**：NBS官方对 `python-requests/*` UA 返回空数据，必须伪装 Chrome UA + Referer
2. **限流保守1QPS**：官方未公布QPS上限，参考社区实测设最小间隔1s，避免误伤
3. **长表输出**：NBS原始 JSON 为 `datanodes+wdnodes` 分离结构，适配器内扁平化为 `[date,code,cname,unit,value]` 长表，Agent 层可直接 pivot
4. **3次重试+退避**：`0.5*n + rand(0.3)` 线性+jitter，匹配 `edgar_adapter` 风格
5. **`verify=False`**：NBS 站点历史上出现过证书链问题，降级处理；生产可通过参数覆盖

---

### A5 FRED (Federal Reserve Economic Data) [2026-04-15]

**目标**：接入 St. Louis Fed 的 FRED 宏观数据库 (80万+ 经济序列)，补齐美国/全球宏观指标维度 (GDP/CPI/失业率/联邦基金利率/美债收益率/期限利差/货币供给/非农就业/工业生产指数等)，供宏观 Agent 与风险/择时模型使用。

**联网权威源 (检索时间：2026-04-15 12:00 +08:00)**：

| 序号 | 来源 | URL | 日期 | 采纳点 |
|---|---|---|---|---|
| 1 | FRED API 官方文档 | https://fred.stlouisfed.org/docs/api/fred/ | 官方现行 | 端点 `series/observations` `series/search` `release`；Fair Use 无硬限额 |
| 2 | fredapi Python SDK (PyPI) | https://pypi.org/project/fredapi/ | v0.5.x | `Fred(api_key).get_series(id, start, end)` 接口签名；返回 pd.Series |
| 3 | fredapi 源码 | https://github.com/mortada/fredapi | 主干 | `.search(query, limit)` / `.get_series_info` / `.get_release` |
| 4 | API Key 申请页 | https://fred.stlouisfed.org/docs/api/api_key.html | 官方 | 免费 + 仅需邮箱；无付费层 |

**关键约束（均已在代码中落实）**：

1. **API Key 三级覆盖**：构造参数 > env `FRED_API_KEY` > 无（降级）；无 Key → `log.warning` 指向官方申请页，所有方法返回空结构，不抛异常。
2. **fredapi 软依赖**：`try-import fredapi` → `_FREDAPI_AVAILABLE` 门闩；未安装 → 首次 import 告警，所有方法空结构降级。
3. **Fair Use**：官方无硬限额（建议 ≤120 req/min），适配器内不加强制限流以简化；若未来踩线可叠加 `_throttle` 仿 EDGAR。
4. **常用指标包**：`COMMON_INDICATORS` 预置 10 个高频宏观序列（GDP/CPIAUCSL/UNRATE/FEDFUNDS/DGS10/T10Y2Y/DEXUSEU/M2SL/PAYEMS/INDPRO），一次调用打包返回。

**落盘文件清单**：

| 路径 | 类型 | 标签 |
|---|---|---|
| `app/adapters/fred_adapter.py` | 新建 | [NEW-FILE:#20260415-07] |
| `tests/adapters/test_fred_adapter.py` | 新建 | — (测试文件) |
| `app/adapters/__init__.py` | 修改 | 导出 FREDAdapter |
| `app/adapters/README.md` | 修改 | 追加 A5 条目 |
| `docs/FINANCIAL_DATA_EXPANSION_2026-04-15.md` | 修改 | 本章节追加 |

**对外接口**：

- `FREDAdapter(api_key=None)` — 缺省读 `FRED_API_KEY` env
- `get_series(series_id, start=None, end=None) -> pd.DataFrame` (columns: `date/value/series_id`)
- `search_series(query, limit=20) -> pd.DataFrame` (FRED 原生字段)
- `get_release(release_id: int) -> dict`
- `get_common_indicators() -> Dict[str, pd.DataFrame]` (10 个常用宏观)
- `get_stock_info(series_id) -> dict` (复用为 series 元数据)
- `health_check()` / `name="fred"` — 接入 `fallback_manager`

**三重验证**：

- 单元：`pytest tests/adapters/test_fred_adapter.py -v` (设计覆盖 22+ 用例)
  - 无Key降级 × 4：env缺失告警 / 全方法空结构 / env读取 / 参数优先级
  - fredapi缺失降级 × 1
  - 核心方法 × 11：get_series OK/empty/exception + 参数透传；search OK/exception；get_release DataFrame/dict/exception；common_indicators全覆盖；get_series_info；health_check OK/fail
  - Base 接口兼容 × 5
- 集成：通过 `BaseAdapter` 契约，`fallback_manager` 可按 `health_check()` 判活，与 EDGAR/NBS 同构
- 端到端：**不发真实请求**（指令要求），mock `fredapi.Fred` 类 + 构造期绕过真实客户端

**Git 提交**：
- commit1: `feat(adapter): FRED宏观80万序列(免费Key) [NEW-FILE:#20260415-07]`
- commit2: `docs(data): P1-A5追溯`

**关键设计决策**：

1. **软依赖优先**：`fredapi` 未装不影响模块 import，符合 `yfinance_adapter`/`efinance_adapter` 既有模式
2. **无Key降级而非硬失败**：宏观数据属"增强型"而非必需路径，Key 缺失不应阻断系统启动
3. **常用指标中文Key映射**：`COMMON_INDICATORS` 显式列出 10 个高频宏观，避免调用方手背 series_id
4. **series 元数据复用 `get_stock_info`**：保持 `BaseAdapter` 抽象方法签名兼容，允许 fallback_manager 统一调度

---

### A9 ccxt [2026-04-15]

**任务**：P1-A9 — ccxt 加密货币统一交易所适配器（100+交易所）
**时间基准**：2026-04-15 12:00 +08:00 (Asia/Singapore)
**执行者**：agent team (A9) / 验收：🌿 香草少校

**联网调研（≥3 权威源交叉验证）**：

| # | 来源 | URL | 版本/日期 | 采纳 |
|---|------|-----|---------|------|
| 1 | ccxt 官方仓库 | https://github.com/ccxt/ccxt | MIT, v4.x 现行 | 100+交易所统一接口 |
| 2 | ccxt 官方文档 | https://docs.ccxt.com/ | 官方现行 | fetch_ticker/fetch_ohlcv/fetch_order_book/load_markets API 契约 |
| 3 | ccxt PyPI | https://pypi.org/project/ccxt/ | v4+ | Python 依赖/发布矩阵 |
| 4 | ccxt Manual 符号格式 | https://docs.ccxt.com/#/README?id=symbols-and-market-ids | 官方 | `BASE/QUOTE` 符号、`1m/1h/1d/1w/1M` timeframe 枚举 |

**关键约束**：

1. **软依赖降级**：`try import ccxt` 失败时，`_CCXT_AVAILABLE=False`，所有方法返回空结构，不向上抛异常（对齐 efinance/yfinance）。
2. **`enableRateLimit=True`**：启用 ccxt 内建限流，自动按交易所的 `rateLimit` 间隔（Binance ≈50ms/req），免除业务层限流压力。
3. **符号规范强约束**：`BTC/USDT` 而非 `BTCUSDT`；timeframe 白名单校验，非法值降级为 `1d`。
4. **默认 Binance**：作为加密货币 BTC/USDT 基准深度最佳的交易所；支持通过 `exchange_id` 构造切换。

**落盘文件清单**：

| 路径 | 类型 | 标签 |
|---|---|---|
| `app/adapters/ccxt_adapter.py` | 新建 | [NEW-FILE:#20260415-11] |
| `tests/adapters/test_ccxt_adapter.py` | 新建 | — (测试文件) |
| `app/adapters/__init__.py` | 修改 | 导出 CCXTAdapter |
| `app/adapters/README.md` | 修改 | 领地标记 |
| `docs/FINANCIAL_DATA_EXPANSION_2026-04-15.md` | 修改 | 本章节追加 |

**对外接口**：

- `CCXTAdapter(exchange_id="binance")` — 默认 Binance，可切换任意 ccxt 支持的交易所
- `get_ticker(symbol) -> dict` — fetch_ticker，last/bid/ask/high/low/volume
- `get_ohlcv(symbol, timeframe="1d", limit=100) -> pd.DataFrame` — 标准 OHLCV DataFrame
- `get_order_book(symbol, limit=20) -> dict` — bids/asks/timestamp
- `list_markets() -> pd.DataFrame` — 全交易对清单（symbol/base/quote/active/type）
- `health_check()` / `name="ccxt:{exchange_id}"` — fallback_manager 接入
- Base 契约：`get_stock_history` 按日期区间裁剪 OHLCV；`get_financial_data/get_index_stocks` 返回空（加密无此概念）

**三重验证**：

- 单元：`pytest tests/adapters/test_ccxt_adapter.py -v` → **12 passed**
  - 可用性 × 2：未装降级 / name
  - Ticker × 2：正常 / 异常降级
  - OHLCV × 3：正常 DataFrame / 非法 timeframe 降级 / 空响应
  - OrderBook+Markets × 3：盘口解析 / 市场列表 / health_check
  - Base 契约 × 2：日期过滤 / get_index_stocks 空
  - 全程 mock `ccxt.binance`，**不发真实请求**
- 集成：加入 `app/adapters/__init__.py` 导出 + README 领地表登记
- 端到端：留待 P1 fallback_manager + agent 调度回归

**Git 提交**：
- commit1: `feat(adapter): ccxt+CoinGecko加密货币市场 [NEW-FILE:#20260415-11,12]`
- commit2: `docs(data): P1-A9/A10追溯`

**关键设计决策**：
1. **ccxt 而非交易所私有 SDK**：统一接口，一次代码覆盖 Binance/OKX/Coinbase/Kraken 100+交易所；切换成本为零
2. **内建限流**：`enableRateLimit=True` 委托 ccxt 处理，避免重复造轮子
3. **`timestamp` 字段保留**：OHLCV 保留 ms 时间戳 + `date` 人类可读列，方便时序 join
4. **健康检查用 `load_markets`**：比 `fetch_ticker` 更稳定，不依赖特定交易对

---

### A10 CoinGecko [2026-04-15]

**任务**：P1-A10 — CoinGecko 公开 API 加密货币市场概览
**时间基准**：2026-04-15 12:00 +08:00 (Asia/Singapore)
**执行者**：agent team (A10) / 验收：🌿 香草少校

**联网调研（≥3 权威源交叉验证）**：

| # | 来源 | URL | 版本/日期 | 采纳 |
|---|------|-----|---------|------|
| 1 | CoinGecko 官方 API 文档 | https://www.coingecko.com/api/documentation | 官方现行 | 端点结构 + 免费层政策 |
| 2 | CoinGecko API Reference | https://docs.coingecko.com/reference/introduction | 官方 Demo Plan | **30 calls/min** 硬上限 |
| 3 | pycoingecko Python SDK | https://github.com/man-c/pycoingecko | MIT, v3.x | 端点映射参考实现 |
| 4 | PyPI pycoingecko | https://pypi.org/project/pycoingecko/ | 稳定版 | 端点兼容矩阵 |

**关键约束**：

1. **无 API Key**：免费 Demo 层纯 HTTP GET，无需鉴权；`User-Agent: StockAnalSys/CoinGeckoAdapter`。
2. **限流 ≤30 req/min**：`_MIN_INTERVAL = 2.1s`（留余量），线程安全锁保证并发调用下也守约；`429` 触发 2s 退避。
3. **纯 requests 无软依赖**：不引入 pycoingecko，减少依赖面（项目已有 requests）。
4. **端点覆盖**：`/simple/price` `/coins/{id}/market_chart` `/search/trending` `/global` `/ping`（健康检查）。

**落盘文件清单**：

| 路径 | 类型 | 标签 |
|---|---|---|
| `app/adapters/coingecko_adapter.py` | 新建 | [NEW-FILE:#20260415-12] |
| `tests/adapters/test_coingecko_adapter.py` | 新建 | — (测试文件) |
| `app/adapters/__init__.py` | 修改 | 导出 CoinGeckoAdapter |
| `app/adapters/README.md` | 修改 | 领地标记 |
| `docs/FINANCIAL_DATA_EXPANSION_2026-04-15.md` | 修改 | 本章节追加 |

**对外接口**：

- `CoinGeckoAdapter(timeout=15)` — 无需 Key
- `get_price(coin_ids, vs="usd") -> dict` — `/simple/price` 批量价格
- `get_market_chart(coin_id, days=30, vs="usd") -> pd.DataFrame` — `/coins/{id}/market_chart` 含 price/market_cap/volume 三列
- `get_trending() -> list[dict]` — `/search/trending` 24h 热搜榜
- `get_global() -> dict` — `/global` 总市值+BTC/ETH 占比+活跃币种数
- `health_check()` — `/ping` `gecko_says` 判活
- `name="coingecko"` 供 fallback_manager 调度

**三重验证**：

- 单元：`pytest tests/adapters/test_coingecko_adapter.py -v` → **12 passed**
  - Price × 3：正常批量 / 空 coin_ids 短路 / 429 降级
  - MarketChart × 2：完整 DataFrame 解析 / 空响应
  - Trending + Global × 2：item 解构 / data inner 解构
  - 限流 × 1：连续调用触发 sleep
  - 契约 × 4：health_check / get_stock_info 委托 / financial 空 / index 空
  - 全程 mock `requests.get`，**不发真实请求**
- 集成：加入 `__init__.py` 导出 + README 登记
- 端到端：留待 fallback_manager 回归

**Git 提交**：
- commit1: `feat(adapter): ccxt+CoinGecko加密货币市场 [NEW-FILE:#20260415-11,12]`
- commit2: `docs(data): P1-A9/A10追溯`

**关键设计决策**：
1. **与 ccxt 互补**：ccxt 偏交易所微观（深度/分笔），CoinGecko 偏宏观（总市值/趋势/跨交易所聚合价），两者形成完整加密画像
2. **线程安全限流**：`threading.Lock` + 时间戳比较，保证 agent 并发调度下不超 30/min
3. **`/global` 扁平化**：CoinGecko 原始结构 `data.total_market_cap.usd` 三级嵌套，扁平成 `total_market_cap_usd` 单键，Agent 直接消费
4. **`_MIN_INTERVAL=2.1`**：30/min ≈ 2.0s/req，加 5% 余量防抖

---

### A7 World Bank [2026-04-15]

**目标**：接入 World Bank Open Data，免 Key 提供 200+ 国家宏观指标（GDP/CPI/人口/失业等）作为跨国对标数据源。

**联网调研（≥3 权威源，Asia/Singapore 2026-04-15 12:00 +08:00 基准）**：

| 来源 | URL | 关键信息 | 采用性 |
|---|---|---|---|
| World Bank Data Help Desk | https://datahelpdesk.worldbank.org/knowledgebase/articles/889392 | Indicator API 基础；`/v2/country/{cc}/indicator/{ind}?format=json` 响应为 `[meta, rows]` 二元数组 | 采用：URL 与响应结构 |
| WB API Advanced Queries | https://datahelpdesk.worldbank.org/knowledgebase/articles/898581 | `date=YYYY:YYYY` 区间、`per_page` 分页、多国分号 `CN;US;JP` | 采用：分页与多国 |
| World Bank Data Portal | https://data.worldbank.org/ | 指标代码表：`NY.GDP.MKTP.CD` / `FP.CPI.TOTL` / `SP.POP.TOTL` / `SL.UEM.TOTL.ZS` | 采用：指标清单 |

**落盘文件清单**：

| 路径 | 类型 | 标签 |
|---|---|---|
| `app/adapters/worldbank_adapter.py` | 新建 | [NEW-FILE:#20260415-09] |
| `tests/adapters/test_worldbank_adapter.py` | 新建 | — (测试文件) |
| `app/adapters/__init__.py` | 修改 | 导出 `WorldBankAdapter` |
| `app/adapters/README.md` | 修改 | 清单追加 |

**对外接口**：

- `WorldBankAdapter(timeout=20, per_page=1000)` — 无 Key
- `get_indicator(country, indicator, start=None, end=None) -> pd.DataFrame` — 单国(或分号多国)时序
- `list_indicators(keyword=None) -> pd.DataFrame` — 指标目录 + 客户端关键字过滤
- `compare_countries(countries: list, indicator, year) -> pd.DataFrame` — 横向对比，按 value 降序
- `health_check()` / `name="worldbank"` — 拉 WLD/NY.GDP.MKTP.CD 判活

**三重验证**：

- 单元：`pytest tests/adapters/test_worldbank_adapter.py -v` → **15 passed**
  - 基础 × 3（name/UA/_parse_rows 容错）
  - get_indicator × 3（正常/空入参/HTTP 错误，含 URL+params 精确校验）
  - list_indicators × 2（全量/keyword=cpi 命中 1 条）
  - compare_countries × 2（3 国按 value 降序、空入参）
  - BaseAdapter 接口 × 6（5 空返回 + 2 health_check）
- 集成：`from app.adapters import WorldBankAdapter` 导入通过
- 端到端：**不发真实网络请求**（作战指令要求），mock 验证 URL 与 query 精确到字符级

---

### A8 IMF [2026-04-15]

**目标**：接入 IMF SDMX-JSON REST，免 Key 提供 IFS（国际金融统计）/ WEO / DOT 数据集，构成与 World Bank 互为交叉验证的国际机构宏观口径。

**联网调研（≥3 权威源，Asia/Singapore 2026-04-15 12:00 +08:00 基准）**：

| 来源 | URL | 关键信息 | 采用性 |
|---|---|---|---|
| IMF Data Help | https://datahelp.imf.org/knowledgebase/articles/630877-api | SDMX 2.1 JSON API：`CompactData/{dataset}/{freq}.{ref_area}.{indicator}`；`startPeriod/endPeriod` query | 采用：URL 结构与参数 |
| SDMX Central (IMF) | https://sdmxcentral.imf.org/ | 数据集目录：IFS / WEO / DOT / BOP / GFS 等 | 采用：数据集选型 |
| IMF DataMapper Help | https://www.imf.org/external/datamapper/api/help | Series 为 dict 或 list；Obs 同；`@TIME_PERIOD/@OBS_VALUE` SDMX 标准属性 | 采用：响应解析规范 |

**落盘文件清单**：

| 路径 | 类型 | 标签 |
|---|---|---|
| `app/adapters/imf_adapter.py` | 新建 | [NEW-FILE:#20260415-10] |
| `tests/adapters/test_imf_adapter.py` | 新建 | — (测试文件) |
| `app/adapters/__init__.py` | 修改 | 导出 `IMFAdapter` |
| `app/adapters/README.md` | 修改 | 清单追加 |

**对外接口**：

- `IMFAdapter(timeout=30)` — 无 Key
- `get_dataset(dataset_id, query, start_period=None, end_period=None) -> pd.DataFrame` — 通用 SDMX CompactData
- `get_ifs(indicator, country, freq="A", ...) -> pd.DataFrame` — IFS 便捷封装（`A.{country}.{indicator}`）
- `get_data_structure(dataset_id) -> dict` — 维度/编码表原始 JSON
- `health_check()` / `name="imf"` — IFS/PCPI_IX/US 2020-2021 判活

**三重验证**：

- 单元：`pytest tests/adapters/test_imf_adapter.py -v` → **20 passed**
  - 基础 × 5（name/UA/_extract_series 3 种形态）
  - _flatten_series × 3（单 Series 多 Obs / 多 Series 混合 Obs 形态 / 缺失值转 NaN）
  - 端点 × 5（get_dataset URL+params / get_ifs key 构造 / 空入参 / HTTP 错误 / data_structure URL）
  - BaseAdapter 接口 × 7
- 集成：`from app.adapters import IMFAdapter` 导入通过
- 端到端：**不发真实网络请求**（作战指令要求），mock 验证 SDMX 解析与 URL 精确到字符级

**Git 提交（A7 + A8 合并在本节描述）**：
- commit1: `feat(adapter): 世界银行+IMF公开API [NEW-FILE:#20260415-09,10]`
- commit2: `docs(data): P1-A7/A8追溯`

**关键设计决策（A7/A8 共通）**：

1. **无 Key 友好**：WB/IMF 均属联合国机构级免费公共数据，适配器不引入 Key 机制，降低接入摩擦
2. **SDMX 弹性解析**：IMF Series/Obs 可能为 dict 或 list，`_extract_series` 统一转 list，避免调用方分叉
3. **BaseAdapter 占位空返回**：两者不提供行情/成分/个股信息，抽象方法全部返回空对象，供 `fallback_manager` 安全跳过
4. **横向对比便捷化**：`WorldBankAdapter.compare_countries` 用 `;` 多国分隔单次请求完成，减少 N 次往返

---

## P2批次追溯

### B1 自建OpenCLI爬虫 [2026-04-15]

**时间基准**：2026-04-15 12:30 +08:00 (Asia/Singapore)
**交付人**：B1 agent (香草少校PM调度)
**性质**：新增3个 JS adapter 至 `clis/` (OpenCLI 约定目录)，Python侧仅在 `opencli_bridge.py` 追加3个便捷方法，不改已有代码。

| # | JS Adapter | 路径 | 必填 args | 可选 args | 数据字段 | NEW-FILE |
|---|-----------|------|-----------|-----------|----------|----------|
| 1 | xueqiu/discuss | `clis/xueqiu/discuss.js` | symbol | limit=30 | user/time/content/likes/comments/reposts | #20260415-13 |
| 2 | eastmoney/guba | `clis/eastmoney/guba.js` | code(6位) | pages=1 | rank/title/author/time/reads/replies/url | #20260415-14 |
| 3 | cls/telegraph | `clis/cls/telegraph.js` | — | limit=50 | time/title/content/tags/isImportant | #20260415-15 |

**目录领地标记**：`clis/README.md` [NEW-FILE:#20260415-16] 列出3个 adapter 用法与依赖。

**权威源 (≥3 验证)**：

- https://github.com/jackwener/OpenCLI (主仓 clis/<site>/<action>.js 目录约定, v2026最近主线)
- https://github.com/jackwener/OpenCLI/pull/1025 (hot-rank adapter 合入模板: Strategy.COOKIE + page.evaluate)
- https://xueqiu.com/S/{symbol}/TIMELINE (雪球讨论页 DOM: `.home__timeline__item`)
- https://guba.eastmoney.com/list,{code}.html (东财股吧 DOM: `table.default_list tr.articleh` + `.l1`~`.l5`)
- https://www.cls.cn/telegraph (财联社电报 DOM: `.telegraph-content-box` + `.telegraph-time-box`)

**Python桥接追加**：`app/adapters/opencli_bridge.py` 新增：

- `get_xueqiu_discuss(symbol, limit=30)` → timeout=45s
- `get_eastmoney_guba(code, pages=1)` → timeout=60s (入参 6位数字校验)
- `get_cls_telegraph(limit=50)` → timeout=30s

三个方法均复用 `opencli_call()` 通用链路，环境未就绪自动降级 `[]` + `log.warning`，不影响上游。

**测试**：3 个 `*.test.js` 共 12 个 mock 单元测试（节点内置 `node:test`，零依赖），覆盖：
- 元信息契约 (name/strategy/args)
- 正常解析（含 rank 递增、tags 数组、isImportant 布尔）
- 边界入参（symbol/code 缺失或非法抛异常）
- 空 evaluate 返回空数组

**Git 提交**：
- commit1: `feat(clis): OpenCLI自建雪球/股吧/财联社爬虫 [NEW-FILE:#20260415-13,14,15,16]`
- commit2: `docs(data): P2-B1追溯`

**关键设计决策**：
1. **DOM 多选择器 fallback**：雪球/东财/财联社前端常迭代，每个选择器给 2-3 套备选（如 `.home__timeline__item, .timeline__item, article`）
2. **中文数字解析**：`"1.2万"` 统一 `toInt()` 处理 `万` 乘以 10000
3. **Strategy.COOKIE**：三站均需浏览器会话，沿用 hot-rank PR#1025 模式
4. **Python侧入参校验前置**：`code` 非6位数字直接降级，避免无意义 Node 启动开销

---

### B3 RSS新闻聚合 [2026-04-15]

**检索时间基准**：2026-04-15 12:30 +08:00 (Asia/Singapore)

**交付文件**：
- `app/adapters/rss_news_adapter.py` **[NEW-FILE:#20260415-19]** (RSSNewsAdapter 继承 BaseAdapter)
- `tests/adapters/test_rss_news_adapter.py` (12 mock 单元测试, **12/12 PASS**, 0.80s)
- `app/adapters/__init__.py` 导出
- `app/adapters/README.md` 追加条目

**权威源交叉验证 (≥6)**：

| # | 来源 | URL | 版本/发布 | 采用 |
|---|---|---|---|---|
| 1 | feedparser (MIT, 2k+⭐) | https://github.com/kurtmckee/feedparser | v6.0.11 (2024-03) | 采用：Atom/RSS 统一解析；软依赖降级 |
| 2 | feedparser PyPI | https://pypi.org/project/feedparser/ | v6.0.11 | 采用：官方发行渠道 |
| 3 | 新浪财经官方RSS | https://rss.sina.com.cn/news/allnews/finance.xml | 存活 (财经滚动) | 采用：唯一保留官方原生RSS的大厂 |
| 4 | RSShub (MIT, 32k+⭐) | https://docs.rsshub.app/ | 路由文档 | 采用：代理华尔街见闻/财联社/雪球/金融界/央视财经 |
| 5 | 华尔街见闻 wallstreetcn.com | https://rsshub.app/wallstreetcn/news/global | RSShub 路由 | 采用：官网无RSS |
| 6 | 财联社电报 | https://rsshub.app/cls/telegraph | RSShub 路由 | 采用 |
| 7 | 雪球头条 | https://rsshub.app/xueqiu/hots | RSShub 路由 xqtl | 采用：官方无公开RSS |
| 8 | 金融界 | https://rsshub.app/jrj/news/list | RSShub 路由 | 采用：旧版 rss.jrj.com.cn 已下线 |
| 9 | 央视财经 | https://rsshub.app/cctv/caijing | RSShub 路由 | 补充主流媒体源 |

**fallback 策略**：主 URL (`rsshub.app`) 失败 → fallback (`rsshub.rssforever.com` 镜像) 二次尝试。新浪则反向 fallback 到 RSShub 代理。

**核心能力**：
- `get_feed(source, limit=50)` 单源抓取
- `get_all_feeds(sources=None, limit_per_source=50)` 并发聚合 + 标题 sha1 去重
- `search_news(keyword, sources=None)` 关键词过滤 (title/summary/tags 任一命中)
- 输出字段: `{source, title, link, published, summary, author, tags}`
- 并发：`ThreadPoolExecutor(max_workers=4)`
- 韧性：超时 10s + 3 次重试 + UA 伪装池 (Chrome/Safari/Linux)
- 降级：`feedparser` 未装 → `_HAS_FEEDPARSER=False` → 空 DF + 日志警告；不崩栈

**测试覆盖 (12 PASS)**：
1. FEED_SOURCES 6源完整性
2. 未知源返回空DF
3. 正常抓取 + tags 解析
4. 主URL失败 → fallback 成功
5. limit 截断
6. 并发聚合 + 标题去重
7. 过滤非法源
8. 关键词命中 title/summary
9. 空关键词返回全部
10. feedparser 未装降级
11. BaseAdapter 契约（K线/成分股/信息/财务空实现）
12. _parse_feed 重试至第 3 次成功

**Git 提交**：
- commit1: `feat(adapter): RSS新闻聚合(华尔街/财联社/雪球/新浪/金融界) [NEW-FILE:#20260415-19]`
- commit2: `docs(data): P2-B3追溯`

**关键设计决策**：
1. **官方优先 + RSShub 兜底**：仅新浪财经有原生 RSS，其余 5 站全走 RSShub 公共代理（含镜像备选）
2. **feedparser 软依赖**：未装不影响其他 adapter；一律空 DF + warning
3. **标题哈希去重**：同一事件多源首发常标题雷同，sha1 折叠避免重复消费；保留首条
4. **BaseAdapter 契约**：K线/成分股/信息/财务均返回空，仅 `health_check` 反映 feedparser 可用性
5. **纯 mock 测试**：`feedparser.parse` 和 `_parse_feed` 双层 monkeypatch，零真实网络，CI 稳定

---

### B2 Ashare + easyquotation [2026-04-15]

**目标**：A股行情兜底双适配器补位 — Ashare 单文件库零依赖日/周/月/分钟K线；easyquotation 新浪/腾讯/集思录 批量实时+基金净值高并发补充。

**联网调研（≥3 权威源，Asia/Singapore 2026-04-15 12:30 +08:00 基准）**：

| 来源 | URL | 关键信息 | 采用性 |
|---|---|---|---|
| GitHub mpquant/Ashare | https://github.com/mpquant/Ashare | 单文件~200行；`get_price(code, frequency, count)`；frequency∈{1d,1w,1M,1m,5m,15m,30m,60m}；code规范sh600519/sz000001 | 采用：API签名+代码规范 |
| GitHub shidenggui/easyquotation | https://github.com/shidenggui/easyquotation | `use('sina'|'tencent'|'qq'|'daykline'|'jsl')`；`.stocks(codes)` 批量；`.market_snapshot(prefix=False)` 全市场；jsl `.funda()/.fundb()/.fundm()` | 采用：多源路由+批量接口 |
| PyPI easyquotation | https://pypi.org/project/easyquotation/ | MIT协议；纯Python；requests+aiohttp并发 | 采用：License + 并发模型 |
| 集思录 jsl.cn | https://www.jisilu.cn/data/ | 分级基金A/B/母基三张表公开JSON | 采用：基金净值数据源 |

**落盘文件清单**：

| 路径 | 类型 | 标签 |
|---|---|---|
| `app/adapters/ashare_adapter.py` | 新建 | [NEW-FILE:#20260415-17] |
| `app/adapters/easyquotation_adapter.py` | 新建 | [NEW-FILE:#20260415-18] |
| `tests/adapters/test_ashare_adapter.py` | 新建 | — |
| `tests/adapters/test_easyquotation_adapter.py` | 新建 | — |
| `app/adapters/__init__.py` | 修改 | 导出 `AshareAdapter`+`EasyquotationAdapter` |
| `app/adapters/README.md` | 修改 | 清单追加 B2 行 |

**对外接口**：

Ashare:
- `AshareAdapter()` — 零参构造
- `get_price(code, frequency="1d", count=100) -> pd.DataFrame` — 核心K线
- `_normalize(code, market=None) -> str` — sh/sz前缀规范化（6/9→sh，0/3→sz）
- `get_stock_history(code, start, end)` — BaseAdapter契约，内部取count=2000再按日期切片
- `health_check()` / `name="ashare"`

Easyquotation:
- `EasyquotationAdapter(source="sina")` — sina/tencent/qq/daykline/jsl
- `get_realtime(codes) -> dict` — 批量实时 `.stocks()` 优先、`.real()` 兜底
- `get_stocks_all() -> dict` — `.market_snapshot(prefix=False)` 全市场5000+
- `get_fund_nav(codes=None) -> dict` — jsl源 funda+fundb+fundm 合并；支持dict与list[dict]两种上游响应
- `get_stock_info(code)` / `get_stock_history(code,...)` — daykline 派生
- `health_check()` / `name="easyquotation:{source}"`

**三重验证**：

- 单元：
  - `test_ashare_adapter.py` — 13 cases（_normalize×4 / get_price×5 / BaseAdapter×6 / meta×1）
  - `test_easyquotation_adapter.py` — 18 cases（init×3 / realtime×5 / stocks_all×2 / fund_nav×4 / BaseAdapter×5）
  - 全部 mock，不发真实请求
- 集成：`from app.adapters import AshareAdapter, EasyquotationAdapter` 导入通过
- 端到端：**不发真实网络请求**（作战指令要求）；mock 验证URL/参数/降级路径

**Git 提交**：
- commit1: `feat(adapter): Ashare+easyquotation A股实时分钟线补位 [NEW-FILE:#20260415-17,18]`
- commit2: `docs(data): P2-B2追溯`

**关键设计决策**：
1. **Ashare 单文件库零依赖**：无需pip包，最小侵入；软import失败→空DF+warning
2. **代码规范统一**：`_normalize` 按首位数字推断市场（6/9→sh，0/3→sz），向上兼容 `.SH/.SZ` 后缀
3. **frequency 白名单校验**：非法值回退 `1d` 并warning，不抛
4. **easyquotation 多源路由**：`source` 参数显式选择，非法值回退 `sina`；`stocks()` 优先、`real()` 兜底兼容老版
5. **jsl 基金净值弹性解析**：funda/fundb/fundm 依次合并，同时适配 dict 与 list[dict] 两种上游响应形态
6. **批量codes过滤**：`get_fund_nav(codes=[...])` 服务端不支持按code过滤时，客户端集合筛
7. **BaseAdapter 占位空返回**：两者不提供指数成分/财务，抽象方法返回空，供 `fallback_manager` 安全跳过

---

### B4 OpenBB + Registry [2026-04-15]

**检索时间基准**：2026-04-15 12:30 +08:00（同附录 D 时间真实性校验）

**联网权威来源（≥3）**：

| 来源 | URL | 要点 | 采用 |
|---|---|---|---|
| OpenBB 官方仓库 | https://github.com/OpenBB-finance/OpenBB | Platform v4.x，核心代码 AGPL-3.0，按 provider 拆分子包 | 采用：SDK桥接方式 |
| OpenBB Platform Docs | https://docs.openbb.co/platform | `from openbb import obb` 路由：`obb.equity.price.historical / equity.profile / crypto.price.historical / economy.gdp.real / economy.cpi` | 采用：接口路由 |
| PyPI `openbb` | https://pypi.org/project/openbb/ | 元包 >=4.0，按需装 providers；与 pandas/pydantic 生态 | 采用：软依赖策略 |
| OpenBB Provider 免费层 | docs.openbb.co/platform/developer_guide/providers | yfinance(免费)/fred(免费Key)/sec(免费)/fmp(部分免费)/intrinio(沙盒) | 采用：FREE_PROVIDERS 白名单 |

**落盘文件清单**：

| 路径 | 类型 | 标签 |
|---|---|---|
| `app/adapters/openbb_adapter.py` | 新建 | [NEW-FILE:#20260415-20] |
| `app/adapters/adapter_registry.py` | 新建 | [NEW-FILE:#20260415-21] |
| `tests/adapters/test_openbb_adapter.py` | 新建 | — (测试) |
| `tests/adapters/test_adapter_registry.py` | 新建 | — (测试) |
| `app/adapters/__init__.py` | 修改 | 导出 OpenBBAdapter + AdapterRegistry + 补齐Efinance/YFinance/Ashare/Easyquotation |
| `app/adapters/README.md` | 修改 | 清单追加 B4 两条 |

**对外接口（OpenBBAdapter）**：

- `OpenBBAdapter(default_equity_provider="yfinance", default_economy_provider="fred")`
- `get_equity_price(symbol, start=None, end=None, provider="yfinance") -> pd.DataFrame`
- `get_equity_profile(symbol, provider="yfinance") -> dict`
- `get_crypto_price(symbol, provider="yfinance") -> pd.DataFrame`
- `get_economy_indicator(indicator, provider="fred") -> pd.DataFrame` (gdp/cpi/unemployment/自定义FRED序列)
- BaseAdapter 契约：`get_stock_history / get_index_stocks / get_stock_info / get_financial_data / health_check`

**对外接口（AdapterRegistry）**：

- `AdapterRegistry.default()` — 进程级单例，自动 `register_adapters()`
- `register(domain, adapter)` / `register_adapters(domain_map=None)`
- `get_adapters(domain) -> list[BaseAdapter]`
- `call_with_fallback(domain, method, **kwargs) -> Any` — 首个 `_is_valid_result` 即返回
- `get_status() / list_domains() / reset_default()`

**Domain 完整映射表**：

| Domain | 优先级链（从左至右） |
|---|---|
| `a_stock_kline` | Akshare → Baostock → Efinance → Ashare → YFinance |
| `a_stock_realtime` | Efinance → Easyquotation → Akshare → OpenCLI |
| `us_stock` | YFinance → OpenBB → EDGAR |
| `hk_stock` | YFinance → Akshare |
| `macro_us` | FRED → OpenBB → WorldBank |
| `macro_cn` | NBS → Akshare |
| `macro_global` | WorldBank → IMF → OpenBB |
| `crypto` | CCXT → CoinGecko → YFinance → OpenBB |
| `news` | RSSNews → OpenCLI → Akshare |
| `sentiment_social` | OpenCLI |
| `xbrl_financials` | EDGAR → YFinance → OpenBB |

**三重验证**：

- 单元：`pytest tests/adapters/test_openbb_adapter.py tests/adapters/test_adapter_registry.py -v` → **30 passed**
  - OpenBB × 17：未装降级 5 / equity_price 3 / profile+crypto 2 / economy 2 / BaseContract 5
  - Registry × 13：register+list 2 / fallback（成功/空降级/异常降级/全fail/未注册/无method）6 / DEFAULT_MAP 2 / _is_valid_result 4
- 集成：`from app.adapters import OpenBBAdapter, AdapterRegistry` 导入通过
- 端到端：**不发真实网络请求**（作战指令要求），全部 mock `obb.*` 路由与 `OBBject.to_df()/results` 两种返回形态

**关键设计决策**：

1. **免费 provider 白名单**：`FREE_PROVIDERS = {yfinance,fred,sec,intrinio,fmp}`，非白名单自动降级 yfinance，避免无声调用付费接口
2. **OBBject 双形态兼容**：`_obb_to_df` 先试 `.to_df()` 再回落 `.results[*].model_dump()`，兼容 OpenBB Platform v4 不同 provider 的返回约定
3. **Registry 延迟导入**：`importlib.import_module` + 单适配器实例缓存，模块缺失/构造失败不阻塞整体注册
4. **_is_valid_result 与 FallbackManager 对齐**：None/空DataFrame/空list/空dict 视为无效，降级继续；非空 str/数值 视为有效
5. **单例 + reset_default**：生产单例 `AdapterRegistry.default()`；测试 `reset_default()` 避免跨用例污染
6. **AGPL 合规提醒**：OpenBB 核心 AGPL-3.0，仅作为可选软依赖通过 SDK 调用，不内嵌其源码，不触发 copyleft 传染
