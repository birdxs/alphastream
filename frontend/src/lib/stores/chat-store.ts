/**
 * Input: 用户交互事件（发送消息、切换对话等）
 * Output: 聊天状态（对话列表、消息、流式内容、artifacts）
 * Pos: lib/stores/chat-store.ts - 聊天核心状态管理
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ChatMessage, Artifact, Conversation } from '@/lib/types';

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  streamingContent: string;
  artifacts: Artifact[];
  followUpQuestions: string[];
  // Q2(2026-04-15): 对话列表刷新计数器 — onDone 递增后 sidebar 自动重载
  conversationsRefreshTick: number;

  // Actions
  setActiveConversation: (id: string | null) => void;
  addMessage: (msg: ChatMessage) => void;
  setStreaming: (streaming: boolean) => void;
  appendStreamContent: (content: string) => void;
  resetStreamContent: () => void;
  addArtifact: (artifact: Artifact) => void;
  clearArtifacts: () => void;
  setFollowUps: (questions: string[]) => void;
  setConversations: (convs: Conversation[]) => void;
  setMessages: (msgs: ChatMessage[]) => void;
  updateConversationTitle: (id: string, title: string) => void;
  bumpConversationsRefresh: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      conversations: [],
      activeConversationId: null,
      messages: [],
      isStreaming: false,
      streamingContent: '',
      artifacts: [],
      followUpQuestions: [],
      conversationsRefreshTick: 0,

      setActiveConversation: (id) => set({ activeConversationId: id }),
      bumpConversationsRefresh: () =>
        set((s) => ({ conversationsRefreshTick: s.conversationsRefreshTick + 1 })),
      addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
      setStreaming: (streaming) => set({ isStreaming: streaming }),
      appendStreamContent: (content) =>
        set((s) => ({ streamingContent: s.streamingContent + content })),
      resetStreamContent: () => set({ streamingContent: '' }),
      addArtifact: (artifact) =>
        set((s) => ({ artifacts: [...s.artifacts, artifact] })),
      clearArtifacts: () => set({ artifacts: [] }),
      setFollowUps: (questions) => set({ followUpQuestions: questions }),
      setConversations: (convs) => set({ conversations: convs }),
      setMessages: (msgs) => set({ messages: msgs }),
      updateConversationTitle: (id, title) =>
        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.conversation_id === id ? { ...c, title } : c
          ),
        })),
    }),
    {
      name: 'chat-storage',
      partialize: (state) => ({
        activeConversationId: state.activeConversationId,
        conversations: state.conversations,
        messages: state.messages,
      }),
    }
  )
);
