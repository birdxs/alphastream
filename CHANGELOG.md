# Changelog

## 2026-05-25 14:48:49 +08:00

- 修复后端任务清理中 aware `now_cn()` 与无时区 `updated_at` 字符串相减导致的启动日志错误。
- 修复 `/api/market_indices` 和 A 股名称缓存加载的 `ThreadPoolExecutor` 超时后等待问题，超时后快速返回降级结果。
- 在 `DISABLE_NETWORK=1` 离线测试环境禁用导入期新闻调度、任务清理与预热线程，避免测试退出后写 closed stream。
- 修复前端首屏 hydration mismatch：语音按钮、本地面板宽度、Dashboard 问候、Agent 折叠状态与对话日期分组改为挂载后读取动态状态。
- 将市场指数离线 503 降级改为前端安静占位/保留旧数据，减少开发联调 console 误报。
