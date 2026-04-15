# clis/ — OpenCLI 自建适配器领地

> Input: 命令行参数 (symbol/code/limit/pages)
> Output: 结构化 JSON 数组；供 `app/adapters/opencli_bridge.py` 通过 `opencli <name> --format=json` 调用
> Pos: 项目根 `clis/` — OpenCLI 浏览器爬取适配器集中地 (Strategy.COOKIE)
>
> 一旦这里的结构发生变化，请务必更新我... 就像重新标记领地一样。

## 适配器清单

| 路径 | name | 必填 args | 可选 args | 数据字段 |
|------|------|-----------|-----------|----------|
| `xueqiu/discuss.js` | `xueqiu/discuss` | `symbol` (如 `SZ000001`) | `limit=30` | user/time/content/likes/comments/reposts |
| `eastmoney/guba.js` | `eastmoney/guba` | `code` (6位数字) | `pages=1` | rank/title/author/time/reads/replies/url |
| `cls/telegraph.js` | `cls/telegraph` | — | `limit=50` | time/title/content/tags/isImportant |

## 约定

- 每个 adapter 导出 `{ name, description, strategy, args, run(ctx) }`，`ctx` 由 OpenCLI 运行时注入 `{ page, logger, args }`。
- 失败抛异常 (`throw new Error`)，由 OpenCLI 捕获并以非零退出码返回；Python 侧 `opencli_bridge.py` 统一降级为空列表 + `log.warning`。
- DOM 选择器多套 fallback，容忍雪球/东财/财联社前端小版本迭代。
- 所有 `--format=json` 输出遵守 `[{...}, {...}]` 顶层数组。

## 依赖

- OpenCLI ≥ PR#1025 (hot-rank adapter 已合入主线)
- Puppeteer / Playwright (由 OpenCLI 运行时管理)
- Node ≥ 18 (内置 `node:test`，测试文件零依赖)

## 本地测试

```bash
node --test clis/xueqiu/discuss.test.js
node --test clis/eastmoney/guba.test.js
node --test clis/cls/telegraph.test.js
```

## 权威源引用 (2026-04-15 12:30 +08:00)

- https://github.com/jackwener/OpenCLI (主仓目录约定)
- https://github.com/jackwener/OpenCLI/pull/1025 (hot-rank 模板)
- https://xueqiu.com/S/{symbol}/TIMELINE
- https://guba.eastmoney.com/list,{code}.html
- https://www.cls.cn/telegraph

[NEW-FILE:#20260415-16]
