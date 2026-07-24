Agent可视化组件目录。

- `agent-status-badge.tsx` - Agent状态徽章（pending/started/completed/error）
- `tool-call-card.tsx` - 工具调用详情卡（name/args_digest/ok/error/duration_ms/source）
- `tool-call-timeline.tsx` - 工具调用时间线列表（P0-4 契约字段）
- `agent-progress-panel.tsx` - Agent进度面板（渐变总进度条+实时事件流时间线+可折叠Agent状态网格，自动滚动跟随）
- `agent-side-panel.tsx` - Mac风格终端Agent实时面板（三点标题栏+等宽字体+树形日志+暗/亮双主题+导出/清空/折叠）
- `agent-log-drawer.tsx` - Agent执行日志抽屉（右侧Sheet，展示Agent状态+工具调用）
- `thinking-chain.tsx` - AI思考链展示组件（可折叠）
- `approval-card.tsx` - HITL 单条确认卡（kind / approval_id / 写仓提案摘要 / 风险级 / 批准拒绝）
- `pending-approvals.tsx` - 轮询 pending API（归一化 kind/approval_id/proposal_id）并挂载确认卡
- `plan-list-panel.tsx` - 只读 GET /api/agent_plans（PlanDAG list，不抓数不执行）

一旦这里的结构发生变化，请务必更新我... 就像重新标记领地一样。
