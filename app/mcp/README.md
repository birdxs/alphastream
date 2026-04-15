- `__init__.py` — 包初始化, MCP 模块入口
- `stock_data_server.py` — 股票数据 MCP Server (5 基础工具)
- `registry_server.py` — L2 Registry 16 domain MCP Server (16 工具, 2026-04-15 扩展)

一旦这里的结构发生变化，请务必更新我... 就像重新标记领地一样。

---

## L2 Registry 16 Domain MCP Tools 清单

详见 `registry_server.py:REGISTRY_TOOLS`。

| # | Tool | Domain | 底层方法 |
|---|---|---|---|
| 1 | a_stock_kline | a_stock_kline | get_stock_history |
| 2 | a_stock_realtime | a_stock_realtime | get_realtime_quotes |
| 3 | us_stock_quote | us_stock | get_stock_history |
| 4 | hk_stock_quote | hk_stock | get_stock_history |
| 5 | crypto_ticker | crypto | get_ticker |
| 6 | macro_us | macro_us | get_series |
| 7 | macro_cn | macro_cn | get_gdp/cpi/pmi/... |
| 8 | macro_global | macro_global | get_indicator |
| 9 | xbrl_financials | xbrl_financials | get_financial_data |
| 10 | news_feed | news | get_feed |
| 11 | esg_rating | esg_rating | get_esg_score |
| 12 | corporate_search | corporate_entity | search_company |
| 13 | jobs_search | hiring_signal | get_hiring_trend |
| 14 | shipping_bdi | commodity_shipping | get_bdi_index |
| 15 | satellite_search | earth_observation | search_datasets |
| 16 | registry_status | - | AdapterRegistry.get_status |

所有 tool 内部: `AdapterRegistry.default().call_with_fallback(domain, method, **kw)` —
自动启用 16 domain 既有的多源降级 + 重试。

## Claude Desktop 配置示例

路径: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "stockanal-registry": {
      "command": "python",
      "args": ["-m", "app.mcp.registry_server"],
      "cwd": "/absolute/path/to/StockAnal_Sys",
      "env": {
        "PYTHONPATH": "/absolute/path/to/StockAnal_Sys"
      }
    }
  }
}
```

> 注: 当前实现保持与 `stock_data_server.py` 一致的 dict+handler 风格, 未依赖
> `mcp` Python SDK (未在 requirements.txt)。如需接入 Claude Desktop stdio 传输,
> 可追加一层 mcp.server.Server 包装 (参考 `docs/OPERATIONS.md` §9)。

## 测试

```bash
pytest tests/mcp/test_registry_server.py -v
```
