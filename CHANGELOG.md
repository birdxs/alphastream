# Changelog

## 2026-05-29 09:43:00 +08:00

- 治理前端 Recharts `The width(-1) and height(-1) of chart should be greater than 0` 警告：新增统一封装 `frontend/src/components/charts/safe-responsive-container.tsx`，用 `ResizeObserver` 实测容器渲染宽高，仅在宽高均 >0 时挂载 Recharts `ResponsiveContainer`，容器被隐藏（`display:none`）、切换或布局未完成（实测尺寸 ≤0）时渲染 `Skeleton` 占位，待尺寸有效后再渲染图表。
- 将 9 处直接使用 `ResponsiveContainer` 的图表替换为 `SafeResponsiveContainer`：`charts/base-line-chart.tsx`、`charts/base-bar-chart.tsx`、`charts/base-pie-chart.tsx`、`artifacts/capital-flow-chart.tsx`、`artifacts/score-radar.tsx`、`artifacts/esg-scorecard.tsx`、`artifacts/shipping-chart.tsx`、`artifacts/hiring-signal.tsx`（折线+饼图两处）。
- 遵守铁律 #1：占位仅为 `Skeleton` 骨架，不渲染任何看起来像真实金融数据的假值。

## 2026-05-29 09:32:08 +08:00

- 治理资金流上游网络降级日志：Eastmoney 个股/板块资金流遇到 `ProxyError`、`RemoteDisconnected`、`ConnectionError`、`Timeout` 等网络层异常时，改为 WARNING 级精简日志（"资金流上游降级: ..."），不再输出完整 Traceback；非网络类异常仍保留 ERROR 级完整堆栈，便于排查真实 bug。
- 返回契约保持不变（`get_individual_fund_flow`/`get_individual_fund_flow_rank`/`get_concept_fund_flow` 的 `data`/`error`/`count`/`source`/`amount_unit` 字段不变），新增单元测试覆盖网络降级与非网络异常分流。

## 2026-05-25 14:48:49 +08:00

- 修复后端任务清理中 aware `now_cn()` 与无时区 `updated_at` 字符串相减导致的启动日志错误。
- 修复 `/api/market_indices` 和 A 股名称缓存加载的 `ThreadPoolExecutor` 超时后等待问题，超时后快速返回降级结果。
- 在 `DISABLE_NETWORK=1` 离线测试环境禁用导入期新闻调度、任务清理与预热线程，避免测试退出后写 closed stream。
- 修复前端首屏 hydration mismatch：语音按钮、本地面板宽度、Dashboard 问候、Agent 折叠状态与对话日期分组改为挂载后读取动态状态。
- 将市场指数离线 503 降级改为前端安静占位/保留旧数据，减少开发联调 console 误报。

## 2026-05-25 15:10:37 +08:00

- 记录 Comdr 手动前端测试值守发现：OneAPI 429 自动重试后成功、资金流 Eastmoney ProxyError 当前会输出完整 Traceback、Recharts 零尺寸容器警告需后续治理。
- 确认手测收尾前后端仍可用：后端 `/health` 200，前端 `/dashboard` HEAD 200。
- 停止本地后端 8888 与前端 3000 服务，清理开发缓存并释放端口；未删除 `node_modules`，未 push。
