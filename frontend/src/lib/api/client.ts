/**
 * Input: 后端API URL + 请求参数
 * Output: 类型安全的API响应
 * Pos: lib/api/client.ts - 统一API客户端，所有后端调用的唯一入口
 * Note: GET/POST 均走 safeJSONParse, 兼容非标 JSON (NaN/Infinity -> null)
 * Note: streamPost 直连后端 SSE_BASE (绕过Next dev rewrites流式buffer问题)
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

import type { SSEHandlers } from '@/lib/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// 前端 fetch 默认超时（由 NEXT_PUBLIC_API_DEFAULT_TIMEOUT_MS 驱动，默认 60s）
const API_DEFAULT_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_API_DEFAULT_TIMEOUT_MS) || 60000;

// SSE 后端 URL 策略（2026-04-15 UI-Q2 修复）
// 问题：原策略直连 http://localhost:8888，但从局域网 IP(如 192.168.43.125:3000)访问前端时
//   a) `window.location.hostname === 'localhost'` 为 false → SSE_BASE='' 走相对 URL
//   b) 若真直连 localhost 也不可达（浏览器的 localhost 是客户端本机）
//   c) 若直连 http://192.168.x:8888 则后端 CORS allowed_origins 未含该 origin → preflight 失败 → 后端 0 POST
// 新策略：默认始终走同源相对 URL，经 Next dev rewrites 代理到后端(同 origin，无 CORS)；
//   若用户显式设置 NEXT_PUBLIC_SSE_URL 才直连（生产 Nginx 反代场景）。
// 关于 rewrites buffer：Next.js 16 dev rewrites 对 text/event-stream 响应会延迟首 chunk ~1s
// 但最终可流，不会永远卡死；权衡之下"能到达后端"比"理论上最快 SSE"更重要。
// Dev 模式必须直连后端:8888 — Next 16 Turbopack dev rewrites 会完全 buffer
// text/event-stream 响应直到上游 close, 导致前端 reader.read() 收不到任何 chunk。
// 策略: 显式 env > 浏览器自动 (hostname+:8888) > SSR 空 (SSR 不会发 SSE)。
const SSE_BASE = (() => {
  if (process.env.NEXT_PUBLIC_SSE_URL) return process.env.NEXT_PUBLIC_SSE_URL;
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== 'undefined' && window.location) {
    const h = window.location.hostname;
    return `${window.location.protocol}//${h}:8888`;
  }
  return '';
})();

// 兼容历史 API 返回字面 NaN/Infinity 的响应 (非标 JSON)。
// 后端已修复为输出 null, 但旧 conversation 持久化数据可能仍含 NaN, 前端做双保险。
// 注意: 只替换"裸露"的 NaN/Infinity (不在字符串引号内的), 使用简单正则 \bNaN\b 已足够覆盖,
// 误伤字符串内 "NaN" 文字的概率极低 (字符串内会带引号, \b 匹配不到字母边界之外的引号模式)。
// 后端错误响应统一形如 {"error": "...", "stock_code": "..."}，提取 error 字段作为 message；
// 解析失败则回退为状态码描述（HTTP 504 等），避免把原始 JSON 字符串直接显示给用户。
async function extractErrorMessage(res: Response): Promise<string> {
  try {
    const txt = await res.text();
    try {
      const j = JSON.parse(txt);
      if (j && typeof j === 'object' && typeof j.error === 'string') return j.error;
    } catch {}
    return txt || `HTTP ${res.status}`;
  } catch {
    return `HTTP ${res.status}`;
  }
}

function safeJSONParse<T>(text: string): T {
  const sanitized = text
    .replace(/\bNaN\b/g, 'null')
    .replace(/\b-Infinity\b/g, 'null')
    .replace(/\bInfinity\b/g, 'null');
  return JSON.parse(sanitized) as T;
}

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
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), API_DEFAULT_TIMEOUT_MS);
    try {
      const res = await fetch(url, { signal: ctrl.signal });
      if (!res.ok) throw new ApiError(res.status, await extractErrorMessage(res));
      return safeJSONParse<T>(await res.text());
    } finally {
      clearTimeout(tid);
    }
  }

  // 通用POST请求
  async post<T>(path: string, body: Record<string, unknown>): Promise<T> {
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), API_DEFAULT_TIMEOUT_MS);
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      if (!res.ok) throw new ApiError(res.status, await extractErrorMessage(res));
      return safeJSONParse<T>(await res.text());
    } finally {
      clearTimeout(tid);
    }
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
        // SSE 走 SSE_BASE（默认同源，经 Next dev rewrites；显式设置 NEXT_PUBLIC_SSE_URL 则直连）
        const sseUrl = `${SSE_BASE}${path}`;
        if (process.env.NODE_ENV !== 'production') {
          console.log('[SSE] POST', sseUrl, 'attempt', attempt + 1, 'body:', body);
        }
        const res = await fetch(sseUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal,
        });
        if (process.env.NODE_ENV !== 'production') {
          console.log('[SSE] response status', res.status, 'ok:', res.ok, 'hasBody:', !!res.body);
        }

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

        // FIX-E1+E3: SSE idle timeout — 仅监控"连续无 chunk"时长，不限制总时长
        // 后端每 15s 会发心跳 `: heartbeat ...\n\n`，正常应远低于 idleMs
        // 优先读 NEXT_PUBLIC_SSE_HEARTBEAT_TIMEOUT_MS，兜底 NEXT_PUBLIC_STREAM_IDLE_TIMEOUT_MS
        const idleMs = Number(process.env.NEXT_PUBLIC_SSE_HEARTBEAT_TIMEOUT_MS)
          || Number(process.env.NEXT_PUBLIC_STREAM_IDLE_TIMEOUT_MS)
          || 120000;
        let lastChunkAt = Date.now();
        let idleAborted = false;
        const idleTimer = setInterval(() => {
          if (Date.now() - lastChunkAt > idleMs) {
            idleAborted = true;
            try { reader.cancel(); } catch {}
            clearInterval(idleTimer);
          }
        }, Math.min(5000, Math.floor(idleMs / 4)));

        // 内部派发：处理一个完整SSE事件块（多行）— 按事件而非按行处理，
        // 避免TCP chunk在event:/data:中间切断时丢失event前缀
        const isDev = process.env.NODE_ENV !== 'production';
        const dispatchBlock = (block: string) => {
          if (isDev) console.log('[SSE-block]', block.slice(0, 200));
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
          if (isDev) console.log('[SSE-dispatch]', effectiveType);
          try {
            switch (effectiveType) {
              case 'token': handlers.onToken?.(payload as Parameters<NonNullable<typeof handlers.onToken>>[0]); break;
              case 'tool_call_start': handlers.onToolCallStart?.(payload as Parameters<NonNullable<typeof handlers.onToolCallStart>>[0]); break;
              case 'tool_call_result': handlers.onToolCallResult?.(payload as Parameters<NonNullable<typeof handlers.onToolCallResult>>[0]); break;
              case 'artifact': handlers.onArtifact?.(payload as Parameters<NonNullable<typeof handlers.onArtifact>>[0]); break;
              case 'agent_progress': handlers.onAgentProgress?.(payload as Parameters<NonNullable<typeof handlers.onAgentProgress>>[0]); break;
              case 'reasoning': handlers.onReasoning?.(payload as Parameters<NonNullable<typeof handlers.onReasoning>>[0]); break;
              // [UI-Q4] llm_request: 发LLM前的完整prompt/messages → 作为reasoning事件呈现
              case 'llm_request': handlers.onReasoning?.(payload as Parameters<NonNullable<typeof handlers.onReasoning>>[0]); break;
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
          lastChunkAt = Date.now();
          buffer += decoder.decode(value, { stream: true });
          if (buffer.length > 1_048_576) {
            console.warn('[SSE] buffer exceeded 1MB, flushing');
            buffer = '';
          }
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
          clearInterval(idleTimer);
          try { reader.cancel(); } catch {}
          try { handlers.onClose?.(); } catch (e) { console.warn('[SSE] onClose error', e); }
          if (idleAborted) {
            handlers.onError?.({ code: 'IDLE_TIMEOUT', message: `连续 ${Math.round(idleMs/1000)}s 无数据，连接已断开` });
          }
          if (!doneEventSeen && !idleAborted) {
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
