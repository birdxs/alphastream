# StockAnal UI 改造方案 A–D

**审批状态：已通过 2026-07-24 Comdr 全量 A–D**  
**代码状态：S-UI-0~3 + S-UI-charts 已落地 · S-UI-4 curl + CDP 五路由 + 主题已做 · api-docs swagger 代理已修（`8cdfe24`） · §8.1 sticky/Agent/HITL 等仍未勾（仍禁 push）**  
版本：`v1.6-sui4-final-snapshot` · 日期：`2026-07-24`  
作者：香草少校（PM 方案稿）· 范围：本地开发 · **禁止 push**

---

## 1. 审批栏

| 项 | 勾选 | 说明 |
|---|---|---|
| **通过（允许进入 S-UI-0 起编码）** | [x] | **已通过 2026-07-24 Comdr 全量 A–D** |
| **驳回（退回修订）** | [ ] | 须写明驳回条款与修订要求 |
| **有条件通过** | [ ] | 仅允许 Token 冻结，A–D 仍锁 |
| 审批人 | Comdr | |
| 审批时间（+08:00） | 2026-07-24 | 全量 A–D 一次通过 |
| 批注意见 | 全部审批通过，立即执行 | |

**锁已解除**：Comdr 已通过；S-UI-0~3 + charts token 代码已落地。S-UI-4 **curl + CDP 五路由/假数双窗 + 主题切换**已完成；**api-docs** BE 302/200 + FE shell + **`:3000/static/swagger.json` 代理 200（`8cdfe24`，此前 404 已修）**；剩余 **§8.1 sticky 强滚、Agent/HITL/provenance/scorecard 真 SSE、浏览器 Swagger 点选、涨跌色有数帧**。仍禁止 push；禁止启动全量 `npm run build` 做无关改造。

---

## 2. 第一性原理

### 2.1 产品不是「行情看板」，是 **Agent 决策工位**

用户主任务链：

1. **看见可信市场上下文**（指数/自选/持仓，铁律 #1 零假值）
2. **发起/续聊 Agent 分析**（SSE、工具调用、进度）
3. **审阅可追溯结论**（provenance、scorecard、artifact）
4. **HITL 批准/驳回**（Plan 状态机节点上的人机闸门）
5. **沉淀到工位**（会话、任务历史、对比、组合）

UI 的成功标准 = 缩短「问题 → 有证据的决策」路径，而非堆叠更多卡片。

### 2.2 可信数据优先于视觉炫技

- 加载：Skeleton /「—」/「加载中」；禁止 demo 股价与假指数。
- 降级：503/空 indices 安静占位，不闪假数。
- 来源：关键数字旁可挂 `source` / provenance 轻量标识（C 工位重点）。

### 2.3 信息架构（IA）服务决策，不服务页面目录

首页 = **工位入口**（上下文条 + 对话/Agent 主舞台 + 结果坞），  
二级页 = 工具间（个股/组合/扫描/设置），  
禁止首页同时当「产品官网 + 仪表盘 + 聊天室」。

---

## 3. 现状诊断

### 3.1 视觉方言分裂

| 区域 | 现象 | 影响 |
|---|---|---|
| `globals.css` + Tailwind | token 半齐，语义色与图表色未冻结 | 同语义不同灰阶 |
| `market/*` | ticker sticky 后仍与卡片圆角/间距不统一 | 「行情条」像另一产品 |
| `chat/*` + `agent/*` | 气泡、进度、侧栏密度不一致 | Agent 流难扫读 |
| `artifacts/*` | 卡片边框/标题层级随意 | 结论可信度被稀释 |
| charts | SafeResponsiveContainer 已治 -1 警告，主题色未统一 | 日/夜切换跳动 |

### 3.2 IA 叠层

- 首页同时承载：指数栏、AI 工作区、入口导航、局部 dashboard 语义。
- Dashboard / Watchlist / Portfolio 与首页信息重复，用户不知「默认工位」在哪。
- Agent 侧栏、会话侧栏、artifact 面板三层可同时开，宽度争抢。

### 3.3 日志态 / 运行态 UI

- 503 降级、名称缺省 `null`、Wind 配额告警等，前端多为 console 或弱文案。
- 缺少统一 **SystemToast / InlineStatus** 语义（info/warn/degraded/error）。
- 开发态噪音与用户态提示未分层（铁律 #1 相关降级必须用户可见且不吓人）。

### 3.4 高度链与滚动

