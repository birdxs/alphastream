# RESEARCH-01: Reasoning 协议三方对比调研

- 时间: 2026-05-18 11:32:00 +08:00 (Asia/Singapore)
- 时间源校验: 本机 date 2026-05-18 11:31:58 +0800, Google Date 头 02:32:01 GMT, 偏差 < 5s
- 检索时间锚点: 2026-05-18 11:32 +08:00
- 调研对象: DeepSeek V4 Preview / MiMo-V2.5-Pro / OpenAI o1
- 触发: FIX-5 reasoning_content 协议适配需求

## 一、DeepSeek V4 状态确认

**已发布**：DeepSeek V4 Preview 于 **2026-04-24** 官方公告，两个变体：
- **DeepSeek-V4-Pro**: 1.6T 总参 / 49B 激活 / 1M context
- **DeepSeek-V4-Flash**: 284B 总参 / 13B 激活 / 1M context

API 迁移：base_url 不变，model 改为 `deepseek-v4-pro` 或 `deepseek-v4-flash`。**legacy `deepseek-chat` / `deepseek-reasoner` 将于 2026-07-24 下线**，当前指向 v4-flash 的非思考/思考模式。

## 二、三方协议对比矩阵

| Provider | reasoning 触发字段 | 响应字段 | 多轮回传规则（无 tool） | 多轮回传规则（含 tool） | tool_calls | json_mode | prefix cache | 备注 |
|---|---|---|---|---|---|---|---|---|
| **DeepSeek V4** (Pro/Flash) | `thinking:{type:enabled}` + `reasoning_effort:high/max` | `delta.reasoning_content` + `delta.content` | 不需回传，传了被忽略 | **必须回传**，否则 400 | 支持，新协议 | 支持 (`response_format:{type:json_object}`) | 支持，计费字段 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` | 与 R1 协议**相反** |
| **DeepSeek R1** (legacy `deepseek-reasoner`) | 模型名直接走 reasoning | `reasoning_content` | **不能回传**，传了 400 | **不能回传**，传了 400 | 不支持工具调用 | 不支持 | 部分支持 | 即将 2026-07-24 下线 |
| **MiMo-V2.5-Pro** (Xiaomi) | `chat_template_kwargs:{enable_thinking:true}` 或部署侧默认 | `message.reasoning_content` | 不需回传 | **必须回传** (与 V4 同) | 支持，需 `--tool-call-parser mimo` | 支持 | vLLM/SGLang 自托管，OneAPI 网关代理 | 1.02T MoE / 42B 激活 / 1M context |
| **MiMo via OpenRouter** | `reasoning` parameter | `reasoning_details[]` 数组 | 保留 reasoning_details | 保留 reasoning_details | 支持 | 支持 | 透传上游 | 字段名不同 |
| **OpenAI o1 / o3** | `reasoning_effort:low/medium/high` | (内部 reasoning 不暴露) | 无需回传，API 屏蔽 | 无需回传 | 支持 | 支持 | 支持 | reasoning token 计费在 usage |
| **GPT-4 / Claude / 普通模型** | 无 reasoning 字段 | 仅 `delta.content` | N/A | N/A | 支持 | 支持 | 部分支持 | 兜底路径 |

## 三、本项目影响分析

`.env` 当前配置 `OPENAI_API_MODEL=mimo-v2.5-pro`，通过 `https://oneapi.xiongmaodaxia.online/v1`（OneAPI 网关，OpenAI 兼容协议代理 mimo）。

错误现象：`Param Incorrect: The reasoning_content in the thinking mode must be passed back to the API.`

**根因**：`app/core/ai_client.py` 当前实现仅持久化 `message.content`，**丢弃了 `reasoning_content`**。MiMo（与 DeepSeek V4 同协议）在多轮 tool call 中要求 reasoning_content 必须回传，否则 400。

## 四、设计决策

按 Comdr 指令实现 **`app/core/llm_providers.py` 适配器层**：

