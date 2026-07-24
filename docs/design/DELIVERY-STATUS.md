# 交付状态清单 · Sprint0–4（AI 原生融化）

```
Input: Sprint0–4 已落地 commit + 本地可使用验收证据
Output: 中文交付清单（能力 / 启动 / 验证 / 限制 / 回滚）
Pos: docs/design/DELIVERY-STATUS.md — 交付冲刺唯一状态入口
```

| 字段 | 值 |
|------|-----|
| **文档版本** | `v1.4-sprint4c-pending-provenance` |
| **交付锚点** | **2026-07-24 10:15:00 +08:00**（S4C：前端写仓 pending UI + decision_memo.provenance；校时：本机 ≡ Cloudflare/GitHub Date，偏差 ≤100s，通过） |
| **分支** | `main`（本地 ahead origin，默认 **不 push**） |
| **工作目录** | `/Users/panda/Downloads/StockAnal_Sys` |
| **设计依据** | `docs/design/dojo-agents-absorption-plan.md` v1.2+ |
| **约束** | 铁律 #1–#4；禁 Playwright；默认禁 push |

---

## 1. Sprint 状态一览

| Sprint | 状态 | 说明 |
|--------|------|------|
| Sprint 0 | **DONE** | 只读盘点 + 契约 → `sprint0-inventory.md` |
| Sprint 1 | **DONE（主切片）** | 护栏 / HITL / 辩论证据 / 工具时间线 |
| Sprint 2 | **DONE** | 意图规则路由 + 持仓 snapshot 只读 |
| Sprint 3 | **DONE** | 组合风险诊断 + 观察 mode |
| Sprint 4 | **DONE（写仓 harness 骨架）** | 提案+approval 闸门 + decision 挂载；facade/P2 选修未开 |

### P0 汇总

| ID | 能力 | 状态 |
|----|------|------|
| P0-1 工具护栏 | **DONE** |
| P0-2 意图协议 + 写工具硬拦 | **DONE**（`execute_tool` 白名单 + 写名 no-op；拟写仓 intent `portfolio_write_blocked` + system_hint 硬拒绝） |
| P0-3 真仓只读 | **DONE** |
| P0-4 工具时间线 | **DONE**（`provenance[]` 结构化数组仍属**已知缺口**，见 §8） |
| P0-5 HITL 确认面 | **DONE** |
| P0-6 辩论证据面 | **DONE**（terminal 完成态可再统一，非阻塞） |
| P0-7 降级帽 | **DONE**（`degradations` + `confidence_cap` + `agent.degraded` 事件 + DecisionCard/SidePanel 横幅；真机压测为可选补验） |

---

## 2. 已交付能力列表（commit 哈希）

| 能力 | 短哈希 | 完整哈希（前 12） | 说明 |
|------|--------|-------------------|------|
| Sprint3 组合诊断 + 观察 | `b612718` | `b612718993fa` | `risk_monitor` 诊断字段；`/portfolio` UI；store `live\|watch` |
| Sprint2 意图 + 持仓工具 | `f0d1289` | `f0d128920e2b` | `intent_router`；portfolio snapshot tools；chat 注入 |
| 前端 tool 断言对齐 P0-4 | `7d78236` | — | agent-store 测试与 normalize 契约 |
| Sprint1 文档记录 | `fd077ae` | — | P0-3 辩论 / P0-4 时间线文档 |
| 辩论 + 工具时间线 | `0c244f9` | — | debate_card / tool timeline contract |
| HITL 测试对齐 | `627a969` | — | pending card props + approval API tests |
| HITL 确认面 | `fe1c08e` | — | ApprovalCard / side-panel / API |
| 工具护栏 | `dd0fbc4` | — | `tool_guardrails` failure storm |
| **P0-2 写工具硬拦 + 拟写意图** | `e7714bf` | — | `tools.execute_tool` WRITE_TOOL_BLOCKED；`intent_router` portfolio_write_blocked |
| Sprint0 盘点锁定 | `7886bd5` | — | inventory + approval |
| **最终交付 handoff** | `e7714bf` | — | 本文 §9 验收清单 + §10 commit 全表 + §11 已知缺口 |
| Settings 导航入口 | `7d19e75` | — | 顶栏/移动齿轮 → `/settings` |
| Wind use_wind + 配额 | `7cae626` | — | 请求级开关；`/api/wind/quota` 鉴权策略 |
| profile `_outer_pool` + portfolio 输入守卫 | 本冲刺 | （见最终 commit） | P0：移除全局池 shutdown 残留；portfolio 非 dict 400 |

设计/计划文档同步：`docs/design/dojo-agents-absorption-plan.md`、本文件。

---

## 3. 如何启动（本地）

### 3.1 环境要点

- Python 3 + 项目依赖（`requirements.txt`）
- Node + `frontend/node_modules`（已 install）
- 本地开发建议：

```bash
export AUTH_REQUIRED=false
export DISABLE_NETWORK=0   # 真行情可开；纯烟测可用 1
export MOCK_LLM=1          # 无密钥时 chat 可 mock；真 LLM 时关掉
export RATE_LIMIT_ENABLED=false
export PORT=8888
```

### 3.2 后端（8888）

```bash
cd /Users/panda/Downloads/StockAnal_Sys
# 清旧进程
lsof -ti:8888 | xargs kill -9 2>/dev/null
pkill -9 -f "python.*run.py" 2>/dev/null

AUTH_REQUIRED=false DISABLE_NETWORK=0 MOCK_LLM=1 RATE_LIMIT_ENABLED=false PORT=8888 \
  python3 run.py
```

