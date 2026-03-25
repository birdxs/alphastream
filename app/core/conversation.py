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
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

CONVERSATION_DIR = os.path.join(os.path.dirname(__file__), '../../data/conversations')


class ConversationManager:
    """对话管理器 — 存储和检索多轮对话历史"""

    def __init__(self):
        os.makedirs(CONVERSATION_DIR, exist_ok=True)

    def create_conversation(self, title: str = '') -> str:
        """创建新对话，返回conversation_id"""
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        conv = {
            'conversation_id': conv_id,
            'title': title or '新对话',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'messages': [],
            'stock_codes': [],
            'analysis_refs': []
        }
        self._save_conversation(conv_id, conv)
        return conv_id

    def add_message(self, conversation_id: str, role: str, content: str,
                    artifacts: List[Dict] = None, tool_calls: List[Dict] = None) -> str:
        """添加消息到对话，返回message_id"""
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
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        conv['messages'].append(message)
        conv['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 自动更新标题（第一条用户消息的前20个字符）
        if role == 'user' and conv['title'] == '新对话':
            conv['title'] = content[:20] + ('...' if len(content) > 20 else '')

        # 保留最近50条消息防止无限增长
        if len(conv['messages']) > 50:
            conv['messages'] = conv['messages'][-50:]

        self._save_conversation(conversation_id, conv)
        return msg_id

    def get_messages_for_ai(self, conversation_id: str, max_messages: int = 20) -> List[Dict]:
        """获取对话历史，转换为OpenAI messages格式"""
        conv = self._load_conversation(conversation_id)
        if not conv:
            return []

        messages = []
        for msg in conv['messages'][-max_messages:]:
            messages.append({
                'role': msg['role'],
                'content': msg['content']
            })
        return messages

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """获取完整对话"""
        return self._load_conversation(conversation_id)

    def list_conversations(self, limit: int = 20) -> List[Dict]:
        """列出最近的对话（不含完整消息）"""
        conversations = []
        try:
            files = sorted(os.listdir(CONVERSATION_DIR), reverse=True)
            for f in files[:limit]:
                if f.endswith('.json'):
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
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载对话失败: {e}")
        return None

    def _save_conversation(self, conversation_id: str, data: Dict):
        filepath = os.path.join(CONVERSATION_DIR, f"{conversation_id}.json")
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存对话失败: {e}")


# 全局单例
_manager = None

def get_conversation_manager() -> ConversationManager:
    global _manager
    if _manager is None:
        _manager = ConversationManager()
    return _manager
