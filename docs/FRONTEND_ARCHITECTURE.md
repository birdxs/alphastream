# 前后端分离架构设计文档

```
Input: 技术选型共识 + 后端API规范 + 现有模板基线
Output: 完整前后端分离架构方案（项目结构/API客户端/页面迁移/组件/状态/实时通信/部署）
Pos: docs/FRONTEND_ARCHITECTURE.md - Phase 2 架构设计产出，前端开发实施唯一蓝图
```

> 一旦我被修改，请更新所属文件夹的 README.md。

---

**版本**: v1.0.0
**基于**: FRONTEND_RESEARCH.md 调研结论
**后端版本**: Flask v2.3.0 (API.md)
**技术栈**: Next.js 15 + React 19 + shadcn/ui + TailwindCSS + TradingView LWC + ECharts + Zustand/Jotai

---

## 目录

- [1. 项目结构设计](#1-项目结构设计)
- [2. API客户端设计](#2-api客户端设计)
- [3. 页面迁移映射表](#3-页面迁移映射表)
- [4. 组件设计](#4-组件设计)
- [5. 状态管理架构](#5-状态管理架构)
- [6. 实时通信设计](#6-实时通信设计)
- [7. 部署架构](#7-部署架构)
- [8. 后端需要的改动清单](#8-后端需要的改动清单)

---

## 1. 项目结构设计

```
frontend/
├── src/
│   ├── app/                           # Next.js 15 App Router
│   │   ├── (auth)/                    # 认证页面组（预留）
│   │   │   ├── login/page.tsx
│   │   │   └── layout.tsx
│   │   ├── dashboard/                 # 智能仪表盘
│   │   │   └── page.tsx
│   │   ├── stock/
│   │   │   └── [code]/               # 股票详情（动态路由）
│   │   │       ├── page.tsx
│   │   │       └── loading.tsx
│   │   ├── analysis/                  # Agent智能分析
│   │   │   └── page.tsx
│   │   ├── market-scan/               # 市场扫描
│   │   │   └── page.tsx
│   │   ├── portfolio/                 # 投资组合
│   │   │   └── page.tsx
│   │   ├── fundamental/               # 基本面分析
│   │   │   └── page.tsx
│   │   ├── capital-flow/              # 资金流向
│   │   │   └── page.tsx
│   │   ├── scenario/                  # 情景预测
│   │   │   └── page.tsx
│   │   ├── risk/                      # 风险监控
│   │   │   └── page.tsx
│   │   ├── qa/                        # 智能问答
│   │   │   └── page.tsx
│   │   ├── industry/                  # 行业分析
│   │   │   └── page.tsx
│   │   ├── etf/                       # ETF分析
│   │   │   └── page.tsx
│   │   ├── layout.tsx                 # 根布局（导航 + 侧边栏壳）
│   │   ├── page.tsx                   # 首页（财经门户）
│   │   ├── error.tsx                  # 全局错误边界
│   │   ├── loading.tsx                # 全局加载态
│   │   ├── not-found.tsx              # 404页面
│   │   └── globals.css                # 全局样式入口
│   │
│   ├── components/                    # 可复用组件
│   │   ├── ui/                        # shadcn/ui 基础组件（由CLI安装）
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── input.tsx
│   │   │   ├── select.tsx
│   │   │   ├── skeleton.tsx
│   │   │   ├── table.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── toast.tsx
│   │   │   ├── tooltip.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── progress.tsx
│   │   │   ├── slider.tsx
│   │   │   ├── switch.tsx
│   │   │   └── sheet.tsx
│   │   │
│   │   ├── charts/                    # 图表组件
│   │   │   ├── candlestick-chart.tsx   # K线图（TradingView LWC）
│   │   │   ├── volume-chart.tsx        # 成交量（TradingView LWC）
│   │   │   ├── indicator-overlay.tsx   # 技术指标叠加层
│   │   │   ├── radar-chart.tsx         # 雷达图（ECharts）
│   │   │   ├── pie-chart.tsx           # 饼图（ECharts）
│   │   │   ├── bar-chart.tsx           # 柱状图（ECharts）
│   │   │   ├── line-chart.tsx          # 折线图（ECharts）
│   │   │   ├── heatmap-chart.tsx       # 热力图（ECharts）
│   │   │   ├── fund-flow-chart.tsx     # 资金流向图（ECharts）
│   │   │   ├── scenario-chart.tsx      # 情景预测扇形图（ECharts）
│   │   │   └── chart-container.tsx     # 图表容器（响应式 + 加载态）
│   │   │
│   │   ├── stock/                     # 股票业务组件
│   │   │   ├── stock-search.tsx        # 股票搜索框（A/HK/US切换）
│   │   │   ├── stock-card.tsx          # 股票卡片（简要信息）
│   │   │   ├── stock-price-ticker.tsx  # 实时价格跳动
│   │   │   ├── stock-score-badge.tsx   # 评分徽章
│   │   │   ├── stock-table.tsx         # 股票列表表格
│   │   │   ├── stock-detail-header.tsx # 详情页头部
│   │   │   └── market-type-switch.tsx  # 市场类型切换器
│   │   │
│   │   ├── analysis/                  # 分析业务组件
│   │   │   ├── agent-progress.tsx      # Agent分析进度条（多节点）
│   │   │   ├── agent-report-card.tsx   # 单Agent报告卡片
│   │   │   ├── decision-panel.tsx      # 投资决策面板（BUY/SELL/HOLD）
│   │   │   ├── investor-opinions.tsx   # 投资大师意见面板
│   │   │   ├── consensus-panel.tsx     # AI共识面板
│   │   │   ├── bull-bear-debate.tsx    # 多空辩论对比
│   │   │   ├── risk-gauge.tsx          # 风险仪表盘
│   │   │   ├── fundamental-card.tsx    # 基本面指标卡片
│   │   │   ├── capital-flow-panel.tsx  # 资金流向面板
│   │   │   ├── scenario-panel.tsx      # 情景预测面板（三情景）
│   │   │   ├── execution-log.tsx       # 执行日志展示
│   │   │   └── analysis-depth-selector.tsx # 研究深度选择器
│   │   │
│   │   ├── layout/                    # 布局组件
│   │   │   ├── app-sidebar.tsx         # 侧边栏导航
│   │   │   ├── top-navbar.tsx          # 顶部导航栏
│   │   │   ├── breadcrumb-nav.tsx      # 面包屑
│   │   │   ├── theme-toggle.tsx        # 主题切换（亮/暗）
│   │   │   ├── market-color-toggle.tsx # 涨跌色切换（中国/国际）
│   │   │   └── footer.tsx              # 页脚
│   │   │
│   │   └── common/                    # 通用组件
│   │       ├── async-task-tracker.tsx   # 异步任务追踪器
│   │       ├── error-boundary.tsx       # 错误边界
│   │       ├── empty-state.tsx          # 空状态
│   │       ├── loading-skeleton.tsx     # 骨架屏
│   │       ├── data-freshness.tsx       # 数据新鲜度指示器
│   │       ├── confirm-dialog.tsx       # 确认对话框
│   │       └── number-animate.tsx       # 数字跳动动画
│   │
│   ├── lib/                           # 工具库
│   │   ├── api/                       # API客户端层
│   │   │   ├── client.ts               # 基础API客户端（fetch封装）
│   │   │   ├── stock.ts                # 股票相关API
│   │   │   ├── analysis.ts             # 分析相关API（Agent/增强/ETF）
│   │   │   ├── market.ts               # 市场扫描/指数/板块API
│   │   │   ├── fundamental.ts          # 基本面/资金流/风险API
│   │   │   ├── industry.ts             # 行业分析API
│   │   │   ├── news.ts                 # 新闻/历史API
│   │   │   ├── qa.ts                   # 智能问答API
│   │   │   ├── mcp.ts                  # MCP工具API
│   │   │   └── types.ts                # API请求/响应类型（与API.md对齐）
│   │   │
│   │   ├── hooks/                     # 自定义Hooks
│   │   │   ├── use-async-task.ts        # 异步任务轮询
│   │   │   ├── use-stock-data.ts        # 股票数据获取+缓存
│   │   │   ├── use-agent-analysis.ts    # Agent分析流程
│   │   │   ├── use-market-scan.ts       # 市场扫描
│   │   │   ├── use-websocket.ts         # WebSocket连接管理
│   │   │   ├── use-debounce.ts          # 防抖
│   │   │   ├── use-local-storage.ts     # 本地存储
│   │   │   └── use-media-query.ts       # 响应式断点
│   │   │
│   │   ├── stores/                    # 状态管理
│   │   │   ├── app-store.ts             # 应用全局状态（Zustand）
│   │   │   ├── portfolio-store.ts       # 投资组合状态（Zustand）
│   │   │   ├── price-atoms.ts           # 实时股价原子（Jotai）
│   │   │   ├── task-atoms.ts            # 异步任务状态原子（Jotai）
│   │   │   └── analysis-atoms.ts        # 分析进度原子（Jotai）
│   │   │
│   │   ├── utils/                     # 工具函数
│   │   │   ├── format.ts                # 数字/日期/百分比格式化
│   │   │   ├── stock-code.ts            # 股票代码校验与格式化
│   │   │   ├── color.ts                 # 涨跌色计算（中国/国际模式）
│   │   │   ├── chart-helpers.ts         # 图表数据转换
│   │   │   └── cn.ts                    # className合并（clsx + twMerge）
│   │   │
│   │   └── types/                     # TypeScript类型定义
│   │       ├── stock.ts                 # 股票数据类型
│   │       ├── analysis.ts              # 分析结果类型
│   │       ├── market.ts                # 市场/行业类型
│   │       └── api.ts                   # API通用类型（分页/错误/异步任务）
│   │
│   └── styles/                        # 全局样式
│       └── globals.css                 # Tailwind指令 + CSS变量（主题色/涨跌色）
│
├── public/                            # 静态资源
│   ├── favicon.ico
│   └── images/
│
├── next.config.ts                     # Next.js配置（API代理rewrite）
├── tailwind.config.ts                 # Tailwind配置（金融色彩系统）
├── tsconfig.json                      # TypeScript配置
├── components.json                    # shadcn/ui配置
├── package.json
├── Dockerfile                         # 前端Docker（多阶段构建）
├── .env.local                         # 环境变量（NEXT_PUBLIC_API_URL等）
└── .env.example                       # 环境变量样例
```

### 1.1 目录职责说明

| 目录 | 职责 | 关键约束 |
|------|------|----------|
| `app/` | 路由与页面，每个route一个文件夹 | 仅包含页面级组件，不含业务逻辑 |
| `components/ui/` | shadcn/ui原子组件，由CLI生成 | 禁止手动修改，升级时覆盖 |
| `components/charts/` | 图表组件，封装TradingView LWC和ECharts | 统一暴露`data`/`options`/`onEvent` Props |
| `components/stock/` | 股票业务组件 | 可组合，不直接调用API |
| `components/analysis/` | 分析展示组件 | 仅负责展示，数据由Hooks注入 |
| `lib/api/` | API调用层，唯一与后端通信的模块 | 所有请求必须经过`client.ts` |
| `lib/hooks/` | 数据获取与副作用封装 | 桥接API层与组件层 |
| `lib/stores/` | 全局/实时状态 | Zustand管全局，Jotai管高频 |

---

## 2. API客户端设计

### 2.1 基础客户端 (`lib/api/client.ts`)

```typescript
// lib/api/client.ts
// Input: API请求配置
// Output: 类型安全的响应数据
// Pos: 所有HTTP请求的唯一出口

interface ApiClientConfig {
  baseUrl: string;
  timeout: number;
  headers: Record<string, string>;
}

interface ApiResponse<T> {
  data: T;
  status: number;
  ok: boolean;
}

interface ApiError {
  error: string;
  path?: string;
  method?: string;
  status: number;
}

class ApiClient {
  private config: ApiClientConfig;
  private requestInterceptors: Array<(config: RequestInit) => RequestInit> = [];
  private responseInterceptors: Array<(response: Response) => Response> = [];

  constructor(config?: Partial<ApiClientConfig>) {
    this.config = {
      baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8888',
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
      ...config,
    };
  }

  // 请求拦截器注册
  useRequestInterceptor(fn: (config: RequestInit) => RequestInit) {
    this.requestInterceptors.push(fn);
  }

  // 响应拦截器注册
  useResponseInterceptor(fn: (response: Response) => Response) {
    this.responseInterceptors.push(fn);
  }

  async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.config.baseUrl}${endpoint}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

    let config: RequestInit = {
      ...options,
      headers: { ...this.config.headers, ...options.headers },
      signal: controller.signal,
    };

    // 执行请求拦截器
    for (const interceptor of this.requestInterceptors) {
      config = interceptor(config);
    }

    try {
      let response = await fetch(url, config);
      clearTimeout(timeoutId);

      // 执行响应拦截器
      for (const interceptor of this.responseInterceptors) {
        response = interceptor(response);
      }

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw {
          error: errorBody.error || `HTTP ${response.status}`,
          path: endpoint,
          method: options.method || 'GET',
          status: response.status,
        } as ApiError;
      }

      const data = await response.json();
      return { data: data as T, status: response.status, ok: true };
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw { error: '请求超时', path: endpoint, status: 408 } as ApiError;
      }
      throw error;
    }
  }

  get<T>(endpoint: string, params?: Record<string, string>) {
    const query = params ? '?' + new URLSearchParams(params).toString() : '';
    return this.request<T>(`${endpoint}${query}`);
  }

  post<T>(endpoint: string, body?: unknown) {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  }
}

export const apiClient = new ApiClient();
export type { ApiResponse, ApiError, ApiClientConfig };
```

### 2.2 异步任务轮询Hook (`lib/hooks/use-async-task.ts`)

```typescript
// lib/hooks/use-async-task.ts
// Input: 启动函数 + 状态轮询端点 + 轮询间隔
// Output: { status, progress, result, error, start, cancel }
// Pos: 所有异步任务（分析/扫描/ETF）的统一管理

import { useState, useCallback, useRef, useEffect } from 'react';
import { apiClient } from '@/lib/api/client';

type TaskStatus = 'idle' | 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

interface AsyncTaskState<TResult> {
  taskId: string | null;
  status: TaskStatus;
  progress: number;        // 0-100
  result: TResult | null;
  error: string | null;
  currentStep: string;
}

interface UseAsyncTaskOptions {
  pollInterval?: number;    // 默认 2000ms
  maxRetries?: number;      // 轮询失败重试次数，默认 3
  onProgress?: (progress: number, step: string) => void;
  onComplete?: (result: unknown) => void;
  onError?: (error: string) => void;
}

function useAsyncTask<TParams, TResult>(
  startEndpoint: string,       // e.g. '/api/start_agent_analysis'
  statusEndpoint: string,      // e.g. '/api/agent_analysis_status'
  cancelEndpoint?: string,     // e.g. 可选取消端点
  options: UseAsyncTaskOptions = {}
) {
  const { pollInterval = 2000, maxRetries = 3, onProgress, onComplete, onError } = options;

  const [state, setState] = useState<AsyncTaskState<TResult>>({
    taskId: null, status: 'idle', progress: 0, result: null, error: null, currentStep: '',
  });

  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const retriesRef = useRef(0);

  // 清理轮询
  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  // 轮询状态
  const pollStatus = useCallback(async (taskId: string) => {
    try {
      const { data } = await apiClient.get<{
        id: string; status: TaskStatus; progress: number;
        result: TResult & { current_step?: string };
      }>(`${statusEndpoint}/${taskId}`);

      retriesRef.current = 0; // 成功则重置重试计数

      const currentStep = data.result?.current_step || '';
      setState(prev => ({
        ...prev,
        status: data.status,
        progress: data.progress,
        result: data.status === 'completed' ? data.result as TResult : prev.result,
        currentStep,
      }));

      onProgress?.(data.progress, currentStep);

      if (data.status === 'completed') {
        stopPolling();
        onComplete?.(data.result);
      } else if (data.status === 'failed' || data.status === 'cancelled') {
        stopPolling();
        const errMsg = data.status === 'failed' ? '任务执行失败' : '任务已取消';
        setState(prev => ({ ...prev, error: errMsg }));
        onError?.(errMsg);
      }
    } catch {
      retriesRef.current++;
      if (retriesRef.current >= maxRetries) {
        stopPolling();
        setState(prev => ({ ...prev, status: 'failed', error: '轮询超时，请刷新页面查看结果' }));
        onError?.('轮询超时');
      }
    }
  }, [statusEndpoint, stopPolling, maxRetries, onProgress, onComplete, onError]);

  // 启动任务
  const start = useCallback(async (params: TParams) => {
    stopPolling();
    setState({ taskId: null, status: 'pending', progress: 0, result: null, error: null, currentStep: '初始化中...' });

    try {
      const { data } = await apiClient.post<{ task_id: string }>(startEndpoint, params);
      const taskId = data.task_id;
      setState(prev => ({ ...prev, taskId }));
      retriesRef.current = 0;
      pollingRef.current = setInterval(() => pollStatus(taskId), pollInterval);
    } catch (err: unknown) {
      const errorMsg = (err as { error?: string })?.error || '启动任务失败';
      setState(prev => ({ ...prev, status: 'failed', error: errorMsg }));
      onError?.(errorMsg);
    }
  }, [startEndpoint, pollInterval, stopPolling, pollStatus, onError]);

  // 取消任务
  const cancel = useCallback(async () => {
    if (state.taskId && cancelEndpoint) {
      stopPolling();
      await apiClient.post(`${cancelEndpoint}/${state.taskId}`);
      setState(prev => ({ ...prev, status: 'cancelled' }));
    }
  }, [state.taskId, cancelEndpoint, stopPolling]);

  // 组件卸载时清理
  useEffect(() => stopPolling, [stopPolling]);

  return { ...state, start, cancel, isLoading: state.status === 'pending' || state.status === 'running' };
}

export { useAsyncTask };
export type { AsyncTaskState, UseAsyncTaskOptions, TaskStatus };
```

### 2.3 API模块拆分（按API.md分组）

| 模块文件 | 覆盖端点 | 对应API.md章节 |
|----------|----------|----------------|
| `api/analysis.ts` | start_agent_analysis, agent_analysis_status, agent_analysis_history, delete_agent_analysis, agent_pending_approvals, agent_submit_approval, active_tasks, start_stock_analysis, analysis_status, cancel_analysis, enhanced_analysis, start_etf_analysis, etf_analysis_status | Agent智能分析 + 股票分析 + ETF分析 |
| `api/stock.ts` | stock_data, analyze (POST) | 股票数据 |
| `api/market.ts` | start_market_scan, scan_status, cancel_scan, index_stocks, board_stocks, index_analysis | 市场扫描 + 指数/板块 |
| `api/fundamental.ts` | fundamental_analysis, capital_flow, north_flow_history, concept_fund_flow, individual_fund_flow_rank, individual_fund_flow, risk_analysis, portfolio_risk, scenario_predict | 基本面 + 资金流向 + 风险 + 情景预测 |
| `api/industry.ts` | industry_analysis, industry_fund_flow, industry_detail, industry_compare, sector_stocks | 行业分析 |
| `api/news.ts` | latest_news, history_analysis, search_us_stocks | 新闻与历史 |
| `api/qa.ts` | qa | 智能问答 |
| `api/mcp.ts` | mcp/tools, mcp/call | MCP工具 |

### 2.4 核心TypeScript类型定义 (`lib/api/types.ts`)

```typescript
// lib/api/types.ts — 与后端 API.md v2.3.0 严格对齐

// ===== 通用类型 =====
export type MarketType = 'A' | 'HK' | 'US';
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type ActionType = 'BUY' | 'SELL' | 'HOLD';

export interface AsyncTaskResponse {
  task_id: string;
  status: TaskStatus;
  message?: string;
}

export interface TaskStatusResponse<T = unknown> {
  id: string;
  status: TaskStatus;
  progress: number;        // 0-100
  result: T;
}

export interface ApiErrorResponse {
  error: string;
  path?: string;
  method?: string;
}

// ===== Agent分析类型 =====
export interface AgentAnalysisParams {
  stock_code: string;
  market_type?: MarketType;
  research_depth?: 1 | 2 | 3 | 4 | 5;
  selected_analysts?: string[];
  analysis_date?: string;
  enable_memory?: boolean;
  max_output_length?: number;
}

export interface AgentDecision {
  action: ActionType;
  reasoning: string;
  confidence: number;      // 0.0-1.0
  risk_score: number;       // 0.0-1.0
}

export interface AgentReport {
  score: number;
  ai_commentary: string;
  tool_calls?: unknown[];
  [key: string]: unknown;  // 各Agent特有字段
}

export interface InvestorOpinion {
  recommendation: ActionType;
  confidence: number;
  reasoning: string;
}

export interface InvestorConsensus {
  final_recommendation: ActionType;
  consensus_confidence: string;
  consensus_confidence_score: number;
  agreement_level: string;
  consensus_reasoning: string;
  key_agreements: string[];
  key_disagreements: string[];
  weight_analysis: string;
  ai_driven: boolean;
}

export interface ExecutionLogEntry {
  agent: string;
  status: 'success' | 'failed';
  mode: 'ai_agent' | 'fallback';
  tools_used: number;
}

export interface AgentAnalysisResult {
  decision: AgentDecision;
  final_state: {
    stock_code: string;
    company_name: string;
    technical_report: AgentReport;
    fundamental_report: AgentReport;
    capital_flow_report: AgentReport;
    sentiment_report: AgentReport;
    bull_case: string;
    bear_case: string;
    risk_assessment: AgentReport;
    investor_opinions: {
      buffett: InvestorOpinion;
      munger: InvestorOpinion;
      lynch: InvestorOpinion;
      damodaran: InvestorOpinion;
    };
    investor_consensus: InvestorConsensus;
    router_decision: 'normal' | 'fast_fail';
    execution_log: ExecutionLogEntry[];
    errors: string[];
  };
  current_step: string;
  execution_log: ExecutionLogEntry[];
  errors: string[];
}

// ===== 股票数据类型 =====
export interface StockDataPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  sma20: number;
  sma50: number;
  ema12: number;
  ema26: number;
  macd: number;
  signal: number;
  histogram: number;
  rsi14: number;
  atr14: number;
  bb_upper: number;
  bb_middle: number;
  bb_lower: number;
}

export interface StockAnalysisResult {
  stock_code: string;
  stock_name: string;
  score: number;
  rating: string;
}

// ===== 市场扫描类型 =====
export interface MarketScanParams {
  stock_list: string[];
  min_score?: number;
  market_type?: MarketType;
}

// ===== 基本面类型 =====
export interface FundamentalData {
  fundamental_score: number;
  pe_ratio: number;
  pb_ratio: number;
  roe: number;
  debt_ratio: number;
  revenue_growth: number;
  profit_growth: number;
}

// ===== 情景预测类型 =====
export interface ScenarioResult {
  optimistic: ScenarioDetail;
  baseline: ScenarioDetail;
  pessimistic: ScenarioDetail;
}

export interface ScenarioDetail {
  probability: number;
  target_price: number;
  key_assumptions: string[];
}

// ===== 投资组合类型 =====
export interface PortfolioItem {
  stock_code: string;
  weight: number;
}

export interface PortfolioRiskResult {
  total_risk: number;
  var_95: number;
  correlation_matrix: number[][];
  [key: string]: unknown;
}
```

---

## 3. 页面迁移映射表

### 3.1 路由映射

| # | 原始模板(Jinja2) | Next.js路由 | URL路径 | 渲染模式 | 核心组件 | 依赖API端点 |
|---|------------------|-------------|---------|----------|----------|-------------|
| 1 | `index.html` | `app/page.tsx` | `/` | SSG+CSR | TopNavbar, StockSearch, StockCard, MarketOverview | stock_data, latest_news, index_stocks |
| 2 | `dashboard.html` | `app/dashboard/page.tsx` | `/dashboard` | CSR | DashboardGrid, StockCard, RadarChart, LineChart, ActiveTaskTracker | active_tasks, stock_data, latest_news |
| 3 | `stock_detail.html` | `app/stock/[code]/page.tsx` | `/stock/:code` | CSR | CandlestickChart, VolumeChart, IndicatorOverlay, StockDetailHeader, FundamentalCard, CapitalFlowPanel | stock_data, fundamental_analysis, capital_flow, individual_fund_flow |
| 4 | `agent_analysis.html` | `app/analysis/page.tsx` | `/analysis` | CSR | StockSearch, AnalysisDepthSelector, AgentProgress, DecisionPanel, InvestorOpinions, ConsensusPanel, BullBearDebate, ExecutionLog | start_agent_analysis, agent_analysis_status, agent_analysis_history |
| 5 | `market_scan.html` | `app/market-scan/page.tsx` | `/market-scan` | CSR | StockTable, BoardSelector, AsyncTaskTracker, BarChart | start_market_scan, scan_status, index_stocks, board_stocks |
| 6 | `portfolio.html` | `app/portfolio/page.tsx` | `/portfolio` | CSR | PieChart, StockTable, RiskGauge, PortfolioEditor | portfolio_risk, stock_data |
| 7 | `fundamental.html` | `app/fundamental/page.tsx` | `/fundamental` | CSR | StockSearch, FundamentalCard, RadarChart, BarChart | fundamental_analysis |
| 8 | `capital_flow.html` | `app/capital-flow/page.tsx` | `/capital-flow` | CSR | FundFlowChart, StockSearch, HeatmapChart, StockTable | capital_flow, north_flow_history, concept_fund_flow, individual_fund_flow_rank |
| 9 | `scenario_predict.html` | `app/scenario/page.tsx` | `/scenario` | CSR | ScenarioPanel, ScenarioChart, StockSearch | scenario_predict |
| 10 | `risk_monitor.html` | `app/risk/page.tsx` | `/risk` | CSR | RiskGauge, RadarChart, StockTable | risk_analysis, portfolio_risk |
| 11 | `qa.html` | `app/qa/page.tsx` | `/qa` | CSR | ChatInterface, StockSearch, MessageBubble | qa |
| 12 | `industry_analysis.html` | `app/industry/page.tsx` | `/industry` | CSR | HeatmapChart, BarChart, StockTable, IndustrySelector | industry_analysis, industry_fund_flow, industry_detail, industry_compare, sector_stocks |
| 13 | `etf_analysis.html` | `app/etf/page.tsx` | `/etf` | CSR | StockSearch, AsyncTaskTracker, RadarChart, BarChart | start_etf_analysis, etf_analysis_status |
| 14 | `layout.html` | `app/layout.tsx` | (全局) | SSG | AppSidebar, TopNavbar, ThemeToggle, MarketColorToggle, Footer | - |
| 15 | `error.html` | `app/error.tsx` + `app/not-found.tsx` | (错误) | SSG | ErrorBoundary, EmptyState | - |

### 3.2 渲染策略说明

| 模式 | 适用页面 | 理由 |
|------|----------|------|
| SSG (静态生成) | 首页框架、布局、错误页 | 内容固定，首屏极速 |
| CSR (客户端渲染) | 仪表盘、股票详情、所有分析页 | 数据实时性要求高，依赖用户交互 |
| Streaming SSR | 首页新闻区域（未来考虑） | 个性化内容，但非MVP必须 |

### 3.3 迁移优先级排序

| 优先级 | 页面 | 理由 |
|--------|------|------|
| P0 | layout, 首页, stock_detail, dashboard | 核心框架 + 使用频率最高 |
| P1 | agent_analysis, market_scan | 核心业务功能 |
| P2 | fundamental, capital_flow, industry | 分析功能组 |
| P3 | portfolio, risk, scenario, qa, etf | 辅助功能 |
| P4 | error, not-found | 错误兜底 |

---

## 4. 组件设计

### 4.1 核心组件清单与层级

```
App (layout.tsx)
├── AppSidebar              # 侧边栏导航（可折叠）
├── TopNavbar               # 顶部栏
│   ├── StockSearch         # 全局搜索（A/HK/US）
│   ├── ThemeToggle         # 亮/暗主题
│   └── MarketColorToggle   # 涨跌色模式
└── PageContent             # 页面内容区
    └── [各页面组件树]
```

### 4.2 图表组件 Props 接口

```typescript
// CandlestickChart — K线图（TradingView Lightweight Charts）
interface CandlestickChartProps {
  data: StockDataPoint[];            // OHLCV数据
  height?: number;                    // 图表高度，默认400
  showVolume?: boolean;               // 是否显示成交量，默认true
  indicators?: Array<'sma20' | 'sma50' | 'ema12' | 'ema26' | 'bb'>;  // 叠加指标
  onCrosshairMove?: (point: { time: string; price: number }) => void;
  colorMode?: 'cn' | 'intl';         // 涨跌色模式
  className?: string;
}

// RadarChart — 雷达图（ECharts）
interface RadarChartProps {
  dimensions: string[];               // 维度名称
  values: number[];                    // 维度得分
  maxValues?: number[];                // 各维度最大值
  height?: number;
  title?: string;
  className?: string;
}

// FundFlowChart — 资金流向图（ECharts）
interface FundFlowChartProps {
  data: {
    date: string;
    mainForce: number;     // 主力
    retail: number;        // 散户
    northbound?: number;   // 北向
  }[];
  height?: number;
  className?: string;
}

// ScenarioChart — 情景扇形图（ECharts）
interface ScenarioChartProps {
  currentPrice: number;
  scenarios: ScenarioResult;
  days: number;
  height?: number;
  className?: string;
}
```

### 4.3 业务组件 Props 接口

```typescript
// AgentProgress — Agent分析进度
interface AgentProgressProps {
  progress: number;                    // 0-100
  currentStep: string;
  status: TaskStatus;
  executionLog?: ExecutionLogEntry[];
}

// DecisionPanel — 投资决策面板
interface DecisionPanelProps {
  decision: AgentDecision;
  companyName: string;
  stockCode: string;
}

// InvestorOpinions — 投资大师意见
interface InvestorOpinionsProps {
  opinions: Record<string, InvestorOpinion>;  // buffett/munger/lynch/damodaran
}

// ConsensusPanel — AI共识面板
interface ConsensusPanelProps {
  consensus: InvestorConsensus;
}

// BullBearDebate — 多空辩论
interface BullBearDebateProps {
  bullCase: string;
  bearCase: string;
}

// RiskGauge — 风险仪表盘
interface RiskGaugeProps {
  riskScore: number;                   // 0-100
  riskLevel: string;
  details?: { label: string; value: number }[];
}

// StockSearch — 股票搜索
interface StockSearchProps {
  onSelect: (code: string, marketType: MarketType) => void;
  placeholder?: string;
  defaultMarket?: MarketType;
  showMarketSwitch?: boolean;
}

// StockCard — 股票卡片
interface StockCardProps {
  code: string;
  name: string;
  price: number;
  change: number;               // 涨跌额
  changePercent: number;         // 涨跌幅
  score?: number;
  onClick?: () => void;
}

// AsyncTaskTracker — 异步任务追踪器
interface AsyncTaskTrackerProps {
  taskId: string | null;
  status: TaskStatus;
  progress: number;
  currentStep: string;
  onCancel?: () => void;
}

// AnalysisDepthSelector — 研究深度选择器
interface AnalysisDepthSelectorProps {
  value: 1 | 2 | 3 | 4 | 5;
  onChange: (depth: 1 | 2 | 3 | 4 | 5) => void;
  depthDescriptions: Record<number, string>;  // 各深度对应Agent链说明
}
```

### 4.4 组件设计原则

1. **单一职责**: 每个组件只做一件事，展示组件不包含API调用
2. **组合优于继承**: 通过Props组合小组件构建页面
3. **数据下行/事件上行**: 数据通过Props传入，交互通过回调上报
4. **受控优先**: 表单和选择器使用受控模式
5. **懒加载图表**: 图表组件使用`next/dynamic`懒加载，避免SSR报错

```typescript
// 图表懒加载示例
import dynamic from 'next/dynamic';

const CandlestickChart = dynamic(
  () => import('@/components/charts/candlestick-chart'),
  { ssr: false, loading: () => <ChartSkeleton /> }
);
```

---

## 5. 状态管理架构

### 5.1 状态分层策略

| 层级 | 工具 | 管理内容 | 持久化 |
|------|------|----------|--------|
| 全局应用状态 | Zustand | 主题、涨跌色模式、侧边栏折叠、用户偏好 | localStorage |
| 投资组合状态 | Zustand | 自选股列表、持仓数据、组合权重 | localStorage |
| 实时数据原子 | Jotai | 当前查看股票的实时价格、分析进度 | 无（内存） |
| 异步任务状态 | Jotai | 各任务ID/状态/进度 | 无（内存） |
| 服务端缓存 | fetch cache / SWR模式 | API响应缓存（5分钟） | 无 |
| URL状态 | Next.js searchParams | 筛选条件、分页、排序 | URL |

### 5.2 Zustand Store 设计

```typescript
// lib/stores/app-store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AppState {
  // 主题
  theme: 'light' | 'dark' | 'system';
  setTheme: (theme: 'light' | 'dark' | 'system') => void;

  // 涨跌色模式（中国红涨绿跌 / 国际绿涨红跌）
  colorMode: 'cn' | 'intl';
  setColorMode: (mode: 'cn' | 'intl') => void;

  // 侧边栏
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;

  // 默认市场
  defaultMarket: MarketType;
  setDefaultMarket: (market: MarketType) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      theme: 'system',
      setTheme: (theme) => set({ theme }),

      colorMode: 'cn',
      setColorMode: (colorMode) => set({ colorMode }),

      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

      defaultMarket: 'A',
      setDefaultMarket: (defaultMarket) => set({ defaultMarket }),
    }),
    { name: 'stockanal-app-settings' }
  )
);

// lib/stores/portfolio-store.ts
interface PortfolioState {
  // 自选股
  watchlist: string[];                 // 股票代码列表
  addToWatchlist: (code: string) => void;
  removeFromWatchlist: (code: string) => void;

  // 持仓组合
  holdings: PortfolioItem[];
  updateHoldings: (items: PortfolioItem[]) => void;
}

export const usePortfolioStore = create<PortfolioState>()(
  persist(
    (set) => ({
      watchlist: [],
      addToWatchlist: (code) => set((s) => ({
        watchlist: s.watchlist.includes(code) ? s.watchlist : [...s.watchlist, code],
      })),
      removeFromWatchlist: (code) => set((s) => ({
        watchlist: s.watchlist.filter((c) => c !== code),
      })),

      holdings: [],
      updateHoldings: (items) => set({ holdings: items }),
    }),
    { name: 'stockanal-portfolio' }
  )
);
```

### 5.3 Jotai Atoms 设计

```typescript
// lib/stores/price-atoms.ts
import { atom } from 'jotai';

// 当前查看的股票代码
export const currentStockCodeAtom = atom<string>('');

// 实时价格数据（高频更新，Jotai原子避免全局重渲染）
export const stockPriceAtom = atom<{
  code: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  timestamp: string;
} | null>(null);

// lib/stores/task-atoms.ts
import { atom } from 'jotai';

// 当前活跃任务映射（taskId → 状态）
export const activeTasksAtom = atom<Map<string, {
  type: 'agent' | 'scan' | 'stock' | 'etf';
  stockCode: string;
  status: TaskStatus;
  progress: number;
}>>(new Map());

// lib/stores/analysis-atoms.ts
// Agent分析进度（独立原子，仅订阅者重渲染）
export const agentProgressAtom = atom<{
  taskId: string;
  progress: number;
  currentStep: string;
  status: TaskStatus;
}>({ taskId: '', progress: 0, currentStep: '', status: 'idle' });
```

### 5.4 数据流图

```
                          ┌─────────────┐
                          │  Flask API   │
                          │  :8888       │
                          └──────┬───────┘
                                 │ HTTP/JSON
                          ┌──────▼───────┐
                          │  API Client  │
                          │  (fetch)     │
                          └──────┬───────┘
                    ┌────────────┼────────────┐
                    │            │            │
              ┌─────▼─────┐ ┌───▼────┐ ┌─────▼─────┐
              │  Hooks     │ │ Hooks  │ │  Hooks    │
              │(useStock)  │ │(useTask)│ │(useWS)   │
              └─────┬─────┘ └───┬────┘ └─────┬─────┘
                    │           │             │
         ┌──────────┤     ┌────▼─────┐  ┌────▼─────┐
         │          │     │  Jotai   │  │  Jotai   │
    ┌────▼────┐ ┌───▼───┐│  Atoms   │  │  Price   │
    │ Zustand │ │ React ││ (tasks)  │  │  Atoms   │
    │ (global)│ │ State ││          │  │          │
    └────┬────┘ └───┬───┘└────┬─────┘  └────┬─────┘
         │          │         │              │
         └──────────┴─────────┴──────────────┘
                          │
                   ┌──────▼──────┐
                   │  Components │
                   │  (UI层)     │
                   └─────────────┘
```

---

## 6. 实时通信设计

### 6.1 通信方案选择

| 场景 | 方案 | 理由 |
|------|------|------|
| Agent分析进度 | HTTP轮询 (现有方案) | 后端已实现，进度更新频率低（1-3秒），无需WebSocket |
| 实时股价推送 | SSE (Server-Sent Events) | 单向推送、自动重连、HTTP兼容、实现成本低 |
| 交互式问答 | SSE 流式响应 | LLM生成文本适合流式 |
| 多任务状态同步 | WebSocket（未来） | 当多用户/多任务并发时升级 |

### 6.2 SSE 连接管理 (`lib/hooks/use-sse.ts`)

```typescript
// lib/hooks/use-sse.ts
// 用于实时股价推送和问答流式响应

interface UseSSEOptions<T> {
  url: string;
  onMessage: (data: T) => void;
  onError?: (error: Event) => void;
  enabled?: boolean;
  reconnectInterval?: number;  // 默认 3000ms
  maxReconnectAttempts?: number;  // 默认 5
}

function useSSE<T>(options: UseSSEOptions<T>) {
  // 核心逻辑：
  // 1. 创建 EventSource 连接
  // 2. 解析 JSON 消息并调用 onMessage
  // 3. 错误时自动重连（指数退避）
  // 4. 超过最大重连次数则停止
  // 5. 组件卸载时关闭连接
  // 6. enabled=false 时不连接
}
```

### 6.3 重连策略

```
连接断开 → 等待 3s → 重连(1) → 等待 6s → 重连(2) → 等待 12s → 重连(3) → ... → 重连(5) → 停止并通知用户
```

- 使用指数退避: `delay = baseDelay * 2^(attempt-1)`，上限 30 秒
- 页面可见性变化时(`visibilitychange`)暂停/恢复连接
- 网络恢复时(`online`事件)立即重连

### 6.4 消息协议（SSE推送，需后端新增）

```
event: price_update
data: {"code":"600519","price":1688.50,"change":12.30,"change_pct":0.73,"volume":18234,"ts":"2026-03-25 14:30:15"}

event: task_progress
data: {"task_id":"agent_001","progress":40,"step":"情绪分析师完成"}

event: heartbeat
data: {"ts":"2026-03-25 14:30:00"}
```

### 6.5 MVP阶段通信方案

MVP阶段优先使用 **HTTP轮询**（后端已全面支持），SSE作为第二阶段优化：

| 阶段 | 方案 | 实现成本 |
|------|------|----------|
| MVP | HTTP轮询（useAsyncTask Hook） | 零后端改动 |
| Phase 2 | SSE 实时股价 + 流式问答 | 后端新增2个SSE端点 |
| Phase 3 | WebSocket 多任务同步 | 后端新增WebSocket支持 |

---

## 7. 部署架构

### 7.1 整体架构图

```
                    ┌─────────────────────────────────────────┐
                    │              Docker Host                 │
                    │                                         │
  用户浏览器 ──────►│  ┌─────────┐    ┌──────────┐            │
        :80/:443    │  │  Nginx  │    │ Next.js  │            │
                    │  │  :80    ├───►│ :3000    │            │
                    │  │         │    │(frontend)│            │
                    │  │  /api/* ├──┐ └──────────┘            │
                    │  │  /static├┐ │                         │
                    │  └─────────┘│ │ ┌──────────┐            │
                    │             │ └►│  Flask   │            │
                    │             │   │  :8888   │            │
                    │             │   │(backend) │            │
                    │             │   └────┬─────┘            │
                    │             │        │                   │
                    │             │   ┌────▼─────┐            │
                    │             │   │  Redis   │ (可选缓存)  │
                    │             │   │  :6379   │            │
                    │             │   └──────────┘            │
                    └─────────────────────────────────────────┘
```

### 7.2 Docker Compose 配置

```yaml
# docker-compose.yml
version: '3.8'

services:
  nginx:
    image: nginx:1.27-alpine
    ports:
      - "${EXPOSE_PORT:-80}:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
    depends_on:
      - frontend
      - backend
    restart: unless-stopped
    networks:
      - stockanal-net

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      - NEXT_PUBLIC_API_URL=http://nginx:80
    expose:
      - "3000"
    restart: unless-stopped
    networks:
      - stockanal-net

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - FLASK_ENV=production
      - ALLOWED_ORIGINS=http://localhost,http://localhost:80,http://nginx
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_BASE_URL=${OPENAI_BASE_URL}
      - OPENAI_MODEL=${OPENAI_MODEL}
    expose:
      - "8888"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    networks:
      - stockanal-net

  redis:
    image: redis:7-alpine
    expose:
      - "6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped
    networks:
      - stockanal-net
    profiles:
      - with-redis   # 可选启用: docker compose --profile with-redis up

networks:
  stockanal-net:
    driver: bridge

volumes:
  redis-data:
```

### 7.3 Nginx 配置

```nginx
# nginx/conf.d/default.conf

upstream frontend {
    server frontend:3000;
}

upstream backend {
    server backend:8888;
}

server {
    listen 80;
    server_name _;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 压缩
    gzip on;
    gzip_types text/plain application/json application/javascript text/css;
    gzip_min_length 1024;

    # API请求 → Flask后端
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 长连接支持（Agent分析可能耗时较长）
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;

        # SSE支持
        proxy_buffering off;
        proxy_cache off;
    }

    # 兼容旧路由 /analyze
    location /analyze {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 搜索API（旧路由无/api前缀）
    location /search_us_stocks {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Swagger文档
    location /api/docs {
        proxy_pass http://backend;
    }

    # 后端静态文件（swagger.json等）
    location /static/ {
        proxy_pass http://backend;
    }

    # SSE端点（如果后端支持）
    location /api/sse/ {
        proxy_pass http://backend;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }

    # 所有其他请求 → Next.js前端
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Next.js HMR WebSocket（开发环境）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Next.js静态资源（长缓存）
    location /_next/static/ {
        proxy_pass http://frontend;
        expires 365d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 7.4 前端 Dockerfile（多阶段构建）

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS base

# 依赖安装阶段
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

# 构建阶段
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# 运行阶段（最小镜像）
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
```

### 7.5 Next.js 配置

```typescript
// frontend/next.config.ts
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',  // Docker优化，生成独立运行包

  // 开发环境API代理（绕过CORS，开发时直连后端）
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.BACKEND_URL || 'http://localhost:8888'}/api/:path*`,
      },
      {
        source: '/analyze',
        destination: `${process.env.BACKEND_URL || 'http://localhost:8888'}/analyze`,
      },
      {
        source: '/search_us_stocks',
        destination: `${process.env.BACKEND_URL || 'http://localhost:8888'}/search_us_stocks`,
      },
    ];
  },

  // 图片优化配置
  images: {
    unoptimized: true,  // 无外部图片CDN时关闭
  },
};

export default nextConfig;
```

### 7.6 环境变量

```bash
# frontend/.env.local（开发环境）
NEXT_PUBLIC_API_URL=http://localhost:8888
BACKEND_URL=http://localhost:8888

# frontend/.env.production（生产环境，Docker内）
NEXT_PUBLIC_API_URL=
# 留空，生产环境通过Nginx反代，前端请求同源，无需指定API地址

# 后端 .env 需新增
ALLOWED_ORIGINS=http://localhost,http://localhost:3000,http://localhost:80
```

---

## 8. 后端需要的改动清单

### 8.1 CORS配置更新

**当前状态**: `web_server.py:88` 已有CORS配置，通过 `ALLOWED_ORIGINS` 环境变量控制。

**需要改动**:

| 项目 | 当前 | 目标 | 优先级 |
|------|------|------|--------|
| ALLOWED_ORIGINS默认值 | `localhost:8888` | 增加 `localhost:3000`（开发）和生产域名 | P0 |
| CORS路径 | 仅 `/api/*` | 增加 `/analyze`, `/search_us_stocks` | P0 |
| CORS Headers | `Content-Type, X-API-Key` | 无需额外改动 | - |
| Credentials | 未启用 | 保持不启用（无cookie认证） | - |

**改动代码**:
```python
# web_server.py 第87-88行
allowed_origins = os.getenv(
    'ALLOWED_ORIGINS',
    'http://localhost:8888,http://127.0.0.1:8888,http://localhost:3000,http://127.0.0.1:3000,http://localhost'
).split(',')

CORS(app, resources={
    r"/api/*": {"origins": allowed_origins, "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type", "X-API-Key"]},
    r"/analyze": {"origins": allowed_origins, "methods": ["POST", "OPTIONS"]},
    r"/search_us_stocks": {"origins": allowed_origins, "methods": ["GET", "OPTIONS"]},
})
```

### 8.2 SSE端点（Phase 2 新增，MVP不需要）

| 端点 | 功能 | 优先级 |
|------|------|--------|
| `GET /api/sse/price?codes=600519,000001` | 实时股价推送（1秒间隔） | P2 |
| `POST /api/sse/qa` | 流式问答响应（LLM token流） | P2 |
| `GET /api/sse/task/<task_id>` | 任务进度推送（替代轮询） | P3 |

### 8.3 API响应格式标准化

**当前问题与建议**:

| # | 问题 | 现状 | 建议 | 优先级 |
|---|------|------|------|--------|
| 1 | 错误响应不统一 | 部分返回 `{"error": "..."}` 部分直接抛异常 | 统一为 `{"error": string, "code"?: string}` | P1 |
| 2 | 旧路由无 `/api` 前缀 | `/analyze`, `/search_us_stocks` | 新增 `/api/analyze`, `/api/search_us_stocks` 别名路由，保留旧路由兼容 | P1 |
| 3 | 分页支持缺失 | industry_analysis等返回全量 | 添加 `page`/`page_size`/`total` 字段 | P2 |
| 4 | 响应时间戳缺失 | 无 | 所有响应添加 `"timestamp": "2026-03-25 14:30:00"` | P3 |
| 5 | 批量删除确认 | delete_agent_analysis无二次确认 | 前端实现确认弹窗即可，后端无需改 | - |

### 8.4 后端改动实施计划

| 阶段 | 改动 | 工作量 | 风险 |
|------|------|--------|------|
| MVP (与前端同步) | CORS更新 + `/api`别名路由 | 0.5天 | 低 |
| Phase 2 | SSE端点 + 错误响应标准化 | 2天 | 中（需测试兼容性） |
| Phase 3 | 分页支持 + 响应时间戳 | 1天 | 低 |

### 8.5 无需改动的部分

以下后端能力已满足前端需求，无需调整：

- 异步任务模式（start → poll → cancel）已完善
- Agent分析全链路（Function Calling + 进度上报）已稳定
- 股票代码校验已实现（`validate_stock_code`函数）
- 缓存机制已配置（SimpleCache / Redis可选）
- Swagger文档已集成

---

## 附录A: Tailwind 金融色彩系统

```css
/* frontend/src/styles/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* 基础色 */
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;

    /* 中国模式涨跌色 */
    --price-up: 0 72% 51%;          /* 红涨 */
    --price-down: 142 72% 29%;      /* 绿跌 */
    --price-flat: 0 0% 45%;         /* 灰平 */

    /* 评分色阶 */
    --score-excellent: 142 72% 29%;  /* ≥80 */
    --score-good: 47 100% 50%;       /* 60-79 */
    --score-warning: 25 95% 53%;     /* 40-59 */
    --score-danger: 0 72% 51%;       /* <40 */
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
  }

  /* 国际模式涨跌色 */
  [data-color-mode="intl"] {
    --price-up: 142 72% 29%;        /* 绿涨 */
    --price-down: 0 72% 51%;        /* 红跌 */
  }
}
```

## 附录B: 关键文件尺寸预估

| 组件/模块 | 预估文件数 | 预估代码行数 |
|-----------|-----------|-------------|
| `app/` 页面 | 15 | ~3000 |
| `components/ui/` (shadcn) | 16 | ~1600 (CLI生成) |
| `components/charts/` | 11 | ~2200 |
| `components/stock/` | 7 | ~1000 |
| `components/analysis/` | 12 | ~2400 |
| `components/layout/` | 6 | ~800 |
| `components/common/` | 7 | ~700 |
| `lib/api/` | 10 | ~1200 |
| `lib/hooks/` | 8 | ~800 |
| `lib/stores/` | 5 | ~400 |
| `lib/utils/` | 5 | ~500 |
| `lib/types/` | 4 | ~400 |
| 配置文件 | 6 | ~200 |
| **总计** | **~112** | **~15,200** |

---

此项目的任何功能、架构更新，必须在结束后同步更新相关文档。这是我们契约的一部分。
