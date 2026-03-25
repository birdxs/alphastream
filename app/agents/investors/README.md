## investors - 投资者人格Agent子系统

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 模块入口 | 导出所有投资者Agent和协调器 |
| `buffett.py` | 核心Agent | 巴菲特风格：护城河、安全边际、长期持有 |
| `munger.py` | 核心Agent | 芒格风格：反向思维、多元思维模型、避免愚蠢 |
| `lynch.py` | 核心Agent | 彼得林奇风格：PEG估值、六大股票分类、成长股 |
| `damodaran.py` | 核心Agent | 达摩达兰风格：DCF估值、量化驱动、叙事+数字 |
| `investor_coordinator.py` | 协调器 | AI驱动共识构建：综合权衡4位投资者论据强度，AI不可用时降级到投票机制 |

### 共识构建机制

协调器采用AI驱动的综合研判替代简单投票计数：

1. **基础投票统计**（`_compute_vote_stats`）：作为参考数据，不作为最终决策
2. **投资者分析收集**（`_collect_investor_analyses`）：格式化所有投资者的完整分析文本
3. **AI综合研判**（`_build_consensus`）：由AI首席策略官权衡论据逻辑强度、分析分歧根因
4. **降级机制**（`_fallback_consensus`）：AI不可用时退回到原有Counter投票逻辑

返回字段中 `ai_driven: true/false` 标识当前共识是否由AI生成。

一旦这里的结构发生变化，请务必更新我... 就像重新标记领地一样。
