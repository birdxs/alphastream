# Input  : pytest 收集阶段加载的共享 fixture 模块
# Output : 为后端 unit/integration/api/sse 测试提供 mock_ai_client / flask_app /
#          flask_client / sse_client / mock_event_bus / mock_adapters / tmp_data_dir
# Pos    : 仓库根目录（pytest rootdir），所有 tests/** 模块默认可见这些 fixture
#
# 一旦此文件被修改，请同步更新：
#   - tests/audit/test_framework.md  Fixture 章节
#   - tests/audit/README.md          使用示例章节

"""W1 测试体系共享 fixture。

设计原则：
1. LLM 全 mock，绝不触发真调用（即使本地有 OPENAI_API_KEY）。
2. 外部 IO（akshare/yfinance/HTTP）由 mock_adapters 兜底，子测试可覆盖。
3. Flask app 走 TESTING=True，CSRF/限流类副作用关闭。
4. SSE 客户端基于 EventBus.create_sse_bridge() 实现，事件可遍历。
"""

from __future__ import annotations

import json
import os
import sys
import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# --------------------------------------------------------------------------- #
# 0. 环境变量：在任何 app.* 模块被 import 之前注入
# --------------------------------------------------------------------------- #

os.environ.setdefault("ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_URL", "https://test.invalid/v1")
os.environ.setdefault("OPENAI_API_MODEL", "test-model")
os.environ.setdefault("DISABLE_NETWORK", "1")  # 允许业务代码读取此标志自行短路

# 将仓库根加入 sys.path，保证 `import app.*` 在子目录测试中也能命中
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# --------------------------------------------------------------------------- #
# 1. 通用工具 fixture
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def repo_root() -> Path:
    """仓库根目录 Path。"""
    return _REPO_ROOT


@pytest.fixture(scope="session")
def tmp_data_dir(tmp_path_factory) -> Iterator[Path]:
    """会话级临时 data 目录，替代真实 data/，避免污染本地。

    通过环境变量 DATA_DIR 暴露，业务代码若读取该变量可被重定向。
    """
    d = tmp_path_factory.mktemp("data_session")
    old = os.environ.get("DATA_DIR")
    os.environ["DATA_DIR"] = str(d)
    try:
        yield d
    finally:
        if old is None:
            os.environ.pop("DATA_DIR", None)
        else:
            os.environ["DATA_DIR"] = old


# --------------------------------------------------------------------------- #
# 2. mock_ai_client：拦截 app.core.ai_client 的三大入口
# --------------------------------------------------------------------------- #

