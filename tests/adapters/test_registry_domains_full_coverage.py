# -*- coding: utf-8 -*-
"""J1 16 domain × agent method 全覆盖严格断言 [NEW-FILE:#20260415-43]
Input: AdapterRegistry.default() + monkeypatch mock 上游
Output: 16 domain 调用 agent method 时 tried 非空的回归守卫
Pos: tests/adapters — J1 扫平 I1 遗留 6 warn 的闭环验证

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

追溯:
    I1 (commit 487ad1c) 修复 4 域 tried=[] (news/sentiment_social/esg_rating/hiring_signal)
    J1 (2026-04-15) 扫平 6 个非I1 warn:
        - a_stock_realtime.get_individual_fund_flow  (efinance/akshare/easyquotation alias)
        - macro_us.get_macro_indicators              (fred/openbb/worldbank alias)
        - macro_cn.get_macro_indicators              (nbs alias)
        - macro_global.get_macro_indicators          (worldbank/imf/openbb alias)
        - earth_observation.search_collections       (satellite alias → search_datasets)
        - corporate_entity.search_entity             (corporate alias → search_company)
"""
import pytest
from app.adapters.adapter_registry import AdapterRegistry


FULL_AGENT_METHOD_MAP = {
    "a_stock_kline":       "get_stock_history",
    "a_stock_realtime":    "get_individual_fund_flow",
    "us_stock":            "get_financials",
    "hk_stock":            "get_stock_history",
    "macro_us":            "get_macro_indicators",
    "macro_cn":            "get_macro_indicators",
    "macro_global":        "get_macro_indicators",
    "crypto":              "get_stock_history",
    "news":                "get_latest_news",
    "sentiment_social":    "get_social_sentiment",
    "xbrl_financials":     "get_financials",
    "esg_rating":          "get_esg_rating",
    "commodity_shipping":  "get_bdi_index",
    "earth_observation":   "search_collections",
    "corporate_entity":    "search_entity",
    "hiring_signal":       "get_hiring_trend",
}


@pytest.fixture(scope="module")
def registry():
    AdapterRegistry.reset_default()
    return AdapterRegistry.default()


@pytest.mark.parametrize("domain,method", list(FULL_AGENT_METHOD_MAP.items()))
def test_each_domain_has_method_implementor(registry, domain, method):
    """每个 domain 至少有1个已注册 adapter 声明了 agent method (hasattr)"""
    adapters = registry.get_adapters(domain)
    assert adapters, f"domain={domain} 未注册任何adapter"
    hits = [a.name for a in adapters if hasattr(a, method)]
    assert hits, (
        f"domain={domain}.{method} hasattr命中0; "
        f"注册={[a.name for a in adapters]}"
    )


@pytest.mark.parametrize("domain,method", list(FULL_AGENT_METHOD_MAP.items()))
def test_tried_nonempty_when_upstream_fails(registry, domain, method, monkeypatch):
    """mock所有实现method的adapter抛异常, 验证 tried 列表非空 (method被识别+记录)。

    关键: tried=[] 表示 adapter.name 未被append, 意味着 hasattr(method) 全部失败,
    即 J1 alias 缺失 — 这是 I1 -> J1 任务守的核心回归。
    """
    adapters = registry.get_adapters(domain)
    assert adapters, f"domain={domain} 未注册任何adapter"

    def _boom(*a, **k):
        raise RuntimeError(f"mock_{domain}_{method}_no_network")

    patched_any = False
    for a in adapters:
        if hasattr(a, method):
            monkeypatch.setattr(a, method, _boom)
            patched_any = True
    assert patched_any, f"domain={domain}.{method} 没有任何adapter声明此方法 — J1对齐缺失"

    with pytest.raises(Exception) as exc_info:
        registry.call_with_fallback(domain, method, **_probe_kwargs(domain, method))
    msg = str(exc_info.value)
    assert "tried=[]" not in msg, (
        f"J1 REGRESSION: domain={domain}.{method} tried=[] — "
        f"alias 在 registry 层未被发现 (hasattr 表/实例化失败): {msg}"
    )


def _probe_kwargs(domain: str, method: str) -> dict:
    """为各 domain.method 构造最小合法调用参数 (mock 场景只需能进入 getattr)"""
    base = {
        "a_stock_kline":      {"code": "000001", "start_date": "20240101", "end_date": "20240201"},
        "a_stock_realtime":   {"code": "000001"},
        "us_stock":           {"code": "AAPL"},
        "hk_stock":           {"code": "00700", "start_date": "20240101", "end_date": "20240201"},
        "macro_us":           {"indicators": ["GDP"]},
        "macro_cn":           {"indicators": ["GDP"]},
        "macro_global":       {"indicators": ["GDP"]},
        "crypto":             {"code": "BTC-USD", "start_date": "20240101", "end_date": "20240201"},
        "news":               {"code": "AAPL"},
        "sentiment_social":   {"code": "600519"},
        "xbrl_financials":    {"code": "AAPL"},
        "esg_rating":         {"code": "AAPL"},
        "commodity_shipping": {},
        "earth_observation":  {"keyword": "MODIS"},
        "corporate_entity":   {"query": "Apple"},
        "hiring_signal":      {"keyword": "engineer"},
    }
    return base.get(domain, {})


def test_j1_alias_adapters_registered(registry):
    """J1 修复的6域对应的alias承载adapter均已注册"""
    st = registry.get_status()
    d = st["domains"]
    # a_stock_realtime 至少 efinance/akshare/easyquotation 任一
    assert any(x in d.get("a_stock_realtime", []) for x in ("efinance", "akshare", "easyquotation:sina", "easyquotation:tencent"))
    # macro_us 至少 fred/openbb/worldbank
    assert any(x in d.get("macro_us", []) for x in ("fred", "openbb", "worldbank"))
    # macro_cn 至少 nbs
    assert "nbs" in d.get("macro_cn", [])
    # macro_global 至少 worldbank/imf/openbb
    assert any(x in d.get("macro_global", []) for x in ("worldbank", "imf", "openbb"))
    # earth_observation: satellite
    assert "satellite" in d.get("earth_observation", [])
    # corporate_entity: opencorporates
    assert "opencorporates" in d.get("corporate_entity", [])
