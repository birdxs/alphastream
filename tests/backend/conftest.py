# Input  : pytest 收集阶段加载的 backend 共享 fixture
# Output : agent_event_recorder / patched_ai_client / iso_checkpointer / _block_external_network
# Pos    : tests/backend/conftest.py - 供 W2-BE02 (后端 Agent 编排测试) 使用
#
# 一旦本文件结构变化，请同步更新 tests/backend/README.md 与所属测试模块。
"""W2-BE02 后端 Agent 测试专用 fixture。

之所以单独建：
- 根 conftest 的 ``mock_event_bus`` 通过 ``eb_mod.event_bus`` 取单例，但
  ``app.core.event_bus`` 模块上并不存在 ``event_bus`` 属性，只有 ``EventBus()``
  单例与 ``get_event_bus()`` 工厂；该 fixture 会直接报 AttributeError。
  这里提供 ``agent_event_recorder``，对 EventBus 单例 publish 做 spy，
  既能记录事件又不破坏既有订阅链路。
- 多数 agent 用 ``from app.core.ai_client import chat_completion`` 的函数内
  lazy import，``mock_ai_client`` 已经覆盖；但部分模块在导入时绑定 ``chat_completion``
  到本模块属性，仍需 ``patched_ai_client`` 在 agent 模块自身上 setattr 一遍。
- ``iso_checkpointer`` 让需要并发测试 SqliteSaver 的用例独占一个临时 db，避免
  与默认 ``data/langgraph_checkpoint.db`` 互相干扰。
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock

import pytest

logger = logging.getLogger(__name__)

# 导入前/收集阶段再写一次后台门控（web_server 模块级 _startup_background_enabled）
# 与根 conftest.py 双保险，减少 atexit closed-stream 噪声
os.environ.setdefault("DISABLE_NETWORK", "1")
os.environ.setdefault("MOCK_LLM", "1")
os.environ.setdefault("AUTH_REQUIRED", "false")
os.environ["STOCKANAL_DISABLE_BACKGROUND"] = "1"


# ==============================================================================
# 全局外网阻断 fixture（autouse）
# 阻断所有单元测试的外网调用，避免超时或真实 I/O 污染测试结果。
# 集成测试目录 tests/backend/integration/ 中的测试可在自身内覆盖这些 mock。
# ==============================================================================
@pytest.fixture(autouse=True)
def _block_external_network(request, monkeypatch):
    """autouse fixture：阻断外网调用，返回安全空值让测试走"无数据"分支。

    阻断策略：
    1. AdapterRegistry.call_with_fallback → None（阻断 news/sentiment_social/esg_rating 等域）
    2. app.core.search.search_stock_news_unified → []（阻断联网新闻搜索）
    3. app.core.search.search_web / multi_search → []（阻断通用搜索）
    4. 设置 DISABLE_NETWORK=1, MOCK_LLM=1, STOCKANAL_DISABLE_BACKGROUND=1 环境变量

    环境变量门控：SKIP_NETWORK_BLOCK=1 可跳过本 fixture（用于明确需要外网的测试）。
    集成测试目录 tests/backend/integration/ 默认也应用，但可在测试内用 monkeypatch 覆盖。
    """
    # 允许通过环境变量跳过（用于真实集成测试场景）
    if os.environ.get("SKIP_NETWORK_BLOCK") == "1":
        yield
        return

    # 1. 设置网络屏蔽环境变量
    monkeypatch.setenv("DISABLE_NETWORK", "1")
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setenv("STOCKANAL_DISABLE_BACKGROUND", "1")

    # 1b. 确保 app.core.tools stub（如果已注入）含有 execute_tool 属性，避免 T020 等测试崩溃
    try:
        import sys as _sys_inner
        _tools_mod = _sys_inner.modules.get("app.core.tools")
        if _tools_mod is not None and not hasattr(_tools_mod, "execute_tool"):
            _tools_mod.execute_tool = lambda name, args: None
    except Exception:
        pass

    # 2. 阻断 AdapterRegistry.call_with_fallback（主要外网入口）
    try:
        import app.adapters.adapter_registry as _ar_mod
        if hasattr(_ar_mod, "AdapterRegistry"):
            # mock instance level call_with_fallback via class patch
            monkeypatch.setattr(
                _ar_mod.AdapterRegistry, "call_with_fallback",
                lambda self, domain, method, **kw: None,
                raising=False,
            )
    except Exception:
        pass

    # 3. 阻断 app.core.search.search_stock_news_unified（agent 调用的外网新闻搜索）
    # 注意：test_core_search.py 测试 search 函数本身，不应 mock 其被测函数
    _is_search_test = "test_core_search" in (request.node.fspath.basename if hasattr(request.node, "fspath") else "")
    if not _is_search_test:
        try:
            import app.core.search as _search_mod
            if hasattr(_search_mod, "search_stock_news_unified"):
                monkeypatch.setattr(_search_mod, "search_stock_news_unified", lambda *a, **kw: [])
        except Exception:
            pass

    yield


# -- 防 sys.modules stub 污染：conftest 模块级预加载真实 adapter_registry ----------
# [FIX-ORDER-POLLUTION 2026-05-19]
# test_agent_decision.py 在模块级通过 ``if "app.adapters.adapter_registry" not in sys.modules``
# 条件注入轻量 stub（仅含 list_adapters/get，缺少 DEFAULT_DOMAIN_MAP/default()）。
# conftest.py 先于测试文件被 pytest 导入，在此预加载真实模块，使条件永久为 False。
# decision 测试函数内的真实网络调用通过 _collect_decision_context 降级安全（失败返回None）。
try:
    import importlib as _importlib
    _importlib.import_module("app.adapters.adapter_registry")
except Exception:
    pass


# -- agent_event_recorder ------------------------------------------------------
@pytest.fixture
def agent_event_recorder(monkeypatch):
    """对 ``EventBus`` 单例 publish 做 spy，返回事件列表与查询 helper。

    用法：
        def test_xx(agent_event_recorder):
            ...
            assert agent_event_recorder.has("agent.started")
            evts = agent_event_recorder.filter("agent.completed")
    """
    import app.core.event_bus as eb_mod

    bus = eb_mod.EventBus()  # 单例
    records: List[Tuple[str, Any]] = []
    # 直接在实例 __dict__ 中注入 spy（不用 monkeypatch，避免 monkeypatch 恢复时把绑定方法写入实例字典）
    # 保存类方法引用，spy 中调用时传入 self=bus
    _class_publish = eb_mod.EventBus.publish

    def _spy(event_name: str, data: Any = None) -> None:
        records.append((event_name, data))
        return _class_publish(bus, event_name, data)

    bus.__dict__['publish'] = _spy

    class _Recorder:
        events = records

        def has(self, name: str) -> bool:
            return any(n == name for n, _ in records)

        def filter(self, name: str) -> List[Any]:
            return [d for n, d in records if n == name]

        def clear(self) -> None:
            records.clear()

        def names(self) -> List[str]:
            return [n for n, _ in records]

    yield _Recorder()

    # teardown：从实例字典中清除 spy，避免污染后续测试的 EventBus 单例
    bus.__dict__.pop('publish', None)


# -- patched_ai_client ---------------------------------------------------------
@pytest.fixture
def patched_ai_client(monkeypatch):
    """同时 patch ``app.core.ai_client.{get_ai_client,chat_completion,
    chat_with_tools,get_completion_content,get_ai_model}``。

    返回 dict，可在测试里改写 ``return_value`` 或 ``side_effect``：
        patched_ai_client["chat_completion"].return_value = (resp_obj, None)
    """
    import app.core.ai_client as ai_mod

    fake_client = MagicMock(name="FakeAIClient")

    mocks: Dict[str, MagicMock] = {
        "get_ai_client": MagicMock(return_value=fake_client),
        "get_ai_model": MagicMock(return_value="test-model"),
        # chat_completion 返回 (resp, error)
        "chat_completion": MagicMock(return_value=(MagicMock(name="resp"), None)),
        # chat_with_tools 返回最终 messages 列表
        "chat_with_tools": MagicMock(
            return_value=[{"role": "assistant", "content": "mocked-tool-final"}]
        ),
        # get_completion_content 返回字符串
        "get_completion_content": MagicMock(return_value="mocked-ai-text"),
    }

    for name, mock in mocks.items():
        if hasattr(ai_mod, name):
            monkeypatch.setattr(ai_mod, name, mock)

    return mocks


# -- iso_checkpointer ----------------------------------------------------------
@pytest.fixture
def iso_checkpointer(tmp_path, monkeypatch):
    """重置 coordinator 全局 _checkpointer_instance，让 get_checkpointer 用临时 db。

    返回 (saver_or_none, db_path)。失败时 saver=None（环境无 langgraph sqlite）。
    """
    import app.agents.coordinator as coord_mod

    monkeypatch.setattr(coord_mod, "_checkpointer_instance", None, raising=False)

    # 让 db_dir 指向 tmp_path
    orig_dirname = os.path.dirname

    def _fake_dirname(p):
        return orig_dirname(p)

    # 直接 monkeypatch get_checkpointer 内部 db_path -> tmp_path
    db_path = tmp_path / "langgraph_checkpoint.db"

    def _patched_get_checkpointer():
        if coord_mod._checkpointer_instance is not None:
            return coord_mod._checkpointer_instance
        try:
            import sqlite3
            from langgraph.checkpoint.sqlite import SqliteSaver

            conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30.0)
            coord_mod._checkpointer_instance = SqliteSaver(conn)
        except Exception as e:  # noqa: BLE001
            logger.warning("iso_checkpointer 初始化失败 %s", e)
            coord_mod._checkpointer_instance = None
        return coord_mod._checkpointer_instance

    monkeypatch.setattr(coord_mod, "get_checkpointer", _patched_get_checkpointer)
    return _patched_get_checkpointer, db_path


# -- minimal_state -------------------------------------------------------------
@pytest.fixture
def minimal_state():
    """构造一个最小但合法的 StockAnalysisState，便于 agent 测试。"""
    return {
        "stock_code": "000001",
        "market_type": "A",
        "research_depth": 3,
        "messages": [],
        "technical_report": None,
        "fundamental_report": None,
        "capital_flow_report": None,
        "sentiment_report": None,
        "bull_case": None,
        "bear_case": None,
        "debate_summary": None,
        "investor_opinions": None,
        "investor_consensus": None,
        "router_decision": None,
        "risk_assessment": None,
        "final_decision": None,
        "execution_log": [],
        "progress": 0.0,
        "errors": [],
    }


# -- 自动 stub agent_memory / strategy 持久层，避免文件 IO 噪音 ----------------
@pytest.fixture(autouse=True)
def _stub_agent_memory(monkeypatch):
    """所有 agent 测试默认 stub 掉 agent_memory / strategy_evolver 的持久化。"""
    try:
        import app.core.agent_memory as mem_mod
    except Exception:
        return

    fake_mem = MagicMock(name="FakeAgentMemory")
    fake_mem.get_recent_summary.return_value = ""
    fake_mem.recall_for_agent.return_value = ""
    fake_mem.save_agent_analysis.return_value = None
    fake_mem.save_decision.return_value = None
    monkeypatch.setattr(mem_mod, "get_agent_memory", lambda: fake_mem)
    return fake_mem