健康检查：

```bash
curl -sS http://127.0.0.1:8888/health
# 期望 HTTP 200；body 含 status=ok；uptime_s 在真重启后 < 60
```

### 3.3 前端（3000）

```bash
cd /Users/panda/Downloads/StockAnal_Sys/frontend
lsof -ti:3000 | xargs kill -9 2>/dev/null
pkill -9 -f "next dev" 2>/dev/null

npm run dev
# → http://127.0.0.1:3000
```

### 3.4 真重启铁证

1. kill 后 `lsof -nP -iTCP:8888,3000 -sTCP:LISTEN` 为空  
2. 启动后立刻 `curl /health` → **`uptime_s < 60`**  
3. 引用旧 PID / 大 uptime = **伪重启**，验收无效  

---

## 4. 如何验证（功能路径）

### 4.1 API 烟测（后端）

```bash
# 健康
curl -sS -o /tmp/h.json -w "%{http_code}" http://127.0.0.1:8888/health

# HITL 待审批列表（空列表合法）
curl -sS -o /tmp/pending.json -w "%{http_code}" \
  http://127.0.0.1:8888/api/agent_pending_approvals

# Wind 配额（未配 key 时仍应结构化返回或明确降级，不 5xx 风暴）
curl -sS -o /tmp/wind.json -w "%{http_code}" \
  http://127.0.0.1:8888/api/wind/quota

# 组合风险（样例 body；无仓空数组合法）
curl -sS -X POST http://127.0.0.1:8888/api/portfolio_risk \
  -H 'Content-Type: application/json' \
  -d '{"portfolio":[{"code":"600519","name":"贵州茅台","shares":100,"cost_price":1500}]}'
```

期望：上述路径 **非 5xx 为主**；portfolio_risk 含诊断扩展字段时可见 `sector_concentration` / `defensive_weight` 等（视实现键名）。

### 4.2 UI 路径（浏览器 / CDP Bridge）

| # | URL | 验证点 |
|---|-----|--------|
| 1 | http://127.0.0.1:3000/settings | 顶栏齿轮可达；**Wind 区块**（开关 + 配额展示/错误态，禁止假配额数字） |
| 2 | http://127.0.0.1:3000/portfolio | **诊断卡**或 Skeleton/—；持仓可设 **观察** 标签（`watch`） |
| 3 | http://127.0.0.1:3000/ | 首页无白屏崩溃；指数区 Skeleton 或真数（铁律 #1） |
| 4 | 侧栏 Agent | 有待审批时 **ApprovalCard**；无 pending 不报错 |
| 5 | Chat | 发消息时请求体可带 `portfolio_snapshot`（DevTools Network）；intent meta 可见时展示 badge |

### 4.3 CDP 截图登记（交付冲刺）

| 场景 | 路径 | 结果 | 截图 / 证据 |
|------|------|------|-------------|
| Settings / Wind | `/settings` | **PASS（CDP DOM）** 可见「设置 / Wind 数据源配置 / 今日剩余配额 / 启用 Wind 数据源」 | `/tmp/delivery_settings.png`；HTML `/tmp/delivery_settings.html` |
| Portfolio 诊断 | `/portfolio` | **PASS（SSR HTML）** 含「持仓/观察/风险/诊断/组合」；CDP 部分会话卡在 App Router `loading.tsx` 流式挂起，不影响 HTTP 200 + HTML 交付 | `/tmp/delivery_portfolio.png`（可能仍为 loading 壳）；HTML `/tmp/delivery_portfolio.html` |
| 首页 | `/` | **PASS（截图）** 导航壳可达、无全页崩溃；指数区可为 Skeleton/实时 | `/tmp/delivery_home.png`；HTML `/tmp/delivery_home.html` |

CDP 备注：settings 硬刷后可见 Wind 配额真数（S/A/B 剩余，与 `/api/wind/quota` 一致）；portfolio 客户端悬停 loading 记入「已知限制」，非 5xx。

---

## 5. 已知限制

1. **P0-7（合约 DONE）**：`degradations` + `confidence_cap` + `agent.degraded` + DecisionCard/SidePanel 已接；真机断网压测证据包仍可选。  
2. **P0-2（handoff DONE）**：只读白名单 + 写工具名 `WRITE_TOOL_BLOCKED` no-op；拟写意图 `portfolio_write_blocked` + system_hint 硬拒绝；**真写 harness 未做**（Sprint4）。  
3. **provenance[]（已知缺口）**：工具时间线字段已规范；完整数据血统折叠 Artifact / `provenance[]` 数组未 schema 化。  
4. **Sprint3 未含 P1 Skills/Plan/Memory/回放**；仅组合诊断 + 观察 mode。  
5. **Wind**：无 `WIND_API_KEY` 时付费工具全降级；配额页不应显示造假剩余积分（空 key 时 remaining=满额未消费，属闸门初值非假交易结果）。  
6. **auth**：`AUTH_REQUIRED=false` 仅本地；生产须开启鉴权 + CSRF。  
7. **旧 TradingAgents 路径**：P0 只强化 LangGraph；旧路径只读兼容。  
8. **默认不 push**；本地可能 `ahead origin` 数百 commit。  
9. **网络**：本机访问东财/部分源失败时指数/K 线降级为 Skeleton/重试，属环境非伪数据。  
10. **LLM**：`MOCK_LLM=1` 时 chat 为 mock，不可当真实投研结论。  
11. **`/api/portfolio_risk` 冷路径慢**：真机约 60s 量级（上游行业/数据链）；样例可 200 但需放宽客户端超时。  
12. **CDP Bridge 偶发客户端卡在全局 `loading.tsx`**：RSC streaming 未落稳时 main 仅「加载中...」；`curl` SSR HTML 已含完整文案时可判交付。  
13. **历史 `api_stock_profile` `_outer_pool`**：BD-3 后 finally 仍 shutdown 未定义池 → 本冲刺已修（见 §7）。  
14. **`PortfolioRiskSchema` 允许 Raw**：传入字符串数组会 `str.get` 500；本冲刺加运行时对象守卫 → 400 INVALID_INPUT。