- 已修：`html/body height:100%` + `main overflow-y-auto` + 指数 sticky。
- 风险残留：嵌套 `overflow-y-auto`（BM-4 类）、modal 滚动锁（BM-3 类）在部分路由仍可能复发。
- 改造时 **禁止** 破坏 main 作为全站滚动祖先的约定。

---

## 4. 范围与非目标

### 4.1 范围 A–D

| 代号 | 名称 | 目标一句话 |
|---|---|---|
| **A** | 设计系统 | 冻结 Token + 基础组件皮肤，消灭视觉方言 |
| **B** | 首页 IA | 首页收敛为「上下文条 + Agent 主舞台 + 结果坞」 |
| **C** | Agent 工位 | 对话/进度/HITL/provenance/scorecard/artifact 一体工位 |
| **D** | 皮肤 | 日/夜（及可选高对比）主题，仅换肤不改 IA |

### 4.2 非目标（本方案明确不做）

- 不改后端路由契约、OpenAPI、schema 校验逻辑。
- 不接真券商、不改 Wind 积分策略、不做 Plan 真 step 运行时（见 dojo 未做清单）。
- 不引入 Playwright；真测仅 CDP / Kimi WebBridge / curl。
- 不重写图表库、不换 Zustand、不升级 Next major。
- 不新建大型 UI 框架目录；优先改现有 `frontend/src/**`。
- 未批前 **零** frontend 业务编码。

---

## 5. Token 草案表

> 冻结后写入 `frontend/src/app/globals.css` `@theme` / CSS 变量；数值可 ±1 档微调，**语义名不可随意改**。

### 5.1 色（语义）

| Token | 日间 | 夜间 | 用途 |
|---|---|---|---|
| `--bg-canvas` | `#F7F8FA` | `#06060F` | 页面底 |
| `--bg-surface` | `#FFFFFF` | `#0E0E1A` | 卡片/面板 |
| `--bg-elevated` | `#FFFFFF` | `#16162A` | 浮层/sticky |
| `--border-subtle` | `#E6E8EF` | `#2A2A3D` | 分割 |
| `--text-primary` | `#0F172A` | `#F1F5F9` | 主文 |
| `--text-secondary` | `#64748B` | `#94A3B8` | 次文 |
| `--text-muted` | `#94A3B8` | `#64748B` | 占位/— |
| `--accent` | `#4F46E5` | `#818CF8` | 主行动 |
| `--accent-muted` | `#EEF2FF` | `#1E1B4B` | 选中底 |
| `--up` | `#DC2626` | `#F87171` | 涨（A 股红） |
| `--down` | `#16A34A` | `#4ADE80` | 跌（A 股绿） |
| `--warn` | `#D97706` | `#FBBF24` | 降级/配额 |
| `--danger` | `#B91C1C` | `#FCA5A5` | 错误 |
| `--ok` | `#059669` | `#34D399` | 成功/HITL 通过 |

### 5.2 字号

| Token | 值 | 场景 |
|---|---|---|
| `--fs-xs` | 12px | 来源标签、provenance |
| `--fs-sm` | 13px | 辅助说明 |
| `--fs-md` | 14px | 正文/对话 |
| `--fs-lg` | 16px | 面板标题 |
| `--fs-xl` | 20px | 页面标题 |
| `--fs-num` | 15px tabular | 价格/涨跌幅 |

### 5.3 间距 / 圆角 / 阴影

| Token | 值 |
|---|---|
| `--space-1`…`--space-8` | 4 / 8 / 12 / 16 / 24 / 32 / 40 / 48 px |
| `--radius-sm/md/lg` | 6 / 10 / 16 px |
| `--shadow-elev` | `0 8px 24px rgba(0,0,0,.08)`（夜：更高透明度） |
| `--z-sticky` | 20 |
| `--z-modal` | 50 |
| `--z-toast` | 60 |

### 5.4 运动

| Token | 值 | 约束 |
|---|---|---|
| `--ease-std` | `cubic-bezier(.2,.8,.2,1)` | 面板展开 |
| `--dur-fast` | 120ms | hover |
| `--dur-med` | 200ms | 侧栏 |
| 禁止 | 无意义 loop 动画 | 金融场景克制 |

---

## 6. 文件落点（实现时只改下列既有路径）

