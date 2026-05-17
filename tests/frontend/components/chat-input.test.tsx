// Input: ChatInput 组件交互（输入/快捷键/附件/停止）
// Output: vitest 用例 — 验证 onSend/onStop 回调、Blob URL 创建与清理
// Pos: tests/frontend/components/ — FE-03 关键组件测试

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';

// mock 依赖 stores 与 hooks，避免外部副作用
vi.mock('@/lib/stores/chat-store', () => ({
  useChatStore: (selector?: (s: { isStreaming: boolean }) => unknown) => {
    const state = { isStreaming: false };
    return selector ? selector(state) : state;
  },
}));

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

import { ChatInput } from '@/components/chat/chat-input';

describe('ChatInput 组件', () => {
  beforeEach(() => {
    // mock URL.createObjectURL / revokeObjectURL
    const urlMap = new Map<string, string>();
    let counter = 0;
    globalThis.URL.createObjectURL = vi.fn((blob: Blob) => {
      counter += 1;
      const url = `blob:mock-${counter}`;
      urlMap.set(url, blob.constructor.name);
      return url;
    });
    globalThis.URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('键入文字后点击发送 → onSend 被调用', async () => {
    const onSend = vi.fn();
    const onStop = vi.fn();
    const user = userEvent.setup();

    render(<ChatInput onSend={onSend} onStop={onStop} />);

    const textarea = screen.getByPlaceholderText(/股票代码|分析问题/);
    await user.type(textarea, '600519');

    // 找到发送按钮（图标按钮通过 title 或 form 寻找）
    const buttons = screen.getAllByRole('button');
    // 发送按钮通常是包含 Send 图标的按钮，点击 form 提交
    const sendBtn = buttons.find((b) => b.getAttribute('type') === 'submit') || buttons[buttons.length - 1];
    await user.click(sendBtn);

    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend.mock.calls[0][0]).toContain('600519');
  });

  it('Ctrl+Enter 快捷键触发发送', async () => {
    const onSend = vi.fn();
    const onStop = vi.fn();
    const user = userEvent.setup();

    render(<ChatInput onSend={onSend} onStop={onStop} />);

    const textarea = screen.getByPlaceholderText(/股票代码|分析问题/);
    await user.click(textarea);
    await user.type(textarea, '测试消息');
    await user.keyboard('{Control>}{Enter}{/Control}');

    expect(onSend).toHaveBeenCalled();
  });

  it('附件上传 → 创建 Blob URL', async () => {
    const onSend = vi.fn();
    const onStop = vi.fn();

    const { container } = render(<ChatInput onSend={onSend} onStop={onStop} />);

    // 找到 hidden file input
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeTruthy();

    const file = new File(['x'], 'a.png', { type: 'image/png' });
    Object.defineProperty(fileInput, 'files', { value: [file] });
    fileInput.dispatchEvent(new Event('change', { bubbles: true }));

    expect(globalThis.URL.createObjectURL).toHaveBeenCalled();
  });

  it('组件卸载 → revokeObjectURL 被调用清理 Blob', async () => {
    const onSend = vi.fn();
    const onStop = vi.fn();

    const { container, unmount } = render(<ChatInput onSend={onSend} onStop={onStop} />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['x'], 'a.png', { type: 'image/png' });
    Object.defineProperty(fileInput, 'files', { value: [file] });
    fileInput.dispatchEvent(new Event('change', { bubbles: true }));

    unmount();
    // unmount cleanup 应触发 revokeObjectURL
    expect(globalThis.URL.revokeObjectURL).toHaveBeenCalled();
  });
});