class _FakeChoiceMessage:
    def __init__(self, content: str = "", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []
        # OpenAI SDK 用 dict() 序列化时也常被访问 .role
        self.role = "assistant"


class _FakeChoice:
    def __init__(self, content: str = "", tool_calls=None, finish_reason: str = "stop"):
        self.message = _FakeChoiceMessage(content=content, tool_calls=tool_calls)
        self.finish_reason = finish_reason
        self.index = 0


class _FakeResponse:
    """轻量结构，兼容 ai_client.get_completion_content 等访问。"""

    def __init__(self, content: str = "test-response", tool_calls=None,
                 model: str = "test-model"):
        self.choices = [_FakeChoice(content=content, tool_calls=tool_calls)]
        self.model = model
        self.id = "chatcmpl-test"
        self.created = int(time.time())
        self.usage = MagicMock(prompt_tokens=10, completion_tokens=10, total_tokens=20)


class _FakeStreamChunk:
    def __init__(self, content: str = "", finish_reason: Optional[str] = None):
        delta = MagicMock()
        delta.content = content
        delta.tool_calls = None
        choice = MagicMock()
        choice.delta = delta
        choice.finish_reason = finish_reason
        self.choices = [choice]


@pytest.fixture
def mock_ai_client(monkeypatch) -> Dict[str, MagicMock]:
    """拦截 ai_client 的 chat_completion / chat_with_tools / chat_completion_stream。

    返回 dict，键为函数名，值为 MagicMock，便于断言 call_args。

    用法：
        def test_xx(mock_ai_client):
            mock_ai_client["chat_completion"].return_value = _FakeResponse("hello")
            ...
    """
    import app.core.ai_client as ai_mod

    fake_client = MagicMock(name="FakeOpenAIClient")

    mocks: Dict[str, MagicMock] = {}

    def _fake_get_ai_client():
        return fake_client

    def _fake_get_ai_model():
        return "test-model"

    def _fake_chat_completion(client, messages, temperature=0.7, max_tokens=4096,
                              tools=None, tool_choice=None):
        return _FakeResponse(content="mocked-ai-response")

    def _fake_chat_with_tools(client, messages, tools_schema, tool_executor=None,
                              *args, **kwargs):
        # 默认直接返回一个 text-only 的最终 message 列表
        return [{"role": "assistant", "content": "mocked-tool-final"}]

    def _fake_chat_completion_stream(client, messages, temperature=0.7, max_tokens=4096,
                                     tools=None, tool_choice=None):
        # 生成 3 段 chunk + 一个停止 chunk
        chunks = [
            _FakeStreamChunk("mocked-"),
            _FakeStreamChunk("stream-"),
            _FakeStreamChunk("response"),
            _FakeStreamChunk("", finish_reason="stop"),
        ]
        for c in chunks:
            yield c

    def _fake_chat_with_tools_stream(client, messages, tools_schema, tool_executor=None,
                                     *args, **kwargs):
        yield {"type": "content", "content": "mocked-tool-stream"}
        yield {"type": "done"}

    mocks["get_ai_client"] = MagicMock(side_effect=_fake_get_ai_client)
    mocks["get_ai_model"] = MagicMock(side_effect=_fake_get_ai_model)
    mocks["chat_completion"] = MagicMock(side_effect=_fake_chat_completion)
    mocks["chat_with_tools"] = MagicMock(side_effect=_fake_chat_with_tools)
    mocks["chat_completion_stream"] = MagicMock(side_effect=_fake_chat_completion_stream)
    mocks["chat_with_tools_stream"] = MagicMock(side_effect=_fake_chat_with_tools_stream)
    mocks["client"] = fake_client

    for name in ("get_ai_client", "get_ai_model", "chat_completion",
                 "chat_with_tools", "chat_completion_stream",
                 "chat_with_tools_stream"):
        if hasattr(ai_mod, name):
            monkeypatch.setattr(ai_mod, name, mocks[name])

    return mocks


# --------------------------------------------------------------------------- #
# 3. event_bus：mock_event_bus 截获 publish 调用
# --------------------------------------------------------------------------- #

@pytest.fixture
def mock_event_bus(monkeypatch):
    """截获所有 EventBus.publish 调用，无论是 EventBus().publish()、
    get_event_bus().publish() 还是任何持有实例的调用方。

    修复说明（D04 / BE-01c）：
      旧实现引用 eb_mod.event_bus 模块级常量，该常量不存在（EventBus 是
      单例但无模块级别名），导致 AttributeError。新实现直接 patch 类方法
      EventBus.publish，覆盖所有实例调用路径。

    返回对象提供：
        .events  -> List[Tuple[event_name, data]]
        .filter(name) -> 过滤后的数据列表
        .names() -> 已发布事件名列表
        .clear()
    """
    from app.core.event_bus import EventBus

    records: List[tuple] = []
    original_publish = EventBus.publish

    def _capture(self, event_name: str, data: Any = None) -> None:
        records.append((event_name, data))
        # 保留原行为以便已订阅的回调仍能跑
        return original_publish(self, event_name, data)

    monkeypatch.setattr(EventBus, "publish", _capture)

    class _Recorder:
        @property
        def events(self):
            return list(records)

        def filter(self, name: str):
            return [d for n, d in records if n == name]

        def names(self):
            return [n for n, _ in records]

        def clear(self):
            records.clear()

    yield _Recorder()


# --------------------------------------------------------------------------- #
# 4. flask_app / flask_client
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def flask_app():
    """加载真实 Flask app（app.web.web_server.app），切换为 TESTING 模式。

    注意：web_server 在 import 阶段会执行较多初始化（analyzer、缓存等），
    所以放在 session 级避免重复成本。
    """
    # 延迟 import，确保前置环境变量已生效
    from app.web import web_server as ws

    ws.app.config["TESTING"] = True
    ws.app.config["DEBUG"] = False
    # 关闭 SECRET_KEY 强校验场景
    ws.app.config.setdefault("SECRET_KEY", "test-secret")
    return ws.app


@pytest.fixture
def flask_client(flask_app):
    """Flask test_client，每个测试一个，自动 push application context。"""
    with flask_app.app_context():
        with flask_app.test_client() as client:
            yield client


# --------------------------------------------------------------------------- #
# 5. sse_client：消费 SSE 流，返回事件列表
# --------------------------------------------------------------------------- #

class _SSEClient:
    """辅助消费 Flask test_client 返回的 SSE 响应。"""

    def __init__(self, response):
        self.response = response

    def events(self, max_events: int = 50, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """解析 text/event-stream 响应，返回事件 dict 列表。

        SSE 格式：每个事件由空行分隔，可包含 event:/data:/id: 字段。
        data 字段尝试 json.loads，失败则保留原字符串。
        """
        out: List[Dict[str, Any]] = []
        buf: List[str] = []
        start = time.monotonic()
        try:
            for raw in self.response.iter_encoded():
                if time.monotonic() - start > timeout:
                    break
                text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
                for line in text.splitlines(keepends=False):
                    if line == "":
                        if buf:
                            evt = self._parse_block(buf)
                            if evt:
                                out.append(evt)
                            buf = []
                            if len(out) >= max_events:
                                return out
                    else:
                        buf.append(line)
        except Exception:
            pass
        if buf:
            evt = self._parse_block(buf)
            if evt:
                out.append(evt)
        return out

    @staticmethod
    def _parse_block(lines: List[str]) -> Optional[Dict[str, Any]]:
        evt: Dict[str, Any] = {}
        data_parts: List[str] = []
        for ln in lines:
            if ln.startswith(":"):
                # 注释行
                continue
            if ":" not in ln:
                continue
            key, _, val = ln.partition(":")
            val = val.lstrip(" ")
            if key == "data":
                data_parts.append(val)
            else:
                evt[key] = val
        if data_parts:
            raw = "\n".join(data_parts)
            try:
                evt["data"] = json.loads(raw)
            except Exception:
                evt["data"] = raw
        return evt or None


@pytest.fixture
def sse_client(flask_client):
    """工厂 fixture：sse_client(path, **kwargs) -> _SSEClient。"""
    def _factory(path: str, method: str = "GET", **kwargs) -> _SSEClient:
        resp = flask_client.open(path, method=method, **kwargs)
        return _SSEClient(resp)
    return _factory


# --------------------------------------------------------------------------- #
# 6. mock_adapters：屏蔽 akshare / yfinance 等外部 IO
# --------------------------------------------------------------------------- #

@pytest.fixture
def mock_adapters(monkeypatch):
    """统一拦截常见外部数据源，返回 MagicMock。

    覆盖范围（按需扩展）：
      - akshare 模块（如已安装）
      - yfinance 模块
      - app.adapters.* 内 fetch_* / get_* 类函数（仅替换被测试显式触发的）

    返回 dict：{ "akshare": MagicMock, "yfinance": MagicMock, "stubs": {...} }
    """
    stubs: Dict[str, MagicMock] = {}

    for mod_name in ("akshare", "yfinance", "baostock", "efinance", "easyquotation"):
        try:
            import importlib
            mod = importlib.import_module(mod_name)
            stub = MagicMock(name=f"mock_{mod_name}", spec=mod)
            monkeypatch.setitem(sys.modules, mod_name, stub)
            stubs[mod_name] = stub
        except Exception:
            # 模块未安装：创建纯 MagicMock 占位
            stub = MagicMock(name=f"mock_{mod_name}")
            monkeypatch.setitem(sys.modules, mod_name, stub)
            stubs[mod_name] = stub

    return stubs


# --------------------------------------------------------------------------- #
# 7. 自动级清理：每个测试结束确保 EventBus 没有泄漏的桥
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _cleanup_sse_bridges():
    yield
    try:
        from app.core.event_bus import event_bus
        # 强制清空（仅在测试场景），避免跨测试事件污染
        with getattr(event_bus, "_bridges_lock", threading.Lock()):
            if hasattr(event_bus, "_sse_bridges"):
                event_bus._sse_bridges = []
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 8. 便利：导出常用 Fake 类，子测试可 import 复用
# --------------------------------------------------------------------------- #

__all__ = [
    "mock_ai_client",
    "mock_event_bus",
    "flask_app",
    "flask_client",
    "sse_client",
    "mock_adapters",
    "tmp_data_dir",
    "repo_root",
]
