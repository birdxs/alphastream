// Input: ConversationSidebar 组件
// Output: vitest 用例 — 加载列表 + 删除刷新（无 reload）
// Pos: tests/frontend/components/ — FE-03 关键组件测试

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';

const apiGet = vi.fn();
const apiDelete = vi.fn();
const apiPost = vi.fn();

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => apiGet(...args),
    delete: (...args: unknown[]) => apiDelete(...args),
    post: (...args: unknown[]) => apiPost(...args),
  },
}));

vi.mock('@/lib/stores/chat-store', () => {
  const state = {
    conversationId: null as string | null,
    setConversationId: vi.fn(),
    setMessages: vi.fn(),
    clearMessages: vi.fn(),
    setStreaming: vi.fn(),
  };
  return {
    useChatStore: (selector?: (s: typeof state) => unknown) =>
      selector ? selector(state) : state,
  };
});

import { ConversationSidebar } from '@/components/chat/conversation-sidebar';

describe('ConversationSidebar 组件', () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiDelete.mockReset();
    apiPost.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('加载会话列表 → 渲染会话项', async () => {
    apiGet.mockResolvedValueOnce({
      conversations: [
        {
          conversation_id: 'c1',
          title: '会话A',
          created_at: '2026-05-17T00:00:00Z',
          updated_at: '2026-05-17T00:00:00Z',
        },
        {
          conversation_id: 'c2',
          title: '会话B',
          created_at: '2026-05-17T00:00:00Z',
          updated_at: '2026-05-17T00:00:00Z',
        },
      ],
    });

    render(<ConversationSidebar />);

    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledWith('/api/conversations');
    });

    await waitFor(() => {
      expect(screen.getByText('会话A')).toBeTruthy();
      expect(screen.getByText('会话B')).toBeTruthy();
    });
  });

  it('删除会话 → 二次点击确认 → 调用 DELETE 并就地刷新列表（无 reload）', async () => {
    apiGet.mockResolvedValue({
      conversations: [
        {
          conversation_id: 'c1',
          title: '待删会话',
          created_at: '2026-05-17T00:00:00Z',
          updated_at: '2026-05-17T00:00:00Z',
        },
      ],
    });
    apiDelete.mockResolvedValue(undefined);

    // 监测 reload 是否被错误调用
    const reloadSpy = vi.fn();
    const originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, reload: reloadSpy },
    });

    render(<ConversationSidebar />);

    await waitFor(() => {
      expect(screen.getByText('待删会话')).toBeTruthy();
    });

    const user = userEvent.setup();
    // 删除按钮 aria-label = "删除对话: <title>"
    const delBtn = screen.getByRole('button', { name: /删除对话: 待删会话/ });
    // 第一次点击：进入 pendingDelete 状态
    await user.click(delBtn);
    // 第二次点击：同一按钮触发 DELETE
    const confirmBtn = await waitFor(() =>
      screen.getByRole('button', { name: /确认删除对话: 待删会话/ }),
    );
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(apiDelete).toHaveBeenCalledWith('/api/conversations/c1');
    });

    // 关键回归点：不应触发整页 reload
    expect(reloadSpy).not.toHaveBeenCalled();
  });
});
