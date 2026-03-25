# AI-Native 前端架构设计文档

```
Input: AI-native产品战略 + 后端Multi-Agent API + 技术栈共识
Output: Chat+Artifacts范式的完整前端架构方案（项目结构/AI集成/Artifacts注册/Agent可视化/对话系统/状态管理/部署）
Pos: docs/FRONTEND_ARCHITECTURE.md - AI-native前端架构唯一蓝图，指导全部前端开发实施
```

> 一旦我被修改，请更新所属文件夹的 README.md。

---

**版本**: v2.0.0
**范式**: AI-Native "Chat + Artifacts"
**后端版本**: Flask v2.3.0 (Multi-Agent, 13 Agents + MCP Tools)
**技术栈**: Next.js 15 + React 19 + TypeScript + Vercel AI SDK 6 + assistant-ui + TradingView LWC + Recharts + shadcn/ui + Tailwind CSS + Zustand + Jotai + AG-UI协议

---

## 目录

- [1. 产品形态概述](#1-产品形态概述)
- [2. 项目结构设计（AI-Native版）](#2-项目结构设计ai-native版)
- [3. AI集成架构（核心）](#3-ai集成架构核心)
- [4. Artifacts组件注册表](#4-artifacts组件注册表)
- [5. Agent可视化设计](#5-agent可视化设计)
- [6. 对话系统设计](#6-对话系统设计)
- [7. 状态管理（三层架构）](#7-状态管理三层架构)
- [8. 后端适配](#8-后端适配)
- [9. 部署架构](#9-部署架构)
- [10. 迁移策略](#10-迁移策略)

---

## 1. 产品形态概述

### 1.1 核心理念

抛弃传统"15个页面 + 表单查询"的Web应用范式，转向 **AI-Native金融对话产品**。用户通过自然语言与AI分析师对话，AI实时生成可交互的金融分析组件（Artifacts），形成"对话驱动分析"的全新体验。

### 1.2 界面布局

```
┌─────────────────────────────────────────────────────────────┐
│  NavBar: Logo · 首页 · 投资组合 · 自选股 · 设置       用户  │
├──────────────────────┬──────────────────────────────────────┤
│                      │                                      │
│   AI 对话面板        │       Artifacts 工作区                │
│   (~35% 宽度)        │       (~65% 宽度)                     │
│                      │                                      │
│  ┌────────────────┐  │  ┌────────────────────────────────┐  │
│  │ Agent思考过程   │  │  │  AI实时生成的可交互组件         │  │
│  │ (折叠/展开)     │  │  │                                │  │
│  ├────────────────┤  │  │  · K线图                       │  │
│  │ 工具调用卡片    │  │  │  · 技术指标面板                │  │
│  │ (Timeline)      │  │  │  · 基本面评分卡                │  │
│  ├────────────────┤  │  │  · 资金流向图                  │  │
│  │ 流式文本回复    │  │  │  · 风险雷达图                  │  │
│  │                │  │  │  · 投资者观点对比              │  │
│  ├────────────────┤  │  │                                │  │
│  │ 预判性提问      │  │  │  [钉住] [全屏] [导出]          │  │
│  │ · 深入技术面?   │  │  └────────────────────────────────┘  │
│  │ · 对比同行业?   │  │                                      │
│  │ · 查看资金流?   │  │  ┌────────────────────────────────┐  │
│  ├────────────────┤  │  │  投资者人格观点对比             │  │
│  │ 💬 输入框      │  │  │  巴菲特 | 芒格 | 林奇 | 达摩达兰│  │
│  └────────────────┘  │  └────────────────────────────────┘  │
│                      │                                      │
└──────────────────────┴──────────────────────────────────────┘
```

- **左侧对话面板**：基于 assistant-ui 的 headless Chat UI，承载全部用户交互
- **右侧Artifacts工作区**：AI根据工具调用结果实时渲染React组件，用户可交互、钉住、全屏、导出
- **锚点视图**：仅保留首页（市场概览）、投资组合、自选股 3个结构化页面

---

## 2. 项目结构设计（AI-Native版）

```
frontend/
├── src/
│   ├── app/                              # Next.js 15 App Router（精简路由）
│   │   ├── page.tsx                      # 首页：AI对话 + 市场概览
│   │   ├── layout.tsx                    # 根布局（NavBar + 对话/Artifacts双栏壳）
│   │   ├── chat/
│   │   │   └── page.tsx                  # 核心：AI分析对话页（全屏对话模式）
│   │   ├── portfolio/
│   │   │   └── page.tsx                  # 锚点：投资组合仪表盘
│   │   ├── watchlist/
│   │   │   └── page.tsx                  # 锚点：自选股看板
│   │   ├── settings/
│   │   │   └── page.tsx                  # 设置（API密钥/偏好/主题）
│   │   ├── error.tsx                     # 全局错误边界
│   │   ├── loading.tsx                   # 全局加载态
│   │   ├── not-found.tsx                 # 404
│   │   └── globals.css                   # 全局样式
│   │
│   ├── components/
│   │   ├── chat/                         # 对话组件（基于assistant-ui）
│   │   │   ├── chat-panel.tsx            # 对话主面板容器
│   │   │   ├── message-list.tsx          # 消息列表（流式渲染）
│   │   │   ├── message-bubble.tsx        # 单条消息气泡
│   │   │   ├── chat-input.tsx            # 输入框（支持快捷命令）
│   │   │   ├── suggested-questions.tsx   # 预判性提问建议
│   │   │   ├── stream-markdown.tsx       # Streamdown流式Markdown渲染器
│   │   │   └── command-palette.tsx       # 快捷命令面板
│   │   │
│   │   ├── artifacts/                    # Artifacts组件（AI生成的可交互组件）
│   │   │   ├── artifact-workspace.tsx    # Artifacts工作区容器
│   │   │   ├── artifact-card.tsx         # 单个Artifact卡片（钉住/全屏/导出）
│   │   │   ├── artifact-registry.ts     # 组件注册表（工具名→React组件映射）
│   │   │   ├── candlestick-chart.tsx     # K线图（TradingView LWC）
│   │   │   ├── technical-analysis-panel.tsx  # 技术指标面板
│   │   │   ├── fundamental-scorecard.tsx     # 基本面评分卡
│   │   │   ├── capital-flow-chart.tsx        # 资金流向图（Recharts）
│   │   │   ├── news-feed.tsx                 # 新闻资讯列表
│   │   │   ├── risk-radar-chart.tsx          # 风险雷达图（Recharts）
│   │   │   ├── web-search-results.tsx        # 网络搜索结果
│   │   │   └── investor-personas.tsx         # 投资者人格观点对比卡片
│   │   │
│   │   ├── agent/                        # Agent可视化组件
│   │   │   ├── agent-progress-panel.tsx  # Multi-Agent进度面板
│   │   │   ├── agent-status-badge.tsx    # 单Agent状态徽章
│   │   │   ├── tool-call-timeline.tsx    # 工具调用Timeline
│   │   │   ├── tool-call-card.tsx        # 单次工具调用卡片
│   │   │   ├── thinking-chain.tsx        # 思考链展示（折叠/展开）
│   │   │   └── agent-log-drawer.tsx      # Agent日志抽屉
│   │   │
│   │   ├── charts/                       # 通用图表组件
│   │   │   ├── base-candlestick.tsx      # TradingView LWC K线基础封装
│   │   │   ├── base-line-chart.tsx       # Recharts 折线图
│   │   │   ├── base-bar-chart.tsx        # Recharts 柱状图
│   │   │   ├── base-radar-chart.tsx      # Recharts 雷达图
│   │   │   ├── base-pie-chart.tsx        # Recharts 饼图
│   │   │   └── chart-container.tsx       # 图表容器（响应式 + 加载态）
│   │   │
│   │   ├── ui/                           # shadcn/ui 基础组件（CLI安装）
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── input.tsx
│   │   │   ├── select.tsx
│   │   │   ├── skeleton.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── progress.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── toast.tsx
│   │   │   ├── tooltip.tsx
│   │   │   ├── sheet.tsx
│   │   │   ├── scroll-area.tsx
│   │   │   ├── collapsible.tsx
│   │   │   └── separator.tsx
│   │   │
│   │   └── layout/                       # 布局组件
│   │       ├── navbar.tsx                # 顶部导航栏
│   │       ├── split-layout.tsx          # 对话+Artifacts双栏布局
│   │       ├── resizable-panel.tsx       # 可拖拽调整面板宽度
│   │       └── mobile-drawer.tsx         # 移动端抽屉布局
│   │
│   ├── lib/
│   │   ├── ai/                           # AI SDK集成（核心）
│   │   │   ├── provider.tsx              # AI Runtime Provider配置
│   │   │   ├── use-stock-chat.ts         # useChat封装（股票分析专用hook）
│   │   │   ├── stream-ui-renderer.tsx    # streamUI渲染器
│   │   │   ├── tool-registry.ts          # 工具注册表（MCP工具→UI组件映射）
│   │   │   ├── streamdown-config.ts      # Streamdown流式Markdown配置
│   │   │   └── ag-ui-adapter.ts          # AG-UI协议适配器
│   │   │
│   │   ├── api/                          # 后端API客户端
│   │   │   ├── client.ts                 # Axios/Fetch基础客户端
│   │   │   ├── stock-api.ts              # 股票数据API
│   │   │   ├── analysis-api.ts           # 分析服务API
│   │   │   ├── chat-api.ts              # AI对话SSE API
│   │   │   └── types.ts                  # API响应类型定义
│   │   │
│   │   ├── stores/                       # 状态管理
│   │   │   ├── chat-store.ts             # 对话状态（Zustand）
│   │   │   ├── agent-store.ts            # Agent状态（Zustand）
│   │   │   ├── artifact-store.ts         # Artifacts状态（Zustand）
│   │   │   └── atoms.ts                  # 原子状态（Jotai）- UI偏好/主题
│   │   │
│   │   ├── types/                        # TypeScript类型定义
│   │   │   ├── chat.ts                   # 对话相关类型
│   │   │   ├── agent.ts                  # Agent相关类型
│   │   │   ├── artifact.ts               # Artifact相关类型
│   │   │   ├── stock.ts                  # 股票数据类型
│   │   │   └── tool-call.ts              # 工具调用类型
│   │   │
│   │   └── utils/                        # 工具函数
│   │       ├── format.ts                 # 数据格式化（价格/百分比/大数）
│   │       ├── stock-code.ts             # 股票代码解析/验证
│   │       └── cn.ts                     # classnames工具
│   │
│   └── hooks/                            # 自定义Hooks
│       ├── use-sse.ts                    # SSE连接管理
│       ├── use-artifact-pin.ts           # Artifact钉住/取消
│       ├── use-stock-context.ts          # 当前分析股票上下文
│       └── use-responsive.ts             # 响应式布局
│
├── public/
│   └── icons/                            # Agent头像/图标
│
├── next.config.ts                        # Next.js配置（SSE代理等）
├── tailwind.config.ts                    # Tailwind配置
├── tsconfig.json                         # TypeScript配置
├── package.json
├── components.json                       # shadcn/ui配置
└── Dockerfile                            # 前端容器化
```

### 2.1 路由对比（旧→新）

| 旧路由（15页面）               | 新路由（AI-Native） | 说明                         |
| ----------------------------- | ------------------- | ---------------------------- |
| `/dashboard`                  | `/`                 | 首页整合市场概览+AI对话入口   |
| `/stock/[code]`               | 废弃                | 通过对话生成Artifact替代      |
| `/analysis`                   | `/chat`             | AI对话页为核心分析入口        |
| `/fundamental`                | 废弃                | 对话触发→Artifact展示         |
| `/capital-flow`               | 废弃                | 对话触发→Artifact展示         |
| `/scenario`                   | 废弃                | 对话触发→Artifact展示         |
| `/risk`                       | 废弃                | 对话触发→Artifact展示         |
| `/qa`                         | 废弃                | 并入AI对话                   |
| `/industry`                   | 废弃                | 对话触发→Artifact展示         |
| `/etf`                        | 废弃                | 对话触发→Artifact展示         |
| `/market-scan`                | 废弃                | 对话触发→Artifact展示         |
| `/portfolio`                  | `/portfolio`        | 保留：结构化投资组合仪表盘    |
| `/watchlist`（新增）           | `/watchlist`        | 保留：自选股看板             |
| `/settings`（新增）            | `/settings`         | 保留：用户设置               |

**核心原则**：从12+个独立页面精简到 **4个路由**（首页/对话/投资组合/自选股/设置），其余功能全部通过AI对话 + Artifacts动态生成。

---

## 3. AI集成架构（核心）

### 3.1 整体数据流

```
用户输入
  │
  ▼
┌──────────────┐     SSE Stream      ┌──────────────────────┐
│  Next.js前端  │ ◄──────────────────► │   Flask后端           │
│              │   POST /api/ai/chat  │                      │
│  useChat()   │ ──────────────────► │   OrchestratorAgent   │
│              │                      │     ├─ TechnicalAgent │
│  streamUI()  │ ◄─ SSE events ───── │     ├─ FundamentalAgent│
│              │   · text_delta       │     ├─ CapitalFlowAgent│
│  Artifacts   │   · tool_call_start  │     ├─ RiskAgent      │
│  渲染        │   · tool_call_result │     ├─ NewsAgent      │
│              │   · agent_progress   │     ├─ SentimentAgent │
│              │   · thinking         │     └─ ConsensusAgent │
└──────────────┘                      └──────────────────────┘
```

### 3.2 Vercel AI SDK 6 集成

#### useChat Hook 封装

```typescript
// lib/ai/use-stock-chat.ts
import { useChat } from 'ai/react';
import { toolRegistry } from './tool-registry';

export function useStockChat() {
  const chat = useChat({
    api: '/api/ai/chat',           // Next.js Route Handler代理到Flask
    streamProtocol: 'data',        // AI SDK Data Stream协议
    maxSteps: 10,                  // 允许多步工具调用
    onToolCall: async ({ toolCall }) => {
      // 工具调用时触发Artifact渲染
      const renderer = toolRegistry.get(toolCall.toolName);
      if (renderer) {
        return renderer(toolCall.args);
      }
    },
  });

  return {
    ...chat,
    // 快捷命令解析
    sendAnalysis: (stockCode: string) =>
      chat.append({ role: 'user', content: `分析 ${stockCode}` }),
    sendComparison: (codes: string[]) =>
      chat.append({ role: 'user', content: `对比 ${codes.join(' 和 ')}` }),
  };
}
```

#### streamUI 渲染器

```typescript
// lib/ai/stream-ui-renderer.tsx
import { streamUI } from 'ai/rsc';
import { artifactRegistry } from '@/components/artifacts/artifact-registry';

// 根据工具调用名称，动态渲染对应的React Artifact组件
export function renderToolResult(toolName: string, result: unknown) {
  const ArtifactComponent = artifactRegistry[toolName];
  if (!ArtifactComponent) {
    return <pre>{JSON.stringify(result, null, 2)}</pre>;
  }
  return <ArtifactComponent data={result} />;
}
```

#### Streamdown 配置

```typescript
// lib/ai/streamdown-config.ts
import { createStreamdownConfig } from 'streamdown';

export const streamdownConfig = createStreamdownConfig({
  // 流式Markdown渲染配置
  components: {
    code: ({ children, language }) => (
      <SyntaxHighlighter language={language}>{children}</SyntaxHighlighter>
    ),
    table: ({ children }) => (
      <div className="overflow-x-auto">
        <table className="min-w-full">{children}</table>
      </div>
    ),
    // 自定义金融术语高亮
    strong: ({ children }) => (
      <span className="text-primary font-semibold">{children}</span>
    ),
  },
  // 流式渲染：逐字符/逐词呈现
  streaming: {
    mode: 'word',          // 逐词渲染（比逐字符更平滑）
    cursorStyle: 'blink',  // 打字机光标
  },
});
```

### 3.3 AG-UI协议适配

```typescript
// lib/ai/ag-ui-adapter.ts

// AG-UI事件类型映射
type AGUIEvent =
  | { type: 'TEXT_MESSAGE_START'; messageId: string }
  | { type: 'TEXT_MESSAGE_CONTENT'; delta: string }
  | { type: 'TEXT_MESSAGE_END' }
  | { type: 'TOOL_CALL_START'; toolCallId: string; toolName: string }
  | { type: 'TOOL_CALL_ARGS'; delta: string }
  | { type: 'TOOL_CALL_END' }
  | { type: 'STATE_DELTA'; delta: object }      // Agent状态增量
  | { type: 'CUSTOM'; name: string; value: unknown };  // 自定义事件

// 将Flask后端SSE事件转换为AG-UI协议事件
export class AGUIAdapter {
  parseSSEEvent(event: MessageEvent): AGUIEvent {
    const data = JSON.parse(event.data);
    switch (data.event) {
      case 'text_delta':
        return { type: 'TEXT_MESSAGE_CONTENT', delta: data.content };
      case 'tool_call_start':
        return {
          type: 'TOOL_CALL_START',
          toolCallId: data.call_id,
          toolName: data.tool_name,
        };
      case 'tool_call_result':
        return { type: 'TOOL_CALL_END' };
      case 'agent_progress':
        return {
          type: 'STATE_DELTA',
          delta: { agents: data.agents },
        };
      case 'thinking':
        return {
          type: 'CUSTOM',
          name: 'thinking',
          value: data.content,
        };
      default:
        return { type: 'CUSTOM', name: data.event, value: data };
    }
  }
}
```

### 3.4 Next.js Route Handler（SSE代理）

```typescript
// app/api/ai/chat/route.ts
import { NextRequest } from 'next/server';

const FLASK_API = process.env.FLASK_API_URL || 'http://localhost:5000';

export async function POST(req: NextRequest) {
  const body = await req.json();

  // 将请求转发到Flask后端，返回SSE流
  const response = await fetch(`${FLASK_API}/api/ai/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: body.messages,
      stock_code: body.stockCode,
      session_id: body.sessionId,
    }),
  });

  // 直接透传SSE流到前端
  return new Response(response.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
```

---

## 4. Artifacts组件注册表

### 4.1 注册表设计

每个后端MCP工具调用的结果，映射到一个前端React Artifact组件：

```typescript
// components/artifacts/artifact-registry.ts
import { CandlestickChart } from './candlestick-chart';
import { TechnicalAnalysisPanel } from './technical-analysis-panel';
import { FundamentalScorecard } from './fundamental-scorecard';
import { CapitalFlowChart } from './capital-flow-chart';
import { NewsFeed } from './news-feed';
import { RiskRadarChart } from './risk-radar-chart';
import { WebSearchResults } from './web-search-results';
import { InvestorPersonas } from './investor-personas';
import type { ComponentType } from 'react';

export const artifactRegistry: Record<string, ComponentType<{ data: any }>> = {
  get_stock_data:          CandlestickChart,
  get_technical_indicators: TechnicalAnalysisPanel,
  get_fundamental_data:    FundamentalScorecard,
  get_capital_flow:        CapitalFlowChart,
  get_stock_news:          NewsFeed,
  get_risk_assessment:     RiskRadarChart,
  search_web:              WebSearchResults,
  // 复合Artifact（多工具结果聚合）
  investor_consensus:      InvestorPersonas,
};
```

### 4.2 各Artifact组件规格

| 工具名                     | Artifact组件                | 渲染库               | 交互能力                       |
| ------------------------- | -------------------------- | -------------------- | ------------------------------ |
| `get_stock_data`          | `<CandlestickChart>`      | TradingView LWC      | 缩放/十字线/切换周期/叠加均线   |
| `get_technical_indicators`| `<TechnicalAnalysisPanel>` | Recharts + 卡片      | Tab切换MACD/KDJ/RSI/BOLL      |
| `get_fundamental_data`    | `<FundamentalScorecard>`   | shadcn/ui Cards      | 评分仪表盘/财务指标表格/趋势图  |
| `get_capital_flow`        | `<CapitalFlowChart>`       | Recharts Sankey/Bar  | 切换日/周维度/主力/散户筛选     |
| `get_stock_news`          | `<NewsFeed>`               | shadcn/ui List       | 展开摘要/外链跳转/情感标签      |
| `get_risk_assessment`     | `<RiskRadarChart>`         | Recharts Radar       | 悬停查看各维度详情/风险等级色带  |
| `search_web`              | `<WebSearchResults>`       | shadcn/ui Cards      | 来源链接/相关度排序             |
| `investor_consensus`      | `<InvestorPersonas>`       | 自定义卡片布局        | 并排对比/展开详细论述            |

### 4.3 Artifact卡片功能

每个Artifact渲染为一张卡片，具备以下通用能力：

```typescript
// components/artifacts/artifact-card.tsx
interface ArtifactCardProps {
  id: string;
  title: string;
  toolName: string;
  children: React.ReactNode;
  timestamp: Date;
}

// 功能按钮：
// [钉住]   - 将Artifact固定到工作区，不随对话滚动消失
// [全屏]   - 全屏展示图表，获得更大交互空间
// [导出]   - 导出为PNG/CSV/PDF
// [刷新]   - 重新调用工具获取最新数据
// [关闭]   - 从工作区移除
```

### 4.4 投资者人格观点对比（特色Artifact）

```
┌─────────────────────────────────────────────────────┐
│                投资者共识分析：600519                  │
├────────────┬────────────┬────────────┬──────────────┤
│  巴菲特     │  芒格       │  彼得·林奇  │  达摩达兰    │
│  价值投资   │  逆向思维   │  成长投资   │  估值模型    │
│            │            │            │              │
│  评级: 买入 │  评级: 持有 │  评级: 买入 │  评级: 持有  │
│  置信: 0.85│  置信: 0.72│  置信: 0.78│  置信: 0.68  │
│            │            │            │              │
│  "护城河深  │  "管理层优  │  "PEG合理   │  "DCF显示    │
│   厚，品牌  │   秀，但需  │   但需关注  │   内在价值   │
│   定价权强" │   警惕估值" │   增速拐点" │   略高于现价"│
│            │            │            │              │
│  [展开详细] │  [展开详细] │  [展开详细] │  [展开详细]  │
└────────────┴────────────┴────────────┴──────────────┘
│              综合共识: 谨慎买入 (0.76)               │
└─────────────────────────────────────────────────────┘
```

---

## 5. Agent可视化设计

### 5.1 Multi-Agent进度面板

展示13个Agent的执行状态，嵌入对话流中：

```
┌─ Agent执行状态 ──────────────────────────────┐
│                                              │
│  ✅ TechnicalAgent      技术面分析完成  1.2s  │
│  ✅ FundamentalAgent    基本面分析完成  2.1s  │
│  🔄 CapitalFlowAgent   正在分析资金流...     │
│  ⏳ RiskAgent           等待中              │
│  ⏳ SentimentAgent      等待中              │
│  ✅ NewsAgent           新闻采集完成    0.8s  │
│  ⏳ IndustryAgent       等待中              │
│  ⏳ MacroAgent          等待中              │
│  ⏳ ValuationAgent      等待中              │
│  ⏳ PatternAgent        等待中              │
│  ⏳ QuantAgent          等待中              │
│  ⏳ InvestorAgent       等待中              │
│  ⏳ ConsensusAgent      等待中              │
│                                              │
│  总进度: ████████░░░░░░░░░░ 3/13 (23%)       │
│  预计剩余: ~8s                               │
└──────────────────────────────────────────────┘
```

```typescript
// components/agent/agent-progress-panel.tsx
interface AgentStatus {
  name: string;
  displayName: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  duration?: number;      // 耗时（秒）
  progress?: number;      // 0-100
  message?: string;       // 状态描述
}

interface AgentProgressPanelProps {
  agents: AgentStatus[];
  totalProgress: number;  // 0-100
  estimatedRemaining?: number; // 预计剩余秒数
}
```

### 5.2 工具调用Timeline

每次Function Calling可视化为一张卡片，按时间线排列：

```
┌─ 工具调用记录 ───────────────────────────────┐
│                                              │
│  14:32:01 ──┬── get_stock_data(600519)       │
│             │   入参: {code: "600519",        │
│             │          period: "daily"}       │
│             │   耗时: 0.3s                    │
│             │   结果: 245条K线数据 ✅          │
│             │   → 生成 <CandlestickChart>     │
│             │                                │
│  14:32:02 ──┬── get_technical_indicators(..) │
│             │   入参: {code: "600519",        │
│             │          indicators: ["MACD",   │
│             │           "KDJ", "RSI"]}        │
│             │   耗时: 0.5s                    │
│             │   结果: 3组指标数据 ✅            │
│             │   → 生成 <TechnicalAnalysis>    │
│             │                                │
│  14:32:03 ──┬── get_fundamental_data(600519) │
│             │   ...                          │
└─────────────┴────────────────────────────────┘
```

```typescript
// components/agent/tool-call-card.tsx
interface ToolCallCardProps {
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown>;
  result?: unknown;
  status: 'calling' | 'completed' | 'error';
  startTime: Date;
  duration?: number;
  artifactId?: string;   // 关联的Artifact ID
}
```

### 5.3 思考链展示

AI的推理过程以折叠块形式展示，默认折叠，点击展开：

```typescript
// components/agent/thinking-chain.tsx
interface ThinkingChainProps {
  steps: Array<{
    agent: string;
    thought: string;
    timestamp: Date;
  }>;
  defaultExpanded?: boolean;
}

// 渲染为可折叠的灰色区块：
// ▶ 💭 分析思路 (点击展开)
// ▼ 💭 分析思路
//   1. 用户询问600519的投资价值...
//   2. 需要综合技术面、基本面、资金面...
//   3. 先获取K线数据判断趋势...
```

---

## 6. 对话系统设计

### 6.1 消息类型定义

```typescript
// lib/types/chat.ts

// 消息角色
type MessageRole = 'user' | 'assistant' | 'system';

// 消息内容类型
type MessageContentPart =
  | { type: 'text'; text: string }                         // 纯文本
  | { type: 'tool-call'; toolName: string; args: object; callId: string }  // 工具调用
  | { type: 'tool-result'; toolName: string; result: unknown; callId: string } // 工具结果
  | { type: 'artifact'; artifactId: string; toolName: string; data: unknown }  // Artifact组件
  | { type: 'thinking'; content: string }                  // 思考过程
  | { type: 'agent-progress'; agents: AgentStatus[] }      // Agent进度
  | { type: 'suggestions'; questions: string[] };           // 预判性提问

interface ChatMessage {
  id: string;
  role: MessageRole;
  content: MessageContentPart[];
  createdAt: Date;
  metadata?: {
    stockCode?: string;
    sessionId?: string;
    model?: string;
  };
}
```

### 6.2 对话流程（典型场景）

```
用户: "分析一下茅台"
  │
  ├─ 前端解析 → 识别为股票分析请求 → stockCode: "600519"
  │
  ├─ POST /api/ai/chat { messages, stockCode: "600519" }
  │
  ├─ SSE Stream开始 ──────────────────────────────────
  │   │
  │   ├─ event: thinking
  │   │   "用户想了解贵州茅台的投资价值，需要全面分析..."
  │   │   → 渲染 <ThinkingChain>（折叠）
  │   │
  │   ├─ event: agent_progress
  │   │   { agents: [{ name: "TechnicalAgent", status: "running" }] }
  │   │   → 渲染 <AgentProgressPanel>
  │   │
  │   ├─ event: tool_call_start { tool: "get_stock_data", args: {...} }
  │   │   → 渲染 <ToolCallCard status="calling">
  │   │
  │   ├─ event: tool_call_result { tool: "get_stock_data", result: {...} }
  │   │   → 渲染 <CandlestickChart> 到Artifacts工作区
  │   │   → 更新 <ToolCallCard status="completed">
  │   │
  │   ├─ event: tool_call_start { tool: "get_technical_indicators", ... }
  │   │   → ...
  │   │
  │   ├─ event: text_delta "## 贵州茅台(600519) 综合分析\n\n"
  │   │   → Streamdown流式渲染Markdown
  │   │
  │   ├─ event: text_delta "### 技术面分析\n当前价格..."
  │   │   → 继续流式渲染
  │   │
  │   ├─ event: agent_progress（所有Agent完成）
  │   │
  │   ├─ event: suggestions
  │   │   ["深入分析技术指标?", "查看资金流向?", "对比五粮液?",
  │   │    "评估风险水平?", "查看最新新闻?"]
  │   │   → 渲染 <SuggestedQuestions>
  │   │
  │   └─ event: done
  │
  └─ 完成：左侧显示完整分析文本 + Agent状态
           右侧显示K线图/技术面板/评分卡等Artifacts
```

### 6.3 快捷命令系统

```typescript
// components/chat/command-palette.tsx

const QUICK_COMMANDS = [
  {
    trigger: /^分析\s*(\w+)/,
    description: '分析指定股票',
    example: '分析600519 / 分析茅台',
    action: (match: string) => `请对 ${match} 进行全面投资分析`,
  },
  {
    trigger: /^对比\s*(.+)\s*和\s*(.+)/,
    description: '对比两只股票',
    example: '对比茅台和五粮液',
    action: (a: string, b: string) => `请对比分析 ${a} 和 ${b}`,
  },
  {
    trigger: /^风险\s*(\w+)/,
    description: '风险评估',
    example: '风险600519',
    action: (match: string) => `请评估 ${match} 的风险水平`,
  },
  {
    trigger: /^资金\s*(\w+)/,
    description: '资金流向分析',
    example: '资金600519',
    action: (match: string) => `请分析 ${match} 的资金流向`,
  },
  {
    trigger: /^新闻\s*(\w+)/,
    description: '最新新闻',
    example: '新闻600519',
    action: (match: string) => `请查询 ${match} 的最新相关新闻`,
  },
];

// 输入框支持 "/" 唤起命令面板
// 输入"分析600519"时，自动匹配并高亮命令提示
```

### 6.4 预判性提问（Follow-up Suggestions）

每次AI回复后，根据上下文生成3-5个推荐的后续问题：

```typescript
// components/chat/suggested-questions.tsx
interface SuggestedQuestionsProps {
  questions: string[];
  onSelect: (question: string) => void;
}

// 渲染为可点击的药丸按钮：
// [深入技术面分析?] [查看资金流向?] [对比同行业?] [评估风险?]
```

后端在SSE流末尾附加suggestions事件，前端渲染为可点击按钮，点击即发送对应问题。

### 6.5 上下文管理

```typescript
// 多轮对话保持分析上下文
// 当用户连续分析同一只股票时，后续问题自动关联

// 示例对话流：
// 用户: "分析茅台"           → context: { stockCode: "600519" }
// AI: [全面分析结果]
// 用户: "技术面怎么看?"       → 自动关联600519的技术面
// AI: [技术面详细分析]
// 用户: "和五粮液对比呢?"     → 新增context: 000858, 保持600519
// AI: [对比分析结果]
```

---

## 7. 状态管理（三层架构）

### 7.1 对话状态（Zustand）

```typescript
// lib/stores/chat-store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ChatState {
  // 会话管理
  sessions: ChatSession[];
  activeSessionId: string | null;

  // 消息
  messages: ChatMessage[];

  // 当前分析上下文
  currentStockCode: string | null;
  currentStockName: string | null;

  // 操作
  addMessage: (msg: ChatMessage) => void;
  createSession: () => string;
  switchSession: (id: string) => void;
  setCurrentStock: (code: string, name: string) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      sessions: [],
      activeSessionId: null,
      messages: [],
      currentStockCode: null,
      currentStockName: null,
      // ... actions
    }),
    { name: 'stock-chat-storage' }
  )
);
```

### 7.2 Agent状态（Zustand）

```typescript
// lib/stores/agent-store.ts
import { create } from 'zustand';

interface AgentState {
  // 各Agent执行状态
  agents: Record<string, AgentStatus>;

  // 工具调用日志
  toolCalls: ToolCallLog[];

  // 思考链
  thinkingSteps: ThinkingStep[];

  // 操作
  updateAgentStatus: (name: string, status: AgentStatus) => void;
  addToolCall: (call: ToolCallLog) => void;
  updateToolCallResult: (callId: string, result: unknown) => void;
  addThinkingStep: (step: ThinkingStep) => void;
  resetAgents: () => void;
}

export const useAgentStore = create<AgentState>()((set) => ({
  agents: {},
  toolCalls: [],
  thinkingSteps: [],
  // ... actions
}));
```

### 7.3 Artifacts状态（Zustand）

```typescript
// lib/stores/artifact-store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ArtifactState {
  // 当前会话的Artifacts
  artifacts: Artifact[];

  // 被"钉住"的Artifacts（跨会话保持）
  pinnedArtifacts: Artifact[];

  // 全屏展示的Artifact
  fullscreenArtifactId: string | null;

  // 操作
  addArtifact: (artifact: Artifact) => void;
  pinArtifact: (id: string) => void;
  unpinArtifact: (id: string) => void;
  setFullscreen: (id: string | null) => void;
  removeArtifact: (id: string) => void;
  clearSessionArtifacts: () => void;
}

interface Artifact {
  id: string;
  toolName: string;         // 来源工具
  title: string;            // 显示标题
  data: unknown;            // 工具返回数据
  stockCode?: string;       // 关联股票
  isPinned: boolean;        // 是否钉住
  createdAt: Date;
}

export const useArtifactStore = create<ArtifactState>()(
  persist(
    (set) => ({
      artifacts: [],
      pinnedArtifacts: [],
      fullscreenArtifactId: null,
      // ... actions
    }),
    {
      name: 'stock-artifacts-storage',
      partialize: (state) => ({
        pinnedArtifacts: state.pinnedArtifacts, // 仅持久化钉住的
      }),
    }
  )
);
```

### 7.4 原子状态（Jotai）— UI偏好

```typescript
// lib/stores/atoms.ts
import { atom } from 'jotai';
import { atomWithStorage } from 'jotai/utils';

// UI偏好
export const themeAtom = atomWithStorage<'light' | 'dark' | 'system'>('theme', 'system');
export const chatPanelWidthAtom = atomWithStorage('chatPanelWidth', 35); // 百分比
export const showThinkingAtom = atomWithStorage('showThinking', false);  // 默认折叠思考链
export const showToolCallsAtom = atomWithStorage('showToolCalls', true); // 显示工具调用

// 派生状态
export const artifactPanelWidthAtom = atom((get) => 100 - get(chatPanelWidthAtom));
```

### 7.5 三层状态关系

```
┌─────────────────────────────────────────────────────┐
│                    状态管理三层架构                    │
│                                                     │
│  ┌─────────────────┐  Zustand (持久化)               │
│  │  ChatStore       │  · 消息历史                     │
│  │  · messages      │  · 会话管理                     │
│  │  · sessions      │  · 当前分析股票                 │
│  │  · currentStock  │                                │
│  └────────┬────────┘                                │
│           │ 触发Agent执行                             │
│  ┌────────▼────────┐  Zustand (会话级)               │
│  │  AgentStore      │  · Agent状态（每次分析重置）      │
│  │  · agents        │  · 工具调用日志                  │
│  │  · toolCalls     │  · 思考链                       │
│  │  · thinkingSteps │                                │
│  └────────┬────────┘                                │
│           │ 工具调用产出Artifact                       │
│  ┌────────▼────────┐  Zustand (混合)                 │
│  │  ArtifactStore   │  · 当前会话Artifacts（会话级）    │
│  │  · artifacts     │  · 钉住的Artifacts（持久化）      │
│  │  · pinned        │  · 全屏状态                     │
│  └─────────────────┘                                │
│                                                     │
│  ┌─────────────────┐  Jotai (持久化)                 │
│  │  UI Atoms        │  · 主题 / 面板宽度              │
│  │  · theme         │  · 思考链展示偏好               │
│  │  · panelWidth    │  · 工具调用显示偏好             │
│  └─────────────────┘                                │
└─────────────────────────────────────────────────────┘
```

---

## 8. 后端适配

### 8.1 新增SSE端点

在现有Flask后端新增一个SSE端点，专门服务AI对话：

```python
# 新增端点: POST /api/ai/chat
# 功能: 接收用户消息，调度Multi-Agent分析，流式返回结果

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    """
    Request Body:
    {
        "messages": [
            {"role": "user", "content": "分析600519"}
        ],
        "stock_code": "600519",    # 可选，前端解析
        "session_id": "uuid"       # 会话ID
    }

    SSE Response Events:
    - thinking:         { "content": "分析思路..." }
    - agent_progress:   { "agents": [{"name": "...", "status": "..."}] }
    - tool_call_start:  { "call_id": "...", "tool_name": "...", "args": {...} }
    - tool_call_result: { "call_id": "...", "tool_name": "...", "result": {...} }
    - text_delta:       { "content": "部分文本..." }
    - suggestions:      { "questions": ["..."] }
    - error:            { "message": "错误信息" }
    - done:             {}
    """

    def generate():
        # 1. 解析用户意图
        # 2. 调度OrchestratorAgent
        # 3. 各子Agent执行时实时推送progress
        # 4. 工具调用时推送tool_call事件
        # 5. 最终结果流式推送text_delta
        # 6. 推送follow-up suggestions
        # 7. 推送done
        pass

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Nginx禁用缓冲
        }
    )
