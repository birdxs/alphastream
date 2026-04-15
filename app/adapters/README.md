# app/adapters — 数据源适配器

此文件夹收纳所有数据源适配器；一旦这里的结构发生变化，请务必更新我……就像重新标记领地一样。

## 文件清单

| 文件 | 地位 | 功能 |
|---|---|---|
| `base_adapter.py` | 契约层 | `BaseAdapter` 抽象基类：K线/成分股/信息/财务/健康检查 |
| `akshare_adapter.py` | 主数据源 | akshare 多数据源冗余（东财/同花顺/新浪/腾讯） |
| `baostock_adapter.py` | 备援数据源 | baostock 日线/周线/月线兜底 |
| `opencli_bridge.py` | 爬取桥(P0-A1 2026-04-15) | OpenCLI 子进程桥：三大热股榜+浏览器爬取；Node/opencli未装降级为空 |
| `__init__.py` | 导出 | 统一入口 |

## 约定

- 所有新适配器必须继承 `BaseAdapter`，实现 6 个抽象方法（不支持的能力返回空对象）
- 头部 3 行铭牌 `Input/Output/Pos` 必填
- 爬取/外部进程类适配器必须对环境缺失做降级，不得向上游抛异常
