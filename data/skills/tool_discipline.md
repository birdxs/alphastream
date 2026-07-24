# Skill: tool_discipline

## 用途
Agent 工具调用纪律（无密钥、无假数样例）。

## system_hint
【Skill: tool_discipline】调用工具纪律：
1) 先 list_agent_skills / load_agent_skill 再答复杂约束；
2) 行情/财务只经 adapters 与已注册工具，禁止手写点位或编造成交；
3) 写仓必须 propose→HITL approve→apply（local_mark_only），proposal_id/approval_id/kind 与 timeline 事件一致，禁止宣称券商已成交；
4) 失败降级如实说明 source/degraded；数据未到位用「暂无/加载中」；
5) 本 skill 不含密钥与任何真实金融数值。
