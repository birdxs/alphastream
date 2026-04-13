# 数据接口鲁棒性升级方案

> 艹，老王我把这个项目的数据接口扒了个底朝天，现在来设计一套接口冗余方案，让这帮憨批接口挂了也能自动切换！

## 一、当前接口使用情况分析

### 1.1 akshare接口清单（当前唯一数据源）

| 模块 | 接口函数 | 用途 | 调用位置 |
|------|----------|------|----------|
| **股票数据** | `ak.stock_zh_a_hist()` | A股历史K线 | stock_analyzer.py:86 |
| | `ak.stock_hk_daily()` | 港股日线 | stock_analyzer.py:88 |
| | `ak.stock_us_hist()` | 美股历史 | stock_analyzer.py:90 |
| | `ak.stock_individual_info_em()` | 个股信息 | stock_analyzer.py:1293 |
| | `ak.stock_info_a_code_name()` | A股代码名称 | stock_analyzer.py:1304 |
| **指数成分股** | `ak.index_stock_cons_weight_csindex()` | 沪深300/中证500/中证1000/上证指数成分股 | web_server.py, index_industry_analyzer.py |
| **行业板块** | `ak.stock_board_industry_name_em()` | 行业板块列表 | industry_analyzer.py:148 |
| | `ak.stock_board_industry_cons_em()` | 行业成分股 | web_server.py:1321, industry_analyzer.py:200 |
| | `ak.stock_board_industry_hist_em()` | 行业历史行情 | industry_analyzer.py:479 |
| **资金流向** | `ak.stock_fund_flow_concept()` | 概念资金流向 | capital_flow_analyzer.py:33 |
| | `ak.stock_individual_fund_flow_rank()` | 个股资金流排名 | capital_flow_analyzer.py:79 |
| | `ak.stock_individual_fund_flow()` | 个股资金流向 | capital_flow_analyzer.py:143 |
| **财务数据** | `ak.stock_financial_analysis_indicator()` | 财务分析指标 | fundamental_analyzer.py:25 |
| | `ak.stock_financial_abstract()` | 财务摘要 | fundamental_analyzer.py:55 |
| | `ak.stock_value_em()` | 估值数据 | fundamental_analyzer.py:28 |
| **ETF数据** | `ak.fund_etf_fund_info_em()` | ETF基金信息 | etf_analyzer.py:36 |
| | `ak.fund_etf_hist_em()` | ETF历史行情 | etf_analyzer.py:68 |
| | `ak.fund_portfolio_hold_em()` | 基金持仓 | etf_analyzer.py:350 |
| | `ak.stock_zh_index_daily()` | 指数日线 | etf_analyzer.py:167,292 |
| **北向资金** | `ak.stock_hsgt_hist_em()` | 北向资金历史 | stock_analyzer.py:142 |
| **新闻数据** | `ak.stock_info_global_cls()` | 财联社新闻 | news_fetcher.py:95 |
| **美股数据** | `ak.stock_us_spot_em()` | 美股实时行情 | us_stock_service.py:27 |

### 1.2 问题分析

1. **单点故障**：所有数据全靠akshare，东方财富接口一封禁，整个系统就瘫痪
2. **无降级机制**：接口挂了直接报错，没有备用方案
3. **无重试机制**：网络抖动就GG
4. **缓存策略单一**：只有简单的内存缓存

---

## 二、akshare内部多数据源冗余分析（重要补充！）

> 艹，老王我发现akshare这个库本身就是个宝藏！同一个功能它提供了多个数据源的接口，后缀命名规则：
> - `_em` = 东方财富
> - `_ths` = 同花顺
> - `_sina` = 新浪
> - `_xq` = 雪球
> - `_tx` = 腾讯
> - `_cninfo` = 巨潮资讯

### 2.1 同功能多数据源接口映射表

#### 2.1.1 历史K线数据

| 数据源 | 接口函数 | 特点 | 推荐度 |
|--------|----------|------|--------|
| 东方财富 | `stock_zh_a_hist` | 数据质量高，无访问限制 | ⭐⭐⭐⭐⭐ |
| 腾讯 | `stock_zh_a_hist_tx` | 稳定，代码格式需带市场前缀(sz/sh) | ⭐⭐⭐⭐ |
| 新浪 | `stock_zh_a_daily` | 官方已不推荐，建议切换到东财 | ⭐⭐ |

