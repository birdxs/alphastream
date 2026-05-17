// Input  : useChatStore 的 actions（addMessage/appendStreamContent/resetStreamContent/setStreaming/addArtifact 等）
// Output : 测试结果（state shape、action 行为、artifacts/messages 列表操作）
// Pos    : tests/frontend/stores/chat-store.test.ts — FE-01 store 单测
//
// 一旦此文件修改，请同步更新 tests/audit/reports/FE-01_stores.md。

import { describe, it, expect, beforeEach } from 'vitest';
import { useChatStore } from '@/lib/stores/chat-store';
import type { ChatMessage, Artifact, Conversation } from '@/lib/types';

function resetChat() {
  useChatStore.setState({
    conversations: [],
    activeConversationId: null,
    messages: [],
    isStreaming: false,
    streamingContent: '',
    artifacts: [],
    followUpQuestions: [],
    conversationsRefreshTick: 0,
  });
}

describe('useChatStore', () => {
  beforeEach(() => {
    resetChat();
  });

  it('初始 state shape 正确', () => {
    const s = useChatStore.getState();
    expect(s.conversations).toEqual([]);
    expect(s.activeConversationId).toBeNull();
    expect(s.messages).toEqual([]);
    expect(s.isStreaming).toBe(false);
    expect(s.streamingContent).toBe('');
    expect(s.artifacts).toEqual([]);
    expect(s.followUpQuestions).toEqual([]);
    expect(s.conversationsRefreshTick).toBe(0);
  });

  it('addMessage 追加消息 / setStreaming 切换流式状态', () => {
    const msg: ChatMessage = {
      role: 'user',
      content: 'hello',
    } as ChatMessage;
    useChatStore.getState().addMessage(msg);
    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useChatStore.getState().messages[0]).toEqual(msg);

    useChatStore.getState().setStreaming(true);
    expect(useChatStore.getState().isStreaming).toBe(true);
  });

  it('appendStreamContent 累积 + resetStreamContent 清空（边界：空字符串）', () => {
    const store = useChatStore.getState();
    store.appendStreamContent('Hello ');
    store.appendStreamContent('world');
    expect(useChatStore.getState().streamingContent).toBe('Hello world');

    // 边界：追加空字符串不应改变内容
    store.appendStreamContent('');
    expect(useChatStore.getState().streamingContent).toBe('Hello world');

    store.resetStreamContent();
    expect(useChatStore.getState().streamingContent).toBe('');
  });

  it('addArtifact 添加 + clearArtifacts 清空', () => {
    const a1: Artifact = { id: 'a1', type: 'chart', data: {} } as unknown as Artifact;
    const a2: Artifact = { id: 'a2', type: 'table', data: {} } as unknown as Artifact;
    useChatStore.getState().addArtifact(a1);
    useChatStore.getState().addArtifact(a2);
    expect(useChatStore.getState().artifacts).toHaveLength(2);

    useChatStore.getState().clearArtifacts();
    expect(useChatStore.getState().artifacts).toEqual([]);
  });

  it('bumpConversationsRefresh 自增 + updateConversationTitle 仅更新匹配项', () => {
    const store = useChatStore.getState();
    store.bumpConversationsRefresh();
    store.bumpConversationsRefresh();
    expect(useChatStore.getState().conversationsRefreshTick).toBe(2);

    const c1: Conversation = { conversation_id: 'c1', title: 'old1' } as Conversation;
    const c2: Conversation = { conversation_id: 'c2', title: 'old2' } as Conversation;
    store.setConversations([c1, c2]);
    store.updateConversationTitle('c1', 'new1');
    const cs = useChatStore.getState().conversations;
    expect(cs[0].title).toBe('new1');
    expect(cs[1].title).toBe('old2');
  });

  it('setActiveConversation 设置和清空', () => {
    useChatStore.getState().setActiveConversation('conv-1');
    expect(useChatStore.getState().activeConversationId).toBe('conv-1');
    useChatStore.getState().setActiveConversation(null);
    expect(useChatStore.getState().activeConversationId).toBeNull();
  });
});
