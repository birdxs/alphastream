# Bug Hunt Round 2 - GitHub Issues 清单

生成时间：2026-07-08  
总数：19 条 Bug  
已修复：14 项 ✅  
待办：5 项（P4）

---

## ✅ 已修复（14 项）

### [P0-Critical] HA-1: 数据库 schema 版本控制缺失
**Labels**: `P0`, `database`, `critical`  
**修复**: commit 64a3233  
**方案**: 新增 `_init_schema_version()` + PRAGMA user_version 管理  
**文件**: `app/core/database.py`, `app/core/wind_budget.py`  
**验证**: `PRAGMA user_version` 返回 1

---

### [P1] BD-1: web_server.py 单文件 5000+ 行
**Labels**: `P1`, `architecture`, `refactor`  
**修复**: commit 64a3233  
**方案**: 工具函数提取到 `app/web/utils.py`（215 行）  
**影响**: 20+ 通用函数复用性提升

---

### [P1] BD-2: nginx 硬编码配置
**Labels**: `P1`, `architecture`, `config`  
**修复**: commit 64a3233  
**方案**: 创建 `nginx/*.conf.template`（2 文件）  
**变量**: `${BACKEND_PORT}`, `${FRONTEND_PORT}`, `${SSL_CERT}`

---

### [P1] HA-2: 8 处裸 except 无日志
**Labels**: `P1`, `robustness`, `logging`  
**修复**: commit 64a3233  
**方案**: 改为具体异常类型 + logger.error  
**文件**: `web_server.py`（2 处）, `wind_adapter.py`, `capital_flow_analyzer.py`

---

### [P1] HA-3: 15 处环境变量无 default
**Labels**: `P1`, `robustness`, `config`  
**修复**: commit 64a3233  
**方案**: `os.getenv(key)` → `os.getenv(key, default)`  
**文件**: 9 个后端模块

---

### [P1] HA-4: 11 处全局状态裸访问
**Labels**: `P1`, `robustness`, `concurrency`  
**修复**: commit 64a3233  
**方案**: 封装为函数访问 + 文档化线程安全性  
**文件**: `network_resilience.py`（典型）

---

### [P1] 离线名称 bug: 字典未加载
**Labels**: `P1`, `bug`, `offline`  
**修复**: commit 64a3233  
**根因**: `app.logger` 在模块级执行时 context 未激活  
**方案**: `_offline_logger = logging.getLogger(__name__)`  
**验证**: 5528 条名称成功加载

---

### [P1] WM-1: Wind 超时配置偏长
**Labels**: `P1`, `config`, `timeout`  
**修复**: commit 64a3233  
**方案**: `WIND_CALL_TIMEOUT` 600s → 120s  
**文件**: `.env`（本地改动）

---

### [P2-A] BM-1: Zustand migrate 静默失败
**Labels**: `P2`, `frontend`, `logging`  
**修复**: commit babe02e  
**方案**: `migrate` 函数加 `logger.info('Migration: v${old} → v${new}')`  
**文件**: `*-store.ts`（2 处）

---

### [P2-A] BM-2: localStorage 核弹清理
**Labels**: `P2`, `frontend`, `storage`  
**修复**: commit babe02e  
**方案**: `clear()` → 选择性清理 `stockanal_` 前缀  
**文件**: 3 处前端

---

### [P2-A] BM-3: Modal 滚动锁定缺失
**Labels**: `P2`, `frontend`, `ux`  
**修复**: commit babe02e  
**方案**: `useEffect` 控制 `document.body.style.overflow`  
**文件**: 7 个 modal 组件

---

### [P2-A] BM-4: 双滚动条问题
**Labels**: `P2`, `frontend`, `css`  
**修复**: commit babe02e  
**方案**: 移除嵌套 `overflow-y-auto`  
**文件**: `dashboard/page.tsx`

---

### [P3] HA-6: NODE_ENV 无 fallback
**Labels**: `P3`, `frontend`, `config`  
**修复**: commit 1eabea8  
**方案**: 13 处加 `?? 'development'`  
**文件**: 6 个前端文件

---

### [P3] BD-7: Schema 覆盖率 66%
**Labels**: `P3`, `architecture`, `validation`  
**修复**: commit 1eabea8  
**方案**: 新增 10 Schema，装饰 10 路由  
**成果**: 60/91 → 71/92 (77%)

---

### [P3] BD-8: 守护线程无监控
**Labels**: `P3`, `monitoring`, `health-check`  
**修复**: commit 1eabea8  
**方案**: `/api/health/deep` 加 `_hd_check_daemon_threads()`  
**检查**: 5 类守护线程存活状态

---

### [P3] BM-5: 94 处 broad except
**Labels**: `P3`, `code-quality`, `error-handling`  
**修复**: commit 1eabea8  
**方案**: 11 处关键位置加注释说明合理性  
**残余**: 83 处（P4 待办）

---

## 📋 P4 待办（5 项）

### [P4] BD-3: 线程池资源池化
**Labels**: `P4`, `performance`, `resource`  
**问题**: 39 处临时 `ThreadPoolExecutor` 创建  
**方案**: 模块级全局池 `_GLOBAL_THREAD_POOL`  
**预计**: 4h  
**优先级**: Medium（稳定性提升）

---

### [P4] BD-4: 长函数拆解
**Labels**: `P4`, `refactor`, `maintainability`  
**问题**: `api_start_stock_analysis` 245 行  
**方案**: 拆分为 4 个 <50 行子函数  
**预计**: 6h  
**优先级**: Medium（可维护性）

---

### [P4] BD-5: 缓存 TTL 管理
**Labels**: `P4`, `cache`, `robustness`  
**问题**: `_PROFILE_CACHE` / `_INDEX_CACHE` 永久缓存  
**方案**: 新增 `PROFILE_CACHE_TTL_S`（default 86400）  
**预计**: 2h  
**优先级**: Low

---

### [P4] HA-5: 定时器泄漏
**Labels**: `P4`, `frontend`, `memory-leak`  
**问题**: 52 setInterval vs 23 clearInterval  
**方案**: 补齐 `useEffect` cleanup  
**预计**: 3h  
**优先级**: Medium（内存泄漏风险）

---

### [P4] BD-6: nginx 模板渲染验证
**Labels**: `P4`, `devops`, `config`  
**问题**: `.template` 文件已创建，渲染流程待验证  
**方案**: 编写 `envsubst` 启动脚本  
**预计**: 1h  
**优先级**: Low

---

**文件路径**: `docs/bug-hunt-round-2-issues.md`  
**总工时（P4）**: 约 16h
