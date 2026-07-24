# UI Renovation Plan A–D（精简版）

> **文档状态**：**待 Comdr 审批**  
> **编制时间**：2026-07-24 18:21:05 +08:00  
> **性质**：设计草案（docs only）；**禁止**在本轮修改 `frontend/` 源码、**禁止 push**  
> **对标基线**：`docs/FRONTEND_REDESIGN_PLAN.md`（2026-03-26 v3.0）+ 当前实现（Next.js 16.2.9 / Dark Glassmorphism 部分落地）  
> **约束铁律**：#1 金融零假值 · #2 禁用 Playwright（真测用 WebBridge）· #3 不启全量 build/服务于 worker 批内

---

## 0. 目标与非目标

### 0.1 目标

| # | 目标 | 验收口径 |
|---|------|----------|
| G1 | 统一视觉语言（Dark Glass + 钴蓝品牌 + 语义涨跌色） | 全站 token 一致，无硬编码色块散落 |
| G2 | 信息架构清晰：首页对话 / 仪表盘 / 个股 / 组合 四主场景 | 导航 ≤ 1 次跳转达主任务 |
| G3 | AI 工作区可读：进度 / 工具调用 / 产物卡片分层 | 流式中无布局抖动、产物可折叠 |
| G4 | 金融数据呈现专业化：骨架态 / 空态 / 降级态三态完备 | 无假数占位（铁律 #1） |
| G5 | 移动端可用：底栏 + Drawer，核心路径可完成 | 375px 宽无横向溢出 |

### 0.2 非目标（本轮不做）

- 不重写后端 API / OpenAPI / schema
- 不引入新 UI 框架（保持 shadcn + Tailwind + Recharts）
- 不做品牌重塑（Logo/命名）与营销落地页
- 不扩 agent 能力（Plan/Skills/Memory 属 `dojo-agents-absorption-plan`）
- 不启全量 `npm run build` 作为默认验证（优先 tsc + eslint + 定点 WebBridge）

---

## 1. 现状快照（只读盘点）

### 1.1 已有资产（可复用，禁止推倒重来）

| 层 | 路径 | 状态 |
|----|------|------|
| Design tokens | `frontend/src/app/globals.css` | Dark/Light 双主题 + 毛玻璃变量已部分落地 |
| 布局壳 | `layout.tsx` + `navbar` + `mobile-tab-bar` + `mobile-drawer` | main 为全站滚动容器 |
| 市场条 | `components/market/market-overview.tsx` | sticky 指数栏 + SSE |
| AI 对话 | `components/chat/*` + `components/agent/*` | 流式 / 工具卡 / 审批 / 进度 |
| 产物 | `components/artifacts/*` + `charts/*` | K线 / 资金流 / 雷达 / ESG 等 |
| 状态 | `lib/stores/*` + hooks | zustand persist + 名称缓存守卫 |

### 1.2 主要缺口（驱动 A–D 分期）

| ID | 缺口 | 影响场景 | 建议阶段 |
|----|------|----------|----------|
| U1 | token 使用不均，局部硬编码色/间距 | 全站 | A |
| U2 | 卡片/空态/骨架态模式不统一 | dashboard / stock | A |
| U3 | 首页三栏比例与 Bento 模块未固化 | `/` | B |
| U4 | 个股页 tab 信息密度与降级占位不齐 | `/stock/[code]` | B |
| U5 | Agent 产物区折叠/固定/全屏交互弱 | chat artifact-panel | C |
| U6 | 组合/对比/筛选视觉次要页不一致 | portfolio/compare/screener | C |
| U7 | 设置页信息架构扁平、风控开关难找 | `/settings` | D |
| U8 | 动效与可访问性（focus/reduced-motion）未系统化 | 全站 | D |

---

## 2. 设计原则（审批后写死）

1. **只改原件优先**：token → 共用组件 → 页面；禁止平行新建“v2 页面树”。
2. **数据诚实**：loading = Skeleton/Spinner；无数据 = "—"/"暂无"；禁止 mock 数值（铁律 #1）。
3. **密度可调**：专业默认高密度；移动端降密度，不删关键数字。
4. **AI 与行情分离**：行情条始终可见；AI 流不阻塞指数/报价刷新。
5. **渐进交付**：每阶段可独立合并、可独立回滚；阶段门禁未过不得开下阶段。

---

## 3. 阶段 A — Design System 固化（Foundation）

**工期建议**：2–3 人日 · **风险**：Low · **依赖**：无

### 3.1 范围

