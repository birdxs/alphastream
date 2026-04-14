# AI Agent 17 搜索引擎集成手册

> 落盘时间: 2026-04-14 18:12 +08:00 (Asia/Singapore)  
> 负责人: 香草少校 🌿 × Backend 工程师  
> 参考: yanran_digital_life/cognitive_modules/skills/search_skill.py + config/skills/search_engines.json (20260410 基线)  
> 代码位置: `app/core/search_engines.py` (核心) / `app/core/search.py` (门面) / `app/core/tools.py` (LLM tool schema)

---

## 一、17 引擎总览

| # | Engine Key | 名称 | Region | 访问方式 | 需API Key | 状态(20260414实测) |
|---|-----------|-----|--------|----------|-----------|-------|
| 1 | `baidu` | 百度 | 中文 | HTML 抓取 | 否 | ✅ 已验证 (3/3 返回) |
| 2 | `sogou` | 搜狗 | 中文 | HTML 抓取 | 否 | ✅ 20260410 基线验证 |
| 3 | `so360` | 360 搜索 | 中文 | HTML 抓取 | 否 | ✅ 20260410 基线验证 |
| 4 | `wechat` | 微信搜一搜(搜狗入口) | 中文 | HTML 抓取 | 否 | ✅ 20260410 基线验证 |
| 5 | `toutiao` | 今日头条搜索 | 中文 | HTML 抓取 | 否 | ✅ 20260410 基线验证 |
| 6 | `jisilu` | 集思录(投资站内) | 中文 | HTML 抓取 | 否 | ⚠ 轻量站内，结果偶少 |
| 7 | `bing_cn` | Bing 中国版 | 中文 | HTML 抓取 | 否 | ⚠ 有 JS 渲染风险 |
| 8 | `zhihu` | 知乎(经搜狗 site: 引流) | 中文 | HTML 抓取 | 否 | ✅ 搜狗兜底 |
| 9 | `duckduckgo` | DuckDuckGo(ddgs API) | 全球 | PyPI 包 | 否 | ✅ 8.1.1 稳定 |
| 10 | `duckduckgo_html` | DuckDuckGo HTML | 全球 | HTML 抓取 | 否 | ⚠ 需代理 |
| 11 | `bing` | Bing 国际版 | 全球 | HTML 抓取 | 否 | ⚠ JS 降级 |
| 12 | `brave` | Brave Search | 全球 | HTML 抓取 | 否(可选API) | ✅ 可用 |
| 13 | `qwant` | Qwant | 全球 | HTML 抓取 | 否 | ✅ 20260410 基线验证 |
| 14 | `startpage` | Startpage | 全球 | HTML 抓取 | 否 | ⚠ 需代理 |
| 15 | `ecosia` | Ecosia | 全球 | HTML 抓取 | 否 | ⚠ 反爬 403 |
| 16 | `wikipedia` | Wikipedia (zh/en MediaWiki API) | 知识 | 官方 REST API | 否 | ✅ 已验证 (3/3 中文返回) |
| 17 | `wolframalpha` | WolframAlpha(数学/单位/货币) | 知识 | HTML 抓取 | 否(可选API) | ✅ 20260410 基线验证 |

额外可选（走独立分支，有 key 自动进入并发/fallback 链尾）：
- `tavily` → `TAVILY_API_KEY`
- `serp` → `SERP_API_KEY` (Serper.dev)

---

## 二、Fallback 链（multi_search 调度策略）

| Chain | 顺序 | 用途 |
|-------|-----|-----|
| `auto` (默认) | duckduckgo→baidu→bing_cn→sogou→so360→wechat→brave | 通用 |
| `cn` | baidu→sogou→so360→wechat→toutiao→bing_cn | 强中文意图 |
| `global` | duckduckgo→brave→bing→qwant→duckduckgo_html | 英文/国际话题 |
| `news` | wechat→toutiao→baidu→sogou→so360 | 新闻/股票最新消息 |
| `knowledge` | wikipedia→wolframalpha→brave→baidu | 百科/数学/事实 |
| `privacy` | duckduckgo→brave→qwant→startpage | 隐私偏好 |

---

## 三、LLM 统一调用接口

```python
from app.core.search_engines import multi_search

# 1) 默认自动降级
results = multi_search("贵州茅台 最新消息")

# 2) 明确指定引擎
r_wiki = multi_search("量子计算", engine="wikipedia")
r_math = multi_search("sin(30度)", engine="wolframalpha")

# 3) 并发多引擎 + 去重合并 + 按出现次数 boost
r_merged = multi_search("特斯拉 财报", engine="concurrent", chain="global")
```

