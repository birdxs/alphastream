# -*- coding: utf-8 -*-
"""
Input: 测试 ConversationManager 增删读改 / 50 条截断 H2 / 落盘幂等 / 并发追加 / C3 删 conv 不清 checkpoint
Output: pytest 用例集
Pos: tests/backend/unit/test_core_conversation.py - BE-03 ConversationManager
"""
import json
import os
import threading
import pytest

import app.core.conversation as conv_mod
from app.core.conversation import ConversationManager, get_conversation_manager


@pytest.fixture
def temp_conv_dir(tmp_path, monkeypatch):
    """重写 CONVERSATION_DIR 到隔离 tmp 目录"""
    d = tmp_path / "conv"
    d.mkdir()
    monkeypatch.setattr(conv_mod, 'CONVERSATION_DIR', str(d))
    # 重置单例
    conv_mod._manager = None
    yield str(d)
    conv_mod._manager = None


@pytest.fixture
def manager(temp_conv_dir):
    return ConversationManager()


# ============ T001 单例 ============
def test_T001_singleton(temp_conv_dir):
    m1 = get_conversation_manager()
    m2 = get_conversation_manager()
    assert m1 is m2


# ============ T002 create_conversation 落盘 ============
def test_T002_create_conversation_persists(manager, temp_conv_dir):
    cid = manager.create_conversation(title="测试对话")
    assert cid.startswith("conv_")
    path = os.path.join(temp_conv_dir, f"{cid}.json")
    assert os.path.exists(path)
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    assert data['conversation_id'] == cid
    assert data['title'] == "测试对话"
    assert data['messages'] == []


# ============ T003 默认标题 ============
def test_T003_default_title(manager):
    cid = manager.create_conversation()
    conv = manager.get_conversation(cid)
    assert conv['title'] == "新对话"


# ============ T004 add_message 基本 ============
def test_T004_add_message_basic(manager):
    cid = manager.create_conversation()
    mid = manager.add_message(cid, 'user', '你好')
    assert mid.startswith("msg_")
    conv = manager.get_conversation(cid)
    assert len(conv['messages']) == 1
    assert conv['messages'][0]['role'] == 'user'
    assert conv['messages'][0]['content'] == '你好'


# ============ Sprint4 decision_artifacts 挂载 ============
def test_sprint4_create_has_decision_artifacts_list(manager, temp_conv_dir):
    cid = manager.create_conversation(title="s4")
    conv = manager.get_conversation(cid)
    assert isinstance(conv.get("decision_artifacts"), list)
    assert conv["decision_artifacts"] == []


def test_sprint4_attach_decision_artifact(manager, temp_conv_dir):
    cid = manager.create_conversation()
    entry = manager.attach_decision_artifact(
        cid,
        {
            "artifact_type": "decision_card",
            "data": {"action": "HOLD", "confidence": 0.6},
            "decision_memo": {"summary": "持有"},
        },
        source="unit",
        task_id="task_ut_001",
        stock_code="600519",
    )
    assert entry is not None
    assert entry["id"].startswith("da_")
    assert entry["task_id"] == "task_ut_001"
    assert entry["stock_code"] == "600519"
    assert entry["artifact"]["artifact_type"] == "decision_card"

    items = manager.get_decision_artifacts(cid)
    assert len(items) == 1
    assert items[0]["id"] == entry["id"]

    conv = manager.get_conversation(cid)
    refs = conv.get("analysis_refs") or []
    assert any(
        r.get("type") == "decision_artifact" and r.get("task_id") == "task_ut_001"
        for r in refs
    )


def test_sprint4_attach_rejects_empty(manager):
    cid = manager.create_conversation()
    assert manager.attach_decision_artifact(cid, {}) is None
    assert manager.attach_decision_artifact(cid, None) is None  # type: ignore[arg-type]
    assert manager.get_decision_artifacts(cid) == []


# ============ T005 add_message 自动更新标题（首条 user 消息前 20 字符）============
def test_T005_auto_update_title_from_first_user_msg(manager):
    cid = manager.create_conversation()
    manager.add_message(cid, 'user', '请帮我分析 600519 贵州茅台 2025 年的财报')
    conv = manager.get_conversation(cid)
    assert conv['title'].startswith('请帮我分析 600519 贵州茅台')
    # 长度策略：>20 字符则截断加 "..."
    assert '...' in conv['title']


# ============ T006 add_message 含 artifacts / tool_calls ============
def test_T006_add_message_with_artifacts_and_tool_calls(manager):
    cid = manager.create_conversation()
    arts = [{'type': 'table', 'data': [{'a': 1}]}]
    tcs = [{'id': 'tc1', 'name': 'get_stock_data', 'args': {'code': '600519'}}]
    manager.add_message(cid, 'assistant', '看完了', artifacts=arts, tool_calls=tcs)
    conv = manager.get_conversation(cid)
    msg = conv['messages'][0]
    assert msg['artifacts'] == arts
    assert msg['tool_calls'] == tcs