| 项 | 动作 | 触达文件（预期） |
|----|------|------------------|
| A1 Token 收口 | 补齐/对齐 glass、涨跌、AI 紫、间距 scale；禁止页面内魔法数字色 | `globals.css` |
| A2 共用原语 | 统一 `GlassCard` / `StatsCard` / `Skeleton` / 空态 EmptyState 用法 | `components/common/*` `ui/*` |
| A3 图表安全壳 | 全站图表经 `SafeResponsiveContainer`；零尺寸不挂载 Recharts | `components/charts/*` |
| A4 语义色映射 | 涨 `color-up` / 跌 `color-down` 全站替换散落 green/red | 组件类名扫尾 |
| A5 文档 | 本文件 §3 验收勾选 + `docs/design/README.md` 领地更新 | docs only |

### 3.2 验收

- [ ] `tsc --noEmit` 0 错误
- [ ] 关键组件 eslint 0 error
- [ ] 视觉：暗/亮主题切换无破版
- [ ] 无新增假数据路径（grep mock/fallback 数值）

### 3.3 回滚

`git checkout -- frontend/src/app/globals.css frontend/src/components/common frontend/src/components/ui`（按实际 diff 收窄）

---

## 4. 阶段 B — 主路径信息架构（Core IA）

**工期建议**：3–4 人日 · **风险**：Medium · **依赖**：A 门禁通过

### 4.1 范围

