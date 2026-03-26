# 前端UI全面对标实现方案 v3.0

> **文档状态**: 待审批
> **编制时间**: 2026-03-26 22:23 +08:00
> **调研基础**: fiscal.ai + uiprompt.site + motionsites.ai + ui-ux-pro-max-skill.com + aura.build
> **对标产品**: Fiscal.ai (原FinChat) / Bloomberg Terminal / Perplexity Finance
> **技术栈**: Next.js 16 + React 19 + TypeScript + Tailwind CSS + shadcn/ui

---

## 一、设计方向总纲

### 1.1 设计风格定义

**Dark Glassmorphism + AI-Native UI + Bento Grid**

| 维度 | 定义 | 来源依据 |
|------|------|---------|
| 视觉基调 | 深色毛玻璃（Dark Glassmorphism） | ui-ux-pro-max 67种风格评估 + aura.build美学 |
| 交互范式 | AI-Native UI（对话驱动+生成式组件） | fiscal.ai Copilot模式 + AI_NATIVE_RESEARCH.md |
| 布局系统 | Bento Grid（便当网格模块化） | uiprompt.site Swiss+Bento推荐 |
| 数据密度 | Financial Dashboard（高密度专业级） | ui-ux-pro-max Financial Dashboard风格 |
| 动效体系 | Purpose-driven Motion（目的驱动动效） | motionsites.ai 2026趋势 |

### 1.2 与当前实现的核心差异

