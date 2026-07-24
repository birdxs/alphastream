# Skill: research_depth

## 用途
分析深度档位提示（stub，非实时行情）。

## system_hint
【Skill: research_depth】深度档位约定：1=快扫关键位/量价；2=加资金流；3=加基本面摘要；4=加行业/对比；5=全量+风险情景。
规则：按用户 research_depth 取对应层，禁止越层编造未请求数据；取数必须走 adapters/工具，本 skill 不提供数值。