```

### 8.2 SSE事件格式

```
event: thinking
data: {"content": "用户询问贵州茅台，需要综合分析..."}

event: agent_progress
data: {"agents": [{"name": "TechnicalAgent", "status": "running", "progress": 50}]}

event: tool_call_start
data: {"call_id": "tc_001", "tool_name": "get_stock_data", "args": {"code": "600519", "period": "daily"}}

event: tool_call_result
data: {"call_id": "tc_001", "tool_name": "get_stock_data", "result": {"dates": [...], "prices": [...]}}

event: text_delta
data: {"content": "## 贵州茅台(600519) 综合分析\n\n"}

event: text_delta
data: {"content": "### 技术面\n当前价格处于..."}

event: suggestions
data: {"questions": ["深入技术面?", "查看资金流?", "对比同行?"]}

event: done
data: {}
```

### 8.3 现有API保持不变

后端现有的REST端点（供MCP工具函数内部调用）全部保持不变：

| 端点                           | 用途                | 变更   |
| ------------------------------ | ------------------- | ------ |
| `GET /api/stock/<code>`        | 股票行情数据         | 不变   |
| `GET /api/analysis/<code>`     | Agent分析报告        | 不变   |
| `GET /api/fundamental/<code>`  | 基本面数据           | 不变   |
| `GET /api/capital-flow/<code>` | 资金流向             | 不变   |
| `GET /api/risk/<code>`         | 风险评估             | 不变   |
| `GET /api/news/<code>`         | 新闻资讯             | 不变   |
| `GET /api/industry/<code>`     | 行业分析             | 不变   |
| `POST /api/qa`                 | 智能问答             | 不变   |
| **`POST /api/ai/chat`**        | **AI对话（新增SSE）** | **新增** |

### 8.4 CORS配置

```python
# Flask CORS配置
from flask_cors import CORS

CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:3000",      # 本地开发
            "https://your-domain.com",    # 生产环境
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["X-Request-Id"],
        "supports_credentials": True,
    }
})
```

---

## 9. 部署架构

### 9.1 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl        # HTTPS证书（可选）
    depends_on:
      - frontend
      - backend
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      - FLASK_API_URL=http://backend:5000
      - NEXT_PUBLIC_API_URL=/api
    expose:
      - "3000"
    restart: unless-stopped

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=sqlite:///stock_analysis.db
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    expose:
      - "5000"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

### 9.2 Nginx配置（SSE长连接支持）

```nginx
# nginx/nginx.conf
upstream frontend {
    server frontend:3000;
}

upstream backend {
    server backend:5000;
}

server {
    listen 80;
    server_name localhost;

    # 前端（Next.js）
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # 后端API（REST）
    location /api/ {
        proxy_pass http://backend/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # 常规API超时
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }

    # SSE端点（长连接特殊配置）
    location /api/ai/chat {
        proxy_pass http://backend/api/ai/chat;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Connection '';

        # SSE关键配置
        proxy_buffering off;                    # 禁用缓冲
        proxy_cache off;                        # 禁用缓存
        proxy_read_timeout 300s;                # 长超时（5分钟）
        proxy_send_timeout 300s;

        # 禁用gzip（避免流式数据被缓冲）
        proxy_set_header Accept-Encoding '';

        # 添加SSE响应头
        add_header X-Accel-Buffering no;
        add_header Cache-Control no-cache;
        add_header Content-Type text/event-stream;
    }
}
```

### 9.3 前端Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
```

