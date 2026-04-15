# -*- coding: utf-8 -*-
"""
Input: mock subprocess.run / shutil.which 驱动下的 OpenCLIBridge 调用
Output: pytest 断言通过/失败
Pos: tests/adapters/test_opencli_bridge.py — P0-A1 单元测试
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

[NEW-FILE:#20260415-03]
"""
from __future__ import annotations

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from app.adapters.opencli_bridge import OpenCLIBridge, _cached_hot_rank


@pytest.fixture(autouse=True)
def _clear_cache():
    """每个用例前清空模块级 TTL 缓存，避免交叉污染"""
    _cached_hot_rank.cache_clear()
    yield
    _cached_hot_rank.cache_clear()


def _mk_proc(stdout: str, rc: int = 0, stderr: str = "") -> MagicMock:
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.returncode = rc
    m.stdout = stdout
    m.stderr = stderr
    return m


# ---------- Case 1: 正常解析 eastmoney/hot-rank ----------
def test_eastmoney_hot_rank_parse_ok():
    payload = [
        {"code": "600519", "name": "贵州茅台", "rank": 1, "change": 2.34},
        {"code": "000858", "name": "五粮液", "rank": 2, "change": 1.12},
    ]
    with patch("app.adapters.opencli_bridge.shutil.which", return_value="/usr/local/bin/opencli"), \
         patch("app.adapters.opencli_bridge.subprocess.run",
               return_value=_mk_proc(json.dumps(payload))):
        bridge = OpenCLIBridge()
        result = bridge.get_eastmoney_hot_rank()

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["code"] == "600519"
    assert result[1]["name"] == "五粮液"


# ---------- Case 2: Node 未安装 → 降级返回 [] ----------
def test_degraded_when_node_missing(caplog):
    with patch("app.adapters.opencli_bridge.shutil.which", return_value=None):
        bridge = OpenCLIBridge()
        result = bridge.opencli_call("eastmoney/hot-rank")

    assert result == []
    assert any("环境未就绪" in rec.message for rec in caplog.records)


# ---------- Case 3: opencli 非零退出码 → 返回 [] ----------
def test_nonzero_exit_returns_empty():
    with patch("app.adapters.opencli_bridge.shutil.which", return_value="/usr/local/bin/opencli"), \
         patch("app.adapters.opencli_bridge.subprocess.run",
               return_value=_mk_proc("", rc=2, stderr="boom")):
        bridge = OpenCLIBridge()
        result = bridge.get_tdx_hot_rank()

    assert result == []


# ---------- Case 4: 子进程超时 → 返回 [] ----------
def test_timeout_returns_empty():
    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0] if args else "opencli", timeout=30)

    with patch("app.adapters.opencli_bridge.shutil.which", return_value="/usr/local/bin/opencli"), \
         patch("app.adapters.opencli_bridge.subprocess.run", side_effect=_raise_timeout):
        bridge = OpenCLIBridge()
        result = bridge.get_ths_hot_rank()

    assert result == []


# ---------- Case 5: 兼容 {"data":[...]} 包裹 schema ----------
def test_wrapped_data_schema():
    wrapped = {"data": [{"code": "000001", "name": "平安银行", "rank": 1}]}
    with patch("app.adapters.opencli_bridge.shutil.which", return_value="/usr/local/bin/opencli"), \
         patch("app.adapters.opencli_bridge.subprocess.run",
               return_value=_mk_proc(json.dumps(wrapped))):
        bridge = OpenCLIBridge()
        result = bridge.opencli_call("eastmoney/hot-rank")

    assert len(result) == 1
    assert result[0]["code"] == "000001"


# ---------- Case 6: 非法JSON → 返回 [] ----------
def test_invalid_json_returns_empty():
    with patch("app.adapters.opencli_bridge.shutil.which", return_value="/usr/local/bin/opencli"), \
         patch("app.adapters.opencli_bridge.subprocess.run",
               return_value=_mk_proc("not a json {{{")):
        bridge = OpenCLIBridge()
        result = bridge.opencli_call("eastmoney/hot-rank")

    assert result == []