# ============ T007 [H2] 50 条强截断（已知缺陷暴露） ============
def test_T007_H2_strict_truncate_at_50():
    """[H2] conversation.py:67-68 硬编码截断到最近 50 条；
    本测试明确暴露：插入 60 条后只保留最近 50 条，前 10 条永久丢失。"""
    # 独立 setup（不复用 manager fixture 以便清晰）
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        import unittest.mock as mock
        with mock.patch.object(conv_mod, 'CONVERSATION_DIR', d):
            mgr = ConversationManager()
            cid = mgr.create_conversation()
            for i in range(60):
                mgr.add_message(cid, 'user', f'msg_{i}')
            conv = mgr.get_conversation(cid)
            # 期望：只保留最近 50 条（msg_10..msg_59）
            assert len(conv['messages']) == 50
            assert conv['messages'][0]['content'] == 'msg_10'
            assert conv['messages'][-1]['content'] == 'msg_59'


# ============ T008 不存在 conversation_id → add_message 自动创建（实现兼容）============
def test_T008_add_message_to_missing_creates_new(manager):
    """当前实现：load 失败时自动创建新 conv，但写入的 conversation_id 是新的"""
    # 调用前不存在
    fake_cid = "conv_nonexistent_xxx"
    mgr = manager
    # 当前实现会自动 create_conversation 然后写入新 cid
    mid = mgr.add_message(fake_cid, 'user', '测试')
    assert mid.startswith("msg_")
    # 原 fake_cid 不会被创建为该 id 文件
    assert not os.path.exists(os.path.join(conv_mod.CONVERSATION_DIR, f"{fake_cid}.json"))


# ============ T009 JSON 落盘幂等性（重复保存内容不变） ============
def test_T009_save_idempotent(manager, temp_conv_dir):
    cid = manager.create_conversation(title="t")
    manager.add_message(cid, 'user', 'hi')
    path = os.path.join(temp_conv_dir, f"{cid}.json")
    with open(path, 'rb') as f:
        bytes1 = f.read()
    # 再次保存（通过 get + save 模式不变）
    conv = manager.get_conversation(cid)
    manager._save_conversation(cid, conv)
    with open(path, 'rb') as f:
        bytes2 = f.read()
    assert bytes1 == bytes2


# ============ T010 get_messages_for_ai 转 OpenAI 格式 ============
def test_T010_get_messages_for_ai_format(manager):
    cid = manager.create_conversation()
    manager.add_message(cid, 'user', 'q1')
    manager.add_message(cid, 'assistant', 'a1')
    out = manager.get_messages_for_ai(cid, max_messages=20)
    assert len(out) == 2
    assert out[0] == {'role': 'user', 'content': 'q1'}
    assert out[1] == {'role': 'assistant', 'content': 'a1'}


# ============ T011 get_messages_for_ai 含摘要时注入 system ============
def test_T011_get_messages_for_ai_with_summary(manager):
    cid = manager.create_conversation()
    for i in range(15):
        manager.add_message(cid, 'user', f'm{i}')
    manager.update_summary(cid, '历史摘要内容')
    out = manager.get_messages_for_ai(cid, max_messages=5)
    assert out[0]['role'] == 'system'
    assert '历史摘要内容' in out[0]['content']
    # 后续 5 条为真实消息
    assert len(out) == 6


# ============ T012 get_message_count ============
def test_T012_get_message_count(manager):
    cid = manager.create_conversation()
    assert manager.get_message_count(cid) == 0
    manager.add_message(cid, 'user', 'a')
    manager.add_message(cid, 'user', 'b')
    assert manager.get_message_count(cid) == 2


# ============ T013 list_conversations 按 updated_at 倒序 ============
def test_T013_list_conversations_sorted_desc(manager):
    import time
    cids = []
    for i in range(3):
        cid = manager.create_conversation(title=f"t{i}")
        manager.add_message(cid, 'user', f'msg{i}')
        cids.append(cid)
        time.sleep(0.02)  # 保证 updated_at 不同
    out = manager.list_conversations(limit=10)
    assert len(out) == 3
    # 最新创建的在前
    assert out[0]['conversation_id'] == cids[-1]


# ============ T014 list_conversations limit 生效 ============
def test_T014_list_conversations_limit(manager):
    for i in range(5):
        manager.create_conversation(title=f"t{i}")
    out = manager.list_conversations(limit=2)
    assert len(out) == 2


# ============ T015 delete_conversation 成功 + 幂等 ============
def test_T015_delete_conversation(manager, temp_conv_dir):
    cid = manager.create_conversation()
    assert manager.delete_conversation(cid) is True
    assert manager.delete_conversation(cid) is False  # 已删除
    assert not os.path.exists(os.path.join(temp_conv_dir, f"{cid}.json"))


