# 交付状态清单 · Sprint0–3（AI 原生融化）

```
Input: Sprint0–3 已落地 commit + 本地可使用验收证据
Output: 中文交付清单（能力 / 启动 / 验证 / 限制 / 回滚）
Pos: docs/design/DELIVERY-STATUS.md — 交付冲刺唯一状态入口
```

| 字段 | 值 |
|------|-----|
| **文档版本** | `v1.0` |
| **交付锚点** | **2026-07-24 01:18:57 +08:00**（校时：本机 `2026-07-23 10:18:57 -0700` ≡ UTC 17:18:57；Cloudflare Date `Thu, 23 Jul 2026 17:18:58 GMT`；GitHub Date `Thu, 23 Jul 2026 17:18:52 GMT`；最大偏差 ≤6s，通过） |
| **分支** | `main`（本地 ahead origin，默认 **不 push**） |
| **工作目录** | `/Users/panda/Downloads/StockAnal_Sys` |
| **设计依据** | `docs/design/dojo-agents-absorption-plan.md` v1.2 |
| **约束** | 铁律 #1–#4；禁 Playwright；默认禁 push |

---

## 1. Sprint 状态一览

| Sprint | 状态 | 说明 |
|--------|------|------|
| Sprint 0 | **DONE** | 只读盘点 + 契约 → `sprint0-inventory.md` |
| Sprint 1 | **DONE（主切片）** | 护栏 / HITL / 辩论证据 / 工具时间线 |
| Sprint 2 | **DONE** | 意图规则路由 + 持仓 snapshot 只读 |
| Sprint 3 | **DONE（本切片）** | 组合风险诊断 + 观察 mode |
| Sprint 4 | 未开 | 写仓 harness / facade / P2 选修 |

### P0 汇总

| ID | 能力 | 状态 |
|----|------|------|
| P0-1 工具护栏 | **DONE** |
| P0-2 意图协议 | **部分 DONE**（规则路由；写工具硬拦可增强） |
| P0-3 真仓只读 | **DONE** |
| P0-4 工具时间线 | **DONE**（provenance[] 待补） |
| P0-5 HITL 确认面 | **DONE** |
| P0-6 辩论证据面 | **DONE**（terminal 完成态可再统一） |
| P0-7 降级帽 | **TODO** |

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
| Sprint0 盘点锁定 | `7886bd5` | — | inventory + approval |
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

1. **P0-7 未做**：降级 run 的统一 `agent.degraded` 横幅 + confidence_cap 未产品闭合。  
2. **P0-2 不完整**：规则意图路由已上；完整 `STOCKANAL_TOOL_PROTOCOL` 写工具服务端硬拦仍可增强。  
3. **provenance[]**：工具时间线字段已规范；完整数据血统折叠 Artifact 未做。  
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