---

## 6. 回滚命令

### 6.1 按能力回退最近交付（示例，注意依赖顺序）

```bash
cd /Users/panda/Downloads/StockAnal_Sys

# 仅回退 Sprint3 组合诊断（示例）
git revert --no-edit b612718

# 回退 Sprint2 意图+持仓
git revert --no-edit f0d1289

# 回退 HITL 确认面（可能需连带 627a969）
git revert --no-edit 627a969 fe1c08e

# 回退工具护栏
git revert --no-edit dd0fbc4
```

### 6.2 检出单文件到指定 commit 之前

```bash
git checkout <commit>^ -- path/to/file
```

### 6.3 停服

```bash
lsof -ti:8888 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
pkill -9 -f "python.*run.py" 2>/dev/null
pkill -9 -f "next dev" 2>/dev/null
```

### 6.4 文档

删除或还原 `docs/design/DELIVERY-STATUS.md` 与 `dojo-agents-absorption-plan.md` 中 v1.2 状态段。

---

## 7. 交付冲刺验证记录

| 项 | 记录 |
|----|------|
| 校验时间 | **2026-07-24 01:18:57 +08:00** 起（本机 2026-07-23 10:18–10:41 PDT） |
| 后端真重启 | kill 后 `python3 run.py`；**`uptime_s=3.007`**（READY 样本，PID 约 1602 批）`{"status":"ok","version":"3.1.0"}` |
| `/health` | **200** `status=ok` |
| `/api/agent_pending_approvals` | **200** `{"approvals":[],"count":0}` |
| `/api/wind/quota` | **200** `success=true` remaining S50/A30/B20（当日未消费） |
| `/api/portfolio_risk` 合法 body | **200** ~61s；含 `diagnosis`/`sector_concentration`/`name_overlap`/`defensive_weight`；`risk_level=极低` |
| `/api/portfolio_risk` 非法 string[] | **400** `INVALID_INPUT`（守卫后） |
| `/api/stock_profile?stock_code=600519` | **200** 名称贵州茅台，pe/pb/roe 真数（`_outer_pool` 修后） |
| 前端 HTTP | `/` `/settings` `/portfolio` **均为 200** |
| CDP | settings **PASS**（DOM 含 Wind 配额与开关）；home 截图 **PASS**；portfolio HTML **PASS**、CDP loading 见限制 #12 |
| P0 级现场修复 | ① `api_stock_profile` 删除未定义 `_outer_pool.shutdown`（Syntax/Name 修复）② `api_portfolio_risk` 强制 portfolio 元素为 dict |
| 最终 docs commit | 见 git log 本轮 `docs: delivery status Sprint0-3...` |

---

## 8. 领地标记

- 文件列表：`DELIVERY-STATUS.md`（本文件）、`dojo-agents-absorption-plan.md`、`sprint0-inventory.md`、`README.md`  
- 地位：设计 + 交付状态  
- 一旦这里的结构发生变化，请务必更新我... 就像重新标记领地一样。


---

## 9. Comdr 回岗验收清单（约 10 分钟手测）

> 目的：不依赖全量自动化，快速确认 Sprint0–3 融化切片 + 本 handoff 写硬拦/降级帽契约可用。  
> 假设：后端 `127.0.0.1:8888`、前端 `127.0.0.1:3000` 可启（若已在跑勿无故杀进程）；`AUTH_REQUIRED=false` 开发模式。

### 9.1 启动与健康（~1 min）

1. 若未监听：  
   - 后端：`AUTH_REQUIRED=false DISABLE_NETWORK=0 MOCK_LLM=1 RATE_LIMIT_ENABLED=false PORT=8888 python3 run.py`  
   - 前端：`cd frontend && npm run dev`  
2. `curl -s http://127.0.0.1:8888/health` → `status=ok`，`uptime_s` 有值。  
3. 浏览器打开 `http://127.0.0.1:3000/` → 指数栏有真实数字或合规「—/加载」，**无假数 1174 类 mock**。

### 9.2 P0-2 写硬拦（~2 min）

4. 离线断言（可不启服务）：  
   ```bash
   AUTH_REQUIRED=false DISABLE_NETWORK=1 MOCK_LLM=1 \
     pytest -q tests/backend/unit/test_sprint2_intent_portfolio.py -k 'write or Write'
   ```  
   期望：拟写意图 + `WRITE_TOOL_BLOCKED` 用例全绿。  
5. Chat 输入「帮我加仓 600519 / 帮我下单买茅台」：模型应**明确拒绝写仓/下单**，不得声称已成功改仓。  
6. （可选）Network：工具结果若出现写类名，JSON 含 `error_code=WRITE_TOOL_BLOCKED`、`executed=false`、`data=null`。

