## investors - 投资者人格Agent子系统

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 模块入口 | 导出所有投资者Agent和协调器 |
| `buffett.py` | 核心Agent | 巴菲特风格：护城河、安全边际、长期持有 |
| `munger.py` | 核心Agent | 芒格风格：反向思维、多元思维模型、避免愚蠢 |
| `lynch.py` | 核心Agent | 彼得林奇风格：PEG估值、六大股票分类、成长股 |
| `damodaran.py` | 核心Agent | 达摩达兰风格：DCF估值、量化驱动、叙事+数字 |
| `investor_coordinator.py` | 协调器 | 调用4个Agent并投票汇总共识建议 |

一旦这里的结构发生变化，请务必更新我... 就像重新标记领地一样。
