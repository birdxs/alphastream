# app/core/ - 核心基础设施
- ai_client.py(AI统一客户端，支持chat_completion被动问答 + chat_with_tools主动Function Calling工具调用循环)
- tools.py(共享工具注册表，LangChain @tool格式 + OpenAI Function Calling schema双格式，含execute_tool分发器)
- data_provider.py(数据层), cache.py(缓存), search.py(搜索), agent_memory.py(Agent长期记忆), event_bus.py(Agent事件总线)
- 一旦这里的结构发生变化，请务必更新我
