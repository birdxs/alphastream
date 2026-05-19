"""
Input: 用户对话消息、AI回复、工具调用记录、Artifact数据
Output: 对话历史存取接口、多轮上下文管理
Pos: app/core/conversation.py - 对话上下文持久化，支持多轮AI分析对话

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import os
import json
import uuid
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

_ASIA_SHANGHAI = timezone(timedelta(hours=8))
now_cn = lambda: datetime.now(_ASIA_SHANGHAI)

logger = logging.getLogger(__name__)

CONVERSATION_DIR = os.path.join(os.path.dirname(__file__), '../../data/conversations')


class ConversationManager:
    """对话管理器 — 存储和检索多轮对话历史

    线程安全：所有 read-modify-write 操作以及底层 _load / _save 均由可重入锁
    `_lock` 保护，避免多线程并发下的 lost-update 与 JSON 文件半写损坏。
    """

    def __init__(self):
        os.makedirs(CONVERSATION_DIR, exist_ok=True)
        # 可重入锁：add_message 内部会同时调 _load_conversation 和 _save_conversation，
        # 因此使用 RLock 允许同线程多次获取。
        self._lock = threading.RLock()

    def create_conversation(self, title: str = '') -> str:
        """创建新对话，返回conversation_id"""
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        conv = {
            'conversation_id': conv_id,
            'title': title or '新对话',
            'created_at': now_cn().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': now_cn().strftime('%Y-%m-%d %H:%M:%S'),
            'messages': [],
            'stock_codes': [],
            'analysis_refs': []
        }
        self._save_conversation(conv_id, conv)
        return conv_id

    def add_message(self, conversation_id: str, role: str, content: str,
                    artifacts: List[Dict] = None, tool_calls: List[Dict] = None) -> str:
        """添加消息到对话，返回message_id (线程安全)

        使用 RLock 串行化 read-modify-write 序列，避免多线程并发下：
        - lost update（两线程基于同一旧快照覆盖写）
        - JSON 文件半写损坏（open('w') 截断与写入穿插）
        """
        with self._lock:
            conv = self._load_conversation(conversation_id)
            if conv is None:
                conv_id = self.create_conversation()
                conv = self._load_conversation(conv_id)
                conversation_id = conv_id

            msg_id = f"msg_{uuid.uuid4().hex[:8]}"
            message = {
                'message_id': msg_id,
                'role': role,
                'content': content,
                'artifacts': artifacts or [],
                'tool_calls': tool_calls or [],
                'created_at': now_cn().strftime('%Y-%m-%d %H:%M:%S')
            }
            conv['messages'].append(message)
            conv['updated_at'] = now_cn().strftime('%Y-%m-%d %H:%M:%S')

            # 自动更新标题（第一条用户消息的前20个字符）
            if role == 'user' and conv['title'] == '新对话':
                conv['title'] = content[:20] + ('...' if len(content) > 20 else '')

            # 保留最近50条消息防止无限增长
            if len(conv['messages']) > 50:
                conv['messages'] = conv['messages'][-50:]

            self._save_conversation(conversation_id, conv)
            return msg_id

    def get_messages_for_ai(self, conversation_id: str, max_messages: int = 20) -> List[Dict]:
        """获取对话历史，转换为OpenAI messages格式（优先使用摘要压缩上下文）"""
        conv = self._load_conversation(conversation_id)
        if not conv:
            return []

        messages = []
        # 如果有摘要且消息超过10条，使用摘要 + 最近几条消息
        summary = conv.get('summary', '')
        all_msgs = conv['messages']
        if summary and len(all_msgs) > 10:
            # 注入摘要作为系统级上下文提示
            messages.append({
                'role': 'system',
                'content': f'以下是之前对话的摘要：{summary}'
            })
            # 仅取最近的消息
            for msg in all_msgs[-max_messages:]:
                messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        else:
            for msg in all_msgs[-max_messages:]:
                messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        return messages

    def update_summary(self, conversation_id: str, summary: str):
        """更新对话摘要"""
        conv = self._load_conversation(conversation_id)
        if conv:
            conv['summary'] = summary
            conv['summary_updated_at'] = now_cn().strftime('%Y-%m-%d %H:%M:%S')
            self._save_conversation(conversation_id, conv)

    def get_message_count(self, conversation_id: str) -> int:
        """获取对话消息数量"""
        conv = self._load_conversation(conversation_id)
        if conv:
            return len(conv.get('messages', []))
        return 0

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """获取完整对话"""
        return self._load_conversation(conversation_id)

    def list_conversations(self, limit: int = 20) -> List[Dict]:
        """列出最近的对话（不含完整消息）

        按 updated_at 倒序，而非按文件名（conv_id 为随机 uuid hex，文件名序 != 时间序）。
        """
        conversations = []
        try:
            # 先按文件 mtime 倒序，避免一次性加载全部 json
            entries = []
            for f in os.listdir(CONVERSATION_DIR):
                if not f.endswith('.json'):
                    continue
                fpath = os.path.join(CONVERSATION_DIR, f)
                try:
                    entries.append((os.path.getmtime(fpath), f))
                except OSError:
                    continue
            entries.sort(key=lambda x: x[0], reverse=True)

            for _mtime, f in entries:
                conv = self._load_conversation(f.replace('.json', ''))
                if conv:
                    conversations.append({
                        'conversation_id': conv['conversation_id'],
                        'title': conv['title'],
                        'created_at': conv['created_at'],
                        'updated_at': conv['updated_at'],
                        'message_count': len(conv['messages']),
                        'stock_codes': conv.get('stock_codes', [])
                    })

            # 以 updated_at 字符串再排序一次（YYYY-MM-DD HH:MM:SS 字典序==时间序），兜底 mtime 与业务时间不一致的情况
            conversations.sort(key=lambda c: c.get('updated_at') or c.get('created_at') or '', reverse=True)
            return conversations[:limit]
        except Exception as e:
            logger.warning(f"列出对话失败: {e}")
        return conversations

    def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话"""
        filepath = os.path.join(CONVERSATION_DIR, f"{conversation_id}.json")
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
        except Exception as e:
            logger.error(f"删除对话失败: {e}")
        return False

    def add_stock_code(self, conversation_id: str, stock_code: str):
        """记录对话涉及的股票代码"""
        conv = self._load_conversation(conversation_id)
        if conv and stock_code not in conv.get('stock_codes', []):
            conv.setdefault('stock_codes', []).append(stock_code)
            self._save_conversation(conversation_id, conv)

    def _load_conversation(self, conversation_id: str) -> Optional[Dict]:
        filepath = os.path.join(CONVERSATION_DIR, f"{conversation_id}.json")
        with self._lock:
            try:
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except Exception as e:
                logger.warning(f"加载对话失败: {e}")
            return None

    def _save_conversation(self, conversation_id: str, data: Dict):
        """原子化保存：先写临时文件再 os.replace，保证读侧永远读到完整 JSON。"""
        filepath = os.path.join(CONVERSATION_DIR, f"{conversation_id}.json")
        tmppath = f"{filepath}.tmp.{os.getpid()}.{threading.get_ident()}"
        with self._lock:
            try:
                with open(tmppath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except OSError:
                        pass
                os.replace(tmppath, filepath)
            except Exception as e:
                logger.error(f"保存对话失败: {e}")
                try:
                    if os.path.exists(tmppath):
                        os.remove(tmppath)
                except OSError:
                    pass


# 全局单例
_manager = None

def get_conversation_manager() -> ConversationManager:
    global _manager
    if _manager is None:
        _manager = ConversationManager()
    return _manager
