# 对标差异跟踪表

> **创建时间**: 2026-03-27 00:26 +08:00
> **总评分**: 40.8% → 目标 100%
> **对标产品**: fiscal.ai / aura.build / Perplexity / ChatGPT / Claude Artifacts

---

## 一、视觉精细度（当前 53.3%）

| # | 项目 | 当前 | 目标 | 优先级 | 状态 | 涉及文件 |
|---|------|------|------|--------|------|---------|
| V1 | 毛玻璃通透度 | 55% | 100% | P0 | ⏳待执行 | globals.css |
| V2 | 背景光斑动画 | 62% | 100% | P0 | ⏳待执行 | page.tsx |
| V3 | 顶部高光条 | 40% | 100% | P0 | ⏳待执行 | globals.css |
| V4 | 渐变边框全覆盖 | 30% | 100% | P0 | ⏳待执行 | message-bubble/artifact-card/welcome |
| V5 | 阴影层次感 | 50% | 100% | P1 | ⏳待执行 | globals.css |
| V6 | 字体层级统一 | 65% | 100% | P1 | ⏳待执行 | 全局组件 |
| V7 | 间距一致性 | 55% | 100% | P1 | ⏳待执行 | 全局组件 |
| V8 | 色彩对比度 | 60% | 100% | P0 | ⏳待执行 | globals.css |
| V9 | 动画流畅度 | 68% | 100% | P1 | ⏳待执行 | page.tsx/组件 |
| V10 | 空状态设计 | 70% | 100% | P2 | ⏳待执行 | artifact-panel/welcome |
| V11 | 骨架屏质量 | 45% | 100% | P1 | ⏳待执行 | artifact-renderer |
| V12 | 响应式断点 | 40% | 100% | P1 | ⏳待执行 | page.tsx/组件 |

## 二、交互逻辑（当前 40.7%）

| # | 项目 | 当前 | 目标 | 优先级 | 状态 | 涉及文件 | 前后端 |
|---|------|------|------|--------|------|---------|--------|
| I1 | 消息发送反馈 | 55% | 100% | P1 | ⏳待执行 | message-bubble/chat-input | 前端 |
| I2 | 流式打字效果 | 60% | 100% | P1 | ⏳待执行 | stream-markdown | 前端 |
| I3 | 停止生成 | 85% | 100% | P2 | ✅已完成 | use-chat-stream | 前端 |
| I4 | 消息重新生成 | 25% | 100% | P0 | ⏳待执行 | message-bubble/use-chat-stream | 前端 |
| I5 | 对话上下文持久化 | 50% | 100% | P0 | ⏳待执行 | chat-store | 前端 |
| I6 | 键盘快捷键 | 55% | 100% | P1 | ⏳待执行 | keyboard-shortcuts | 前端 |
| I7 | 搜索体验 | 40% | 100% | P1 | ⏳待执行 | global-search | 前端 |
| I8 | 页面切换动画 | 20% | 100% | P0 | ⏳待执行 | page.tsx/layout | 前端 |
| I9 | 表单验证 | 35% | 100% | P1 | ⏳待执行 | chat-input | 前端 |
| I10 | 错误处理Toast | 50% | 100% | P0 | ⏳待执行 | 新增sonner | 前端 |
| I11 | 数据刷新WebSocket | 35% | 100% | P1 | ⏳待执行 | 新增ws | 前后端 |
| I12 | 拖拽分割条 | 0% | 100% | P0 | ⏳待执行 | page.tsx | 前端 |
| I13 | 滚动行为 | 55% | 100% | P1 | ⏳待执行 | message-list | 前端 |
| I14 | 手势支持 | 5% | 100% | P2 | ⏳待执行 | 移动端组件 | 前端 |

## 三、AI产品形态（当前 26.2%）

| # | 项目 | 当前 | 目标 | 优先级 | 状态 | 涉及文件 | 前后端 |
|---|------|------|------|--------|------|---------|--------|
| A1 | 思维链可视化 | 40% | 100% | P0 | ⏳待执行 | thinking-chain | 前端 |
| A2 | Agent协作可视化 | 55% | 100% | P1 | ⏳待执行 | agent-progress | 前后端 |
| A3 | 工具调用时间线 | 50% | 100% | P1 | ⏳待执行 | tool-call-timeline | 前端 |
| A4 | Generative UI增强 | 65% | 100% | P1 | ⏳待执行 | artifact系统 | 前端 |
| A5 | 跨会话记忆 | 15% | 100% | P0 | ⏳待执行 | chat-store/后端API | 前后端 |
| A6 | 追问引导 | 70% | 100% | P2 | ⏳待执行 | suggested-questions | 前端 |
| A7 | 数据溯源引用 | 25% | 100% | P0 | ⏳待执行 | message-bubble/后端tools | 前后端 |
| A8 | AI置信度 | 10% | 100% | P1 | ⏳待执行 | message-bubble/后端 | 前后端 |
| A9 | 多模态支持 | 0% | 100% | P2 | ⏳待执行 | chat-input/后端 | 前后端 |
| A10 | 实时协作 | 0% | 100% | P2 | ⏳待执行 | 新增系统 | 前后端 |
| A11 | 个性化推荐 | 10% | 100% | P1 | ⏳待执行 | dashboard/后端 | 前后端 |
| A12 | 语音输入 | 0% | 100% | P2 | ⏳待执行 | chat-input | 前端 |
| A13 | AI主动推送 | 0% | 100% | P1 | ⏳待执行 | 新增WebSocket | 前后端 |

## 四、API路由对齐状态

| 前端调用 | 后端路由 | 状态 | 说明 |
|---------|---------|------|------|
| `/api/ai/chat` | POST | ✅对齐 | SSE流式，支持tools |
| `/api/ai/agent-analyze` | POST | ⚠️Bug | LangGraph并发状态错误 |
| `/api/conversations` | GET | ✅对齐 | 列表 |
| `/api/conversations/{id}` | GET/DELETE | ✅对齐 | 详情/删除 |
| `/api/market_indices` | GET | ✅对齐 | 4指数实时(akshare) |
| `/api/stock_data` | GET | ✅对齐 | K线数据 |
| `/api/fundamental_analysis` | POST | ✅对齐 | 基本面 |
| `/api/individual_fund_flow` | GET | ✅对齐 | 资金流 |
| `/api/risk_analysis` | POST | ✅对齐 | 风险评估 |
| `/api/board_stocks` | GET | ✅对齐 | 板块成分股 |
| `/api/latest_news` | GET | ⚠️待验证 | 新闻列表 |
| `/api/enhanced_analysis` | POST | ⚠️待验证 | 增强分析 |
| WebSocket实时推送 | — | 🔴缺失 | 需新增 |
| 数据溯源引用API | — | 🔴缺失 | 需后端返回sources |
| AI置信度API | — | 🔴缺失 | 需后端返回confidence |
| 用户认证API | — | 🔴缺失 | 需新增auth |

---

## 执行日志

| 时间 | Phase | 动作 | 结果 |
|------|-------|------|------|
| 2026-03-27 00:26 | — | 创建跟踪表 | 落盘 |