### 9.3 P0-3 持仓只读 + Sprint3 诊断（~2 min）

7. 打开 `/portfolio`：手动添加 ≥1 只真实代码持仓（本地 persist）。  
8. Chat：「看看我的持仓风险」→ 应注入 snapshot；只读工具可返回真持仓结构；**无编造权重**。  
9. 组合页风险摘要/观察 mode 切换可见（`live|watch`），不伪造风险分。

### 9.4 P0-5 HITL + P0-6 辩论 + P0-4 时间线（~3 min）

10. 触发需审批路径（若环境有 pending）：侧栏 ApprovalCard 显式批准/拒绝，API 非 404。  
11. 跑一轮 agent 分析（有 key）或回放历史 task：Debate 证据面 + 工具时间线节点可见；无假 K 线。  
12. 决策卡：若有降级，应见 DEGRADED / causes / confidence_cap 横幅（P0-7）。

### 9.5 安全与回归烟测（~2 min）

13. `curl -sI http://127.0.0.1:8888/health | head` → 安全头存在（nosniff / DENY 等，与既有 S3 一致）。  
14. 顶栏 Settings 入口 → `/settings` 可进。  
15. 失败即记：**截图 + 路由 + 时间戳**写入 TODO；勿仅报「感觉有问题」。

**通过标准**：写意图不假成功；只读持仓不编造；无金融假值 UI；健康检查绿。

---

## 10. Commit 全表（Sprint0 起本地关键 hash）

> 生成命令：`git log --oneline -40`（工作区 `/Users/panda/Downloads/StockAnal_Sys`，**handoff 前**基线 HEAD=`6a1a119`；本文件随后 commit 将再增一条）。

| # | 短哈希 | 说明 |
|---|--------|------|
| 1 | `6a1a119` | docs: delivery status Sprint0-3 AI-native meltdown |
| 2 | `b612718` | feat(portfolio): Sprint3 risk diagnosis + watch mode marker |
| 3 | `f0d1289` | feat(agent): Sprint2 intent routing + portfolio snapshot tools |
| 4 | `7d78236` | test(frontend): align agent-store tool result asserts with P0-4 normalize |
| 5 | `fd077ae` | docs: record Sprint1 P0-3 debate surface and P0-4 tool timeline |
| 6 | `0c244f9` | feat(agent): debate evidence surface and tool timeline contract |
| 7 | `627a969` | fix(agent): align P0-5 pending card props and approval API tests |
| 8 | `fe1c08e` | feat(agent): P0-5 HITL confirmation surface first-class |
| 9 | `dd0fbc4` | feat(agent): P0-1 tool call guardrail against failure storms |
| 10 | `7886bd5` | docs(design): Sprint0 inventory + approval locked |
| 11 | `4cd5fd0` | fix(data): second-pass akshare redundancy (code helpers + multi-source) |
| 12 | `be48440` | fix(data): C1-C3/H1-H3 akshare 主备对接猎杀 |
| 13 | `7d19e75` | feat(ui): add Settings entry in top nav for desktop and mobile |
| 14 | `7dcb67f` | docs(todo): CDP Bridge 停服重测结果（Settings/Dashboard/Stock 通过） |
| 15 | `01eb747` | docs(todo): 记录 use_wind 接线与联动真测结果 |
| 16 | `7cae626` | feat(wind): 接线 use_wind 请求级开关 + 配额端点收回鉴权 |
| 17 | `bc19fa3` | fix(review): 名称缓存 BD-3 回归 + Wind 扩展 WIP 冻结基线 |
| 18 | `4373f5f` | docs: Bug Hunt Round 2 最终报告 + Context Engineering 更新 |
| 19+ | （更早） | Bug Hunt Round2 / OpenAPI / 名称字典 / 稳定性等历史批（见 `git log`） |

**本 handoff 预期新增（提交后填入完整 hash）**：

| 短哈希 | 说明 |
|--------|------|
| `e7714bf` | `docs: final delivery handoff for Comdr`（含 P0-2 写硬拦代码 + 本清单） |

### 10.1 最近 30 条 oneline（handoff 前快照）

```
6a1a119 docs: delivery status Sprint0-3 AI-native meltdown
b612718 feat(portfolio): Sprint3 risk diagnosis + watch mode marker
f0d1289 feat(agent): Sprint2 intent routing + portfolio snapshot tools
7d78236 test(frontend): align agent-store tool result asserts with P0-4 normalize
fd077ae docs: record Sprint1 P0-3 debate surface and P0-4 tool timeline
0c244f9 feat(agent): debate evidence surface and tool timeline contract
627a969 fix(agent): align P0-5 pending card props and approval API tests
fe1c08e feat(agent): P0-5 HITL confirmation surface first-class
dd0fbc4 feat(agent): P0-1 tool call guardrail against failure storms
7886bd5 docs(design): Sprint0 inventory + approval locked
4cd5fd0 fix(data): second-pass akshare redundancy (code helpers + multi-source)
be48440 fix(data): C1-C3/H1-H3 akshare 主备对接猎杀
7d19e75 feat(ui): add Settings entry in top nav for desktop and mobile
7dcb67f docs(todo): CDP Bridge 停服重测结果（Settings/Dashboard/Stock 通过）
01eb747 docs(todo): 记录 use_wind 接线与联动真测结果
7cae626 feat(wind): 接线 use_wind 请求级开关 + 配额端点收回鉴权
bc19fa3 fix(review): 名称缓存 BD-3 回归 + Wind 扩展 WIP 冻结基线
4373f5f docs: Bug Hunt Round 2 最终报告 + Context Engineering 更新
（其余见 git log --oneline -40）
```

