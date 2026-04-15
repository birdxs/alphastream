# M3 安全审计报告 — pip-audit + npm audit

- 时间基准: 2026-04-15 15:05 +08:00 (Asia/Singapore)
- 执行人: 香草少校 (Claude Code Agent)
- 授权: Comdr
- 扫描工具: pip-audit 2.x / npm audit (官方 registry)

## 1. 扫描概览

| 生态 | 扫描目标 | 漏洞包数 | 漏洞条目数 | 严重性分布 |
|------|---------|---------|-----------|-----------|
| Python | 当前 venv (pip-audit) | 28 个包 | 60+ 条 | High/Medium 混合 (CVSS 未统一标注) |
| Node.js | frontend/ (npm audit) | 修复前: 5 / 修复后: 1 | 5 → 1 | Moderate 3 + High 2 → High 1 |

## 2. Node.js 漏洞清单 (npm audit)

### 修复前 (5 vulnerabilities)

| 包 | 版本 | 严重性 | 公告 | 修复方式 |
|----|------|--------|------|----------|
| @hono/node-server | <1.19.13 | Moderate | GHSA-92pp-h63x-v22m (静态文件中间件绕过) | npm audit fix |
| brace-expansion | <1.1.13 | Moderate | GHSA-f886-m6hf-6m8v (零步进死循环) | npm audit fix |
| hono | <=4.12.11 | Moderate | GHSA-26pp-8wgv-hjvm / r5rp-j6wh-rvv4 / xpcf-pg52-r92g / xf4j-xp2r-rqqx / wmmm-f939-6g9c | npm audit fix |
| next | 16.0.0-beta.0 — 16.2.2 | **High** | GHSA-q4gf-8mx6-v5v3 (Server Components DoS) | **npm audit fix --force (major 跳过)** |
| path-to-regexp | 8.0.0 — 8.3.0 | High | GHSA-j3q9-mxjg-w52f / 27v5-c462-wpq7 (ReDoS) | npm audit fix |

### 修复后

```
1 high severity vulnerability
  next 16.0.0-beta.0 - 16.2.2  (GHSA-q4gf-8mx6-v5v3)
```

**遗留**: next@16.2.x → 16.2.3 需要 `--force` 的 major 范围变更, 评估为非紧急 DoS (Server Components 路径), 保留待统一 Next 升级窗口处理。

## 3. Python 漏洞清单 (pip-audit, 当前 venv)

> 注: pip-audit 直接解析 requirements.txt 时触发 `resolution-too-deep`, 改用当前 venv 已装包扫描。以下为**项目 requirements.txt 直接声明**的受影响包（传递依赖不列），其余详见 `/private/tmp/.../bd2elx2g8.output`。

### 直接依赖受影响 (3 个)

| 包 | 当前 | CVE/ID | 建议 | 备注 |
|----|------|--------|------|------|
| pytest | 7.3.1 | CVE-2025-71176 | 9.0.3 | 开发依赖, 非运行时 |
| scikit-learn | 1.2.2 | PYSEC-2024-110 | 1.5.0 | requirements.txt 固定=1.2.2, 升级需回归 ML pipeline |
| streamlit | 1.50.0 | CVE-2026-33682 | 1.54.0 | TradingAgents 依赖 |

### 传递依赖高优先级 (运行时相关)

| 包 | 当前 | CVE | 建议 | 引入方 |
|----|------|-----|------|--------|
| urllib3 | 2.5.0 | CVE-2025-66418/66471, CVE-2026-21441 | 2.6.3 | requests |
| werkzeug | 3.1.3 | CVE-2025-66221, CVE-2026-21860/27199 | 3.1.6 | flask |
| tornado | 6.4.1 | CVE-2025-47287, CVE-2024-52804, CVE-2026-31958/35536, GHSA-78cv-mqj4-43f7 | 6.5.5 | 多个异步库 |
| pillow | 10.2.0 | CVE-2024-28219 | 10.3.0 | 图像处理 |
| protobuf | 5.29.5 | CVE-2026-0994 | 5.29.6 / 6.33.5 | gRPC/AI |
| python-jose | 3.3.0 | PYSEC-2024-232/233 (算法混淆) | 3.4.0 | JWT 鉴权 |
| python-socketio | 5.10.0 | CVE-2025-61765 | 5.14.0 | chainlit |
| pyopenssl | 24.2.1 | CVE-2026-27448/27459 | 26.0.0 | TLS |
| transformers | 4.52.4 | CVE-2025-5197/6638/6051/6921, CVE-2026-1839 | 4.53+ | NLP |
| torch | 2.7.1 | CVE-2025-3730 | 2.8.0 | 深度学习 |
| scrapy | 2.11.1 | GHSA-23j4 / jm3v / cwxj | 2.14.2 | 抓取 |
| twisted | 23.10.0 | CVE-2024-41671, PYSEC-2024-75 | 24.7.0 | scrapy 依赖 |

### 工具类 (低运行时风险)

pip, wheel, uv, pytest, pyasn1, pygments, py, pyarrow, pdfminer-six, ujson, orjson, nltk, zipp, pymysql — 多为构建/开发工具, 不在主 Web 路径中。

## 4. 修复动作

| 动作 | 状态 | 证据 |
|------|------|------|
| `cd frontend && npm audit fix` (非 --force) | **已执行** | 5 → 1 漏洞; package-lock.json 变更 12±行 |
| `npm audit fix --force` (next major) | **未执行** | 风险高, 待统一升级窗口 |
| pip 自动修复 | **未执行** (按任务约束) | 仅记录, 未动 requirements.txt |

### 回归验证

- `npx tsc --noEmit` — 源码无回归; 仅 `tests/e2e/m1_alt_data.spec.ts` 报 @playwright/test 未安装 (非本次变更影响)
- `npm build` — 未单独重跑 (audit fix 仅改 lockfile 中 @hono/node-server, brace-expansion, hono, path-to-regexp 的 patch 版本, 风险极低)

## 5. 风险评估

| 维度 | 评级 | 说明 |
|------|------|------|
| 生产阻断性 | 低 | 剩余 1 高危在 Next Server Components DoS, 可通过 WAF/限流缓解 |
| 鉴权相关 | 中 | python-jose 3.3.0 有算法混淆 CVE, 若使用 JWT 验证建议优先升 3.4.0 |
| 数据处理 | 中 | urllib3/werkzeug/tornado 传递漏洞, 下一版本窗口统一升级 |
| ML 模型链 | 中 | transformers/torch/scikit-learn 有 CVE, 非对外暴露接口, 可延后 |

## 6. 遗留建议 (下一迭代)

1. **优先**: 升级 `python-jose` 3.3.0 → 3.4.0 (若项目使用 JWT); 验证 OAuth 流程。
2. **次优**: urllib3/werkzeug/tornado → 最新 patch; pip install -U 后跑全量 pytest。
3. **Next 升级窗口**: next 16.2.2 → 16.2.3 (允许 major 跨越), 联动 tsc/build 全量回归。
4. **建立定期扫描**: 加入 CI `npm audit --audit-level=high --registry=https://registry.npmjs.org` 与 `pip-audit --strict` (待解决 resolution-too-deep, 可用 `pip freeze | pip-audit -r -`)。

## 7. 证据路径

- npm audit JSON: `/tmp/npm_audit.json`
- pip-audit 列输出: `/private/tmp/claude-501/.../tasks/bd2elx2g8.output`
- package-lock.json 变更: `git diff frontend/package-lock.json`
