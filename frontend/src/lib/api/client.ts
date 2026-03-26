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

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          let eventType = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ') && eventType) {
              try {
                const data = JSON.parse(line.slice(6));
                switch (eventType) {
                  case 'token':
                    handlers.onToken?.(data);
                    break;
                  case 'tool_call_start':
                    handlers.onToolCallStart?.(data);
                    break;
                  case 'tool_call_result':
                    handlers.onToolCallResult?.(data);
                    break;
                  case 'artifact':
                    handlers.onArtifact?.(data);
                    break;
                  case 'agent_progress':
                    handlers.onAgentProgress?.(data);
                    break;
                  case 'reasoning':
                    handlers.onReasoning?.(data);
                    break;
                  case 'error':
                    handlers.onError?.(data);
                    break;
                  case 'done':
                    handlers.onDone?.(data);
                    break;
                }
              } catch {
                /* ignore parse errors */
              }
              eventType = '';
            }
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