---

## 11. 已知缺口（不阻塞 handoff）

| 项 | 级别 | 说明 | 建议时窗 |
|----|------|------|----------|
| **Artifact `provenance[]` 结构化数组** | P1 缺口 | P0-4 已有工具时间线事件；设计要求的 `provenance[]` 字段级血统数组未单独 schema 化 | Sprint4 / Skills 并行 |
| **terminal 辩论完成态统一** | Low | 部分路径 terminal 与 progress 完成标记可再对齐 | 联调空窗 |
| **P0-7 真机压测证据包** | Low | 单元/契约已通；可选再补「断网压测截图」 | Comdr 手测 §9.4 |
| **写仓 harness（真写）** | P1/Sprint4 | 刻意未做：当前仅硬拦 + 拒绝提示；真写须 HITL + 前端 store API | 审批后再开 |
| **P1 Skills / Plan DAG** | P1 | 未开 | 设计文档 Sprint4 |
| **data/stock_names.json 本地脏改** | 噪音 | 常驻 runtime 刷新产物，**勿误提交密钥**；handoff 默认不入库 unless 有意刷新 | 提交时注意 exclude |

---

## 12. 本 handoff 代码改动摘要（相对 6a1a119）

| 文件 | 变更 |
|------|------|
| `app/core/tools.py` | `READ_ONLY_TOOL_NAMES` / `is_write_tool_name` / `WRITE_TOOL_BLOCKED` 硬拦；写名优先于护栏 |
| `app/core/intent_router.py` | `INTENT_PORTFOLIO_WRITE` + `_PORTFOLIO_WRITE_RE`；system_hint 硬拒绝假成功 |
| `tests/backend/unit/test_sprint2_intent_portfolio.py` | 拟写意图 + 写工具硬拦最小单测 |
| `docs/design/DELIVERY-STATUS.md` | 本文：验收清单 / commit 全表 / 缺口 |
| `docs/design/dojo-agents-absorption-plan.md` | P0-2/P0-7 状态对齐 DONE（最小描述） |

**验证（真实）**：

```text
AUTH_REQUIRED=false DISABLE_NETWORK=1 MOCK_LLM=1 \
  pytest -q tests/backend/unit/test_sprint2_intent_portfolio.py \
         tests/backend/unit/test_tool_guardrails.py \
         tests/backend/unit/test_core_event_bus.py
→ 51 passed, 1 xfailed
```

**回滚**：

```bash
git revert <本 handoff commit>
# 或仅还原：
git checkout HEAD~1 -- app/core/tools.py app/core/intent_router.py \
  tests/backend/unit/test_sprint2_intent_portfolio.py docs/design/
```

---

## 13. 协调者 / Comdr 下一步指令（可执行）

1. 按 **§9** 手测 10 分钟；失败项开 issue 或 TODO.md 条目。  
2. **默认仍禁 push**；需要同步 origin 时由 Comdr 显式授权。  
3. 缺口表 §11：优先「provenance[]」或「写仓 harness」二选一审批后开 Sprint4。  
4. 释放无人托管会话：本交付以本文 + handoff commit 为边界，**不再 gold-plate**。

## G5–G8 Scorecard / Memo / Reflection / Memory（2026-07-23 15:20 +08:00 锚点）

| 项 | 状态 | 落点 |
|----|------|------|
| G6 Run scorecard | **done** | `app/agents/scorecard.py` 纯函数 + done 时挂 `state.scorecard` / `final_decision.scorecard`；`EVENT_RUN_SCORECARD` + `publish_run_scorecard`；前端 store/SSE/`decision-card`/`agent-side-panel` |
| G5 决策备忘 Artifact | **done** | `build_decision_memo` → `decision_memo` 挂 decision_card（action / veto_reasons / evidence_pointers，无假数） |
| G7 反思可读面 | **done** | `summarize_reflection_readonly` ← `get_past_reflections`；侧栏 + decision-card 只读；**禁止**写生产权重 |
| G8 Memory 预取 | **done** | `run_agent_analysis` 启动时 `get_history` + `get_semantic_summary` → `memory_context`；空历史 `None` |

验证：`AUTH_REQUIRED=false DISABLE_NETWORK=1 MOCK_LLM=1 pytest -q tests/backend/unit/test_agent_scorecard.py`；前端 `tsc --noEmit`。

## 8.5 G1–G4 落地记录（2026-07-24 06:40 +08:00 锚点）

| 项 | 状态 | 落点 | 验证 |
|---|---|---|---|
| **G1 provenance[]** | ✅ | `artifact_wrapper` 产出 `{source,tool,ts,digest}`；`ai_client` tool start/result 事件附带；`coordinator` 汇总至 `result/final_decision`；status API 透出；decision-card 可折叠「数据血统」 | unit + tsc |
| **G2 terminal 态统一** | ✅ | `web_server`：`TASK_*` 扩展 + `normalize_task_status`/`compute_run_terminal`；`/api/agent_analysis_status` 返回 `status/run_terminal/approval_status`；前端 `agent-store` + `agent-status-badge` 映射 HITL 枚举 | unit hitl + tsc |
| **G3 事件别名** | ✅ | `event_bus`：`agent.role_started|finished` 与 `agent.started|completed` 双发；`canonical_event_name`/`event_dedupe_key`；SSE client 多 case；store `appendEvent` 去重不双计 | event_bus unit |
| **G4 写意图硬拦矩阵** | ✅ | `tools._WRITE_TOOL_EXACT` + RE 扩展 mutate/system；`TestWriteGuardMatrixG4`：mutate 名拦截 + portfolio_write system_hint 拒绝假成功 | intent/portfolio unit |

