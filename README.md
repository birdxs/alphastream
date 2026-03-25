# 智能分析系统

![版本](https://img.shields.io/badge/版本-2.2.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.9+-green.svg)
![Flask](https://img.shields.io/badge/Flask-3.1-red.svg)
![AKShare](https://img.shields.io/badge/AKShare-1.16+-orange.svg)
![AI](https://img.shields.io/badge/AI_API-集成-blueviolet.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi_Agent-purple.svg)

![系统首页截图](./images/1.png)

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=LargeCupPanda/StockAnal_Sys&type=Date)](https://star-history.com/#LargeCupPanda/StockAnal_Sys&Date)

## 📝 项目概述

智能分析系统是一个基于Python、Flask和LangGraph的Web应用，整合了多Agent协同分析能力和人工智能辅助决策功能。系统通过多数据源（AKShare/BaoStock）获取股票数据，结合13个专业Agent（技术分析、基本面、资金流、情绪分析、多空辩论、投资者人格、风险管理、智能决策），为投资者提供全方位的AI驱动投资决策支持。

## ✨ 核心功能

### 多维度股票分析

- **技术面分析**：趋势识别、支撑压力位、技术指标（RSI、MACD、KDJ等）
- **基本面分析**：估值分析、财务健康、成长前景
- **资金面分析**：主力资金流向、北向资金、机构持仓
- **智能评分**：100分制综合评分，40-40-20权重分配

### 智能化功能

- **AI增强分析**：通过AI API提供专业投资建议
- **支撑压力位自动识别**：智能识别关键价格区域
- **情景预测**：生成乐观、中性、悲观多种市场情景，优化预测精度和可视化效果
- **智能问答**：支持联网搜索实时信息和多轮对话，回答关于个股的专业问题

### 多Agent协同分析（v2.2.0 新增）

- **LangGraph编排引擎**：动态深度路由（1-5级），按需调用不同数量的Agent
- **9大分析Agent**：技术分析师、基本面分析师、资金流分析师、情绪分析师、看多研究员、看空研究员、风险管理官、投资决策者、反思Agent
- **投资者人格分析**：巴菲特（价值投资）、芒格（多元思维）、彼得·林奇（成长投资）、达摩达兰（估值大师），投票机制综合决策
- **Agent自主进化**：反思学习 + 语义记忆 + 策略自适应演进
- **开源搜索集成**：DuckDuckGo免费搜索（无需API Key）→ Tavily → SERP 多源降级
- **Human-in-the-Loop**：高风险决策自动暂停等待人工审批
- **MCP工具服务器**：5个标准化工具接口，支持跨系统调用

### 市场分析工具

- **市场扫描**：筛选高评分股票，发现投资机会
- **投资组合分析**：评估投资组合表现，提供调整建议
- **风险监控**：多维度风险预警系统
- **指数和行业分析**：支持沪深300、中证500等指数和主要行业成分股分析

### 可视化界面

- **交互式图表**：K线图、技术指标、多维度评分雷达图
- **直观数据展示**：支撑压力位、评分、投资建议等清晰呈现
- **响应式设计**：适配桌面和移动设备的界面
- **财经门户主页**：三栏式财经门户风格布局，左侧功能导航、中间实时财经要闻、右侧舆情热点，底部显示全球主要市场状态

### 实时数据更新

- **实时财经要闻**：时间线形式展示最新财经新闻，自动高亮上涨/下跌相关内容
- **舆情热点监控**：自动识别和展示市场舆情热点，包括人工智能等前沿领域
- **全球市场状态**：实时显示亚太、欧非中东、美洲等全球主要证券市场的开闭市状态
- **自动刷新机制**：系统每10分钟自动刷新，确保数据实时性

## 🔧 系统架构

```
智能分析系统/
│
├── run.py                   # 应用入口
├── app/                     # 应用主目录
│   ├── core/                # 核心基础设施
│   │   ├── ai_client.py      # 统一AI客户端（超时/重试/错误处理）
│   │   ├── data_provider.py   # 统一数据层（多源故障转移）
│   │   ├── cache.py           # Redis统一缓存（Redis/内存降级）
│   │   ├── search.py          # 统一搜索引擎（DuckDuckGo/Tavily/SERP）
│   │   ├── agent_memory.py    # Agent语义记忆系统
│   │   ├── event_bus.py       # Agent事件通信总线
│   │   ├── tools.py           # 共享工具函数
│   │   ├── fallback_manager.py # 故障转移管理器
│   │   └── database.py        # 数据库管理
│   │
│   ├── analysis/            # 分析引擎模块
│   │   ├── stock_analyzer.py        # 股票分析核心引擎
│   │   ├── fundamental_analyzer.py  # 基本面分析
│   │   ├── capital_flow_analyzer.py # 资金流向分析
│   │   ├── industry_analyzer.py     # 行业分析
│   │   ├── index_industry_analyzer.py # 指数行业分析
│   │   ├── etf_analyzer.py          # ETF分析
│   │   ├── scenario_predictor.py    # 情景预测
│   │   ├── risk_monitor.py          # 风险监控
│   │   ├── stock_qa.py              # 智能问答（支持联网搜索）
│   │   ├── news_fetcher.py          # 新闻获取与缓存
│   │   └── us_stock_service.py      # 美股服务
│   │
│   ├── agents/             # 多Agent分析子系统（LangGraph编排）
│   │   ├── coordinator.py          # LangGraph图编排协调器
│   │   ├── technical_analyst.py    # 技术分析Agent
│   │   ├── fundamental_analyst.py  # 基本面Agent
│   │   ├── capital_flow_analyst.py # 资金流Agent
│   │   ├── sentiment_analyst.py    # 情绪/新闻Agent
│   │   ├── bull_researcher.py      # 看多研究员
│   │   ├── bear_researcher.py      # 看空研究员
│   │   ├── risk_manager.py         # 风险管理Agent
│   │   ├── decision_maker.py       # 投资决策Agent
│   │   ├── reflection.py           # 反思学习Agent
│   │   ├── strategy_evolver.py     # 策略自适应演进
│   │   ├── hitl.py                 # Human-in-the-Loop审批
│   │   └── investors/              # 投资者人格Agent
│   │       ├── buffett.py          # 巴菲特风格
│   │       ├── munger.py           # 芒格风格
│   │       ├── lynch.py            # 彼得·林奇风格
│   │       └── damodaran.py        # 达摩达兰风格
│   │
│   ├── mcp/                # MCP协议工具服务器
│   │   └── stock_data_server.py    # 股票数据MCP Server
│   │
│   ├── web/                 # Web服务模块
│   │   ├── web_server.py            # Web服务器和路由控制
│   │   ├── auth_middleware.py       # 认证中间件
│   │   ├── industry_api_endpoints.py # 行业API端点
│   │   ├── templates/               # HTML模板
│   │   │   ├── layout.html          # 基础布局模板
│   │   │   ├── index.html           # 首页（财经门户风格）
│   │   │   ├── dashboard.html       # 智能仪表盘
│   │   │   ├── stock_detail.html    # 股票详情页
│   │   │   ├── market_scan.html     # 市场扫描页面
│   │   │   ├── portfolio.html       # 投资组合页面
│   │   │   ├── etf_analysis.html    # ETF分析页面
│   │   │   ├── agent_analysis.html  # Agent智能分析页面
│   │   │   └── ...                  # 其他页面
│   │   └── static/                  # 静态资源
│   │
│   └── tradingagents/       # 交易代理模块（开发中）
│
├── Dockerfile               # Docker构建文件
├── docker-compose.yml       # Docker编排配置
└── .env                     # 环境变量配置文件
```

### 技术栈

- **后端**：Python 3.9+, Flask 3.1, AKShare, BaoStock
- **AI引擎**：OpenAI兼容API, LangGraph多Agent编排, LangChain
- **前端**：HTML5, CSS3, JavaScript, Bootstrap 5, ApexCharts
- **数据分析**：Pandas, NumPy, Scikit-learn
- **搜索**：DuckDuckGo（免费）, Tavily, SERP API
- **缓存**：Redis（可选）/ 内存缓存
- **部署**：Docker, Gunicorn, docker-compose

## 📦 安装指南

### 环境要求

- Python 3.9+
- pip包管理器
- 网络连接（用于获取股票数据和访问AI API）

### 安装步骤

1. **克隆或下载代码库**

```bash
git clone https://github.com/LargeCupPanda/StockAnal_Sys.git
cd StockAnal_Sys
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

或手动安装主要依赖：

```bash
pip install flask pandas numpy akshare requests matplotlib python-dotenv flask-cors flask-caching
```

3. **创建并配置环境变量**

将`.env-example`复制为`.env`，并设置您的API密钥：

```
# API 提供商 (OpenAI SDK )
API_PROVIDER=openai

# OpenAI API 配置
OPENAI_API_URL=***
OPENAI_API_KEY=your_api_key
OPENAI_API_MODEL=gpt-4o
NEWS_MODEL=你的可联网模型
```

## ⚙️ 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|-------|------|-------|
| `API_PROVIDER` | API提供商选择 | `openai` |
| `OPENAI_API_KEY` | OpenAI API密钥 | 无，必须提供 |
| `OPENAI_API_URL` | OpenAI API端点URL | `https://api.openai.com/v1` |
| `OPENAI_API_MODEL` | 使用的OpenAI模型 | `gpt-4o` |
| `PORT` | Web服务器端口 | `8888` |
| `USE_AGENT_SYSTEM` | Agent系统开关 | `true` |
| `USE_REDIS_CACHE` | Redis缓存开关 | `false` |
| `REDIS_URL` | Redis连接地址 | `redis://localhost:6379` |
| `TAVILY_API_KEY` | Tavily搜索API密钥（可选） | 无 |
| `SERP_API_KEY` | SERP搜索API密钥（可选） | 无 |
| `ALLOWED_ORIGINS` | 允许的跨域来源 | `localhost:8888` |

### 技术指标参数

可在`stock_analyzer.py`中的`__init__`方法中调整以下参数：

- `ma_periods`: 移动平均线周期设置
- `rsi_period`: RSI指标周期
- `bollinger_period`: 布林带周期
- `bollinger_std`: 布林带标准差
- `volume_ma_period`: 成交量均线周期
- `atr_period`: ATR周期

### 缓存机制

系统实现了智能缓存策略，包括：

- **股票数据缓存**：减少重复API调用
- **分析结果缓存**：避免重复计算
- **任务结果缓存**：保存已完成任务的结果
- **新闻数据缓存**：按天存储新闻数据，避免重复内容
- **自动缓存清理**：每天收盘时间(16:30左右)自动清理所有缓存，确保数据实时性
- **Redis统一缓存**：支持Redis集群缓存和内存降级（可选）
- **Agent记忆缓存**：分析历史持久化，支持语义检索

## 🚀 使用指南

### 启动系统

方式一：直接运行

```bash
python run.py
```

方式二：使用启动脚本

```bash
bash scripts/start.sh start
```

启动后，访问 `http://localhost:8888` 打开系统。

### 其他管理命令

```bash
bash scripts/start.sh stop       # 停止服务
bash scripts/start.sh restart    # 重启服务
bash scripts/start.sh status     # 查看服务状态
bash scripts/start.sh monitor    # 以监控模式运行（自动重启）
bash scripts/start.sh logs       # 查看日志
```

### 主要功能页面

1. **首页** (`/`)
   - 三栏式财经门户风格界面
   - 左侧功能导航、中间实时财经要闻、右侧舆情热点
   - 底部显示全球主要市场状态，10分钟自动刷新

2. **智能仪表盘** (`/dashboard`)
   - 输入股票代码，开始分析
   - 查看多维度分析结果和AI建议

3. **股票详情** (`/stock_detail/<stock_code>`)
   - 查看单只股票的详细分析
   - 支持技术图表、支撑压力位和AI分析

4. **市场扫描** (`/market_scan`)
   - 扫描指数成分股或行业股票
   - 筛选高评分股票，发现投资机会

5. **投资组合** (`/portfolio`)
   - 创建和管理个人投资组合
   - 分析组合表现，获取优化建议

6. **基本面分析** (`/fundamental`)
   - 查看股票财务指标和估值分析
   - 分析股票成长性和财务健康状况

7. **资金流向** (`/capital_flow`)
   - 跟踪主力资金和北向资金动向
   - 分析机构持仓变化

8. **情景预测** (`/scenario_predict`)
   - 预测股票未来走势的多种情景
   - 提供乐观、中性、悲观三种预测

9. **风险监控** (`/risk_monitor`)
   - 分析股票和投资组合风险
   - 提供风险预警和应对建议

10. **智能问答** (`/qa`)
    - 通过AI回答关于股票的专业问题
    - 支持联网搜索实时信息和多轮对话

11. **行业分析** (`/industry_analysis`)
    - 分析行业整体表现和资金流向
    - 对比不同行业投资机会

12. **ETF分析** (`/etf_analysis`)
    - ETF基金分析和评估
    - 跟踪ETF表现和持仓分析

13. **Agent智能分析** (`/agent_analysis`)
    - 基于AI Agent的深度分析
    - 多维度智能投资建议

### 常用操作

- **分析股票**：在智能仪表盘输入股票代码，点击"分析"
- **查看股票详情**：点击股票代码或搜索股票进入详情页
- **扫描市场**：在市场扫描页面选择指数或行业，设置最低评分，点击"扫描"
- **管理投资组合**：在投资组合页面添加/删除股票，查看组合分析
- **智能问答**：选择股票后，提问关于该股票的问题，获取AI回答
- **查看实时财经要闻**：在首页浏览最新财经新闻和舆情热点

## 📚 API文档

系统提供了完整的REST API，可通过Swagger文档查看：`/api/docs`

主要API包括：

- 股票分析API：`/api/enhanced_analysis`
- 市场扫描API：`/api/start_market_scan`
- 指数成分股API：`/api/index_stocks`
- 智能问答API：`/api/qa`
- 风险分析API：`/api/risk_analysis`
- 情景预测API：`/api/scenario_predict`
- 行业分析API：`/api/industry_analysis`
- 最新新闻API：`/api/latest_news`
- ETF分析API：`/api/start_etf_analysis`
- Agent分析API：`/api/start_agent_analysis`
- 资金流向API：`/api/capital_flow`
- 基本面分析API：`/api/fundamental_analysis`
- MCP工具列表API：`/api/mcp/tools`
- MCP工具调用API：`/api/mcp/call`
- Agent审批列表API：`/api/agent_pending_approvals`
- Agent审批提交API：`/api/agent_submit_approval`

## 📋 版本历史

### v2.2.0 (当前版本)
- 全面Agent化改造：13个专业Agent + LangGraph编排 + 投资者人格
- 新增开源搜索集成（DuckDuckGo免费搜索，无需API Key）
- 新增Redis统一缓存层 + Agent记忆系统 + 事件总线
- 新增Human-in-the-Loop高风险决策审批
- 新增MCP工具服务器（标准化Agent工具接口）
- 安全加固：CORS限制、输入验证、移除硬编码密钥
- 修复10+个Issue：AI超时、数据源封禁、新闻去重等

### v2.1.2
- 实现数据接口双层冗余架构（akshare内部冗余 + baostock跨库备用）
- 新增DataProvider统一数据层和FallbackManager故障转移管理器

## 🔄 扩展开发

系统设计采用模块化架构，便于扩展开发。主要扩展点包括：

- 添加新的技术指标
- 集成其他数据源
- 开发新的分析模块
- 扩展用户界面功能

## ⚠️ 注意

**当前版本为先驱探索版，旨在学习人工智能在指令分析方面的研究学习。AI生成的内容有很多错误，请勿当成投资建议，若由此造成的一切损失，本项目不负责！**

## 💡 联系与支持

如有问题或建议，请pr：

- 项目有很多问题，基础功能可以运行起来，扩充项目代码全由AI开发，所以进展比较缓慢，请谅解。
- 如你有好的想法或修复，欢迎提交GitHub Issue

## 👥 Contributors

感谢所有为本项目做出贡献的开发者！

<a href="https://github.com/LargeCupPanda/StockAnal_Sys/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=LargeCupPanda/StockAnal_Sys" />
</a>

感谢使用智能分析系统！