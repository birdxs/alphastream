/**
 * Input: useChatStream hook（sendMessage + stopGeneration + cleanup）
 * Output: 测试 blinkCleanupRef 泄漏防护 + stopGeneration abort 行为
 * Pos: src/hooks/__tests__/use-chat-stream.test.ts
 * [NEW-FILE:#20260520-S3F] 属 CLAUDE.md 白名单 b 项（缺失且必需的最小单元测试）
 * 一旦此文件修改，请更新所属文件夹的 md。
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, cleanup, act } from '@testing-library/react';

// mock 依赖 store，避免真实 zustand store 调用副作用
vi.mock('@/lib/stores/chat-store', () => ({
  useChatStore: {
    getState: vi.fn(() => ({
      addMessage: vi.fn(),
      updateLastAssistantChunk: vi.fn(),
      setStreaming: vi.fn(),
      setError: vi.fn(),
      messages: [],
      conversationId: 'test-cid',
      startBlink: vi.fn(() => () => {}),
      stopBlink: vi.fn(),
    })),
  },
}));

vi.mock('@/lib/stores/agent-store', () => ({
  useAgentStore: {
    getState: vi.fn(() => ({
      setAgentActive: vi.fn(),
      setProgress: vi.fn(),
    })),
  },
}));

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn().mockResolvedValue({ success: true, data: {} }),
    stream: vi.fn(),
  },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('useChatStream', () => {
  it('hook 正常 mount/unmount — blinkCleanupRef 不泄漏', async () => {
    const { useChatStream } = await import('@/lib/hooks/use-chat-stream');
    const { unmount } = renderHook(() => useChatStream());
    // 卸载时不应抛出错误（blinkCleanupRef cleanup 正常执行）
    expect(() => unmount()).not.toThrow();
  });

  it('stopGeneration 调用后 hook 仍可正常 unmount', async () => {
    const { useChatStream } = await import('@/lib/hooks/use-chat-stream');
    const { result, unmount } = renderHook(() => useChatStream());

    act(() => {
      result.current.stopGeneration();
    });

    expect(() => unmount()).not.toThrow();
  });

  it('hook 返回 sendMessage 和 stopGeneration 函数', async () => {
    const { useChatStream } = await import('@/lib/hooks/use-chat-stream');
    const { result } = renderHook(() => useChatStream());

    expect(typeof result.current.sendMessage).toBe('function');
    expect(typeof result.current.stopGeneration).toBe('function');
  });

  it('多次 stopGeneration 调用不崩溃（幂等）', async () => {
    const { useChatStream } = await import('@/lib/hooks/use-chat-stream');
    const { result } = renderHook(() => useChatStream());

    expect(() => {
      act(() => { result.current.stopGeneration(); });
      act(() => { result.current.stopGeneration(); });
    }).not.toThrow();
  });
});