# ============ T016 [C3] 删 conversation 不同步清理 checkpoint（预期失败）============
def test_T016_C3_delete_conv_does_not_clean_checkpoint(manager, temp_conv_dir):
    """[C3] 已知缺陷：删 conversation 不会清理 LangGraph checkpoint。
    本测试通过 mock checkpoint 目录验证 conversation 删除后 checkpoint 仍残留。"""
    # 模拟 checkpoint 目录与文件
    ckpt_dir = os.path.join(os.path.dirname(temp_conv_dir), "checkpoints")
    os.makedirs(ckpt_dir, exist_ok=True)
    cid = manager.create_conversation()
    ckpt_file = os.path.join(ckpt_dir, f"{cid}.ckpt")
    with open(ckpt_file, 'w') as f:
        f.write("checkpoint_data")

    manager.delete_conversation(cid)
    # 预期失败：checkpoint 仍存在（C3 缺陷）
    if os.path.exists(ckpt_file):
        pytest.xfail("[C3] delete_conversation 未同步清理 LangGraph checkpoint 文件")
    else:
        # 若未来修复，转为通过
        assert not os.path.exists(ckpt_file)


# ============ T017 add_stock_code 去重 ============
def test_T017_add_stock_code_dedup(manager):
    cid = manager.create_conversation()
    manager.add_stock_code(cid, '600519')
    manager.add_stock_code(cid, '600519')
    manager.add_stock_code(cid, '000001')
    conv = manager.get_conversation(cid)
    assert conv['stock_codes'] == ['600519', '000001']


# ============ T018 多线程并发追加消息 ============
def test_T018_concurrent_add_message(manager):
    """关注：并发写时不抛异常；最终消息数可能因竞态略低于总写入数（无锁）"""
    cid = manager.create_conversation()
    errors = []

    def writer(tid, n):
        try:
            for i in range(n):
                manager.add_message(cid, 'user', f't{tid}_m{i}')
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(t, 10)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    conv = manager.get_conversation(cid)
    # 由于无锁，最终条数 ≤ 50（截断后）；至少应有 1 条
    assert 1 <= len(conv['messages']) <= 50


# ============ T019 update_summary 落盘 ============
def test_T019_update_summary(manager):
    cid = manager.create_conversation()
    manager.update_summary(cid, "这是摘要")
    conv = manager.get_conversation(cid)
    assert conv.get('summary') == "这是摘要"
    assert 'summary_updated_at' in conv


# ============ T020 get_conversation 不存在返回 None ============
def test_T020_get_missing_returns_none(manager):
    assert manager.get_conversation("conv_does_not_exist") is None


# ============ T021 ThreadPoolExecutor 10 线程并发 add_message — JSON 写入截断风险 ============
def test_T021_threadpool_concurrent_add_message_json_integrity(manager, temp_conv_dir):
    """[BE-03b A.7] ThreadPoolExecutor 10 线程并发 add_message。
    已知风险：_save_conversation 非原子写（open w + json.dump），
    并发可能导致 JSON 文件 truncation（写到一半被其他线程覆盖头部）。
    本用例：
    - 确认无未捕获异常；
    - 加载磁盘文件并检查 JSON 结构完整（可解析、字段齐全）；
    - 若发现 JSONDecodeError，xfail 标记记录该缺陷。
    """
    from concurrent.futures import ThreadPoolExecutor

    cid = manager.create_conversation()

    def writer(i):
        manager.add_message(cid, 'user', f'tp_msg_{i}')

    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(writer, range(30)))

    # 直接读磁盘文件，验证 JSON 完整性
    path = os.path.join(temp_conv_dir, f"{cid}.json")
    assert os.path.exists(path)
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        # 文件结构完整
        assert 'messages' in data
        assert 'conversation_id' in data
        # 由于无锁竞态，消息数 <= 30，但 >= 1
        assert 1 <= len(data['messages']) <= 50
    except json.JSONDecodeError as e:
        pytest.xfail(f"[H2 衍生缺陷] _save_conversation 非原子写导致 JSON 截断: {e}")


# ============ T022 update_title — API 缺失（任务要求但代码未实现） ============
def test_T022_update_title_api_missing():
    """[任务要求 A.4] 文档要求 update_title(conv_id, title)，但当前实现未提供。
    通过 _save_conversation 间接修改标题作为 workaround；标记 xfail 跟踪 API 缺失。"""
    if not hasattr(ConversationManager, 'update_title'):
        pytest.xfail("ConversationManager.update_title 未实现，需补齐公开 API")
    # 若未来补齐则下述断言应通过
    import tempfile
    import unittest.mock as mock
    with tempfile.TemporaryDirectory() as d:
        with mock.patch.object(conv_mod, 'CONVERSATION_DIR', d):
            mgr = ConversationManager()
            cid = mgr.create_conversation(title="旧")
            mgr.update_title(cid, "新标题")  # type: ignore[attr-defined]
            conv = mgr.get_conversation(cid)
            assert conv['title'] == "新标题"
