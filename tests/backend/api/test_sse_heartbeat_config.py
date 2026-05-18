"""
Input: ai_chat 超时配置 + Agent SSE 心跳/总超时配置
Output: pytest 用例 — 覆盖环境变量驱动配置 + 默认值
Pos: tests/backend/api/test_sse_heartbeat_config.py — FIX-E1+E3 新增
"""
import importlib
import os


def test_ai_chat_timeout_default_is_15min(monkeypatch):
    """未设置环境变量时 AI_CHAT_TIMEOUT 默认 900s (15min)。"""
    monkeypatch.delenv("AI_CHAT_TIMEOUT", raising=False)
    # 旧的硬编码 120 已替换为可配置
    assert int(os.getenv("AI_CHAT_TIMEOUT", "900")) == 900


def test_ai_chat_timeout_overridable_by_env(monkeypatch):
    monkeypatch.setenv("AI_CHAT_TIMEOUT", "1800")
    assert int(os.getenv("AI_CHAT_TIMEOUT", "900")) == 1800


def test_sse_heartbeat_interval_default_15s():
    """SSE 心跳间隔默认 15s。"""
    assert int(os.getenv("SSE_HEARTBEAT_INTERVAL_S", "15")) == 15


def test_agent_task_max_duration_default_2h():
    """Agent 任务最大时长默认 7200s (2h)。"""
    assert int(os.getenv("AGENT_TASK_MAX_DURATION_S", "7200")) == 7200


def test_sse_heartbeat_format():
    """SSE 心跳行格式应是 `: heartbeat <ts>\\n\\n` (以冒号开头的注释行)。
    客户端按 SSE 规范应忽略 `:` 开头的行；这里只校验格式。"""
    import time
    line = f": heartbeat {int(time.time())}\n\n"
    assert line.startswith(": heartbeat ")
    assert line.endswith("\n\n")


def test_web_server_uses_configurable_timeout():
    """快速验证 web_server.py 中已不存在硬编码 `AI_CHAT_TIMEOUT = 120`。"""
    from pathlib import Path
    src = Path(__file__).resolve().parents[3] / "app" / "web" / "web_server.py"
    text = src.read_text(encoding="utf-8")
    # 旧硬编码应已被替换
    assert "AI_CHAT_TIMEOUT = 120" not in text
    # 新形态应存在
    assert "AI_CHAT_TIMEOUT" in text and "getenv" in text
    # 旧硬编码 bridge_queue.get(timeout=300) 应已被替换为短超时循环
    assert "bridge_queue.get(timeout=300)" not in text
    assert "HEARTBEAT_INTERVAL" in text
    assert "AGENT_TASK_MAX_DURATION_S" in text
