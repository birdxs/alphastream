/**
 * Input: 用户消息文本 + 可选参数（股票代码、市场类型、研究深度）
 * Output: 发送消息函数，自动处理SSE流并更新store
 * Pos: lib/hooks/use-chat-stream.ts - 聊天流式请求Hook，连接API客户端与状态管理
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

import { useCallback } from 'react';
import { apiClient } from '@/lib/api/client';
import { useChatStore } from '@/lib/stores/chat-store';
import { useAgentStore } from '@/lib/stores/agent-store';
import type { SSEHandlers, ChatMessage } from '@/lib/types';

export function useChatStream() {
  const chatStore = useChatStore();
  const agentStore = useAgentStore();

  const sendMessage = useCallback(
    async (
      message: string,
      options: {
        stock_code?: string;
        market_type?: string;
        research_depth?: number;
      } = {}
    ) => {
      // 添加用户消息
      const userMsg: ChatMessage = {
        message_id: `user_${Date.now()}`,
        role: 'user',
        content: message,
        created_at: new Date().toISOString(),
      };
      chatStore.addMessage(userMsg);
      chatStore.setStreaming(true);
      chatStore.resetStreamContent();
      chatStore.clearArtifacts();
      agentStore.reset();

      const handlers: SSEHandlers = {
        onToken: (data) => {
          chatStore.appendStreamContent(data.content);
        },
        onToolCallStart: (data) => {
          agentStore.addToolCall(data);
        },
        onToolCallResult: (data) => {
          agentStore.setToolCallResult(data.tool_call_id, data);
          if (data.artifact) {
            chatStore.addArtifact(data.artifact);
          }
        },
        onArtifact: (data) => {
          chatStore.addArtifact(data);
        },
        onAgentProgress: (data) => {
          agentStore.setAgentProgress(data);
        },
        onError: (data) => {
          console.error('Stream error:', data);
          // 将错误展示为AI消息
          const errorMsg: ChatMessage = {
            message_id: `error_${Date.now()}`,
            role: 'assistant',
            content: `⚠️ ${data.message || '分析过程出错，请稍后重试'}`,
            created_at: new Date().toISOString(),
          };
          chatStore.addMessage(errorMsg);
          chatStore.resetStreamContent();
          chatStore.setStreaming(false);
        },
        onDone: (data) => {
          // 将流式内容转为正式消息
          const assistantMsg: ChatMessage = {
            message_id: `assistant_${Date.now()}`,
            role: 'assistant',
            content: useChatStore.getState().streamingContent,
            artifacts: [...useChatStore.getState().artifacts],
            created_at: new Date().toISOString(),
          };
          chatStore.addMessage(assistantMsg);
          chatStore.resetStreamContent();
          chatStore.setStreaming(false);
          chatStore.setFollowUps(data.follow_up_questions || []);
        },
      };

      try {
        await apiClient.streamPost(
          '/api/ai/chat',
          {
            message,
            conversation_id: chatStore.activeConversationId || '',
            ...options,
          },
          handlers
        );
      } catch (e) {
        chatStore.setStreaming(false);
        console.error('Chat stream error:', e);
      }
    },
    [chatStore, agentStore]
  );

  return { sendMessage };
}