| 落点 | 角色 |
|---|---|
| `frontend/src/app/globals.css` | Token 源、高度链、滚动约定 |
| `frontend/src/app/layout.tsx` | shell、main 滚动、字体、prefetch |
| `frontend/src/app/page.tsx` | **B** 首页 IA |
| `frontend/src/app/dashboard/page.tsx` | 与首页职责对齐/降噪 |
| `frontend/src/app/settings/**` | D 主题开关、Wind 等设置视觉 |
| `frontend/src/app/portfolio/**` | 二级工具间皮肤 |
| `frontend/src/app/stock/**` | 个股页密度与 token |
| `frontend/src/components/chat/**` | **C** 对话主舞台 |
| `frontend/src/components/agent/**` | **C** 进度/侧栏/HITL |
| `frontend/src/components/market/**` | 指数栏/概览 |
| `frontend/src/components/artifacts/**` | 结果坞、scorecard 视觉 |
| `frontend/src/components/layout/**` | 顶栏/导航/抽屉 |
| `frontend/src/components/charts/**` | 图表色绑定 token |
| `frontend/src/lib/stores/**` | 仅主题 preference（若需），禁脏 name 回潮 |
| `docs/design/ui-renovation-plan.md` | 本方案（唯一 UI 改造权威） |
| `TODO.md` | 「UI 改造 A–D」跟踪 |

**禁止**：新建平行 `frontend/src/ui-v2/**` 整树替换；特例须走附录 C 审批。

---

## 7. Sprint 计划 S-UI-0 ~ S-UI-4

### 7.0 S-UI-0 Token 冻结

| 项 | 内容 |
|---|---|
| **目标** | 审批通过后，将 §5 写入 CSS 变量并文档化；无业务 UI 大改 |
| **文件** | `globals.css`、本方案 §5 定稿、`TODO.md` 勾选 |
| **验收** | 变量可在 DevTools 见；日/夜 class 切换变量生效；无视觉回归强制 |
| **回滚** | 还原 `globals.css` token 段 |
| **依赖** | Comdr 审批通过 |

### 7.1 S-UI-1 范围 A 设计系统

| 项 | 内容 |
|---|---|
| **目标** | 按钮/输入/卡片/Badge/Status/Skeleton 统一；涨跌色绑定 `--up/--down` |
| **文件** | `components/ui/*`（若存在）、`layout/*`、`charts/*` 色引用、`globals.css` |
| **验收** | tsc 0；eslint 改动文件 0 error；抽样 3 页无裸 hex 扩散（允许图表临时 map） |
| **回滚** | 按文件 `git checkout -- <paths>` |
| **非目标** | 不改首页 IA、不改 Agent 流程 |

### 7.2 S-UI-2 范围 B+C 首页 IA + Agent 工位

| 项 | 内容 |
|---|---|
| **目标** | 首页 = 上下文条（指数 sticky）+ 主对话/Agent + 右侧/底部结果坞；HITL/Plan 节点可见 |
| **文件** | `page.tsx`、`chat/*`、`agent/*`、`artifacts/*`、`market/market-overview.tsx` |
| **验收** | ① 滚动时指数栏仍可见 ② 无假数 ③ Agent 进行中进度与 artifact 不互相遮死 ④ HITL 入口可发现 ⑤ 高度链不破 |
| **回滚** | 还原 B/C 涉及文件；保留 A token 可选 |
| **风险** | 侧栏宽度争抢；须定义 z-index 与折叠优先级 |

### 7.3 S-UI-3 范围 D 皮肤

| 项 | 内容 |
|---|---|
| **目标** | 日/夜（可选高对比）一键切换；图表与涨跌色跟随 |
| **文件** | `layout.tsx`、主题 provider/store、`settings`、charts token map |
| **验收** | 切换无闪白；localStorage 主题 key 可迁移；对比度可读 |
| **回滚** | 移除主题切换，固定现网默认夜/日之一 |

### 7.4 S-UI-4 回归验收

| 项 | 内容 |
|---|---|
| **目标** | 路由矩阵 + 铁律 #1/#2/#3 合规复验 |
| **文件** | 无新功能；文档与截图证据目录 `/tmp/stockanal_ui/**` |
| **验收** | 见 §8 总清单全勾；聚焦 tsc/eslint；禁全量 vitest/Playwright |
| **回滚** | 标签回退到审批前 commit |

**建议顺序**：S-UI-0 → 1 → 2 → 3 → 4；**禁止**跳过 0 直接做 2。

---

## 8. 验收总清单

