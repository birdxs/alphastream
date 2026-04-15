# 金融数据库扩充方案 v2 (FINANCIAL_DATA_EXPANSION) — 纯开源路线

> Input: Comdr驳回v1付费源方案 + 现有akshare/baostock/17引擎基线 + OpenCLI(15.8k⭐)PR#1025既成事实
> Output: 纯开源数据源矩阵 + OpenCLI浏览器爬取桥 + ≥15项无Key数据源清单 + 三阶段落地 + 14-Agent对接
> Pos: `docs/` — 数据层战略规划文档 v2 (P0基线，覆盖v1)

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

