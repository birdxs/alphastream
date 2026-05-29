# app/core/ - 核心基础设施
- ai_client.py(AI统一客户端，支持chat_completion被动问答 + chat_with_tools主动Function Calling工具调用循环 + chat_completion_stream/chat_with_tools_stream流式输出)
- tools.py(共享工具注册表，LangChain @tool格式 + OpenAI Function Calling schema双格式，含execute_tool分发器)
- artifact_wrapper.py(Generative UI后端数据协议层，将工具结果包装为前端可渲染的Artifact结构化JSON)
- data_provider.py(数据层), cache.py(缓存), search.py(搜索), agent_memory.py(Agent长期记忆)
- event_bus.py(Agent事件总线 + SSE流式桥接，含create_sse_bridge/destroy_sse_bridge队列桥接方法)
- conversation.py(对话上下文持久化，多轮AI分析对话管理，JSON文件存储)
- database.py(数据库), fallback_manager.py(降级管理)
- wind_budget.py(Wind数据源省积分底座：WindCache持久化缓存 + WindQuota日配额闸门S/A/B硬隔离，独立sqlite引擎与业务库隔离) [NEW-FILE:#20260529-WIND-01]
- 一旦这里的结构发生变化，请务必更新我
