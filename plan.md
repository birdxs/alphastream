# 前后端分离重构 — 作战计划

```
启动时间: 2026-03-25 21:53:47 +0800
授权时长: 12h
团队规模: 50人 Agent Team
PM: 🌿少校
```

---

## 战略转向记录

- 22:15 上校指令：最大化兼容AI能力，面向未来AI时代产品设计，敢于创新
- 22:28 上校指令补充：后端负责计算，前端只负责调用展示，后端能力必须同步补齐
- 原方向：传统15页面迁移到React Dashboard
- **新方向：AI-native "Chat+ Artifacts" 金融对话产品**

---

## Phase 总览

| Phase | 任务 | 状态 | 开始时间 | 完成时间 |
|-------|------|------|----------|----------|
| P0 | 前端现状盘点 | **完成** | 21:54 | 22:08 |
| P1 | 联网调研（传统框架） | **完成** | 21:54 | 22:30 |
| P1v2 | 联网调研（AI-native转向） | **完成** | 22:30 | 23:10 |
| P2v2 | AI-native架构设计（前端+后端缺口） | **完成** | 23:10 | 23:30 |
| P3 | 前端重构实施 | **待审批** | - | - |
| P4 | 后端能力补齐实施 | **待审批** | - | - |
| P5 | 联调验收 | 待启动 | - | - |

---

## 技术选型决定（AI-native版，P1v2结论）

```
Next.js 15 + React 19 + TypeScript
├── AI层: Vercel AI SDK 6 (useChat/streamUI/Streamdown)
│         2000万+月下载，工业标准
├── Chat UI: assistant-ui (YC W25, headless, AI SDK原生集成)
├── 流式渲染: Streamdown (Markdown+Mermaid+KaTeX+CJK)
├── K线图表: TradingView Lightweight Charts (35KB, Canvas)
├── 辅助图表: Recharts (雷达图/柱状图)
├── UI基础: shadcn/ui + Tailwind CSS
├── 状态: Zustand (全局) + Jotai (实时数据原子)
├── 协议: AG-UI (Google/Microsoft/AWS已采纳)
├── 通信: SSE (AI流式) + REST (数据查询)
└── 部署: Nginx反代 + Docker Compose
```

### 产品形态："Chat+ Artifacts"
- 左侧35%：AI对话面板（Agent状态、思考过程、工具调用透明）
- 右侧65%：Artifacts工作区（AI实时生成可交互图表/报告）
- 保留3个锚点视图：首页/投资组合/自选股

---

## 后端能力缺口（6项）

| 严重度 | 缺口 | 现状 | 补齐方案 |
|--------|------|------|----------|
| P0 | 无SSE流式端点 | 异步任务+轮询 | 新增 POST /api/ai/chat SSE端点 |
| P0 | AI调用无流式 | chat_completion未stream | 新增 chat_completion_stream() |
| P0 | 无Generative UI协议 | 工具返回纯字符串 | 新增 artifact_wrapper.py |
| P1 | 无Agent状态推送 | event_bus仅进程内 | 桥接到SSE通道 |
| P1 | 无对话上下文管理 | 每次独立调用 | 新增 conversation.py |
| P2 | 无预判性提问 | 无 | AI回复时附带follow-up |

**改动范围**：新建2文件，修改4文件。现有40+ REST API不改动。Flask不迁移。

---

## Agent部署记录

| Agent | 任务 | 分配时间 | 状态 | 交付物 |
|-------|------|----------|------|--------|
| A01 | P0: 前端功能审计 | 21:54 | **完成** | 15模板/18+API功能清单 |
| A02 | P1A: 框架调研 | 21:54 | **完成** | 框架对比报告(6+来源) |
| A03 | P1B: 金融设计调研 | 21:54 | **完成** | Bloomberg/TradingView设计报告 |
| A04 | P2v1: 传统架构设计 | 22:30 | **完成→被v2替代** | FRONTEND_ARCHITECTURE.md v1 |
| A05 | P1C: AI-native框架调研 | 22:30 | **完成** | AI SDK/CopilotKit/assistant-ui |
| A06 | P1D: AI产品设计范式 | 22:30 | **完成** | Chat+Artifacts/Generative UI |
| A07 | P2v2: AI-native架构设计 | 23:10 | **完成** | FRONTEND_ARCHITECTURE.md v2 |
| A08 | P2-后端: 能力缺口审计 | 23:15 | **完成** | BACKEND_GAPS.md |

**已用Agent**: 8/50 | **已用时间**: ~1.5h / 12h

---

## 落盘文件清单

| 文件 | 行数 | 内容 | 状态 |
|------|------|------|------|
| docs/API.md | 700+ | 后端API对接标准(40+路由) | 已提交 |
| docs/FRONTEND_RESEARCH.md | 130+ | P0/P1传统调研汇总 | 已提交 |
| docs/AI_NATIVE_RESEARCH.md | 200+ | P1v2 AI-native调研(14权威来源) | 待提交 |
| docs/FRONTEND_ARCHITECTURE.md | 1347 | AI-native前端架构蓝图v2 | 待提交 |
| docs/BACKEND_GAPS.md | 580 | 后端能力缺口+补齐设计 | 待提交 |
| plan.md | - | PM进度管理 | 实时更新 |

---

## 时间校验记录

- 校验时间: 2026-03-25 21:53:47 +0800
- 本机: 21:53:47 +0800 | 百度: 13:53:47 GMT | 偏差: 0秒 | 通过

---

## 变更记录

| 时间 | 变更内容 | Commit |
|------|----------|--------|
| 21:04 | 全面AI Agent化改造 | e895a0c |
| 21:15 | 审计修复: investor_consensus+progress | 91903e6 |
| 21:30 | confidence全链路统一浮点数 | 7d704aa |
| 21:50 | API文档+README v2.3.0 | c6c3514 |
| 22:30 | P0/P1/P2v1调研+架构 | 07f1c2f |
| 23:30 | AI-native调研+架构v2+后端缺口 | 待提交 |