> **分层口径（禁止虚构完成 · 2026-07-24 S-UI-4 v1.6 终态快照）**  
> - **代码层**：S-UI-0~3 + **S-UI-charts** 已交付（charts/artifacts 绑 design tokens，commit `8ba801a`）。  
> - **工程 + curl 启服**：`tsc --noEmit` 0；长页滚动代码审；**真启** 8888/3000 并 curl 路由矩阵。  
> - **CDP 浏览器路由矩阵（已做）**：Chrome `:9222`；五路由 + 首页 5s/15s；`market_indices` 对照无假价。  
> - **残余（v1.5）**：亮/暗切换截图 + 切换后 bg 亮度采样；`/api-docs` curl+浏览器 shell（当时 FE swagger.json **404**）。  
> - **代理修复（`8cdfe24` / v1.6）**：`next.config.ts` 开发 rewrite `/static/:path*`→`:8888`；curl `:3000/static/swagger.json` **200**（14483B）；浏览器 Swagger **交互点选仍未强测**。sticky **未强测**（首页内容未溢出）；Agent 真 SSE **诚实跳过**（本轮 `MOCK_LLM=1`）。

### 8.1 产品/视觉（浏览器 · **部分完成**）

- [x] 首页职责一句话可解释（工位，非官网）· **CDP：对话+结果工位壳可见（本机 AI 流 timed out 文案亦真，非假行情）**
- [ ] Token 语义色全站一致；涨红跌绿（A 股）无反 · **代码已绑 token；涨跌色对照仍依赖有数指数帧**
- [ ] 指数 sticky 在 main 滚动下可见 · **DOM 有 `sticky top-0 z-20`；v1.5 首页 main `canScroll=false`（scrollHeight=clientHeight）→ 记录「内容未溢出无法强测 sticky」**
- [ ] Agent 工位：输入 → 流式 → 工具/进度 → 结论/artifact 路径清晰 · **壳可见；真 SSE 未跑（MOCK_LLM=1 诚实跳过）**
- [ ] HITL 批准/驳回控件可达、状态可读 · **未点验**
- [ ] provenance 轻量展示（来源/时间）不挡主结论 · **未点验**
- [ ] scorecard 维度可读（coverage/agreement/tool/confidence）· **未点验**
- [x] 空态/降级仅 Skeleton 或「—」/`---`，无假行情 · **首页双窗 `---`；dashboard「暂无指数」；portfolio `—`；对照 503 DEGRADED（前轮）/ cache 真数（v1.5 可见上证 3814.20 等，来自 API 非 mock UI）**
- [x] 日/夜切换无布局塌陷 · **v1.5 CDP：navbar `aria-label=切换主题` 亮↔暗；light `rgb(247,248,250)` ↔ dark `rgb(10,10,26)`；切换采样 `flashWhite=false`；截图 `sui4_theme_before_light.png` / `sui4_theme_after_dark.png`；`layout.tsx` 内联 FOUC 守卫 + reload 后 class 与 storage 一致**

### 8.2 工程/纪律

- [x] 未批零编码（审批已通过后才编码）
- [x] 改动仅 frontend 既有文件 + 本文档/TODO（含 S-UI-charts）
- [x] `tsc --noEmit` = 0（S-UI-charts + S-UI-4）
- [x] 未启 Playwright；未全量 vitest（铁律 #2/#3）
- [x] **未 push**
- [x] curl 真数对照：`/health` 200；路由 200；`market_indices` 可 503 DEGRADED 或 cache 真数（诚实来源头）
- [x] 铁证：关键页 CDP 截图 · `/tmp/stockanal_ui/sui4_*.png`（路由六张 + 主题 before/after + api-docs FE/BE）

### 8.3 回归路由矩阵（curl + CDP 五路由）

| 路由 | 检查点 | 代码层 | curl HTTP | 浏览器终验 |
|---|---|---|---|---|
| `/` | 工位 IA、指数、对话 | 已落地 | [x] 200 | [x] CDP 5s/15s：无假价；截图 home_5s/15s；v1.5 sticky 未强滚 |
| `/dashboard` | 与首页不打架 | 长页滚动代码审通过 | [x] 200 | [x] CDP：暂无指数/降级文案；截图 dashboard |
| `/stock/600519` | 名/价/K 线无假数 | charts token 已绑 | [x] 200 | [x] CDP：贵州茅台 + K 线 loading；无假价 |
| `/portfolio` | 皮肤 + 滚动 | 长页滚动代码审通过 | [x] 200 | [x] CDP：— 空态；main 可滚 |
| `/settings` | 主题/Wind 配额展示 | 空/错态代码已落地 | [x] 200 | [x] CDP：设置页 + 主题切换终验 |
| `/api-docs` 或兼容入口 | 不回归 404 | 后端 302→`/api/docs/`；dev 代理 `/static/*`（`8cdfe24`） | [x] BE 302→200；FE `/api-docs` 200；**`:3000/static/swagger.json` 200**（curl） | [x] BE Swagger 17 ops；FE shell 200；定义代理已修（交互点选未强测） |
| `/health`（前后端） | 存活 | — | [x] 8888+3000 200 | — |