LLM tool 名 `search_web` 已在 `tools.py::OPENAI_TOOLS_SCHEMA` 暴露 engine 参数，Agent 会根据问题语义自行选择。

---

## 四、环境变量

| 变量 | 作用 |
|-----|-----|
| `SEARCH_DISABLED_ENGINES` | 逗号分隔引擎名禁用列表。例: `SEARCH_DISABLED_ENGINES=ecosia,startpage` |
| `DUCKDUCKGO_PROXY` / `HTTPS_PROXY` | 出海代理（DDG/Brave/Qwant 建议配） |
| `TAVILY_API_KEY` | 启用 Tavily |
| `SERP_API_KEY` | 启用 Serper/SERP |

---

## 五、权威来源交叉验证（每引擎 ≥3 源 / 2026-04-14 检索）

### duckduckgo / ddgs
1. [PyPI duckduckgo-search 8.1.1](https://pypi.org/project/duckduckgo-search/) — 官方包，Production/Stable，支持 Python 3.9-3.13（检索时间 2026-04-14 18:05 +08:00）
2. [LangChain 集成文档](https://docs.langchain.com/oss/python/integrations/providers/duckduckgo_search) — 官方集成示例（检索时间 2026-04-14 18:05 +08:00）
3. [GitHub topic duckduckgo-search](https://github.com/topics/duckduckgo-search) — 社区活跃度佐证（检索时间 2026-04-14 18:05 +08:00）

### wikipedia / MediaWiki API
1. [Wikimedia Developer Portal](https://developer.wikimedia.org/build-tools/apis/) — 官方开发者门户（检索时间 2026-04-14 18:05 +08:00）
2. [MediaWiki API documentation](https://www.mediawiki.org/wiki/Documentation/API_documentation) — 官方 API 规范（检索时间 2026-04-14 18:05 +08:00）
3. [Wikimedia API Portal — Python 搜索教程](https://api.wikimedia.org/wiki/Searching_for_Wikipedia_articles_using_Python) — 官方示例（检索时间 2026-04-14 18:05 +08:00）

### brave
1. [Brave Search API 官方页](https://brave.com/search/api/) — 产品官方页（检索时间 2026-04-14 18:06 +08:00）
2. [API Dashboard Quickstart](https://api-dashboard.search.brave.com/documentation/quickstart) — 官方文档（检索时间 2026-04-14 18:06 +08:00）
3. [Pricing 页](https://api-dashboard.search.brave.com/documentation/pricing) — 确认 2026-02-12 改计量付费（$5/1k），月度 $5 credit（检索时间 2026-04-14 18:06 +08:00）

### baidu / sogou / so360 / wechat / toutiao / jisilu / bing_cn / qwant / startpage / ecosia / duckduckgo_html / bing
以上 12 个引擎的 URL 模板、CSS 选择器、可用性基线源自以下本地权威：
1. `~/.claude/skills/multi-search-engine/config.json` — 全局 Claude Code skill 实测版本
2. `yanran_digital_life/config/skills/search_engines.json` — 20260410 基线测试报告（`_verified_engines_20260410` 字段含可用/失败分类）
3. 本项目 2026-04-14 18:11 实测（wikipedia_zh 与 baidu 均返回 3/3 条真实结果，日志见 commit message）

### wolframalpha
1. [WolframAlpha 官方](https://www.wolframalpha.com/) — 产品官站（检索时间 2026-04-14 18:06 +08:00）
2. [WolframAlpha API 文档](https://products.wolframalpha.com/api) — 官方付费 API（本集成用 HTML 抓取 meta/alt）
3. yanran skill `_search_wolframalpha` 20260410 实测通过 — 本模块直接移植该逻辑

---

## 六、已知局限 & 未来改进

- 全球引擎（Bing 国际/Startpage/Ecosia/DDG HTML）在无代理环境下命中率较低 — 已默认把 `duckduckgo`(ddgs) 作为首选而非 HTML 版。
- Baidu / Sogou 在高频调用下会被风控；生产环境建议开启 Redis 结果缓存 (TTL 5-10 min)。
- WolframAlpha HTML 抓取非官方 API；若商业使用建议购买 API key 走结构化响应。
- `jisilu`/`zhihu` 为站内搜索 wrapper，结果形态偏"讨论"而非"百科/新闻"，仅供特定场景使用。
