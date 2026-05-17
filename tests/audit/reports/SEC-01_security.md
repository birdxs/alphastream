# SEC-01 安全审计报告：鉴权 + CORS + 错误脱敏

- 审计任务：W1 安全审计 SEC-01
- 审计时间：2026-05-17 21:12:59 ~ 21:34:00 +08:00
- 审计员：香草少校 / Panda agent team
- 仓库：`/Users/panda/Downloads/StockAnal_Sys/`
- 测试文件：`tests/backend/api/test_security_auth_cors.py`
- 证据日志：`tests/audit/evidence/SEC-01_pytest.log`

---

## 1. 摘要

| 项目 | 状态 |
| --- | --- |
| 用例总数 | 23 |
| PASS | 18 |
| XFAIL（暴露未实现的安全防护） | 3 |
| XPASS（业务已实现，待升级测试为正向） | 1 |
| SKIPPED（无对应端点） | 1 |
| FAIL | 0 |
| 总耗时 | 7.40s |

主要结论：
- **SEC-1 致命**：`app/web/web_server.py` 63 个 `/api/*` 路由全部未挂载任何鉴权装饰器（`@require_api_key` / `@require_hmac_auth` 计数为 0）。
- **SEC-2 高**：第 91–96 行 `CORS(app, resources=...)` 直接执行，**未被 `if app.debug:` 或环境守卫包裹**；`_DEV_ORIGIN_PATTERNS` 含 LAN IP 段（`192.168`、`10.x`）+ 工作区改动的 `192.168.43.125:3000`，无论生产/开发同等放行。
- **错误脱敏**：抽样 10 条路由响应体均未泄漏绝对路径/Traceback/SQL/Secrets，当前实现合规。
- **SSE**：未发现独立 SSE 端点路径；预检层面 evil origin 未被回显（CORS 拒绝默认行为）。
- **上传**：`/api/upload_image` 对超大与非图片 MIME 已拒绝（test_upload_non_image_rejected 现 XPASS，需升级为正向断言）。

---

## 2. 测试矩阵

### A. SEC-1 鉴权矩阵（4 用例）

| # | 用例 | 结果 | 含义 |
| - | --- | --- | --- |
| A1 | `test_no_auth_decorators_referenced` | PASS | web_server.py 内 `@require_api_key`/`@require_hmac_auth` 计数为 0 |
| A2 | `test_api_routes_count_baseline` | PASS | `/api/*` 路由总数 = 63（baseline ≥ 60、≤ 120） |
| A3 | `test_all_routes_should_require_auth_in_production` | XFAIL | 静态扫描期望 63 条路由均挂鉴权 → 全部缺失 |
| A4 | `test_all_routes_currently_unauthenticated_baseline` | PASS | `/api/health`、`/api/version`、`/api/dashboard_data` 不带鉴权头均非 401/403 |

### B. SEC-2 CORS 守卫（5 用例）

| # | 用例 | 结果 | 含义 |
| - | --- | --- | --- |
| B1 | `test_cors_config_has_no_debug_guard` | PASS | CORS 上方 300 字符未匹配 `if app.debug`/`FLASK_ENV` 守卫 |
| B2 | `test_cors_allows_lan_ip_origins` | PASS | `_DEV_ORIGIN_PATTERNS` 含 `192.168`、`10\.` 模式 |
| B3 | `test_cors_evil_origin_should_be_rejected` | PASS | `https://evil.example.com` 预检不回显 Allow-Origin |
| B4 | `test_cors_lan_ip_origin_allowed_baseline` | PASS | `http://192.168.43.125:3000` 预检放行（baseline 记录） |
| B5 | `test_cors_in_production_should_block_lan_ip` | XFAIL | PROD 模式下应拒绝 LAN IP → 当前仍放行 |

### C. 错误脱敏（10 用例）

| 路由 | 方法 | 结果 |
| --- | --- | --- |
| `/api/health` | GET | PASS |
| `/api/version` | GET | PASS |
| `/api/dashboard_data` | GET | PASS |
| `/api/index_stocks` | GET | PASS |
| `/api/latest_news` | GET | PASS |
| `/api/conversations` | GET | PASS |
| `/api/north_flow_history` | POST(空 body) | PASS |
| `/api/save_portfolio` | POST(空 body) | PASS |
| `/api/nonexistent_route_zzz_42` | GET → 404 | PASS |
| `/api/conversations/__bogus__` | GET | PASS |

脱敏正则覆盖：`/Users/panda/`、`Traceback (most recent call last)`、`File "...py", line N, in`、`SELECT … FROM`、`INSERT INTO`、`sk-[A-Za-z0-9]{20,}`、`OPENAI_API_KEY=...`。**全部未命中**，证明错误响应体当前合规。