| 项 | 动作 | 触达 |
|----|------|------|
| B1 首页 | 固化「指数条 + 对话主区 + 产物侧栏」；比例可拖拽复用 `resizable-panel` | `app/page.tsx` chat/* |
| B2 仪表盘 | 自选 / 持仓 / 市场概览 Bento 栅格；空自选引导，不填假行情 | `app/dashboard/*` |
| B3 个股 | Tab 顺序：报价 → K线 → 基本面 → 资金流 → 另类/ESG；缺数 Skeleton | `app/stock/[code]/*` |
| B4 导航 | Navbar 主入口收敛；次要入口进「更多」 | `layout/navbar.tsx` mobile-* |

### 4.2 验收

- [ ] WebBridge：`/` `/dashboard` `/stock/600519` 三页无 Hydration 报错
- [ ] 指数条滚动吸顶仍可见
- [ ] 缺名股票显示 code 占位，不把 code 写入 name 持久化
- [ ] 离线/503 市场指数安静降级（"—"），无 error toast 刷屏

### 4.3 回滚

按页面文件粒度 revert；不触 stores schema 时无需 migrate 回滚。

---

## 5. 阶段 C — AI 工作区与次要页（Agent UX + Secondary）

**工期建议**：3–5 人日 · **风险**：Medium · **依赖**：B 门禁通过

### 5.1 范围

| 项 | 动作 | 触达 |
|----|------|------|
| C1 产物面板 | 折叠 / 固定宽度 / 全屏；标题精简（已有「结果」文案） | `artifact-panel.tsx` |
| C2 工具时间线 | ToolCall 时间线与进度条对齐；失败态可重试文案 | `agent/*` `chat/tool-call-*` |
| C3 审批卡 | Pending approval 视觉优先级高于普通消息 | `approval-card.tsx` |
| C4 组合/对比/筛选 | 视觉对齐 GlassCard + 统一表格密度 | portfolio/compare/screener |
| C5 新闻/扫描 | 列表空态与加载骨架统一 | `app/news` 相关 |

### 5.2 验收

- [ ] SSE 流式中产物区不抖动（固定 min-height 策略）
- [ ] 工具失败展示错误摘要，不抛白屏
- [ ] portfolio / compare 在 1280px / 375px 两档可用
- [ ] 定时器均有 cleanup（防 HA-5 回归）

### 5.3 回滚

分模块 revert；agent 面板与次要页可拆两次 commit 降低风险。

---

## 6. 阶段 D — 抛光、无障碍与设置（Polish）

**工期建议**：2–3 人日 · **风险**：Low–Medium · **依赖**：C 门禁通过

### 6.1 范围

| 项 | 动作 |
|----|------|
| D1 Settings IA | 分组：账户/模型/数据源(Wind)/通知/实验；危险操作二次确认 |
| D2 Motion | 尊重 `prefers-reduced-motion`；数字 count-up 可关 |
| D3 A11y | focus-visible 环、对话框滚动锁（BM-3）、aria-label 扫尾 |
| D4 性能 | 重图表路由动态 import；避免首页同步拉全量产物组件 |
| D5 文档收口 | 更新本计划验收勾选 + CHANGELOG + TODO；同步 `docs/design/README.md` |

### 6.2 验收

- [ ] 键盘可完成：搜索股票 → 加入自选 → 打开个股
- [ ] Settings 中 Wind 配额入口可见且链到既有 `/api/wind/quota` 展示
- [ ] Lighthouse/手工：无严重对比度问题（暗色主路径）
- [ ] 无新 eslint/tsc 债

### 6.3 回滚

设置页与动效开关独立 revert；token 不动则视觉回退成本低。

---

## 7. 里程碑与门禁

```
A Foundation ──gate──► B Core IA ──gate──► C Agent+Secondary ──gate──► D Polish
     │                    │                      │                        │
   tsc/eslint          WebBridge×3            SSE+次要页               a11y+docs
```

| 门禁 | 必过项 | 失败处置 |
|------|--------|----------|
| Gate-A | token 一致 + tsc/eslint | 停 B，修 A |
| Gate-B | 三主路径 WebBridge + 铁律 #1 | 停 C |
| Gate-C | 流式稳定 + 次要页可用 | 停 D |
| Gate-D | a11y + 文档同步 + TODO 清项 | 标记完成待 Comdr 终验 |

---

## 8. 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 大面积 className 替换引入回归 | M | 按组件域分 commit；每域 tsc |
| 暗色 token 改动导致图表对比度下降 | M | 图表色走 CSS 变量，改后 WebBridge 截图 |
| 布局改动触发 Hydration mismatch | H | 动态状态仅 mount 后读（既有模式） |
| 内存压力（本地 16G） | H | 禁全量 vitest/build；单 spec + tsc |
| 与 dojo-agents 文档交叉冲突 | L | UI 不改 agent 协议；只动呈现层 |

---

## 9. 明确不做清单（防范围漂移）

1. 不新建 `frontend-v2/` 或平行路由树  
2. 不替换 Recharts 为其他图表库（本轮）  
3. 不改 Flask 路由契约 / OpenAPI  
4. 不把 Playwright 重新引入 CI  
5. 不在未审批前改 `globals.css` 品牌主色数值（可提案，先批后改）

---

## 10. 与历史文档关系

| 文档 | 关系 |
|------|------|
| `docs/FRONTEND_REDESIGN_PLAN.md` | 上游详细规范；本文件是**可执行分期裁剪** |
| `docs/FRONTEND_ARCHITECTURE.md` | 架构事实源；改布局前必读 |
| `docs/design/dojo-agents-absorption-plan.md` | Agent 能力边界；UI 只消费不扩展协议 |
| `docs/design/DELIVERY-STATUS.md` | 交付真相表；阶段完成后回写 UI 行项 |

---

## 11. 审批栏

| 项 | 内容 |
|----|------|
| 状态 | **待 Comdr 审批** |
| 请求批准 | 阶段 A→D 范围、门禁、非目标 |
| 批准后首动 | 仅开阶段 A（token + 共用原语），仍禁 push 除非另令 |
| 驳回时 | 标注驳回条款号，修订本文件后再次呈批 |
| 起草人 | 香草少校（PM） |
| 起草时间 | 2026-07-24 18:21:05 +08:00 |

**Comdr 批注区**（手填）：

```
[ ] 批准全部 A–D
[ ] 批准仅 A（其余再议）
[ ] 有条件批准：________________
[ ] 驳回：________________
签名/时间：________________
```

---

## 12. TODO（执行清单 · 审批前仅文档态）

### 12.1 审批前（docs only）

- [x] 创建 `docs/design/ui-renovation-plan.md` 精简版 A–D
- [ ] Comdr 填写 §11 审批栏
- [ ] 审批结果同步 `TODO.md` / `CHANGELOG.md` / `docs/design/README.md`

### 12.2 阶段 A（批准后解锁）

- [ ] A1 Token 收口审计表（列出硬编码色命中）
- [ ] A2 EmptyState / Skeleton 用法统一 PR
- [ ] A3 图表 SafeResponsive 覆盖核对
- [ ] A4 涨跌语义色扫尾
- [ ] Gate-A 证据落盘（tsc/eslint 日志路径）

### 12.3 阶段 B

- [ ] B1 首页比例与产物侧栏
- [ ] B2 Dashboard Bento
- [ ] B3 个股 Tab 顺序与降级
- [ ] B4 导航收敛
- [ ] Gate-B WebBridge 三页证据

### 12.4 阶段 C

- [ ] C1 产物面板交互
- [ ] C2 工具时间线
- [ ] C3 审批卡优先级
- [ ] C4 portfolio/compare/screener 对齐
- [ ] C5 新闻/扫描空态
- [ ] Gate-C SSE 稳定证据

### 12.5 阶段 D

- [ ] D1 Settings IA
- [ ] D2 reduced-motion
- [ ] D3 a11y 扫尾
- [ ] D4 图表路由动态 import
- [ ] D5 文档收口
- [ ] Gate-D 终验 → 标记完成

### 12.6 持续约束

- [ ] 全程禁 push（除非 Comdr 书面解除）
- [ ] 全程禁 Playwright
- [ ] 全程禁假数据占位
- [ ] free pages < 5000 停手

---

## 13. 变更记录

| 时间 | 版本 | 说明 |
|------|------|------|
| 2026-07-24 18:21:05 +08:00 | v0.1-draft | 初稿 A–D 精简版，呈 Comdr 审批 |

---

*一旦本设计目录结构变化，请更新 `docs/design/README.md` 领地标记。*