#### 2.1.2 实时行情数据

| 数据源 | 接口函数 | 特点 | 推荐度 |
|--------|----------|------|--------|
| 东方财富 | `stock_zh_a_spot_em` | 全量A股实时行情 | ⭐⭐⭐⭐⭐ |
| 新浪 | `stock_zh_a_spot_sina`(文档中提到) | 重复运行会被封IP | ⭐⭐ |
| 雪球 | `stock_individual_spot_xq` | 单只股票实时行情 | ⭐⭐⭐ |

#### 2.1.3 个股基本信息

| 数据源 | 接口函数 | 特点 | 推荐度 |
|--------|----------|------|--------|
| 东方财富 | `stock_individual_info_em` | 完整个股信息 | ⭐⭐⭐⭐⭐ |
| 雪球 | `stock_individual_basic_info_xq` | 公司简介信息 | ⭐⭐⭐⭐ |

#### 2.1.4 财务数据

| 数据源 | 接口函数 | 特点 | 推荐度 |
|--------|----------|------|--------|
| 东方财富 | `stock_financial_analysis_indicator` | 财务分析指标 | ⭐⭐⭐⭐⭐ |
| 东方财富 | `stock_financial_abstract` | 财务摘要 | ⭐⭐⭐⭐ |
| 同花顺 | `stock_financial_abstract_ths` | 财务摘要(同花顺源) | ⭐⭐⭐⭐ |
| 新浪 | `stock_financial_report_sina` | 财务报表 | ⭐⭐⭐ |
| 同花顺 | `stock_financial_debt_ths` | 负债数据 | ⭐⭐⭐ |
| 同花顺 | `stock_financial_benefit_ths` | 利润数据 | ⭐⭐⭐ |
| 同花顺 | `stock_financial_cash_ths` | 现金流数据 | ⭐⭐⭐ |

#### 2.1.5 行业板块数据

| 数据源 | 接口函数 | 特点 | 推荐度 |
|--------|----------|------|--------|
| 东方财富 | `stock_board_industry_name_em` | 行业板块列表 | ⭐⭐⭐⭐⭐ |
| 东方财富 | `stock_board_industry_cons_em` | 行业成分股 | ⭐⭐⭐⭐⭐ |
| 东方财富 | `stock_board_industry_hist_em` | 行业历史行情 | ⭐⭐⭐⭐⭐ |
| 同花顺 | `stock_board_industry_summary_ths` | 行业汇总 | ⭐⭐⭐⭐ |
| 同花顺 | `stock_board_industry_index_ths` | 行业指数 | ⭐⭐⭐⭐ |

#### 2.1.6 ETF基金数据

| 数据源 | 接口函数 | 特点 | 推荐度 |
|--------|----------|------|--------|
| 东方财富 | `fund_etf_spot_em` | ETF实时行情 | ⭐⭐⭐⭐⭐ |
| 东方财富 | `fund_etf_hist_em` | ETF历史行情 | ⭐⭐⭐⭐⭐ |
| 同花顺 | `fund_etf_spot_ths` | ETF实时行情 | ⭐⭐⭐⭐ |
| 新浪 | `fund_etf_hist_sina` | ETF历史行情 | ⭐⭐⭐ |
| 新浪 | `fund_etf_category_sina` | ETF分类 | ⭐⭐⭐ |

#### 2.1.7 分红派息数据

| 数据源 | 接口函数 | 特点 | 推荐度 |
|--------|----------|------|--------|
| 东方财富 | `stock_fhps_em` | 分红派息汇总 | ⭐⭐⭐⭐⭐ |
| 东方财富 | `stock_fhps_detail_em` | 分红派息明细 | ⭐⭐⭐⭐⭐ |
| 同花顺 | `stock_fhps_detail_ths` | 分红派息明细 | ⭐⭐⭐⭐ |
| 巨潮 | `stock_dividend_cninfo` | 分红数据 | ⭐⭐⭐ |