**验证（本批）**
- `pytest` focused：83 passed, 1 xfailed（预存在 H5）
- `frontend tsc --noEmit`：exit 0
- 禁 push；未启服务

**Commit 建议标签**：`feat(agent): provenance terminal event-alias write-guard matrix`

**回滚**：`git revert` 本批 commit；或还原  
`app/core/{artifact_wrapper,event_bus,tools,ai_client}.py`、`app/agents/coordinator.py`、`app/web/web_server.py`、  
`frontend/src/lib/{types,stores/agent-store,hooks/use-chat-stream,api/client}.ts`、  
`frontend/src/components/{artifacts/decision-card,agent/agent-status-badge}.tsx` 与相关测试。


## 8.6 G9–G12 落地 + 全谱 G1–G12 handoff（2026-07-23 早间工作点 +08:00 锚点）

> 时间锚点：本机 `date` 与 Cloudflare/GitHub HTTPS Date 同源校验通过（偏差 ≪ 100s）。  
> 约束：本地开发；**禁止 push**；聚焦 pytest；不启服务。

### G1–G12 状态总表

| ID | 项 | 状态 | 落点摘要 |
|----|----|------|----------|
| **G1** | provenance[] | ✅ | artifact_wrapper + coordinator + decision-card 血统折叠 |
| **G2** | terminal 态统一 | ✅ | normalize_task_status / run_terminal / HITL 徽章 |
| **G3** | 事件别名 | ✅ | role_started|finished 与 started|completed 双发 + 去重 |
| **G4** | 写意图硬拦矩阵 | ✅ | WRITE 名拦截 + portfolio_write system_hint |
| **G5** | 决策备忘 Artifact | ✅ | build_decision_memo → decision_memo（无假数） |
| **G6** | Run scorecard | ✅ | compute_run_scorecard + EVENT_RUN_SCORECARD |
| **G7** | 反思可读面 | ✅ | summarize_reflection_readonly（禁写权重） |
| **G8** | Memory 预取 | ✅ | get_history + semantic_summary → memory_context |
| **G9** | 市场/板块 facade（薄） | ✅ **本批** | `get_market_overview_brief` / `get_sector_snapshot`；失败空+source；DISABLE_NETWORK 安全 |
| **G10** | OpenAPI 热路由一小批 | ✅ **本批** | +6 path：north_flow / start_stock|agent / upload / wind quota|tools；paths 65→71；最小测试 |
| **G11** | intent badge 加固 | ✅ **本批** | chat-panel 仅消费 meta.intent∈IntentKind→中文标签；否则隐藏（铁律名称） |
| **G12** | 降级夹具补强 | ✅ **本批** | scorecard memo 降级不透传 price_targets；decision-card 降级隐藏价位；unit fixture |

### 本批 commit 文件表（落盘）

| 区域 | 文件 |
|------|------|
| G9 | `app/core/tools.py`（facade + TOOL_EXECUTORS / OPENAI schema / MARKET_TOOLS_SCHEMA） |
| G10 | `app/web/openapi_spec.py`；`tests/backend/api/test_cache_control_headers.py` |
| G11 | `frontend/src/components/chat/chat-panel.tsx`；`frontend/src/lib/types/index.ts`（IntentKind + INTENT_LABELS_ZH） |
| G12 | `app/agents/scorecard.py`；`frontend/src/components/artifacts/decision-card.tsx`；`tests/backend/unit/test_agent_scorecard.py` |
| G9 测 | `tests/backend/unit/test_sprint2_intent_portfolio.py`（TestMarketSectorFacadeG9） |
| 文档 | 本节 + 版本号 |

### 验证（真实命令）

```bash
AUTH_REQUIRED=false DISABLE_NETWORK=1 MOCK_LLM=1 \
  pytest -q tests/backend/unit/test_sprint2_intent_portfolio.py \
         tests/backend/unit/test_agent_scorecard.py \
         tests/backend/api/test_cache_control_headers.py
# → 59 passed, 13 warnings

cd frontend && node node_modules/typescript/bin/tsc --noEmit   # exit 0
npx eslint src/components/chat/chat-panel.tsx \
  src/components/artifacts/decision-card.tsx \
  src/lib/types/index.ts   # exit 0（0 error）
```

import-smoke：`len(OPENAPI_SPEC['paths']) == 71`；`get_market_overview_brief` / `get_sector_snapshot` ∈ TOOL_EXECUTORS。

### 回岗清单（Comdr / 下一 worker）

1. **可选浏览器 10 分钟**：AI 对话触发 market_overview / single_stock_deep，确认顶栏 badge 中文且无 intent 时不显示；故意降级场景下 decision-card **无目标价数字**。  
2. **G9 真网抽样**（非本批必做）：清 DISABLE_NETWORK 后手工 `execute_tool('get_market_overview_brief')` 一次，核对 source≠offline_disabled。  
3. **OpenAPI 消费方**：若 Swagger UI 缓存，刷新 `/api/openapi.json` 确认 71 paths。  
4. **仍默认禁 push**；合并前再跑一次上述 pytest 三文件。

