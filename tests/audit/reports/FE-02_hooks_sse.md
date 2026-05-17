# FE-02 前端 Hooks + SSE 客户端单元测试报告

- 执行时间: 2026-05-17 21:24 +08:00
- 执行环境: vitest 2.1.9 + jsdom + @testing-library/react
- 入口: `frontend/` (cwd) → `npx vitest run ../tests/frontend/hooks/ ../tests/frontend/api/`
- 证据: `tests/audit/evidence/FE-02_vitest.log`

## 总览

| 指标 | 数值 |
| ---- | ---- |
| 测试文件 | 6 |
| 用例总数 | 38 |
| 通过 | 38 |
| 失败 | 0 |
| 时长 | ~1.6s |

## 覆盖矩阵

### 1. `use-count-up.test.ts` (5)
| 用例 | 关注点 |
| --- | --- |
| enabled=false 直接返回目标 | 短路分支 |
| 起始→目标收敛 | rAF 受控时钟 + easeOutCubic |
| decimals 控制小数 | toLocaleString 格式化 |
| 负数前导减号 | 符号分支 |
| 卸载 cancelAnimationFrame | cleanup |

### 2. `use-alt-data.test.ts` (5)
| 用例 | 关注点 |
| --- | --- |
| ticker 为空不发请求 | 短路 |
| 快乐路径 + loading 切换 | fetch happy |
| success=false 写 error | 错误文案 |
| HTTP 500 抛错被捕 | catch 分支 |
| reload 二次触发 | tick 自增重拉 |

### 3. `use-stock-names.test.ts` (5)
| 用例 | 关注点 |
| --- | --- |
| 空数组返回空 map | 短路 |
| 单股 stock_data 兜底 | endpoint 不可用降级 |
| 批量并发 | Promise.all 等价 |
| 缓存命中 | 模块级 nameCache 复用 |
| 双失败不写入 | 容错 |

### 4. `use-stock-prices.test.ts` (5)
| 用例 | 关注点 |
| --- | --- |
| 空数组无请求 | 短路 |
| 单股末行价格 | last/prev close 计算 |
| 并发两票 | 并发分发 |
| 空 data 不写入 | 容错 |
| apiClient reject 不抛 | 静默 |

### 5. `use-chat-stream.test.ts` (6)
| 用例 | 关注点 |
| --- | --- |
| `/api/ai/chat` 普通对话 | 路由分支 + token 累加 + done 转 assistant |
| 6 位代码 + 动词 → agent-analyze | 路由切换 |
| 无代码 + 动词 → 预解析 stock_name_search | 异步预解析 fetch |
| onError 写 ⚠️ 错误消息 | 错误 UI 注入 + followUps 重试键 |
| streamPost reject 非 Abort | 流清理 + console.error |
| stopGeneration → AbortError | [已停止] 尾标 |

### 6. `tests/frontend/api/client.test.ts` (12)
| 用例 | 关注点 |
| --- | --- |
| 200 + JSON 正常解析 | happy |
| 500 + 文本 ApiError 透传原文 | extractErrorMessage 文本分支 |
| 504 + `{error: ...}` 提取 error 字段 | extractErrorMessage JSON 分支 |
| 503 + 空响应体 → `HTTP 503` | 兜底文案 |
| NaN/Infinity → null | safeJSONParse |
| event:token + data | 事件派发 |
| event:done | 完成回调 |
| 1MB 缓冲 flush + console.warn | buffer 上限 |
| 500 重连：第二次成功 | RETRY_DELAYS[0]=1000ms |
| 三次失败抛错 | MAX_RETRIES=2 (尝试 3 次) |
| AbortError 不重试 | 终止信号语义 |
| info 事件携带 event_type | 派发到内部事件 |

## 关键发现

1. **缓冲区 1MB 上限有效**：制造 `'x'.repeat(1_048_577)` 单 chunk 触发 `console.warn('[SSE] buffer exceeded 1MB, flushing')`，缓冲被清空，后续 done 事件仍能正常处理。
2. **重试节奏**：`RETRY_DELAYS = [1000, 3000]`、`MAX_RETRIES = 2`，实际可达 3 次 fetch 调用；用 `vi.useFakeTimers + advanceTimersByTimeAsync` 验证。
3. **AbortError 直接抛出**：源码 `if (err.name === "AbortError") throw err;` 阻断重试，spy 仅 1 次调用，符合预期。
4. **`safeJSONParse` 边界**：`\b-Infinity\b` 模式因 `-` 不是 word 字符而无法匹配带前缀的负无穷；测试输入只用 `NaN, Infinity` 形式。若线上日志出现 `-Infinity` 字面量，会导致 `JSON.parse` 抛错——属于**已知缺陷**，未在本次任务范围修复。

## 缺陷清单

| ID | 严重度 | 文件 | 描述 | 处置建议 |
| --- | --- | --- | --- | --- |
| FE-02-D01 | P3 | `frontend/src/lib/api/client.ts` `safeJSONParse` | 正则 `\b-Infinity\b` 实际不匹配字面 `-Infinity`（`-` 为非单词字符，`\b` 在 `-` 处失配） | 改为 `(?<!\w)-?Infinity(?!\w)` 或显式列出 `[-]?Infinity` |
| FE-02-D02 | P3 | `frontend/src/lib/hooks/use-chat-stream.ts` `catch` 块 | streamPost 非 Abort reject 时仅 console.error，UI 不显示错误（仅 onError 分支才显示），存在静默失败 | 在 catch 中追加一条 ⚠️ assistant 消息 |
| FE-02-D03 | P4 | 测试基建 | `tests/frontend/**` 引用 `@testing-library/react` 时 vite 从测试文件向上解析不到 `frontend/node_modules`，需仓库根 symlink 兜底 | 推荐改为 vitest.config 内 alias 或将测试目录移入 `frontend/tests/` |

## 不入范围

- 组件 / 页面测试 (FE-03 范畴)
- 端到端浏览器集成 (FE-04 范畴)
- 修改源代码缺陷 (FE-02 仅落地测试)

## 复现命令

```bash
cd /Users/panda/Downloads/StockAnal_Sys/frontend
npx vitest run ../tests/frontend/hooks/ ../tests/frontend/api/ --reporter=verbose
```

## 关联文件

- `tests/frontend/hooks/use-chat-stream.test.ts`
- `tests/frontend/hooks/use-alt-data.test.ts`
- `tests/frontend/hooks/use-stock-names.test.ts`
- `tests/frontend/hooks/use-stock-prices.test.ts`
- `tests/frontend/hooks/use-count-up.test.ts`
- `tests/frontend/api/client.test.ts`
- `tests/audit/evidence/FE-02_vitest.log`