---

## 9. 与 `dojo-agents-absorption-plan` 映射

权威：`docs/design/dojo-agents-absorption-plan.md` + `DELIVERY-STATUS.md` 能力真相表。

| Dojo / 能力项 | 后端状态（文档口径） | **UI 视觉形态（本方案）** | 落点 Sprint |
|---|---|---|---|
| **Plan 状态机** | 状态机存在；真 step 未做 | 顶部/侧栏 **Plan Stepper**（只读节点 + 当前态高亮）；未实现 step 不假装可点穿 | C / S-UI-2 |
| **HITL** | 主切片已有批准回路 | **Approval Card**：通过/驳回/反馈；warn 色待批；ok/danger 结果 | C / S-UI-2 |
| **provenance** | 已强制 normalize | 结论脚注式 **Source Chips**（源、时间、tier）；xs 字号 | C / S-UI-2 |
| **scorecard** | `scorecard.py` + UI 已有 | **Scorecard Strip**：四维条/分；低分升风险色 `--warn` | C + artifacts |
| **Skills** | system_hint，非运行时插件市场 | 设置/提示区说明性文案，不做假商店 | 非目标（文案级） |
| **Memory 预取** | 启动预取常开 | 无单独炫技 UI；冷启动用 Skeleton | A 空态 |
| **context compress** | 未做 | 不展示「已压缩」伪状态 | 禁止 |
| **Checkpoint 回放** | 未做 HTTP+前端 | 不画回放时间轴；预留禁用入口样式即可 | 禁止装作成 |
| **辩论/时间线** | Sprint1 主切片 | 时间线密度用 `--fs-sm` + 左轨 | C |
| **Wind 配额** | 配额 API + 鉴权 | Settings 配额条 + warn>70%/danger>90% 语义 | D/Settings |
| **铁律 #1** | 全局 | 任何卡片禁止 fallback 假 K 线 | 全 Sprint |

**映射原则**：UI 只可视化 **已真实存在** 的能力；对「故意未做」项，界面保持隐藏或 disabled+说明，禁止营销式「即将上线」假入口。

---

## 10. TODO 跟踪

- 跟踪段落：根目录 `TODO.md` → **「UI改造A-D … S-UI-4 final snapshot v1.6 · swagger 已修 · sticky/Agent 仍开」**
- 方案路径：`docs/design/ui-renovation-plan.md`（`v1.6-sui4-final-snapshot`）
- 状态机：`待 Comdr 审批` → `已通过` → **S-UI-0~3 代码已落地** → **S-UI-charts 已落地** → `S-UI-4 curl/启服完成` → `S-UI-4 CDP 五路由+假数双窗完成` → `S-UI-4 主题/api-docs 残余` → `swagger 代理修复 8cdfe24` → `sticky/Agent/HITL/Swagger 交互仍开` → `关闭`
- 任何编码 PR/commit 信息须引用：`ui-renovation-plan.md §x` + 审批状态

---

## 11. 回滚

| 层级 | 动作 |
|---|---|
| 文档 | 删除本文件段落/文件；还原 `TODO.md` UI 段；还原 `docs/design/README.md` 行 |
| S-UI-0/1 | `git checkout -- frontend/src/app/globals.css` 及相关 UI 文件 |
| S-UI-2 | 还原 `page.tsx` + `components/chat|agent|artifacts|market` 改动集 |
| S-UI-3 | 还原主题 store/layout；清 localStorage 主题 key（可选 migrate） |
| 整包 | 回退到审批前 tag/commit；不涉及 DB 迁移 |
| 运行态 | 无服务端 schema 变更；回滚无数据修复脚本 |

---

## 12. 变更记录

