# 前后端分离调研报告汇总

```
Input: 全球顶级金融前端方案调研
Output: 技术选型共识 + 权威来源交叉验证
Pos: docs/FRONTEND_RESEARCH.md - Phase 0/1 调研成果汇总
```

> 调研时间: 2026-03-25 21:54~22:30 +0800

---

## Phase 0: 前端现状基线

| 维度 | 现状 | 评分 |
|------|------|------|
| 模板数 | 15个HTML (Jinja2) | - |
| 最大模板 | stock_detail.html 66.4KB | - |
| API调用 | 18+个后端端点 | - |
| CSS框架 | Bootstrap 5.3.0 (CDN) | 9/10 |
| JS框架 | jQuery 3.6.0 + Vanilla | 5/10 |
| 图表库 | ApexCharts 3.35.0 | 9/10 |
| 前端路由 | 无（全页面刷新） | 3/10 |
| 状态管理 | 无 | 2/10 |
| 构建工具 | 无 | 2/10 |
| JS组织 | 全部内联在HTML中 | 3/10 |

---

## Phase 1A: 框架选型（权威来源交叉验证）

### 技术选型共识

| 层级 | 推荐 | 备选 | 来源数 |
|------|------|------|--------|
| 前端框架 | React 19 + Next.js 15 | Vue 3.5 + Nuxt 4 | 6+ |
| K线图表 | TradingView Lightweight Charts (35KB) | - | 3+ |
| 辅助图表 | Apache ECharts 6.0 | ApexCharts | 4+ |
| 状态管理 | Zustand + Jotai | Pinia (Vue) | 4+ |
| 部署 | Nginx反代 + Docker Compose | - | 3+ |
| 渲染模式 | 混合（SSG+CSR），行情用CSR+WebSocket | - | 3+ |

### 关键数据点

- React NPM周下载 96.2M vs Vue 9.2M (10x差距)
- Vue 3.5 Vapor Mode 内存降低56%，DOM操作比React快36%
- TradingView Lightweight Charts 14K Stars, 35KB体积
- ECharts 6.0 支持百万级数据点实时渲染

### 权威来源清单

- State of JS 2025 Survey (13,002开发者)
- NPM/GitHub官方数据 (PkgPulse, NPM Trends)
- 官方文档 (React, Vue, Next.js, ECharts)
- FastAPI CORS官方文档
- LogRocket/DZone/FreeCodeCamp性能分析

---

## Phase 1B: 金融前端设计（权威来源交叉验证）

### 顶级平台设计理念

| 平台 | 核心理念 | 技术 |
|------|----------|------|
| Bloomberg | 隐藏复杂性 + 渐进式变革 | Chromium, HTML5/CSS3 |
| TradingView | 浏览器原生 + 极致性能 | JS + WebGL, Canvas |
| Robinhood | 移动优先 + 颜色驱动决策 | React Native |
| 同花顺/Wind | 高信息密度 + AI工具 | 原生+Web混合 |

### UI组件库推荐

| 方案 | 评分 | 定位 |
|------|------|------|
| shadcn/ui + Tailwind CSS | **4.8/5** | 最现代，完全可控 |
| Ant Design Pro | 3.5/5 | 最多组件，企业级 |
| Arco Design | - | 字节跳动方案 |

### 金融设计规范

- 颜色：中国红涨绿跌 vs 国际绿涨红跌，需支持切换
- 对比度：文本最低4.5:1，关键数据7:1
- 8%男性色觉缺陷：不能仅靠颜色传递信息
- 信息密度：渐进式展示（Progressive Disclosure）
- 图表交互：十字线、缩放平移、技术指标叠加、多面板联动

### 权威来源清单

- Bloomberg UX官方博客
- TradingView GitHub + 官方文档
- Google Material Design (Robinhood案例)
- 证券时报/新浪财经 (国内平台分析)
- FreeCodeCamp/SitePoint (Next.js 15性能数据)

---

## 最终技术栈决定

```
Next.js 15 + React 19
├── UI: shadcn/ui + Tailwind CSS
├── K线图表: TradingView Lightweight Charts
├── 辅助图表: Apache ECharts 6.0
├── 状态管理: Zustand (全局) + Jotai (实时数据原子)
├── 实时通信: WebSocket + SSE
├── 主题: CSS变量 + Tailwind暗色模式
├── 部署: Nginx反代 + Docker Compose
└── 渲染: 混合模式 (SSG静态页 + CSR行情Dashboard)
```