### 9.4 部署拓扑

```
                    ┌─────────┐
                    │  用户    │
                    └────┬────┘
                         │ HTTPS
                    ┌────▼────┐
                    │  Nginx  │
                    │  :80/443│
                    └────┬────┘
                    ┌────┴────┐
              ┌─────▼──┐  ┌──▼──────┐
              │Next.js  │  │  Flask  │
              │  :3000  │  │  :5000  │
              │(前端)   │  │(后端)   │
              └─────────┘  └────┬────┘
                                │
                         ┌──────┴──────┐
                         │   SQLite    │
                         │   + LLM API │
                         └─────────────┘
```

---

## 10. 迁移策略

### 10.1 核心原则

**不迁移15个页面**。战略转向意味着：

1. **废弃**传统表单查询页面（stock/analysis/fundamental/capital-flow/scenario/risk/qa/industry/etf/market-scan）
2. **保留**3个结构化锚点视图（首页/投资组合/自选股）
3. **新建**AI对话系统作为核心交互入口
4. 后端API不变，前端消费方式从"页面表单→REST查询→渲染"改为"对话→Agent编排→SSE流→Artifact渲染"

### 10.2 实施阶段

#### Phase 1：对话核心（2周）

| 任务                          | 产出                                    |
| ----------------------------- | --------------------------------------- |
| 搭建Next.js项目骨架           | 项目结构 + 路由 + 布局                    |
| 集成assistant-ui + AI SDK 6   | `useStockChat` hook + SSE连接            |
| 实现Chat面板                  | 消息列表 + 流式渲染 + 输入框             |
| 后端新增 `/api/ai/chat` SSE   | Agent调度 + SSE事件推送                  |
| 实现Streamdown流式Markdown    | 流式文本渲染                             |