| 维度 | 当前状态 | 目标状态 | 改动规模 |
|------|---------|---------|---------|
| 色彩 | 5层Surface(#060d1f~#223354) 不透明 | 毛玻璃半透明分层 + 钴蓝品牌色 | 重写globals.css |
| 卡片 | 实色bg-card + border | 毛玻璃backdrop-blur + 微光边框 | 重写所有Card组件 |
| 动效 | 基础fade-in/slide-in | 数字跳动+渐变流体+stagger+spring | 新增动效系统 |
| 布局 | 固定三栏(sidebar\|chat\|artifacts) | Bento Grid模块化 + 可调比例 | 重构page.tsx |
| 品牌 | Tailwind默认蓝#3b82f6 | 钴蓝#3737CC + AI紫#6B5EE4 | 全局替换 |
| 数据展示 | 基础文本+图表 | 专业金融仪表盘(sparkline+countup) | 新增组件 |

---

## 二、设计规范（Design Tokens）

### 2.1 色彩系统

```
/* ══════ 暗色主题 Dark Glassmorphism ══════ */

/* 背景层级 */
--bg-base:        #06060F;     /* 最深底层 */
--bg-surface-0:   #0A0A1A;     /* 页面背景 */
--bg-surface-1:   #0F0F23;     /* 一级面板(sidebar/navbar) */
--bg-surface-2:   #14142B;     /* 二级面板(卡片) */
--bg-surface-3:   #1A1A35;     /* hover状态 */

/* 毛玻璃 */
--glass-bg:       rgba(255, 255, 255, 0.04);   /* 玻璃填充 */
--glass-bg-hover: rgba(255, 255, 255, 0.08);   /* 玻璃hover */
--glass-border:   rgba(255, 255, 255, 0.08);   /* 玻璃边框 */
--glass-border-hover: rgba(255, 255, 255, 0.15); /* hover边框 */
--glass-blur:     12px;                          /* 模糊度 */
--glass-shadow:   0 8px 32px rgba(0, 0, 0, 0.36); /* 投影 */

/* 品牌色 */
--brand-primary:  #3737CC;     /* 钴蓝（对标fiscal.ai） */
--brand-primary-light: #4F4FE6; /* 悬停态 */
--brand-primary-glow:  rgba(55, 55, 204, 0.25); /* 发光 */

/* AI专属色 */
--ai-purple:      #6B5EE4;     /* AI元素主色 */
--ai-purple-light: #8578F0;    /* AI hover */
--ai-purple-glow:  rgba(107, 94, 228, 0.2); /* AI发光 */

/* 语义色 */
--color-up:       #46BEA3;     /* 涨/正向（蓝绿） */
--color-down:     #FF8767;     /* 跌/负向（橙） */
--color-warning:  #F59E0B;     /* 警告 */
--color-danger:   #EF4444;     /* 危险 */
--color-success:  #10B981;     /* 成功 */

/* 文本 */
--text-primary:   #F0F0F5;     /* 主文本 */
--text-secondary: #8888A0;     /* 次要文本 */
--text-muted:     #555570;     /* 占位/禁用 */
--text-inverse:   #06060F;     /* 反色文本 */

/* 图表色板 */
--chart-1: #3737CC;  /* 钴蓝 */
--chart-2: #46BEA3;  /* 蓝绿 */
--chart-3: #F59E0B;  /* 琥珀 */
--chart-4: #FF8767;  /* 珊瑚橙 */
--chart-5: #6B5EE4;  /* 紫 */
--chart-6: #EC4899;  /* 粉 */
```

### 2.2 毛玻璃组件配方

```css
/* 标准玻璃卡片 */
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  box-shadow: var(--glass-shadow);
  transition: all 300ms ease-out;
}
.glass-card:hover {
  background: var(--glass-bg-hover);
  border-color: var(--glass-border-hover);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
  transform: translateY(-1px);
}

/* 导航栏玻璃 */
.glass-navbar {
  background: rgba(10, 10, 26, 0.8);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--glass-border);
}

/* 侧边栏玻璃 */
.glass-sidebar {
  background: rgba(15, 15, 35, 0.6);
  backdrop-filter: blur(16px);
  border-right: 1px solid var(--glass-border);
}

/* 输入框玻璃 */
.glass-input {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
}
.glass-input:focus {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 3px var(--brand-primary-glow);
}
```

**性能规则**: 同屏毛玻璃元素 ≤ 5 个，移动端加 `will-change: transform`。

### 2.3 字体系统

```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'JetBrains Mono', 'SF Mono', 'Cascadia Code', ui-monospace, monospace;

/* 字号层级 */
--text-xs:   11px;   /* 辅助/时间戳 */
--text-sm:   13px;   /* 次要内容 */
--text-base: 14px;   /* 正文（金融产品紧凑模式） */
--text-lg:   16px;   /* 小标题 */
--text-xl:   20px;   /* 面板标题 */
--text-2xl:  28px;   /* 页面标题 */
--text-3xl:  36px;   /* 关键数据（如股价） */

/* 行高 */
--leading-tight:  1.3;  /* 标题/数据 */
--leading-normal: 1.5;  /* 正文 */
--leading-relaxed: 1.7; /* 长文本/报告 */
```

**金融数字规则**: 所有数字使用 `font-variant-numeric: tabular-nums lining-nums`，确保列对齐。

### 2.4 间距系统（4pt基准网格）

```
--space-1:  4px     /* 最小间距 */
--space-2:  8px     /* 元素内紧凑间距 */
--space-3:  12px    /* 元素内标准间距 */
--space-4:  16px    /* 组件间间距 */
--space-5:  20px    /* 区块间间距 */
--space-6:  24px    /* 面板内边距 */
--space-8:  32px    /* 大区块间距 */
--space-10: 40px    /* 页面边距 */
--space-12: 48px    /* 特大间距 */
```

### 2.5 圆角系统

```
--radius-sm:  6px    /* 标签/徽章 */
--radius-md:  8px    /* 按钮/输入框 */
--radius-lg:  12px   /* 小卡片 */
--radius-xl:  16px   /* 标准卡片 */
--radius-2xl: 20px   /* 大面板 */
--radius-full: 9999px /* 胶囊/圆形 */
```

### 2.6 动效系统

```css
/* ══════ 时长标准 ══════ */
--duration-instant: 100ms;  /* 即时反馈(opacity/color) */
--duration-fast:    200ms;  /* 微交互(hover/focus) */
--duration-normal:  300ms;  /* 标准过渡(展开/切换) */
--duration-slow:    500ms;  /* 大型动画(页面/模态) */
--duration-slower:  800ms;  /* 装饰动画(渐变流动) */

/* ══════ 缓动函数 ══════ */
--ease-out:    cubic-bezier(0.16, 1, 0.3, 1);      /* 主要进入 */
--ease-in:     cubic-bezier(0.7, 0, 0.84, 0);      /* 退出 */
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);  /* 弹性 */

/* ══════ 动画定义 ══════ */

/* 1. 数字跳动 CountUp */
@keyframes count-up {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 2. 渐变流体脉冲（AI思考状态） */
@keyframes gradient-flow {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
.ai-thinking {
  background: linear-gradient(
    90deg,
    var(--ai-purple) 0%,
    var(--brand-primary) 50%,
    var(--ai-purple) 100%
  );
  background-size: 200% 100%;
  animation: gradient-flow 3s ease infinite;
}

/* 3. 玻璃卡片入场（slide + fade） */
@keyframes glass-enter {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* 4. Stagger列表项 */
.stagger-item { animation: glass-enter var(--duration-normal) var(--ease-out) both; }
.stagger-item:nth-child(1) { animation-delay: 0ms; }
.stagger-item:nth-child(2) { animation-delay: 60ms; }
.stagger-item:nth-child(3) { animation-delay: 120ms; }
.stagger-item:nth-child(4) { animation-delay: 180ms; }
.stagger-item:nth-child(5) { animation-delay: 240ms; }

/* 5. 打字机光标 */
@keyframes cursor-blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 1.1em;
  background: var(--ai-purple);
  animation: cursor-blink 1s step-end infinite;
  vertical-align: text-bottom;
}

/* 6. 价格闪烁 */
@keyframes flash-up   { from { background: rgba(70,190,163,0.25); } to { background: transparent; } }
@keyframes flash-down { from { background: rgba(255,135,103,0.25); } to { background: transparent; } }

/* 7. 涟漪点击反馈 */
@keyframes ripple {
  to { transform: scale(2.5); opacity: 0; }
}

/* ══════ 无障碍 ══════ */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 三、组件改造清单

### 3.1 Phase 1 — 视觉基底重构（最高优先级）

| # | 文件 | 改造内容 | 工作量 |
|---|------|---------|--------|
| 1 | `globals.css` | 全量重写暗色主题 → Dark Glassmorphism Token系统 | 大 |
| 2 | `layout.tsx` | 引入Inter字体(next/font/google)，品牌meta | 小 |
| 3 | `navbar.tsx` | glass-navbar效果，品牌Logo用钴蓝，搜索框毛玻璃 | 中 |
| 4 | `page.tsx` | Bento Grid布局，可拖拽分栏比例（35/65可调） | 中 |
| 5 | `conversation-sidebar.tsx` | glass-sidebar效果，选中项钴蓝指示条 | 中 |
| 6 | `market-overview.tsx` | 玻璃底条，指数数据用font-mono+tabular-nums | 小 |

### 3.2 Phase 2 — 核心组件毛玻璃化

| # | 文件 | 改造内容 | 工作量 |
|---|------|---------|--------|
| 7 | `welcome-screen.tsx` | 渐变Hero区(钴蓝→AI紫径向渐变)，卡片毛玻璃化 | 中 |
| 8 | `chat-panel.tsx` | 头部glass效果，AI状态指示器用渐变流体 | 小 |
| 9 | `message-bubble.tsx` | 用户消息钴蓝渐变，AI消息glass-card风格 | 中 |
| 10 | `chat-input.tsx` | glass-input效果，发送按钮钴蓝渐变+hover缩放 | 中 |
| 11 | `artifact-card.tsx` | glass-card效果，标题栏微光分层，hover发光边框 | 中 |
| 12 | `artifact-panel.tsx` | 空态重设计：渐变背景+毛玻璃capability卡片+脉冲 | 中 |

### 3.3 Phase 3 — 数据展示专业化

| # | 文件 | 改造内容 | 工作量 |
|---|------|---------|--------|
| 13 | `candlestick-chart.tsx` | 图表容器glass-card化，OHLCV crosshair增强 | 中 |
| 14 | `score-radar.tsx` | 雷达图容器毛玻璃化，hover维度详情tooltip | 小 |
| 15 | `capital-flow-chart.tsx` | 柱状图容器毛玻璃，tooltip格式化(万/亿) | 小 |
| 16 | `news-feed.tsx` | 新闻条目glass化，hover边框变亮 | 小 |
| 17 | `investor-personas.tsx` | 4人格卡片glass化，confidence bar用品牌色 | 中 |
| 18 | `fundamental-scorecard.tsx` | 财务指标卡glass化，数字用CountUp动画 | 中 |
| 19 | `technical-panel.tsx` | 技术指标面板glass化，评分数字大号+跳动 | 中 |
| 20 | `risk-radar-chart.tsx` | 风险雷达glass化，风险等级用语义色 | 小 |

### 3.4 Phase 4 — 交互增强

| # | 文件 | 改造内容 | 工作量 |
|---|------|---------|--------|
| 21 | `agent-progress-panel.tsx` | Agent状态用渐变流体(thinking)+弹性checkmark(done) | 中 |
| 22 | `stream-markdown.tsx` | 打字机光标(.typing-cursor)，代码块glass背景 | 中 |
| 23 | `suggested-questions.tsx` | stagger入场动画，pill按钮glass效果 | 小 |
| 24 | `global-search.tsx` | 搜索模态框glass化，结果列表hover发光 | 中 |
| 25 | `command-palette.tsx` | 命令面板glass化，键盘导航高亮用品牌色 | 中 |

### 3.5 Phase 5 — 新增能力（对标fiscal.ai缺失项）

| # | 新增文件 | 功能 | 工作量 |
|---|---------|------|--------|
| 26 | `lib/utils/count-up.ts` | CountUp数字跳动Hook | 小 |
| 27 | `components/common/sparkline.tsx` | 内联迷你折线图（AI回复中嵌入） | 中 |
| 28 | `components/common/stats-card.tsx` | 统计指标卡片（大数字+趋势+sparkline） | 中 |
| 29 | `components/common/glass-card.tsx` | 通用毛玻璃卡片容器（复用基类） | 小 |

---

## 四、逐文件改造详细规格

### 4.1 globals.css — 全量重写

**改造要点**:
- `:root` 浅色主题保留但同步更新品牌色(#3737CC)
- `.dark {}` 完全重写为Dark Glassmorphism Token
- 新增 `.glass-*` 系列工具类
- 新增所有动效@keyframes
- 涨跌色改为蓝绿/橙(--color-up/--color-down)
- 所有间距/圆角/字号使用Token变量

### 4.2 navbar.tsx — 品牌升级

**当前**: 渐变Logo + ghost按钮
**目标**:
```
┌─[钴蓝Logo图标]─AI金融──[对话]──────[🔍 搜索股票... ⌘K]──────[涨跌][主题][⚙]─┐
│  glass-navbar: bg rgba(10,10,26,0.8) + blur(20px) + border-bottom            │
└──────────────────────────────────────────────────────────────────────────────┘
```
- Logo: 钴蓝圆角方块内白色Activity图标
- 搜索框: glass-input效果
- 功能按钮: hover时品牌色发光

### 4.3 page.tsx — Bento Grid布局

**当前**: 固定三栏 sidebar|w-[380px] chat|flex-1 artifacts
**目标**:
```
┌─────────────────────────────────────────────────────┐
│  glass-navbar                                        │
├─────────────────────────────────────────────────────┤
│  market-ticker (glass底条)                            │
├────┬──────────────────┬─────────────────────────────┤
│    │                  │                              │
│侧栏│   Chat面板        │    Artifacts面板              │
│    │   35% (可拖拽)    │    65% (可拖拽)               │
│    │   glass-sidebar   │    glass-card * N            │
│    │                  │    Bento Grid排列              │
│    │                  │                              │
├────┴──────────────────┴─────────────────────────────┤
│  移动端: 底部TabBar (对话/分析)                         │
└─────────────────────────────────────────────────────┘
```
- Chat/Artifacts比例可拖拽调整(ResizablePanel)
- 宽度持久化到localStorage
- Artifacts内部用CSS Grid自适应排列

### 4.4 message-bubble.tsx — 消息气泡重设计

**用户消息**:
- 背景: `linear-gradient(135deg, #3737CC, #4F4FE6)` (钴蓝渐变)
- 文字: 白色
- 圆角: rounded-2xl rounded-br-md
- 头像: 钴蓝圆形 + 白色"我"字

**AI消息**:
- 背景: glass-card (rgba(255,255,255,0.04) + blur)
- 边框: rgba(255,255,255,0.08)
- 圆角: rounded-2xl rounded-bl-md
- 头像: AI紫渐变(#6B5EE4→#3737CC) + 白色"AI"

**Artifact标签**:
- 每种类型独立配色(lucide图标+文字)
- K线:钴蓝 / 技术指标:蓝绿 / 资金流:AI紫 / 新闻:琥珀 / 风险:珊瑚橙

### 4.5 welcome-screen.tsx — Hero区重设计

```
┌──────────────────────────────────────┐
│  ╭─ 径向渐变背景 ─────────────────╮  │
│  │  radial-gradient(              │  │
│  │    circle at 50% 0%,           │  │
│  │    #3737CC 0%,                 │  │
│  │    #212185 40%,                │  │
│  │    #06060F 100%                │  │
│  │  )                             │  │
│  │                                │  │
│  │    [Brain] [Sparkles] [Zap]    │  │
│  │                                │  │
│  │    AI金融分析助手               │  │
│  │    (渐变文字 钴蓝→蓝绿)         │  │
│  │                                │  │
│  │    13个智能Agent · 实时数据     │  │
│  ╰────────────────────────────────╯  │
│                                      │
│  ┌─glass─┐  ┌─glass─┐               │
│  │📈个股  │  │📊行业  │               │
│  │深度分析│  │横向对比│               │
│  └───────┘  └───────┘               │
│  ┌─glass─┐  ┌─glass─┐               │
│  │📉市场  │  │🛡风险  │               │
│  │全景概览│  │预警评估│               │
│  └───────┘  └───────┘               │
│                                      │
│  [沪深300] [北向资金] [板块轮动] ...  │
└──────────────────────────────────────┘
```

### 4.6 artifact-card.tsx — 毛玻璃Artifact容器

- 容器: glass-card效果
- 标题栏: 微弱分层背景(rgba(255,255,255,0.02)) + bottom-border
- 图标: lucide-react组件(非emoji)，用各artifact类型的语义色
- 工具栏: 导出/全屏/折叠 ghost按钮，hover时品牌色
- 入场动画: glass-enter (slide-up + fade + scale)
- 全屏模式: scale过渡动画(300ms)
- 折叠/展开: max-height过渡 + opacity

---

## 五、新增组件规格

### 5.1 GlassCard 通用容器

```tsx
// components/common/glass-card.tsx
interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;      // 是否启用hover效果
  glow?: 'brand' | 'ai' | 'none'; // 发光色
  padding?: 'sm' | 'md' | 'lg';
}
```

### 5.2 StatsCard 统计卡片

```tsx
// components/common/stats-card.tsx
interface StatsCardProps {
  label: string;         // "市值" "PE" "涨跌幅"
  value: number;
  format: 'number' | 'percent' | 'currency' | 'large';
  change?: number;       // 变动值
  sparklineData?: number[]; // 内联趋势线
  icon?: ReactNode;
}
```
- 大号数字(text-3xl font-mono) + CountUp动画
- 变动值用语义色(up/down)
- 右下角sparkline迷你图(40x20px)

### 5.3 Sparkline 内联迷你图

```tsx
// components/common/sparkline.tsx
interface SparklineProps {
  data: number[];
  width?: number;   // 默认80
  height?: number;  // 默认24
  color?: string;   // 默认brand-primary
  showDot?: boolean; // 末端圆点
}
```
- 纯SVG渲染，无依赖
- 颜色随正负变化(up蓝绿/down珊瑚)

### 5.4 useCountUp Hook

```tsx
// lib/utils/count-up.ts
function useCountUp(target: number, options?: {
  duration?: number;    // 默认800ms
  decimals?: number;    // 默认2
  startOnMount?: boolean;
}): { value: string; ref: RefObject }
```
- 使用requestAnimationFrame
- spring缓动

---

## 六、涨跌色系统

### 6.1 双模式支持

| 模式 | 涨 | 跌 | 零 |
|------|-----|-----|-----|
| 中国(cn) | #EF4444 红 | #10B981 绿 | --text-secondary |
| 国际(us) | #46BEA3 蓝绿 | #FF8767 橙 | --text-secondary |

### 6.2 CSS变量实现

```css
/* 默认中国模式 */
:root, [data-color-scheme="cn"] {
  --stock-up: #EF4444;
  --stock-down: #10B981;
}
[data-color-scheme="us"] {
  --stock-up: #46BEA3;
  --stock-down: #FF8767;
}
```

---

## 七、响应式断点

| 断点 | 宽度 | 布局 |
|------|------|------|
| Mobile | < 640px | 单栏 + 底部TabBar + 侧边栏Drawer |
| Tablet | 640-1024px | 双栏(Chat+Artifacts Tab切换) |
| Desktop | 1024-1440px | 三栏(sidebar\|chat\|artifacts) |
| Wide | > 1440px | 三栏 + artifacts 2列grid |

---

## 八、无障碍要求

| 要求 | 规格 |
|------|------|
| 对比度 | 正文 ≥ 4.5:1, 大标题 ≥ 3:1 |
| 触摸目标 | 最小 44×44px |
| 键盘导航 | 所有交互元素可Tab到达 |
| ARIA | 关键区域标注role/aria-label |
| 减弱动效 | prefers-reduced-motion全局支持 |
| 色觉 | 涨跌不仅靠颜色，加箭头/文字 |

---

## 九、执行计划与排期

### Phase 1: 视觉基底（#1-#6） — 优先级P0
**范围**: globals.css + layout + navbar + page + sidebar + market
**预计改动**: 6个文件
**验证**: 启动前后端，Playwright截图对比

### Phase 2: 核心组件（#7-#12） — 优先级P0
**范围**: welcome + chat-panel + message-bubble + chat-input + artifact-card + artifact-panel
**预计改动**: 6个文件
**验证**: 发送分析请求，截图AI回复+Artifact渲染

### Phase 3: 数据展示（#13-#20） — 优先级P1
**范围**: 8个Artifact组件全部glass化
**预计改动**: 8个文件
**验证**: 完整分析流程，所有artifact类型渲染

### Phase 4: 交互增强（#21-#25） — 优先级P1
**范围**: agent-progress + stream-markdown + suggested-questions + 搜索
**预计改动**: 5个文件
**验证**: AI流式输出效果，Agent状态动画

### Phase 5: 新增能力（#26-#29） — 优先级P2
**范围**: 4个新组件
**预计改动**: 4个新文件
**验证**: StatsCard+Sparkline在artifact中展示

---

## 十、风险与回滚

| 风险 | 缓解措施 |
|------|---------|
| 毛玻璃性能 | 同屏≤5个blur元素，移动端降级为半透明无blur |
| 品牌色过深 | 钴蓝在小字体下可能对比度不足，需测试+备选更亮色 |
| 动效过多 | 严格遵循purpose-driven原则，每个动效必须有功能目的 |
| 兼容性 | backdrop-filter在Safari需-webkit-前缀，Firefox 103+支持 |
| 回滚 | 每Phase独立commit，可按Phase回滚 |

---

## 十一、验收标准

1. **视觉**: 截图与fiscal.ai视觉品质相当，Dark Glassmorphism风格统一
2. **功能**: 所有现有功能不受影响（Chat/Artifact/Agent全链路）
3. **性能**: 首屏加载 < 3s，毛玻璃不造成明显卡顿
4. **无障碍**: 所有文本对比度 ≥ 4.5:1
5. **响应式**: Mobile/Tablet/Desktop三端可用
6. **动效**: prefers-reduced-motion下所有动画静默

---

**文档编制**: 🌿少校 (AI金融分析系统 PM)
**审批人**: Comdr
**状态**: 待审批
