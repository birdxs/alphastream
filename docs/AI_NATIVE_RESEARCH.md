# AI-Native 前端调研报告（战略转向）

```
Input: 上校指令 — 最大化兼容AI能力，面向未来AI时代产品设计
Output: AI-native 技术选型共识 + 产品设计范式 + 权威来源交叉验证
Pos: docs/AI_NATIVE_RESEARCH.md - Phase 1C/1D 调研成果（战略转向后）
```

> 调研时间: 2026-03-25 22:30~23:10 +0800

---

## 战略转向

**原方向**：传统15页面迁移到React（Dashboard为主）
**新方向**：AI-native金融对话产品（对话为主、图表为辅、Agent透明化）

---

## 一、AI-Native 框架评估（3+权威来源交叉验证）

| 框架 | Stars | NPM月下载 | AI流式 | Generative UI | 推荐度 |
|------|-------|----------|--------|--------------|--------|
| **Vercel AI SDK 6** | 20k+ | **2000万** | ★★★★★ | ★★★★★ | **首选** |
| **CopilotKit** | 28.6k | - | ★★★★☆ | ★★★★★ | 备选 |
| **assistant-ui** | 7.9k | 5万 | ★★★★★ | ★★★★☆ | **Chat UI首选** |
| LangChain.js | - | - | ★★★★☆ | ★★☆☆☆ | 前端层薄 |
| Chainlit | 11.4k | - | ★★★☆☆ | ★★☆☆☆ | ⚠️团队已撤出 |

### Vercel AI SDK 6 核心能力
- `useChat`/`useCompletion` — 流式AI响应Hooks
- `streamUI` — LLM直接返回React Server Components（Generative UI）
- **Streamdown** — 官方流式Markdown渲染器（Mermaid/KaTeX/CJK）
- `ToolLoopAgent` — 完整工具执行循环（默认20步+人机协作）
- 2000万+月下载，工业标准

### assistant-ui 核心能力
- YC W25投资，Radix风格headless组件
- 与Vercel AI SDK原生集成
- `ToolUI` — 工具调用可视化渲染
- 流式响应一等公民

### 关键协议
- **AG-UI**（CopilotKit发起）：Agent-User双向交互标准，Google/Microsoft/AWS/LangChain已采纳
- **A2UI**（Google 2025.12发布）：声明式Agent-UI格式，安全、跨平台

来源: [AI SDK 6](https://vercel.com/blog/ai-sdk-6) | [assistant-ui](https://www.assistant-ui.com) | [AG-UI](https://docs.ag-ui.com) | [A2UI](https://developers.googleblog.com/introducing-a2ui/)

---

## 二、AI时代产品设计范式

### 核心理念（a16z 2026）
- **从聊天到行动**：最好的AI产品不等待指令，基于上下文主动行动
- **提示框是临时界面**：不要优化提示词，要优化行为理解
- **为Agent设计，而非为人类设计**

### 三种Generative UI模式（CopilotKit定义）
| 类型 | 控制权 | 适用场景 |
|------|--------|----------|
| 静态 | 前端主控，Agent选组件 | 品牌一致性场景 |
| 声明式 | 共享控制，Agent返回JSON规范 | **推荐：本项目** |
| 开放式 | Agent主控，生成完整HTML | 快速原型 |

### 金融AI产品标杆
| 产品 | 交互模式 | 传统Dashboard？ |
|------|----------|----------------|
| Perplexity Finance | 对话+数据卡片 | ❌ 对话为主 |
| Bloomberg ASKB | 对话+Terminal | 混合 |
| FinChat/Fiscal.ai | 对话式研究 | ❌ 对话为主 |
| Alpha Vantage | MCP数据接口 | N/A |

**结论**：2025-2026金融AI产品主流是"对话为主、图表为辅"

来源: [a16z AI Apps 2026](https://a16z.com/notes-on-ai-apps-in-2026/) | [NN/g Perplexity UX](https://www.nngroup.com/articles/perplexity-henry-modisett/) | [Bloomberg ASKB](https://www.bloomberg.com/professional/insights/press-announcement/meet-askb/) | [Smashing Magazine AI Patterns](https://www.smashingmagazine.com/2025/07/design-patterns-ai-interfaces/)

---

## 三、设计五大原则

1. **意图驱动**：用户表达目标，AI决定执行路径
2. **过程透明**：Agent思考链、工具调用、中间结果实时可见
3. **渐进式复杂度**：先结论→展开数据→深入指标
4. **AI在场景中**：将AI嵌入工作流，而非要求用户来到AI
5. **用户保持控制**：随时暂停、编辑、覆盖Agent行为

---

## 四、最终技术栈决定（战略转向后）

```
Next.js 15 + React 19 + TypeScript
├── AI层: Vercel AI SDK 6 (useChat/streamUI/ToolLoopAgent)
├── Chat UI: assistant-ui (headless, Vercel AI SDK原生集成)
├── 流式渲染: Streamdown (Markdown+Mermaid+KaTeX)
├── K线图表: TradingView Lightweight Charts (35KB, Canvas)
├── 辅助图表: Recharts / ECharts (雷达图/柱状图)
├── UI基础: shadcn/ui + Tailwind CSS
├── 状态: Zustand (全局) + Jotai (实时数据原子)
├── 协议: AG-UI (Agent-User交互)
├── 通信: SSE (AI流式) + REST (数据查询)
└── 部署: Nginx反代 + Docker Compose
```

### 产品形态："Chat+ Artifacts"

```
┌──────────────────┬──────────────────────────────┐
│   AI对话面板      │      Artifacts工作区          │
│   (左侧 ~35%)    │      (右侧 ~65%)             │
│                  │                              │
│  Agent状态可见    │  AI实时生成的图表/报告         │
│  思考过程透明     │  K线图(可交互缩放)            │
│  工具调用展示     │  评分雷达图                   │
│  多Agent进度条    │  财务指标对比表               │
│                  │  AI生成的研报                 │
│  用户对话输入     │  Multi-Agent进度面板          │
└──────────────────┴──────────────────────────────┘
```

### vs 原方案对比

| 维度 | 原方案(传统迁移) | 新方案(AI-native) |
|------|-----------------|-------------------|
| 入口 | 15个页面路由+菜单 | 对话为主入口 |
| 图表 | 固定页面布局 | AI按需生成(Generative UI) |
| Agent | 后台运行,只看结果 | 思考过程实时可见 |
| 数据 | 预定义表单查询 | 自然语言描述需求 |
| 竞争力 | 与同花顺/Wind同质化 | Perplexity/Bloomberg ASKB级别 |