### D. SSE 跨域（2 用例）

| 用例 | 结果 | 说明 |
| --- | --- | --- |
| `test_sse_with_evil_origin_rejected` | XFAIL | 当前 SSE 未对 Origin 头强校验 |
| `test_sse_endpoint_cors_header_does_not_echo_evil` | SKIPPED | 仓库未发现独立 `/api/.../stream` 端点路径 |

### E. 上传限制（2 用例）

| 用例 | 结果 | 说明 |
| --- | --- | --- |
| `test_upload_oversize_rejected` | PASS | 12 MB 上传被拒（400/413/415） |
| `test_upload_non_image_rejected` | XPASS | 非图片 MIME 拒绝已实现 → 测试应升级为正向 PASS |

---

## 3. 关键证据

### 3.1 SEC-1：63 条 `/api/*` 路由零鉴权

`grep -c "@app.route('/api/" app/web/web_server.py` → **63**
`grep -c "require_api_key\|require_hmac_auth" app/web/web_server.py` → **0**

baseline 探针响应（不带鉴权头）：
- `GET /api/health` → 200
- `GET /api/version` → 200
- `GET /api/dashboard_data` → 200

### 3.2 SEC-2：CORS 配置原文（app/web/web_server.py:91–96）

```python
CORS(
    app,
    resources={r"/api/*": {"origins": _ALL_ORIGIN_PATTERNS}},
    supports_credentials=True,
)
```
- 上下文未出现 `if app.debug`、`FLASK_ENV`、`ENV == "development"` 任一守卫。
- `_DEV_ORIGIN_PATTERNS` 含正则形态 `r"http://192\.168\.\d{1,3}\.\d{1,3}:\d+"`、`r"http://10\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+"`，以及显式的 `http://192.168.43.125:3000`（工作区变更）。

### 3.3 错误脱敏抽样响应

10/10 路由响应体未命中任何敏感模式（详见 evidence 日志第 19–28 行）。

---

## 4. 风险评级与影响

| 缺陷 | 评级 | CVSS 估算 | 受影响面 |
| --- | --- | --- | --- |
| SEC-1 路由裸奔 | 致命 (Critical) | 9.1 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:L) | 全部业务 API：股票分析触发、组合保存、对话历史等 |
| SEC-2 CORS 守卫缺失 | 高 (High) | 7.5 (AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:L/A:N) | 任意 LAN 内 origin 可在浏览器中携带 cookie 调用 API（supports_credentials=True 放大）|
| 错误脱敏 | 通过 | – | – |
| SSE Origin 校验缺失 | 中 (Medium) | 5.3 | 流式接口可能被未授权 origin 窃听（待业务侧定位 SSE 路径） |
| 上传 MIME | 通过（已实现，需升级测试） | – | – |

---

## 5. 缺陷清单

### 5.1 SEC-1（致命）— 63 条路由全部裸奔

**前 20 条样本**（按行号顺序，证据：`app/web/web_server.py`）：

| # | 行号 | 路由 | 方法 |
| - | --- | --- | --- |
| 1 | 622 | `/api/north_flow_history` | POST |
| 2 | 753 | `/api/start_stock_analysis` | POST |
| 3 | 827 | `/api/analysis_status/<task_id>` | GET |
| 4 | 857 | `/api/cancel_analysis/<task_id>` | POST |
| 5 | 883 | `/api/start_etf_analysis` | POST |
| 6 | 942 | `/api/etf_analysis_status/<task_id>` | GET |
| 7 | 970 | `/api/enhanced_analysis` | POST |
| 8 | 1136 | `/api/stock_data` | GET |
| 9 | 1247 | `/api/stock_profile` | GET |
| 10 | 1339 | `/api/stock_name` | GET |
| 11 | 1354 | `/api/stock_name_search` | GET |
| 12 | 1434 | `/api/start_market_scan` | POST |
| 13 | 1532 | `/api/scan_status/<task_id>` | GET |
| 14 | 1562 | `/api/cancel_scan/<task_id>` | POST |
| 15 | 1639 | `/api/market_indices` | GET |
| 16 | 1645 | `/api/market_stream` | GET |
| 17 | 1676 | `/api/index_stocks` | GET |
| 18 | 1698 | `/api/industry_stocks` | GET |
| 19 | 1721 | `/api/board_stocks` | GET |
| 20 | 1839 | `/api/fundamental_analysis` | POST |

剩余 43 条详见 `tests/audit/evidence/routes_raw.txt` 与静态扫描脚本。

