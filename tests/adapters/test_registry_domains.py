# -*- coding: utf-8 -*-
"""Registry domain map 覆盖性测试 [NEW-FILE:#20260415-40]
Input: AdapterRegistry.default() 单例
Output: 16 domain × agent调用method 可resolve 断言
Pos: tests/adapters — I1 追溯 (news/sentiment_social/esg_rating/hiring_signal tried=[] bug 守卫)

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

追溯: commit 95f089b H2 真端到端 → 4 domain tried=[] → I1 修复: adapter 增别名method
    - RSSNewsAdapter.get_latest_news
    - OpenCLIBridge.get_social_sentiment
    - ESGAdapter.get_esg_rating
    - JobsAdapter.get_hiring_trend
"""
import pytest
from app.adapters.adapter_registry import AdapterRegistry


# agent 端统一调用的方法名 (来自 app/agents/**/*.py _registry_fetch)
AGENT_METHOD_MAP = {
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


def test_default_map_has_16_domains():
    assert len(AdapterRegistry.DEFAULT_DOMAIN_MAP) == 16, \
        f"期望16域, 实际={len(AdapterRegistry.DEFAULT_DOMAIN_MAP)}"


def test_all_domains_registered(registry):
    """每个DEFAULT_DOMAIN_MAP key 至少有1 adapter 注册成功"""
    missing = []
    for domain in AdapterRegistry.DEFAULT_DOMAIN_MAP.keys():
        adapters = registry.get_adapters(domain)
        if not adapters:
            missing.append(domain)
    assert not missing, f"未注册任何adapter的域: {missing}"


@pytest.mark.parametrize("domain", list(AdapterRegistry.DEFAULT_DOMAIN_MAP.keys()))
def test_domain_has_at_least_one_adapter(registry, domain):
    """参数化: 16域每域 tried长度≥1"""
    adapters = registry.get_adapters(domain)
    assert len(adapters) >= 1, f"domain={domain} adapters=[]"


# ============= I1 修复专项回归 =============

@pytest.mark.parametrize("domain,method", [
    ("news", "get_latest_news"),
    ("sentiment_social", "get_social_sentiment"),
    ("esg_rating", "get_esg_rating"),
    ("hiring_signal", "get_hiring_trend"),
])
def test_i1_fixed_domains_method_resolvable(registry, domain, method):
    """I1 修复的4域: 至少1 adapter 实现 agent 调用method"""
    adapters = registry.get_adapters(domain)
    hits = [a.name for a in adapters if hasattr(a, method)]
    assert hits, f"I1 REGRESSION: domain={domain}.{method} hasattr命中0; adapters={[a.name for a in adapters]}"


# 其他 11 个 domain 的 agent method 是否可resolve — 仅记录, 非阻塞
# (capital_flow_analyst/ technical_analyst 等的 method 对齐属于后续 I2+ 任务,
#  I1 仅保证 H2 暴露的 4 域绿灯)
NON_I1_DOMAIN_METHODS = {
    d: m for d, m in AGENT_METHOD_MAP.items()
    if d not in ("news", "sentiment_social", "esg_rating", "hiring_signal")
}


@pytest.mark.parametrize("domain,method", list(NON_I1_DOMAIN_METHODS.items()))
def test_non_i1_agent_method_status(registry, domain, method):
    """J1 升级: 严格断言每个非I1 domain 至少1 adapter 实现 agent method。

    追溯: J1 任务扫平 I1 遗留的 6 个 warn (a_stock_realtime/macro_*/earth_observation/
    corporate_entity), 通过在对应 adapter 加 alias 薄包装对齐 agent 调用层method名。
    """
    adapters = registry.get_adapters(domain)
    assert adapters, f"domain={domain} 未注册任何 adapter"
    hits = [a.name for a in adapters if hasattr(a, method)]
    assert hits, (
        f"J1 REGRESSION: domain={domain}.{method} hasattr命中0; "
        f"注册={[a.name for a in adapters]} — alias 缺失或被误删"
    )


# ============= adapter import 无异常 =============

ADAPTER_MODULES = [
    "akshare_adapter", "baostock_adapter", "efinance_adapter",
    "yfinance_adapter", "edgar_adapter", "nbs_adapter", "fred_adapter",
    "ccxt_adapter", "coingecko_adapter", "worldbank_adapter", "imf_adapter",
    "opencli_bridge", "openbb_adapter", "ashare_adapter",
    "easyquotation_adapter", "rss_news_adapter", "esg_adapter",
    "shipping_adapter", "satellite_adapter", "corporate_adapter",
    "jobs_adapter",
]


@pytest.mark.parametrize("mod_name", ADAPTER_MODULES)
def test_adapter_module_importable(mod_name):
    """每个adapter模块可 import 无硬异常 (软依赖缺失允许)"""
    import importlib
    try:
        importlib.import_module(f"app.adapters.{mod_name}")
    except Exception as e:
        pytest.fail(f"模块 {mod_name} import 硬失败: {type(e).__name__}: {e}")


# ============= Registry signature smoke =============

def test_call_with_fallback_tried_nonempty_on_registered_domain(registry, monkeypatch):
    """call_with_fallback 在 adapter 注册 + method 存在时 tried 非空 (不依赖真实网络)。

    通过monkeypatch让第一个adapter抛异常, 验证 tried 确实追加了 adapter.name。
    """
    domain = "esg_rating"
    method = "get_esg_rating"
    adapters = registry.get_adapters(domain)
    assert adapters, "esg_rating 应已注册"

    def _boom(*a, **k):
        raise RuntimeError("mock_no_network")

    for a in adapters:
        if hasattr(a, method):
            monkeypatch.setattr(a, method, _boom)

    with pytest.raises(Exception) as exc_info:
        registry.call_with_fallback(domain, method, code="AAPL")
    msg = str(exc_info.value)
    # tried=[...] 非空验证: 修复后至少包含 esg_public
    assert "tried=[]" not in msg, f"tried仍为空 — I1修复失效: {msg}"
    assert "esg" in msg.lower() or "mock_no_network" in msg, msg


def test_registry_status_snapshot(registry):
    """快照: status 包含 I1 修复的4域 adapter 名"""
    st = registry.get_status()
    domains = st["domains"]
    assert "rss_news" in domains.get("news", [])
    assert "opencli" in domains.get("sentiment_social", [])
    assert "esg_public" in domains.get("esg_rating", [])
    assert "jobs_adapter" in domains.get("hiring_signal", [])
