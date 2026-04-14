/**
 * Input: 用户消息文本 + 可选参数（股票代码、市场类型、研究深度）
 * Output: 发送消息函数 + 停止生成函数，自动处理SSE流并更新store，完成时支持浏览器Notification推送
 * Pos: lib/hooks/use-chat-stream.ts - 聊天流式请求Hook，连接API客户端与状态管理
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

import { useCallback, useRef } from 'react';
import { apiClient } from '@/lib/api/client';
import { useChatStore } from '@/lib/stores/chat-store';
import { useAgentStore } from '@/lib/stores/agent-store';
import type { SSEHandlers, ChatMessage } from '@/lib/types';

export function useChatStream() {
  // 不订阅store — 通过getState()在回调内获取最新状态，避免全量重渲染
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (
      message: string,
      options: {
        stock_code?: string;
        market_type?: string;
        research_depth?: number;
      } = {}
    ) => {
      // 取消之前的请求
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      const chatStore = useChatStore.getState();
      const agentStore = useAgentStore.getState();

      // 添加用户消息
      const userMsg: ChatMessage = {
        message_id: `user_${Date.now()}`,
        role: 'user',
        content: message,
        created_at: new Date().toISOString(),
      };
      chatStore.addMessage(userMsg);

      // 新对话第一条消息：自动设置对话标题为前20个字符
      const isFirstMessage = chatStore.messages.filter((m) => m.role === 'user').length === 0;
      if (isFirstMessage && chatStore.activeConversationId) {
        const autoTitle = message.slice(0, 20) + (message.length > 20 ? '...' : '');
        chatStore.updateConversationTitle(chatStore.activeConversationId, autoTitle);
      }

      chatStore.setStreaming(true);
      chatStore.resetStreamContent();
      chatStore.clearArtifacts();
      agentStore.reset();
      // 走agent-analyze时立即打开isAnalyzing，让右侧Agent面板在首个事件到达前就显示"进行中"
      // （以下endpoint判断稍后也会计算一次，此处提前点亮即可）
      const _msgHasCode = /\b\d{6}\b/.test(message);
      const _isAgentRoute = /分析|研究|深度|全面|多[aA]gent|agent/.test(message) && (_msgHasCode || options.stock_code);
      if (_isAgentRoute) agentStore.setAnalyzing(true);

      // 累积完整内容（不受打字动画影响），用于onDone时生成最终消息
      let fullContentBuffer = '';

      const handlers: SSEHandlers = {
        onToken: (data) => {
          const content = data.content;
          fullContentBuffer += content;
          if (content.length <= 5) {
            // 短token直接追加
            chatStore.appendStreamContent(content);
          } else {
            // 长文本直接追加（避免requestAnimationFrame导致onDone时内容不完整）
            chatStore.appendStreamContent(content);
          }
        },
        onToolCallStart: (data) => {
          agentStore.addToolCall(data);
          // 实时数据流：工具调用开始
          let argsPreview = '';
          try {
            argsPreview = JSON.stringify(data.arguments ?? {});
          } catch { argsPreview = String(data.arguments ?? ''); }
          agentStore.appendEvent({
            type: 'tool_call_start',
            agent: data.agent,
            title: `调用工具 ${data.tool_name}`,
            detail: argsPreview,
            meta: { tool_call_id: data.tool_call_id, tool_name: data.tool_name, arguments: data.arguments },
          });
        },
        onToolCallResult: (data) => {
          agentStore.setToolCallResult(data.tool_call_id, data);
          if (data.artifact) {
            chatStore.addArtifact(data.artifact);
          }
          // 实时数据流：工具调用结果
          const dur = data.duration_ms != null ? ` · ${data.duration_ms}ms` : '';
          agentStore.appendEvent({
            type: 'tool_call_result',
            title: `${data.tool_name} 完成${dur}`,
            detail: data.result_summary || (data.artifact ? `生成 artifact: ${data.artifact.title}` : ''),
            meta: { tool_call_id: data.tool_call_id, duration_ms: data.duration_ms },
          });
        },
        onArtifact: (data) => {
          chatStore.addArtifact(data);
        },
        onAgentProgress: (data) => {
          agentStore.setAgentProgress(data);
          // 实时数据流：agent状态变化
          const evType: 'agent_started' | 'agent_progress' | 'agent_completed' =
            data.status === 'started' ? 'agent_started' :
            data.status === 'completed' ? 'agent_completed' : 'agent_progress';
          agentStore.appendEvent({
            type: evType,
            agent: data.agent_name,
            title: data.status === 'started'
              ? `${data.agent_name} 启动`
              : data.status === 'completed'
                ? `${data.agent_name} 完成`
                : `${data.agent_name} ${Math.round(data.progress)}%`,
            detail: data.message,
            meta: { progress: data.progress, status: data.status },
          });
        },
        onReasoning: (data) => {
          agentStore.appendEvent({
            type: 'reasoning',
            agent: data.agent,
            title: `${data.agent || '推理'} 思考`,
            detail: data.content,
          });
        },
        onError: (data) => {
          const errText = typeof data === 'string' ? data : (data?.message || data?.error || JSON.stringify(data));
          console.error('Stream error:', errText, data);
          const errorMsg: ChatMessage = {
            message_id: `error_${Date.now()}`,
            role: 'assistant',
            content: `⚠️ ${errText || '分析服务暂时不可用（后端超时/断开）'}\n\n请检查后端服务状态，或点击"重试"。`,
            created_at: new Date().toISOString(),
          };
          chatStore.addMessage(errorMsg);
          chatStore.resetStreamContent();
          chatStore.setStreaming(false); agentStore.setAnalyzing(false);
          // 保存重试建议
          chatStore.setFollowUps(['🔄 重试上一个问题']);
        },
        onDone: (data) => {
          // 将流式内容转为正式消息，优先使用完整缓冲内容避免打字动画导致内容不完整
          const finalContent = fullContentBuffer || useChatStore.getState().streamingContent;
          const assistantMsg: ChatMessage = {
            message_id: `assistant_${Date.now()}`,
            role: 'assistant',
            content: finalContent,
            artifacts: [...useChatStore.getState().artifacts],
            created_at: new Date().toISOString(),
          };
          chatStore.addMessage(assistantMsg);
          chatStore.resetStreamContent();
          chatStore.setStreaming(false); agentStore.setAnalyzing(false);
          chatStore.setFollowUps(data.follow_up_questions || []);

          // Tab标题闪烁提醒 + 浏览器通知
          if (document.hidden) {
            const originalTitle = document.title;
            let blinking = true;
            const interval = setInterval(() => {
              document.title = blinking ? '\u2705 分析完成!' : originalTitle;
              blinking = !blinking;
            }, 1000);
            const stopBlink = () => {
              clearInterval(interval);
              document.title = originalTitle;
              document.removeEventListener('visibilitychange', stopBlink);
            };
            document.addEventListener('visibilitychange', stopBlink);
            setTimeout(stopBlink, 10000);

            // 浏览器Notification推送
            const stockLabel = options.stock_code || '分析';
            if (typeof Notification !== 'undefined') {
              if (Notification.permission === 'granted') {
                new Notification(`AI分析完成 — ${stockLabel}`, {
                  body: '点击返回查看结果',
                  icon: '/favicon.ico',
                });
              } else if (Notification.permission === 'default') {
                Notification.requestPermission().then((perm) => {
                  if (perm === 'granted') {
                    new Notification(`AI分析完成 — ${stockLabel}`, {
                      body: '点击返回查看结果',
                      icon: '/favicon.ico',
                    });
                  }
                });
              }
            }
          }
        },
      };

      // 意图路由：消息含6位股票代码且含"分析"关键字（或options.stock_code存在），走多Agent分析端点；
      // 否则走普通聊天端点
      const codeMatch = message.match(/\b(\d{6})\b/);
      const isAnalyze = /分析|研究|深度|全面|多[aA]gent|agent/.test(message) && (codeMatch || options.stock_code);
      const endpoint = isAnalyze ? '/api/ai/agent-analyze' : '/api/ai/chat';
      const body = isAnalyze
        ? {
            stock_code: options.stock_code || codeMatch?.[1] || '',
            market_type: options.market_type || 'A',
            research_depth: options.research_depth ?? 3,
            user_message: message,
            conversation_id: chatStore.activeConversationId || '',
          }
        : {
            message,
            conversation_id: chatStore.activeConversationId || '',
            ...options,
          };

      try {
        await apiClient.streamPost(
          endpoint,
          body,
          handlers,
          abortRef.current.signal
        );
      } catch (e) {
        if (e instanceof DOMException && e.name === 'AbortError') {
          // 用户主动取消，正常处理
          const currentContent = useChatStore.getState().streamingContent;
          if (currentContent) {
            const stoppedMsg: ChatMessage = {
              message_id: `assistant_${Date.now()}`,
              role: 'assistant',
              content: currentContent + '\n\n[已停止]',
              artifacts: [...useChatStore.getState().artifacts],
              created_at: new Date().toISOString(),
            };
            chatStore.addMessage(stoppedMsg);
          }
          chatStore.resetStreamContent();
          chatStore.setStreaming(false); agentStore.setAnalyzing(false);
          return;
        }
        chatStore.setStreaming(false); agentStore.setAnalyzing(false);
        console.error('Chat stream error:', e);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { sendMessage, stopGeneration };
}
