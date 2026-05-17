# FE-01 Zustand Store 单元测试报告

- 报告时间：2026-05-17 21:01:20 +08:00
- 时间校验：本地 2026-05-17 20:57:26 +0800 vs Google HTTPS Date 头 2026-05-17 12:57:28 GMT，偏差 ≤ 100s，通过。
- 执行人：agent FE-01
- 范围：仅 6 个 Zustand store，不含 hook / 组件 / page。

## 1. 交付物清单

| 文件 | 路径 | 说明 |
| --- | --- | --- |
| 测试 | `tests/frontend/stores/agent-store.test.ts` | 8 用例，含 P0-1 滑动窗口 |
| 测试 | `tests/frontend/stores/chat-store.test.ts` | 6 用例 |
| 测试 | `tests/frontend/stores/theme-store.test.ts` | 5 用例 |
| 测试 | `tests/frontend/stores/settings-store.test.ts` | 5 用例 |
| 测试 | `tests/frontend/stores/watchlist-store.test.ts` | 6 用例 |
| 测试 | `tests/frontend/stores/portfolio-store.test.ts` | 6 用例 |
| 日志 | `tests/audit/evidence/FE-01_vitest.log` | vitest --reporter=verbose 全文 |

## 2. 依赖安装状态

- lockfile：`frontend/package-lock.json`（npm 体系）
- 安装命令：`npm install --no-audit --no-fund`
- 结果：`added 251 packages in 30s`，无 ERR_ 报错，仅 2 条 deprecated 警告（whatwg-encoding@3.1.1、glob@10.5.0），不影响 vitest 运行。
- vitest 版本：`vitest/2.1.9 darwin-arm64 node-v24.3.0`

## 3. 测试执行结果

```
Test Files  6 passed (6)
     Tests  36 passed (36)
  Duration  853ms
```

| Store | 用例数 | 通过 | 失败 |
| --- | --- | --- | --- |
| useAgentStore | 8 | 8 | 0 |
| useChatStore | 6 | 6 | 0 |
| useThemeStore | 5 | 5 | 0 |
| useSettingsStore | 5 | 5 | 0 |
| useWatchlistStore | 6 | 6 | 0 |
| usePortfolioStore | 6 | 6 | 0 |
| **合计** | **36** | **36** | **0** |

## 4. 关键覆盖项

### 4.1 P0-1 暴露与验证 — agent-store 滑动窗口
- 用例：`appendEvent 添加 600 条事件 → MAX_EVENTS 滑动窗口生效（events.length === 500）[P0-1]`
- 断言：`events.length === 500` 且 `events[0].title === 'evt-100'`、`events[499].title === 'evt-599'`
- 结论：滑动窗口实现按预期工作，确认 `MAX_EVENTS = 500`，前 100 条被切除。
- 补充：`addToolCall` 同样在 600 次后命中 500 上限（toolCalls 列表也复用 MAX_EVENTS 截断）。

### 4.2 theme-store localStorage 持久化
- 用例：`localStorage 持久化：toggle 后 localStorage 中 theme-storage 包含新值`
- 路径：`localStorage.getItem('theme-storage')` → JSON.parse → `{ state: { theme, stockColorScheme } }`
- 结论：zustand `persist` 中间件按 key=`theme-storage` 落地，结构与默认 storage 一致。

### 4.3 settings-store 边界与持久化
- 验证 `setResearchDepth(0)` / `setResearchDepth(-1)` 不被拦截（无内置校验），可作为后续表单层校验依据。
- `settings-storage` localStorage key 正确写入。

### 4.4 watchlist-store 去重边界
- 验证重复 `addItem('AAPL', '苹果2')` 不会覆盖也不会创建副本，与 source `s.items.some(i => i.code === code) ? s.items : [...]` 实现一致。

### 4.5 portfolio-store API 名校正
- 任务表使用 `addItem/updateItem/removeItem`，但实际源码 API 为 `addHolding/updateHolding/removeHolding`，测试按真实 API 编写，未修改源码。
- 验证 `updateHolding('NOPE', ...)` 对不存在 code 不抛错也不改其他项的“静默更新”语义。

### 4.6 chat-store 流式与对话操作
- `appendStreamContent`+ `resetStreamContent` 边界：空串追加不改变内容。
- `updateConversationTitle` 仅匹配 `conversation_id` 的项。

## 5. 工程缺陷与建议

| ID | 严重度 | 描述 | 建议 |
| --- | --- | --- | --- |
| FE-01-D1 | 中 | `frontend/vitest.config.ts` 原配置 include 含 `../tests/frontend/**`，但缺 `server.fs.allow` 配置，vite 默认拒绝 root 外文件，导致首次跑全部 6 个文件 "Failed to load url ... Does the file exist?"。 | 本任务已补 `server.fs.allow = [..(repo root), .(frontend)]`。建议在 W1a 配置追溯文档中补充该项。 |
| FE-01-D2 | 低 | 任务表 store 方法名（agent-store `setPhase/addThought/updateToolCall`；portfolio-store `addItem/updateItem/removeItem`；chat-store `appendStream`）与真实源码不一致。 | 后续 W 系列任务文档更新为 `setAgentProgress/appendReasoningToken/setToolCallResult/addHolding/appendStreamContent`，避免误导。 |
| FE-01-D3 | 低 | settings-store 无 `setResearchDepth` 入参校验（接受 0/负值）。 | 表单层增加 `clamp(1..10)` 校验或在 store action 内 guard。 |
| FE-01-D4 | 低 | npm install 出现 2 条 deprecated 警告（whatwg-encoding、glob）。 | 跟踪上游 jsdom/vite 升级，暂不阻塞。 |

## 6. 复现方式

```bash
cd /Users/panda/Downloads/StockAnal_Sys/frontend
npm install --no-audit --no-fund
npx vitest run ../tests/frontend/stores/ --reporter=verbose
```

完整日志：`tests/audit/evidence/FE-01_vitest.log`
