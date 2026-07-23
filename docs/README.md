文件列表：见下索引表
地位：系统文档目录（承担 docs/ 总索引职责，无需独立 INDEX.md — "优先只改不增"原则）
功能：作战记录 | 架构蓝图 | API契约 | 数据层扩张 | 搜索引擎交叉验证

一旦这里的结构发生变化，请务必更新我... 就像重新标记领地一样。

## 文档索引 (2026-04-15 14:00 +08:00)

### 交接档案 (置顶)
| 文档 | 功能 |
|---|---|
| `FINAL_REPORT_2026-04-15.md` | **一日作战总结报告** — 109 commits/10 Phase/21 adapter/12 Agent/10 API/15 Artifact 全链路交接 [NEW-FILE:#20260415-55] |

### 运维入门
| 文档 | 功能 |
|---|---|
| `OPERATIONS.md` | **v3.1 运维手册** — 启动/Key申请/代理/故障排查/14-Agent链路 [NEW-FILE:#20260415-42] |

### 架构与对接
| 文档 | 功能 |
|---|---|
| `design/dojo-agents-absorption-plan.md` | **DojoAgents 吸收·融化设计**（AI 原生贯穿；待 Comdr 审批；禁未授权编码） |
| `API.md` | 40+ 后端路由对接规范 (含 P3 10 端点) |
| `FRONTEND_ARCHITECTURE.md` | Next.js 16 + React 19 + Chat/Artifacts 范式蓝图 |
| `FRONTEND_RESEARCH.md` | 前端技术选型调研 |
| `FRONTEND_REDESIGN_PLAN.md` | Dark Glassmorphism 重构计划 |
| `FRONTEND_GAP_REVIEW.md` | 前端实现与设计差距审查 |

### 数据层与搜索层
| 文档 | 功能 |
|---|---|
| `FINANCIAL_DATA_EXPANSION_2026-04-15.md` | **数据层 v2**：21 adapter + 16 domain Registry + 10 P3 API + 5 Artifact + 12 Agent 接入全纪录 |
| `SEARCH_ENGINES.md` | 17 引擎 (8 CN + 9 全球 + 2 知识) 权威来源交叉验证 |
| `BACKEND_GAPS.md` | 后端差距追踪 |

### 作战记录
| 文档 | 功能 |
|---|---|
| `BATTLE_2026-04-14.md` | 2026-04-14 上午作战 |
| `BATTLE_2026-04-14_PM.md` | 2026-04-14 下午作战 (v3.0 重构收尾) |
| `GAP_TRACKING.md` | 总体差距闭环追踪 |
| `AI_NATIVE_RESEARCH.md` | AI-Native 范式调研 |

## 文件夹领地标记入口

- 根 `README.md` — 项目总览 + 启动指引
- `app/adapters/README.md` — 21 adapter 清单 (含 P3 另类数据 5 支柱)
- `clis/README.md` — 3 JS 爬虫 (雪球/东财股吧/财联社)
- `frontend/src/components/artifacts/README.md` — 15 Artifact 组件 (含 P3 另类数据 5 组件)