1. **请求侧 normalize_request**:
   - DeepSeek R1 / legacy reasoner: 主动剥离 history 中所有 assistant.reasoning_content
   - DeepSeek V4 / MiMo: 保留 history 中 assistant.reasoning_content，特别是 tool_call 上下文
   - OpenAI o1: 不传 reasoning_content（API 不接收），可加 `reasoning_effort` 透传
   - Generic: 剥离所有 reasoning 字段，纯 OpenAI 兼容

2. **响应侧 parse_stream_chunk**:
   - 统一返回 `(thinking_delta, content_delta, tool_call_delta, usage)`
   - 兼容 `delta.reasoning_content` (DeepSeek V4 / MiMo) 与 `delta.reasoning_details[]` (OpenRouter)

3. **路由 get_adapter(model_name)**:
   - 前缀匹配：`deepseek-r1*` / `deepseek-reasoner` / `deepseek-v4*` / `deepseek-v3*` / `deepseek-chat` / `mimo-*` / `o1-*` / `o3-*` / 其他兜底

4. **缓存字段透传** (DeepSeek V4 新特性):
   - 从 `usage.prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` 读取并 publish 到 event_bus，供后续优化决策

## 五、证据清单 (≥3 来源)

| # | 来源 | URL | 发布日期 | 检索时间 (+08:00) | 采纳判定 |
|---|---|---|---|---|---|
| 1 | DeepSeek 官方 V4 发布公告 | https://api-docs.deepseek.com/news/news260424 | 2026-04-24 | 2026-05-18 11:32 | 采纳：V4 双变体 + API 迁移 + thinking mode 默认 |
| 2 | DeepSeek Thinking Mode 官方协议文档 | https://api-docs.deepseek.com/guides/thinking_mode | 2026 | 2026-05-18 11:32 | 采纳：多轮回传规则（无 tool 忽略 / 含 tool 必须回传） |
| 3 | Issue: LiteLLM #26395 V4 multi-turn reasoning_content 剥离 bug | https://github.com/BerriAI/litellm/issues/26395 | 2026-04-25+ | 2026-05-18 11:32 | 采纳：业界同类 bug 与修复路径参照 |
| 4 | Issue: openclaw #71435 V4 + tool_calls 400 | https://github.com/openclaw/openclaw/issues/71435 | 2026-04-26+ | 2026-05-18 11:32 | 采纳：印证 R1→V4 协议反转 |
| 5 | n8n Issue #29119 deepseek-v4-flash thinking + tools 400 | https://github.com/n8n-io/n8n/issues/29119 | 2026-04-25+ | 2026-05-18 11:32 | 采纳：兜底佐证 |
| 6 | Xiaomi MiMo-V2.5-Pro vLLM Recipes | https://recipes.vllm.ai/XiaomiMiMo/MiMo-V2.5-Pro | 2026 | 2026-05-18 11:32 | 采纳：MiMo 与 V4 同协议规则确认 |
| 7 | MiMo-V2.5-Pro HuggingFace | https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro | 2026 | 2026-05-18 11:32 | 采纳：模型规格与 reasoning_content 暴露方式 |
| 8 | OpenRouter MiMo-V2.5-Pro API | https://openrouter.ai/xiaomi/mimo-v2.5-pro/api | 2026 | 2026-05-18 11:32 | 采纳：reasoning_details 字段差异 |
| 9 | DeepSeek API 更新日志 | https://api-docs.deepseek.com/updates | 持续 | 2026-05-18 11:32 | 采纳：合并字段调整与迁移时间表 |

## 六、未来挑战

- DeepSeek V4 GA 版本可能再次调整协议（当前是 Preview）→ adapter 层抽象足够鲁棒
- mimo 多 backend（OneAPI / OpenRouter / 自托管 vLLM/SGLang）字段名不一致 → adapter 用 base_url + model_name 双键路由
- 1M context 后期可能影响成本 → 透传 cache hit/miss 计费供观测