#### Phase 2：Artifacts系统（2周）

| 任务                          | 产出                                    |
| ----------------------------- | --------------------------------------- |
| Artifact注册表 + 卡片容器     | 工具→组件映射 + 钉住/全屏/导出           |
| CandlestickChart              | TradingView LWC K线图                   |
| TechnicalAnalysisPanel        | 技术指标面板（MACD/KDJ/RSI/BOLL）       |
| FundamentalScorecard          | 基本面评分卡                             |
| CapitalFlowChart              | 资金流向图                               |
| RiskRadarChart                | 风险雷达图                               |
| NewsFeed + WebSearchResults   | 新闻/搜索结果                            |

#### Phase 3：Agent可视化 + 锚点视图（1.5周）

| 任务                          | 产出                                    |
| ----------------------------- | --------------------------------------- |
| Agent进度面板                 | 13 Agent状态实时展示                     |
| 工具调用Timeline              | Function Calling可视化                   |
| 思考链展示                    | 折叠/展开思考过程                        |
| InvestorPersonas              | 投资者人格观点对比卡片                    |
| 首页                          | 市场概览 + AI对话入口                    |
| 投资组合页                    | 持仓仪表盘                               |
| 自选股页                      | 自选股看板                               |

#### Phase 4：打磨 + 部署（1周）

