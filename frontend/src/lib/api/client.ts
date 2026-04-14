/**
 * Input: 后端API URL + 请求参数
 * Output: 类型安全的API响应
 * Pos: lib/api/client.ts - 统一API客户端，所有后端调用的唯一入口
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

import type { SSEHandlers } from '@/lib/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  // 通用GET请求
  async get<T>(path: string, params?: Record<string, string>): Promise<T> {
    let url = `${this.baseUrl}${path}`;
    if (params) {
      const sp = new URLSearchParams(params);
      url += `?${sp.toString()}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.json();
  }

  // 通用POST请求
  async post<T>(path: string, body: Record<string, unknown>): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.json();
  }

  // SSE流式请求（支持自动重连，最多重试2次）
  async streamPost(
    path: string,
    body: Record<string, unknown>,
    handlers: SSEHandlers,
    signal?: AbortSignal
  ): Promise<void> {
    const MAX_RETRIES = 2;
    const RETRY_DELAYS = [1000, 3000];

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const res = await fetch(`${this.baseUrl}${path}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal,
        });

        if (!res.ok || !res.body) {
          if (attempt < MAX_RETRIES) {
            await new Promise(r => setTimeout(r, RETRY_DELAYS[attempt]));
            continue;
          }
          handlers.onError?.({ code: 'FETCH_ERROR', message: `HTTP ${res.status}` });
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let doneEventSeen = false;

        // 内部派发：处理一个完整SSE事件块（多行）— 按事件而非按行处理，
        // 避免TCP chunk在event:/data:中间切断时丢失event前缀
        const dispatchBlock = (block: string) => {
          let eventType = '';
          let dataStr = '';
          for (const rawLine of block.split('\n')) {
            const line = rawLine.replace(/\r$/, '');
            if (!line) continue;
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
              // 多行 data 拼接（SSE 规范）
              dataStr += (dataStr ? '\n' : '') + line.slice(5).trimStart();
            }
          }
          if (!eventType || !dataStr) return;
          let data: unknown;
          try { data = JSON.parse(dataStr); } catch (e) {
            console.warn('[SSE] JSON parse error for event', eventType, e);
            return;
          }
          let effectiveType = eventType;
          let payload: unknown = data;
          if (eventType === 'info' && data && typeof data === 'object' && typeof (data as { event_type?: unknown }).event_type === 'string') {
            const d = data as { event_type: string; data?: unknown };
            effectiveType = d.event_type;
            payload = d.data ?? d;
          }
          try {
            switch (effectiveType) {
              case 'token': handlers.onToken?.(payload as Parameters<NonNullable<typeof handlers.onToken>>[0]); break;
              case 'tool_call_start': handlers.onToolCallStart?.(payload as Parameters<NonNullable<typeof handlers.onToolCallStart>>[0]); break;
              case 'tool_call_result': handlers.onToolCallResult?.(payload as Parameters<NonNullable<typeof handlers.onToolCallResult>>[0]); break;
              case 'artifact': handlers.onArtifact?.(payload as Parameters<NonNullable<typeof handlers.onArtifact>>[0]); break;
              case 'agent_progress': handlers.onAgentProgress?.(payload as Parameters<NonNullable<typeof handlers.onAgentProgress>>[0]); break;
              case 'reasoning': handlers.onReasoning?.(payload as Parameters<NonNullable<typeof handlers.onReasoning>>[0]); break;
              case 'error': handlers.onError?.(payload as Parameters<NonNullable<typeof handlers.onError>>[0]); break;
              case 'done':
                doneEventSeen = true;
                handlers.onDone?.(payload as Parameters<NonNullable<typeof handlers.onDone>>[0]);
                break;
            }
          } catch (handlerErr) {
            console.warn('[SSE] handler error for event', effectiveType, handlerErr);
          }
        };

        try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            // 末尾残余作为最后一个事件块派发（若有）
            if (buffer.trim()) dispatchBlock(buffer);
            break;
          }
          buffer += decoder.decode(value, { stream: true });
          // SSE 事件以空行（\n\n 或 \r\n\r\n）分隔
          let sepIdx: number;
          while ((sepIdx = buffer.search(/\r?\n\r?\n/)) !== -1) {
            const block = buffer.slice(0, sepIdx);
            const sepMatch = buffer.slice(sepIdx).match(/^(\r?\n\r?\n)/);
            buffer = buffer.slice(sepIdx + (sepMatch ? sepMatch[1].length : 2));
            if (block.trim()) dispatchBlock(block);
          }
        }
        } finally {
          // 无论 done 事件是否触发、handler 是否抛错，都强制通知上层清理 loading 状态
          try { handlers.onClose?.(); } catch (e) { console.warn('[SSE] onClose error', e); }
          if (!doneEventSeen) {
            console.warn('[SSE] stream closed without done event');
          }
        }
        return; // 成功处理完毕，退出重试循环

      } catch (e) {
        if (e instanceof DOMException && e.name === 'AbortError') throw e;
        if (attempt < MAX_RETRIES) {
          await new Promise(r => setTimeout(r, RETRY_DELAYS[attempt]));
          continue;
        }
        throw e;
      }
    }
  }

  // DELETE请求
  async delete(path: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}${path}`, { method: 'DELETE' });
    if (!res.ok) throw new ApiError(res.status, await res.text());
  }
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const apiClient = new ApiClient();
export { ApiError };