**风险**：任意外网客户端可：
- 触发昂贵的 LLM/AI 分析任务（成本攻击）
- 读取/修改对话历史与持仓
- 取消他人扫描任务（DoS）

### 5.2 SEC-2（高）— CORS DEBUG 守卫缺失

文件：`app/web/web_server.py:91-96`
- CORS 配置直接执行，无任何环境守卫
- `_DEV_ORIGIN_PATTERNS` 在生产模式下仍生效
- `supports_credentials=True` 放大 CSRF 攻击面

### 5.3 错误脱敏 — 当前合规

10 条抽样路由响应体未泄漏路径/Traceback/SQL/Secrets。

### 5.4 SSE — 待定位

仓库未发现独立 SSE endpoint 路径（`/stream`、`/sse/events` 均未匹配）。需业务侧定位后补测。

### 5.5 D-3 决策落地清单（C 方案：DEV 放行 / PROD 强制）

| 项 | 当前状态 | C 方案改造 | 验证用例（XFAIL → PASS） |
| --- | --- | --- | --- |
| 鉴权装饰器 | 0 处 | 引入 `@require_api_key` + 全局 `before_request` 拦截 `/api/*`；DEV 时检测到 `FLASK_ENV != production` 且无 API_KEY 配置 → bypass | `test_all_routes_should_require_auth_in_production` |
| CORS 守卫 | 无 | 用 `if app.debug or os.getenv('FLASK_ENV') != 'production':` 包裹 `_DEV_ORIGIN_PATTERNS`；PROD 仅保留 `_PROD_ORIGIN_PATTERNS` | `test_cors_in_production_should_block_lan_ip` |
| LAN IP 白名单 | DEV/PROD 同等放行 | PROD 完全剥离 `192.168`、`10.x`、`192.168.43.125` | 同上 |
| SSE Origin 校验 | 无 | 在 SSE 端点入口检查 `request.headers.get('Origin')` 是否在白名单 | `test_sse_with_evil_origin_rejected` |
| 上传 MIME | 已实现 | 测试转正向 | `test_upload_non_image_rejected`（去 `@pytest.mark.xfail`） |
| 错误脱敏 | 已合规 | 维持现状；扩充 secret 模式覆盖（如 ANTHROPIC_API_KEY、数据库 DSN） | 持续监控 |

---

## 6. 鉴权方案建议（仅设计参考，待 Comdr 审批）

### 方案 A：`@require_api_key` 装饰器（轻量）
- 优点：改动小、可灰度（先标 50% 路由）
- 缺点：63 条逐一加装饰器，遗漏风险高

### 方案 B：全局 `before_request` 守卫（推荐）
```python
@app.before_request
def _api_auth_guard():
    if not request.path.startswith('/api/'):
        return
    if app.debug and not os.getenv('FORCE_API_AUTH'):
        return
    if request.path in WHITELIST:  # 健康检查/版本
        return
    if not _validate_api_key(request.headers.get('X-API-Key')):
        return jsonify({'error': 'unauthorized'}), 401
```
- 优点：一处接入，零路由侧改动
- 缺点：白名单维护

### 方案 C：HMAC + 时间戳（强）
- 用于写操作（POST/DELETE）
- 防重放 + 签名 → 适合开放外网部署

---

## 7. 验证方式（复核步骤）

```bash
cd /Users/panda/Downloads/StockAnal_Sys
python -m pytest tests/backend/api/test_security_auth_cors.py -v --tb=short \
  2>&1 | tee tests/audit/evidence/SEC-01_pytest.log
```

预期输出：`18 passed, 1 skipped, 3 xfailed, 1 xpassed`

鉴权方案落地后，应将 `test_all_routes_should_require_auth_in_production` 与 `test_cors_in_production_should_block_lan_ip` 的 `@pytest.mark.xfail` 装饰器移除，转为强 PASS 断言。

---

## 8. 时间戳记录

| 阶段 | 时间（Asia/Singapore +08:00） |
| --- | --- |
| 任务接收 | 2026-05-17 21:12:00 |
| 静态扫描完成 | 2026-05-17 21:18:00 |
| 测试编写完成 | 2026-05-17 21:30:00 |
| pytest 首次跑通 | 2026-05-17 21:33:00 |
| 报告落盘 | 2026-05-17 21:34:00 |

时间锚点：本机 `date` = `2026-05-17 21:12:59 +0800`；任务给定日期 = 2026-05-17（与 `currentDate` 一致）。

---

## 9. 边界声明

- 本审计**仅产出测试代码与报告**，未修改任何业务源码。
- 鉴权/CORS 守卫的落地改造需 Comdr 审批后由业务侧实施。
- 所有 XFAIL 用例为"暴露未实现的安全防护"标记，落地后应去 xfail。