| 任务                          | 产出                                    |
| ----------------------------- | --------------------------------------- |
| 快捷命令系统                  | "/"命令面板 + 自然语言解析               |
| 预判性提问                    | Follow-up建议生成                        |
| 状态持久化                    | Zustand persist + 会话恢复              |
| Docker Compose                | Nginx + Next.js + Flask 容器编排         |
| 响应式适配                    | 移动端对话/Artifact抽屉布局              |

### 10.3 风险与回滚

| 风险                         | 缓解措施                                 |
| ---------------------------- | ---------------------------------------- |
| SSE连接不稳定                 | 自动重连 + 消息ID去重 + 断点续传          |
| 流式渲染闪烁/卡顿             | Streamdown word模式 + requestAnimationFrame |
| Artifact数据量过大            | 虚拟化渲染 + 分页加载 + Web Worker处理    |
| Agent响应时间过长              | 超时兜底 + 逐步展示已完成Agent结果        |
| 移动端布局不适配              | 单栏模式：对话优先，Artifact抽屉式展开     |

---

## 附录A：关键依赖版本

| 依赖                          | 版本       | 用途                    |
| ----------------------------- | ---------- | ----------------------- |
| Next.js                       | 15.x       | 全栈框架                |
| React                         | 19.x       | UI库                    |
| TypeScript                    | 5.x        | 类型安全                |
| `ai` (Vercel AI SDK)          | 6.x        | AI集成（useChat/streamUI）|
| `@assistant-ui/react`         | latest     | Chat UI headless组件    |
| `streamdown`                  | latest     | 流式Markdown渲染        |
| `lightweight-charts`          | 4.x        | TradingView K线图       |
| `recharts`                    | 2.x        | 辅助图表                |
| `@shadcn/ui`                  | latest     | 基础UI组件              |
| `tailwindcss`                 | 4.x        | CSS框架                 |
| `zustand`                     | 5.x        | 全局状态管理            |
| `jotai`                       | 2.x        | 原子状态管理            |

## 附录B：与旧架构的关键差异

| 维度             | 旧架构（v1.0）                      | 新架构（v2.0 AI-Native）               |
| ---------------- | ----------------------------------- | -------------------------------------- |
| 交互范式         | 表单查询 → 页面展示                  | 对话驱动 → Artifact实时生成             |
| 路由数量         | 12+ 页面                            | 4个路由（首页/对话/组合/自选）          |
| 数据获取         | 每页独立REST调用                     | 统一通过AI Agent编排                    |
| 实时性           | 轮询 / WebSocket                     | SSE流式推送                            |
| 图表库           | TradingView LWC + ECharts           | TradingView LWC + Recharts            |
| AI集成           | 无（后端独立运行Agent）              | Vercel AI SDK 6 全链路集成             |
| 状态管理         | Zustand + Jotai                     | Zustand（3层） + Jotai（UI原子）       |
| Agent可见性      | 无                                  | 进度面板/工具Timeline/思考链           |

---

*此项目的任何功能、架构更新，必须在结束后同步更新相关文档。这是我们契约的一部分。*