| 版本 | 时间（+08:00） | 说明 |
|---|---|---|
| v0.1-draft | 2026-07-24 | 精简版 A–D 初稿（已落盘） |
| v1.0-draft-for-approval | 2026-07-24 | 按审批模板重排：审批栏/第一性原理/现状诊断/Token/S-UI-0~4/dojo 映射；待 Comdr 审批 |
| v1.1-approved | 2026-07-24 | **已通过 2026-07-24 Comdr 全量 A–D**；解锁 S-UI-0 起编码（仍禁 push） |
| v1.1-sui4-static | 2026-07-24 20:06 +08:00 | **S-UI-4 静态预检**：tsc/eslint exit 0；dashboard/settings/portfolio 滚动代码审通过（当时 S-UI-0~3 实现 commit 未齐；现已补齐，见下行） |
| v1.2-sui-code-landed | 2026-07-24 | **S-UI-0~3 实现 commit 已齐**：`972f3b8`（S-UI-0 tokens）· `8ac9012`/`9ec81f2`（S-UI-1）· `f8d0fe3`/`ddf1d50`（S-UI-2）· `3a5c6c7`/`6ee6409`（S-UI-3 等）；终验**不再**阻塞于 0~3，**仅待 S-UI-4 WebBridge**；§8 工程项已勾静态预检真完成项 |
| v1.3-sui4-partial | 2026-07-24 | S-UI-4 **curl/启服**完成；当时 CDP 无 tab，浏览器列未勾 |
| v1.4-sui4-browser | 2026-07-24 23:13 +08:00 | **CDP 五路由矩阵 + 首页 5s/15s 假数对照**完成；截图 `/tmp/stockanal_ui/sui4_*.png`；§8.1 空态/首页工位已勾；亮暗/Agent/HITL/sticky/`/api-docs` 仍 `[ ]`；验收后停 8888/3000 |
| v1.5-sui4-residual | 2026-07-24 23:18~23:32 +08:00 | **残余**：主题亮↔暗 `flashWhite=false` + 截图；`/api-docs` BE 302/200 + FE shell 200（当时 FE swagger.json 404）；sticky 未强测；Agent 真 SSE 因 MOCK_LLM=1 跳过；截图 theme/api-docs 增补；停 8888/3000 |
| v1.6-sui4-final-snapshot | 2026-07-24 | **终态文档对齐**：`8cdfe24` 修 FE `:3000/static/swagger.json` 404→200；TODO/plan/CHANGELOG 与「已代理已修」一致；仍未勾 sticky 强测 / Agent 真 SSE / Swagger 交互 / 涨跌色有数帧；仍禁 push |

---

## 附录 A · 决策摘要（给 Comdr 快读）

1. **为什么改**：视觉方言 + IA 叠层削弱「Agent 决策工位」主路径。  
2. **改什么**：A 系统 → B 首页 IA → C 工位（HITL/provenance/scorecard）→ D 皮肤。  
3. **不改什么**：后端契约、未交付 dojo 能力装作成、Playwright、大重构目录。  
4. **怎么控**：审批栏硬锁 + Sprint 回滚点 + 铁律 #1/#2/#3。  
5. **审批与交付状态（2026-07-24）**：§1 已勾选通过；**S-UI-0~3 代码已落地**；S-UI-4 **curl + CDP 五路由 + 主题**已完成；**api-docs swagger 代理已修（`8cdfe24`）**；§8.1 sticky 强测/Agent/HITL/provenance/scorecard/Swagger 交互/涨跌色有数帧仍开。

## 附录 B · 与历史修复的兼容

- 高度链 / sticky 指数 / SafeResponsiveContainer / 名称 code 污染清洗 / market 503 安静降级：**改造时必须回归，禁止回退。**  
- OpenAPI / 鉴权 / CSRF：**UI 不触后端。**

## 附录 C · 风险登记

| 风险 | 等级 | 缓解 |
|---|---|---|
| 未批抢跑编码 | High | 本文硬锁 + TODO 状态 |
| 侧栏过宽挤死对话 | Med | S-UI-2 折叠优先级表 |
| 主题闪白 | Med | CSS 变量 + 默认跟随系统可选 |
| 假能力入口 | High | §9 映射禁止装作成 |
| 内存/OOM | High | 铁律 #3；禁全量 vitest/build |

---

**文末声明**：本文为设计与治理文档，不包含可执行业务补丁。  
**审批状态：已通过 2026-07-24 Comdr 全量 A–D。**  
**代码状态：S-UI-0~3 + charts 已落地 · S-UI-4 v1.6 主题已勾 · swagger 代理已修（`8cdfe24`） · sticky/Agent/Swagger 交互仍开 · 仍禁 push。**