### 仍暂缓项（明确不在本批）

| 项 | 原因 | 建议门槛 |
|----|------|----------|
| **真券商 / 真 mutate 用户持仓** | 仅 local_mark_only 骨架；无 broker | Comdr 书面审批 + 审计 + 独立适配器 |
| **provenance[] 证据链深化** | 非本切片 | 对齐 scorecard/decision_memo 字段后补 |
| **Plan DAG 执行引擎（真跑 step）** | 本批仅状态机 | 挂 analyzer 编排 + 超时/配额统一 |
| **Skills 深替换 / dojosdk 数据面** | 破坏 adapters/Wind 铁证链 | 仅 system_hint facade；禁替换 adapters |
| **git push** | 工作区纪律 + 本地 ahead origin | Comdr 显式授权 |
| **全量 vitest / npm build / 启服务** | 铁律 #3 资源 | 仅 tsc + 聚焦 eslint + 聚焦 pytest |

---

## Sprint4 写仓提案闸门 + decision 挂载（2026-07-24 09:30 +08:00 收尾）

**任务约束**：禁 push；禁启服；离线可测；铁律 #1–3。  
**代表 commit**：`78d6f34`（骨架）+ 本批（意图提示升级 + 状态表对齐）。

### 落地项

| 项 | 路径 | 说明 |
|----|------|------|
| 写仓提案 store | `app/core/write_proposal.py` | [NEW-FILE:#20260724-S4] propose/decide/apply；RLock；进程内 |
| 工具闸门 | `app/core/tools.py` | 三工具 + schema；裸 `portfolio_write_*` 仍 `WRITE_TOOL_BLOCKED` 并 hint 提案路径 |
| 意图 system_hint | `app/core/intent_router.py` | `portfolio_write_blocked` 硬拦假成功 + 引导 propose→decide→apply |
| 会话挂载 | `app/core/conversation.py` | `decision_artifacts` + `attach_decision_artifact` |
| chat/agent 接线 | `app/web/web_server.py` | assistant 落盘后挂 decision_card/scorecard |
| 测试 | `test_sprint2_intent_portfolio.py` + `test_core_conversation.py` | 闸门全链路 + 意图提示 + 挂载断言 |

### 语义铁证（禁止假下单）

- `propose` → `success=true, executed=false, broker=null, approval_id`
- `apply` 未批 → `APPROVAL_REQUIRED, executed=false`
- `apply` 已批 → `applied=true, local_marked=true, executed=false, broker=null, apply_mode=local_mark_only`
- 响应文案含「非成交 / 禁止解读为…已下单」
- 意图层不得输出「已下单/已加仓成功」

### P1-3 验收对照

| 计划要点 | 实测 |
|----------|------|
| 提案工具 | `propose_portfolio_write` / `decide_*` / `apply_*` |
| apply 需 approval_id | 无/拒批 → `APPROVAL_REQUIRED` |
| 无审批不落真仓 | apply 不 mutate 用户 portfolio-store；仅本地 mark |
| executed 恒 false | 全路径 `executed=false`、`broker=null` |

### 聚焦测试命令

```bash
AUTH_REQUIRED=false DISABLE_NETWORK=1 MOCK_LLM=1 pytest -q \
  tests/backend/unit/test_sprint2_intent_portfolio.py \
  tests/backend/unit/test_tool_guardrails.py \
  tests/backend/unit/test_hitl_gate.py \
  tests/backend/integration/test_hitl.py \
  tests/backend/unit/test_agent_scorecard.py \
  --tb=short
```

### 未纳入本 Sprint4 骨架

- 真券商 / 真 mutate 用户持仓（需 Comdr 书面审批）
- 市场 facade 余项 / P2 选修
- provenance[] 结构化深化

### 回滚

```bash
git revert <本批 commit>
# 全回退骨架：git revert 78d6f34
# 或：rm app/core/write_proposal.py；还原 tools.py / intent_router.py / conversation.py / web_server.py / 测试与文档
```

---

## Sprint4+ 薄切片：HITL 提案桥 + Plan DAG + Skill stub（2026-07-24 09:35 +08:00）

**任务约束**：禁 push；禁启服；铁律 #1–3；优先现有文件 + 白名单 core 新模块。  
**校时锚点**：本机 2026-07-23 18:29:49 -0700 ⇔ UTC 2026-07-24 01:29:53（Cloudflare Date）；偏差 ≤10s，通过。  
**代表 commit message**：`feat(agent): plan dag thin slice + hitl proposal bridge + skill stub`

### 落地项

| 项 | 路径 | 说明 |
|----|------|------|
| HITL ↔ write_proposal 桥 | `app/agents/hitl.py` + `app/core/write_proposal.py` | propose 登记 `register_non_blocking_pending(task_id=approval_id)`；`get_pending` 合并 store；`submit_approval` ↔ `decide_approval` 同语义；decide 清 HITL pending |
| Plan DAG 轻量模块 | `app/core/plan_dag.py` [NEW-FILE:#20260724-S4B] | 串行/depends_on 校验、环检测、状态机；不抓数不下单 |
| Skills stub | `app/core/skill_loader.py` [NEW-FILE:#20260724-S4B] | builtin + 可选 `data/skills` + reflection/strategy 片段 → system_hint；**禁替代 adapters** |
| 工具只读挂载 | `app/core/tools.py` | `create_analysis_plan` / `get_plan_status` / `load_agent_skill` / `list_agent_skills` |
| 测试 | `tests/backend/unit/test_plan_dag_hitl_bridge.py` [NEW-FILE:#20260724-S4B] | 桥接 4 + DAG 5 + Skill 4 |

### 语义铁证

- propose 后 `approval_manager.get_pending_approvals()` 含 `task_id=approval_id`，`kind=portfolio_write_proposal`
- `submit_approval(aid, True)` → store `status=approved`，pending 清空；`apply` 仍 `executed=false, broker=null`
- 仅 store pending（无 HITL 本地项）时 submit 仍桥接成功；`get_pending` 可从 store 合并
- Plan：未知 depend / 环 → 明确 error_code；依赖未完成 start → `DEPENDS_NOT_MET`；全完成 → plan `completed`
- Skill：builtin 有 hint；未知 id → `SKILL_NOT_FOUND`；hint 无假行情数值

### 聚焦测试（本批实测）

```bash
AUTH_REQUIRED=false DISABLE_NETWORK=1 MOCK_LLM=1 pytest -q \
  tests/backend/unit/test_plan_dag_hitl_bridge.py \
  tests/backend/unit/test_hitl_gate.py \
  tests/backend/unit/test_sprint2_intent_portfolio.py
# → 57 passed（2026-07-24 09:35 +08:00 当次）
```

### 特例登记

- [NEW-FILE:#20260724-S4B] `app/core/plan_dag.py` / `skill_loader.py` / `test_plan_dag_hitl_bridge.py`
- 触发：无既有 plan/skills 模块可只改；测试白名单 b + 全新 core e
- 回滚：`git revert <commit>` 或删除三新文件并还原 hitl/write_proposal/tools/docs/README

### 未纳入（S4B 时点；部分已在 S4C 关闭）

- Plan step 真执行 analyzer / 超时编排
- Skills 替换数据 adapters / 新建 `data/skills` 内容包（目录可选，本次未强制新建）
- ~~前端 pending-approvals UI 改 kind 展示~~ → **S4C 已关**
- 启服联调 / push

---

## Sprint4+ 薄切片：前端写仓 pending + decision_memo.provenance（2026-07-24 02:15 UTC / 10:15 +08:00）

**任务约束**：禁 push；禁启服（run.py/next/8888/3000）；铁律 #1–3；优先改现有文件。  
**校时锚点**：本机 2026-07-23 18:xx -0700 ⇔ UTC 2026-07-24 01:xx（Cloudflare/GitHub Date）；偏差 ≤100s，通过。  
**代表 commit message**：`feat(agent): pending write-proposal UI + decision_memo provenance align`

### 落地项

| 项 | 路径 | 说明 |
|----|------|------|
| ApprovalCard kind/approval_id | `frontend/src/components/agent/approval-card.tsx` | `portfolio_write_proposal` 紫系区分；展示 approval/proposal 短 id + code/shares/weight 结构摘要（零假价） |
| Pending 归一化 | `frontend/src/components/agent/pending-approvals.tsx` | 解析 API `kind`/`approval_id`/`proposal_id`/`decision.*`；key 优先 approval_id |
| decision_memo.provenance | `app/agents/scorecard.py` | `_collect_memo_provenance`：合并 state/fd provenance，去重，跳过空源；memo 挂 `provenance[]` |
| 类型 + DecisionCard | `frontend/src/lib/types/index.ts` + `decision-card.tsx` | `DecisionMemo.provenance`；UI 回退 `memo.provenance` 若顶层缺省 |
| 单测 | `tests/backend/unit/test_agent_scorecard.py` | 空 provenance=[]；state+fd 去重合并 2 源 |

### 语义铁证（离线）

- pending 项 `kind=portfolio_write_proposal` → 卡文案「写仓需确认」+ `data-approval-id` / `data-kind`
- `build_decision_memo` 在无血统时 `provenance==[]`；有 state/fd 摘要时去重输出 `{source,tool,digest?}`，不含 price 字段
- DecisionCard 顶层或 memo 任一有 provenance 即折叠展示「数据血统」

### 聚焦测试（本批实测）

```bash
AUTH_REQUIRED=false DISABLE_NETWORK=1 MOCK_LLM=1 pytest -q \
  tests/backend/unit/test_agent_scorecard.py \
  tests/backend/unit/test_sprint2_intent_portfolio.py \
  tests/backend/unit/test_plan_dag_hitl_bridge.py \
  tests/backend/unit/test_hitl_gate.py \
  tests/backend/unit/test_tool_guardrails.py \
  --tb=line
# → 80 passed（scorecard 含新增 provenance 用例；2026-07-24 当次）

cd frontend && node node_modules/typescript/bin/tsc --noEmit
# → exit 0
```

### 未纳入

- 启服浏览器复验 pending 真卡片
- Plan step 真执行 / Skills 内容包 / 真券商
- provenance OpenAPI schema 专项（运行时与类型已对齐，spec 字典可后补）

### 回滚

```bash
git revert <本批 commit>
# 或还原：approval-card / pending-approvals / decision-card / types / scorecard / test_agent_scorecard / 本节文档
```

### 下一批（仍可离线）

1. OpenAPI 补 `/api/agent_pending_approvals` 响应字段 `kind`/`approval_id`/`proposal_id`（若 spec 仍旧）
2. Plan step 纯状态工具深化（不抓数）
3. Skills `data/skills` 最小 builtin 包（无假行情文案）
4. 启服后：propose → pending 卡片 → approve → apply 本地 mark 联调（需 Comdr 授权启服）