#### 2.1.8 分时数据

| 数据源 | 接口函数 | 特点 | 推荐度 |
|--------|----------|------|--------|
| 东方财富 | `stock_zh_a_hist_min_em` | 分钟级历史数据 | ⭐⭐⭐⭐⭐ |
| 东方财富 | `stock_intraday_em` | 日内分时 | ⭐⭐⭐⭐ |
| 新浪 | `stock_intraday_sina` | 日内分时 | ⭐⭐⭐ |
| 腾讯 | `stock_zh_a_tick_tx` | Tick数据 | ⭐⭐⭐ |

### 2.2 akshare内部冗余策略

```
┌─────────────────────────────────────────────────────────────────┐
│                    AkshareAdapter (akshare适配器)                │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │ 东方财富   │  │  同花顺   │  │   新浪    │  │  雪球/腾讯 │    │
│  │  (_em)    │  │  (_ths)   │  │  (_sina)  │  │ (_xq/_tx) │    │
│  │  优先级1   │  │  优先级2  │  │  优先级3  │  │  优先级4   │    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘    │
│        │              │              │              │          │
│        └──────────────┴──────────────┴──────────────┘          │
│                              ▼                                  │
│              ┌─────────────────────────────┐                   │
│              │   InternalFallback          │                   │
│              │   (akshare内部故障转移)       │                   │
│              │   - 同功能多接口自动切换      │                   │
│              │   - 返回格式统一标准化        │                   │
│              └─────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 返回数据格式差异处理

> 艹，不同数据源返回的字段名不一样，老王得统一处理！

#### 历史K线数据字段映射

| 标准字段 | 东方财富(stock_zh_a_hist) | 腾讯(stock_zh_a_hist_tx) |
|----------|---------------------------|--------------------------|
| date | 日期 | date |
| open | 开盘 | open |
| close | 收盘 | close |
| high | 最高 | high |
| low | 最低 | low |
| volume | 成交量 | volume |
| amount | 成交额 | amount |

#### 财务数据字段映射

| 标准字段 | 东方财富 | 同花顺 | 新浪 |
|----------|----------|--------|------|
| roe | 净资产收益率 | 净资产收益率 | roe |
| eps | 每股收益 | 基本每股收益 | eps |
| pe | 市盈率 | 市盈率(动态) | pe_ratio |

---

## 三、baostock接口能力分析（跨库冗余）

### 3.1 可用接口清单

| 接口函数 | 用途 | 对应akshare接口 |
|----------|------|-----------------|
| `bs.query_history_k_data_plus()` | 历史K线数据 | `ak.stock_zh_a_hist()` |
| `bs.query_hs300_stocks()` | 沪深300成分股 | `ak.index_stock_cons_weight_csindex("000300")` |
| `bs.query_zz500_stocks()` | 中证500成分股 | `ak.index_stock_cons_weight_csindex("000905")` |
| `bs.query_sz50_stocks()` | 上证50成分股 | `ak.index_stock_cons_weight_csindex("000001")` |
| `bs.query_stock_basic()` | 股票基本信息 | `ak.stock_individual_info_em()` |
| `bs.query_stock_industry()` | 行业分类 | `ak.stock_board_industry_name_em()` |
| `bs.query_profit_data()` | 盈利能力数据 | `ak.stock_financial_analysis_indicator()` |
| `bs.query_balance_data()` | 偿债能力数据 | 财务数据补充 |
| `bs.query_growth_data()` | 成长能力数据 | 财务数据补充 |
| `bs.query_operation_data()` | 营运能力数据 | 财务数据补充 |
| `bs.query_cash_flow_data()` | 现金流数据 | 财务数据补充 |
| `bs.query_dupont_data()` | 杜邦分析数据 | 财务数据补充 |
| `bs.query_dividend_data()` | 分红数据 | 分红信息 |
| `bs.query_adjust_factor()` | 复权因子 | 复权计算 |
| `bs.query_all_stock()` | 全部股票列表 | `ak.stock_info_a_code_name()` |
| `bs.query_trade_dates()` | 交易日历 | 交易日判断 |

### 3.2 baostock特点

- **优点**：免费、稳定、无访问限制、数据质量高
- **缺点**：需要login/logout、数据更新略慢（T+1）、无实时数据、无资金流向数据

---

## 四、接口冗余架构设计（双层冗余）

### 4.1 核心设计原则（升级版 - 双层冗余架构）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       DataProvider (统一数据层)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────┐  ┌──────────────┐ │
│  │              AkshareAdapter (第一层冗余)          │  │  baostock   │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │  │  (第二层)    │ │
│  │  │东方财富  │ │ 同花顺  │ │  新浪   │ │雪球/腾讯│ │  │             │ │
│  │  │ (_em)   │ │ (_ths)  │ │ (_sina) │ │(_xq/tx)│ │  │  跨库备用    │ │
│  │  │ 优先级1 │ │ 优先级2 │ │ 优先级3 │ │ 优先级4│ │  │             │ │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └───┬────┘ │  └──────┬──────┘ │
│  │       └───────────┴──────────┴───────────┘      │         │        │
│  │                       ▼                         │         │        │
│  │         ┌─────────────────────────┐             │         │        │
│  │         │  InternalFallback       │             │         │        │
│  │         │  (akshare内部故障转移)   │             │         │        │
│  │         └─────────────────────────┘             │         │        │
│  └──────────────────────┬──────────────────────────┘         │        │
│                         │                                    │        │
│                         └────────────────┬───────────────────┘        │
│                                          ▼                            │
│                        ┌─────────────────────────────┐                │
│                        │   CrossLibFallbackManager   │                │
│                        │   (跨库故障转移管理器)        │                │
│                        │   - akshare全挂 → baostock  │                │
│                        │   - 自动重试 + 健康检查      │                │
│                        └─────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

**双层冗余策略**：
1. **第一层（akshare内部）**：东财挂了切同花顺，同花顺挂了切新浪...
2. **第二层（跨库）**：akshare全挂了切baostock

### 4.2 接口映射表（升级版 - 含akshare内部冗余）

| 功能 | akshare主接口 | akshare备用接口 | baostock兜底 | 降级策略 |
|------|---------------|-----------------|--------------|----------|
| A股历史K线 | `stock_zh_a_hist` | `stock_zh_a_hist_tx` | `query_history_k_data_plus` | 三级切换 |
| 个股基本信息 | `stock_individual_info_em` | `stock_individual_basic_info_xq` | `query_stock_basic` | 三级切换 |
| 财务分析指标 | `stock_financial_analysis_indicator` | `stock_financial_abstract_ths` | `query_profit_data` | 三级切换 |
| 财务摘要 | `stock_financial_abstract` | `stock_financial_abstract_ths` | `query_profit_data` | 三级切换 |
| 行业板块列表 | `stock_board_industry_name_em` | `stock_board_industry_summary_ths` | `query_stock_industry` | 三级切换 |
| 行业成分股 | `stock_board_industry_cons_em` | - | - | 单源+缓存 |
| 行业历史行情 | `stock_board_industry_hist_em` | `stock_board_industry_index_ths` | - | 双级切换 |
| ETF实时行情 | `fund_etf_spot_em` | `fund_etf_spot_ths` | - | 双级切换 |
| ETF历史行情 | `fund_etf_hist_em` | `fund_etf_hist_sina` | - | 双级切换 |
| 分红派息 | `stock_fhps_detail_em` | `stock_fhps_detail_ths` | `query_dividend_data` | 三级切换 |
| 沪深300成分股 | `index_stock_cons_weight_csindex` | - | `query_hs300_stocks` | 双级切换 |
| 中证500成分股 | `index_stock_cons_weight_csindex` | - | `query_zz500_stocks` | 双级切换 |
| 资金流向 | `stock_individual_fund_flow` | - | - | 单源+缓存 |
| 北向资金 | `stock_hsgt_hist_em` | - | - | 单源+缓存 |

---

## 五、实施方案

### 5.1 新增文件结构

```
app/
├── core/
│   ├── data_provider.py      # 统一数据提供层（新增）
│   ├── fallback_manager.py   # 故障转移管理器（新增）
│   └── database.py
├── adapters/                  # 数据源适配器（新增目录）
│   ├── __init__.py
│   ├── base_adapter.py       # 适配器基类
│   ├── akshare_adapter.py    # akshare适配器
│   └── baostock_adapter.py   # baostock适配器
```

### 5.2 核心类设计

#### 4.2.1 BaseAdapter（适配器基类）

```python
# app/adapters/base_adapter.py
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd

class BaseAdapter(ABC):
    """数据源适配器基类 - 老王说：所有数据源都得按这个规矩来！"""

    @abstractmethod
    def get_stock_history(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史K线"""
        pass

    @abstractmethod
    def get_index_stocks(self, index_code: str) -> list:
        """获取指数成分股"""
        pass

    @abstractmethod
    def get_stock_info(self, code: str) -> dict:
        """获取股票基本信息"""
        pass

    @abstractmethod
    def get_financial_data(self, code: str) -> dict:
        """获取财务数据"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        pass
```

#### 4.2.2 FallbackManager（故障转移管理器）

```python
# app/core/fallback_manager.py
class FallbackManager:
    """故障转移管理器 - 老王说：接口挂了？自动给你换一个！"""

    def __init__(self, adapters: list, max_retries: int = 3):
        self.adapters = adapters  # 按优先级排序的适配器列表
        self.max_retries = max_retries
        self.adapter_status = {a.__class__.__name__: True for a in adapters}

    def execute(self, method_name: str, *args, **kwargs):
        """执行方法，自动故障转移"""
        last_error = None

        for adapter in self.adapters:
            if not self.adapter_status.get(adapter.__class__.__name__, True):
                continue  # 跳过已标记为不可用的适配器

            for retry in range(self.max_retries):
                try:
                    method = getattr(adapter, method_name)
                    result = method(*args, **kwargs)
                    if result is not None and not (isinstance(result, pd.DataFrame) and result.empty):
                        return result
                except Exception as e:
                    last_error = e
                    if retry == self.max_retries - 1:
                        self.adapter_status[adapter.__class__.__name__] = False
                    continue

        raise last_error or Exception("所有数据源均不可用")
```

#### 4.2.3 DataProvider（统一数据层）

```python
# app/core/data_provider.py
class DataProvider:
    """统一数据提供层 - 老王说：调数据就找我，别管底下用的啥！"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_adapters()
        return cls._instance

    def _init_adapters(self):
        from app.adapters.akshare_adapter import AkshareAdapter
        from app.adapters.baostock_adapter import BaostockAdapter

        self.fallback = FallbackManager([
            AkshareAdapter(),   # 主数据源
            BaostockAdapter(),  # 备用数据源
        ])

    def get_stock_history(self, code, start_date, end_date):
        return self.fallback.execute('get_stock_history', code, start_date, end_date)

    # ... 其他方法
```

### 5.3 改造步骤

#### 第一阶段：基础设施搭建（优先级P0）

| 步骤 | 任务 | 涉及文件 |
|------|------|----------|
| 1 | 创建adapters目录和基类 | `app/adapters/base_adapter.py` |
| 2 | 实现akshare适配器 | `app/adapters/akshare_adapter.py` |
| 3 | 实现baostock适配器 | `app/adapters/baostock_adapter.py` |
| 4 | 实现故障转移管理器 | `app/core/fallback_manager.py` |
| 5 | 实现统一数据层 | `app/core/data_provider.py` |

#### 第二阶段：核心模块改造（优先级P1）

| 步骤 | 任务 | 涉及文件 |
|------|------|----------|
| 6 | 改造stock_analyzer | `app/analysis/stock_analyzer.py` |
| 7 | 改造fundamental_analyzer | `app/analysis/fundamental_analyzer.py` |
| 8 | 改造index_industry_analyzer | `app/analysis/index_industry_analyzer.py` |

#### 第三阶段：扩展模块改造（优先级P2）

| 步骤 | 任务 | 涉及文件 |
|------|------|----------|
| 9 | 改造capital_flow_analyzer | `app/analysis/capital_flow_analyzer.py` |
| 10 | 改造industry_analyzer | `app/analysis/industry_analyzer.py` |
| 11 | 改造etf_analyzer | `app/analysis/etf_analyzer.py` |
| 12 | 改造web_server接口 | `app/web/web_server.py` |

---

## 六、核心代码实现

### 6.1 AkshareAdapter（含内部冗余）

```python
# app/adapters/akshare_adapter.py
import akshare as ak
import pandas as pd
from .base_adapter import BaseAdapter

class AkshareAdapter(BaseAdapter):
    """akshare适配器 - 老王说：内部多数据源自动切换！"""

    # 接口冗余配置：同功能多数据源
    FALLBACK_CONFIG = {
        'stock_history': [
            {'func': 'stock_zh_a_hist', 'code_format': 'plain'},      # 东财
            {'func': 'stock_zh_a_hist_tx', 'code_format': 'prefix'},  # 腾讯
        ],
        'stock_info': [
            {'func': 'stock_individual_info_em'},      # 东财
            {'func': 'stock_individual_basic_info_xq'}, # 雪球
        ],
        'financial_data': [
            {'func': 'stock_financial_analysis_indicator'},  # 东财
            {'func': 'stock_financial_abstract_ths'},        # 同花顺
            {'func': 'stock_financial_report_sina'},         # 新浪
        ],
        'industry_list': [
            {'func': 'stock_board_industry_name_em'},     # 东财
            {'func': 'stock_board_industry_summary_ths'}, # 同花顺
        ],
        'etf_spot': [
            {'func': 'fund_etf_spot_em'},  # 东财
            {'func': 'fund_etf_spot_ths'}, # 同花顺
        ],
        'etf_hist': [
            {'func': 'fund_etf_hist_em'},   # 东财
            {'func': 'fund_etf_hist_sina'}, # 新浪
        ],
    }

    # 字段映射：统一不同数据源的返回格式
    FIELD_MAPPING = {
        'stock_zh_a_hist': {'日期': 'date', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'},
        'stock_zh_a_hist_tx': {},  # 腾讯接口字段已是英文
    }

    def _call_with_fallback(self, config_key: str, *args, **kwargs) -> pd.DataFrame:
        """内部冗余调用 - 自动切换数据源"""
        configs = self.FALLBACK_CONFIG.get(config_key, [])
        last_error = None

        for config in configs:
            func_name = config['func']
            try:
                func = getattr(ak, func_name)
                result = func(*args, **kwargs)
                if result is not None and not result.empty:
                    # 统一字段名
                    mapping = self.FIELD_MAPPING.get(func_name, {})
                    if mapping:
                        result.rename(columns=mapping, inplace=True)
                    return result
            except Exception as e:
                last_error = e
                continue

        raise last_error or Exception(f"所有{config_key}接口均不可用")

    def get_stock_history(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史K线 - 东财挂了自动切腾讯"""
        # 先尝试东财接口
        try:
            df = ak.stock_zh_a_hist(symbol=code, start_date=start_date, end_date=end_date, adjust="qfq")
            if df is not None and not df.empty:
                df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
                return df
        except:
            pass

        # 东财挂了，切腾讯（需要加市场前缀）
        prefix = 'sh' if code.startswith('6') else 'sz'
        tx_code = f"{prefix}{code}"
        df = ak.stock_zh_a_hist_tx(symbol=tx_code, start_date=start_date, end_date=end_date, adjust="qfq")
        return df

    def get_financial_data(self, code: str) -> dict:
        """获取财务数据 - 东财→同花顺→新浪"""
        # 东财
        try:
            return ak.stock_financial_analysis_indicator(symbol=code, start_year="2023")
        except:
            pass
        # 同花顺
        try:
            return ak.stock_financial_abstract_ths(symbol=code)
        except:
            pass
        # 新浪
        return ak.stock_financial_report_sina(stock=code)

    def health_check(self) -> bool:
        try:
            ak.stock_zh_a_spot_em()
            return True
        except:
            return False
```

### 6.2 BaostockAdapter（跨库备用）

```python
# app/adapters/baostock_adapter.py
import baostock as bs
import pandas as pd
from .base_adapter import BaseAdapter

class BaostockAdapter(BaseAdapter):
    """baostock数据源适配器 - 老王说：akshare挂了就靠你了！"""

    def __init__(self):
        self._logged_in = False

    def _ensure_login(self):
        if not self._logged_in:
            lg = bs.login()
            if lg.error_code != '0':
                raise Exception(f"baostock登录失败: {lg.error_msg}")
            self._logged_in = True

    def _convert_code(self, code: str) -> str:
        """转换股票代码格式：000001 -> sh.000001 或 sz.000001"""
        code = code.replace('.SH', '').replace('.SZ', '').replace('sh', '').replace('sz', '')
        if code.startswith('6'):
            return f"sh.{code}"
        else:
            return f"sz.{code}"

    def get_stock_history(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史K线"""
        self._ensure_login()
        bs_code = self._convert_code(code)

        # 转换日期格式 20240101 -> 2024-01-01
        if len(start_date) == 8:
            start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        if len(end_date) == 8:
            end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"  # 前复权
        )

        data_list = []
        while (rs.error_code == '0') and rs.next():
            data_list.append(rs.get_row_data())

        df = pd.DataFrame(data_list, columns=rs.fields)

        # 标准化列名和数据类型
        df.rename(columns={'date': 'date'}, inplace=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['date'] = pd.to_datetime(df['date'])

        return df

    def get_index_stocks(self, index_code: str) -> list:
        """获取指数成分股"""
        self._ensure_login()

        index_map = {
            '000300': bs.query_hs300_stocks,
            '000905': bs.query_zz500_stocks,
            '000001': bs.query_sz50_stocks,
        }

        query_func = index_map.get(index_code)
        if not query_func:
            raise ValueError(f"不支持的指数代码: {index_code}")

        rs = query_func()
        stocks = []
        while (rs.error_code == '0') and rs.next():
            row = rs.get_row_data()
            # baostock返回格式：sh.600000，需要转换
            code = row[1].replace('sh.', '').replace('sz.', '')
            stocks.append(code)

        return stocks

    def get_financial_data(self, code: str) -> dict:
        """获取财务数据"""
        self._ensure_login()
        bs_code = self._convert_code(code)

        result = {}

        # 盈利能力
        rs = bs.query_profit_data(code=bs_code, year=2024, quarter=3)
        if rs.error_code == '0' and rs.next():
            data = dict(zip(rs.fields, rs.get_row_data()))
            result['profit'] = data

        # 成长能力
        rs = bs.query_growth_data(code=bs_code, year=2024, quarter=3)
        if rs.error_code == '0' and rs.next():
            data = dict(zip(rs.fields, rs.get_row_data()))
            result['growth'] = data

        return result

    def get_stock_info(self, code: str) -> dict:
        """获取股票基本信息"""
        self._ensure_login()
        bs_code = self._convert_code(code)

        rs = bs.query_stock_basic(code=bs_code)
        if rs.error_code == '0' and rs.next():
            return dict(zip(rs.fields, rs.get_row_data()))
        return {}

    def health_check(self) -> bool:
        """健康检查"""
        try:
            self._ensure_login()
            rs = bs.query_trade_dates(start_date="2024-01-01", end_date="2024-01-02")
            return rs.error_code == '0'
        except:
            return False

    def __del__(self):
        if self._logged_in:
            bs.logout()
```

---

## 七、配置管理

### 6.1 环境变量配置

```bash
# .env 新增配置
# 数据源优先级配置（逗号分隔，按优先级排序）
DATA_SOURCES=akshare,baostock

# 重试配置
DATA_RETRY_COUNT=3
DATA_RETRY_DELAY=1

# 健康检查间隔（秒）
HEALTH_CHECK_INTERVAL=300

# 缓存配置
CACHE_TTL_STOCK_HISTORY=3600
CACHE_TTL_INDEX_STOCKS=86400
CACHE_TTL_FINANCIAL=86400
```

### 6.2 配置类

```python
# config/data_config.py
import os

class DataConfig:
    DATA_SOURCES = os.getenv('DATA_SOURCES', 'akshare,baostock').split(',')
    RETRY_COUNT = int(os.getenv('DATA_RETRY_COUNT', 3))
    RETRY_DELAY = int(os.getenv('DATA_RETRY_DELAY', 1))
    HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', 300))
```

---

## 八、测试方案

### 7.1 单元测试

```python
# tests/test_data_provider.py
def test_fallback_to_baostock():
    """测试akshare失败时自动切换到baostock"""
    provider = DataProvider()
    # Mock akshare失败
    with patch('akshare.stock_zh_a_hist', side_effect=Exception("接口挂了")):
        df = provider.get_stock_history('000001', '20240101', '20240301')
        assert not df.empty

def test_retry_mechanism():
    """测试重试机制"""
    # ...
```

### 7.2 集成测试

```bash
# 模拟akshare不可用
export DISABLE_AKSHARE=true
python -m pytest tests/integration/
```

---

## 九、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| baostock数据延迟 | 实时性降低 | 仅作为备用，优先使用akshare |
| 两个数据源都挂 | 系统不可用 | 增加本地缓存持久化 |
| 数据格式不一致 | 分析结果偏差 | 适配器层统一数据格式 |
| baostock登录限制 | 并发问题 | 使用连接池管理 |

---

## 十、后续扩展

1. **增加更多数据源**：Tushare、新浪财经、同花顺等
2. **数据质量监控**：对比多数据源数据一致性
3. **智能路由**：根据数据类型自动选择最优数据源
4. **本地数据库缓存**：SQLite/Redis持久化热点数据

---

> 艹，老王把方案写完了！这套架构搞完，就算东方财富把akshare封到姥姥家去，系统也能照常运行！

---

## 十一、实施进度记录

### 第一阶段：基础设施搭建 ✅ 已完成

| 步骤 | 任务 | 状态 | 完成时间 |
|------|------|------|----------|
| 1 | 创建adapters目录和基类 | ✅ | 2025-12-15 |
| 2 | 实现akshare适配器（含内部冗余） | ✅ | 2025-12-15 |
| 3 | 实现baostock适配器 | ✅ | 2025-12-15 |
| 4 | 实现故障转移管理器 | ✅ | 2025-12-15 |
| 5 | 实现统一数据层 | ✅ | 2025-12-15 |

### 第二阶段：核心模块改造 ✅ 已完成

| 步骤 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 6 | 改造stock_analyzer | ✅ | get_stock_data/get_stock_info已改造 |
| 7 | 改造fundamental_analyzer | ✅ | get_financial_indicators已改造 |
| 8 | 改造index_industry_analyzer | ✅ | analyze_index/analyze_industry/compare_industries已改造 |

### 第三阶段：扩展模块改造 ✅ 已完成

| 步骤 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 9 | 改造capital_flow_analyzer | ✅ | get_sector_stocks已改造 |
| 10 | 改造industry_analyzer | ✅ | _get_industry_code/get_industry_stocks/compare_industries已改造 |
| 11 | 改造etf_analyzer | ✅ | 已接入DataProvider |
| 12 | 改造web_server | ✅ | /api/index_stocks, /api/industry_stocks, /api/board_stocks已改造 |

### 新增文件清单

```
app/
├── adapters/                    # 新增目录
│   ├── __init__.py             # 模块导出
│   ├── base_adapter.py         # 适配器基类
│   ├── akshare_adapter.py      # akshare适配器（含内部多源冗余）
│   └── baostock_adapter.py     # baostock适配器
├── core/
│   ├── fallback_manager.py     # 故障转移管理器（新增）
│   └── data_provider.py        # 统一数据层（新增）
```

### 已改造文件

- `app/analysis/stock_analyzer.py` - 已接入DataProvider
- `app/analysis/fundamental_analyzer.py` - 已接入DataProvider
- `app/analysis/index_industry_analyzer.py` - 已接入DataProvider
- `app/analysis/capital_flow_analyzer.py` - 已接入DataProvider
- `app/analysis/industry_analyzer.py` - 已接入DataProvider
- `app/analysis/etf_analyzer.py` - 已接入DataProvider
- `app/web/web_server.py` - 已接入DataProvider

> 艹，老王把所有模块都改完了！双层冗余架构已全面部署，东财挂了自动切腾讯/同花顺，akshare全挂了自动切baostock！
