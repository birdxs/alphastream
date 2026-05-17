// Input: MessageBubble 组件
// Output: vitest 用例 — user/assistant 渲染 + artifacts 透传
// Pos: tests/frontend/components/ — FE-03 关键组件测试

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import React from 'react';

// 简化 ArtifactRenderer，仅返回包含 artifact_type 的可识别 div
vi.mock('@/components/chat/artifact-renderer', () => ({
  ArtifactRenderer: ({ artifact }: { artifact: { artifact_type: string; title: string } }) => (
    <div data-testid="artifact-stub" data-type={artifact.artifact_type}>
      {artifact.title}
    </div>
  ),
}));

// stream-markdown 简化为 plain
vi.mock('@/components/chat/stream-markdown', () => ({
  StreamMarkdown: ({ content }: { content: string }) => <div>{content}</div>,
}));

import { MessageBubble } from '@/components/chat/message-bubble';
import type { ChatMessage } from '@/lib/types';

describe('MessageBubble 组件', () => {
  afterEach(() => cleanup());

  it('role=user 渲染用户消息内容', () => {
    const msg: ChatMessage = {
      message_id: 'm1',
      role: 'user',
      content: '你好世界',
      created_at: '2026-05-17T00:00:00Z',
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText('你好世界')).toBeTruthy();
  });

  it('role=assistant 渲染助手消息内容', () => {
    const msg: ChatMessage = {
      message_id: 'm2',
      role: 'assistant',
      content: '这是助手回复',
      created_at: '2026-05-17T00:00:00Z',
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText('这是助手回复')).toBeTruthy();
  });

  it('含 artifacts → 渲染 Badge 标签（含 title）供右栏导航', () => {
    const msg: ChatMessage = {
      message_id: 'm3',
      role: 'assistant',
      content: '',
      created_at: '2026-05-17T00:00:00Z',
      artifacts: [
        {
          type: 'artifact',
          artifact_type: 'decision_card',
          title: '决策卡片',
          data: { action: 'BUY' },
        },
      ],
    };
    render(<MessageBubble message={msg} />);
    // Badge 包含 artifact.title（与占位提示中均含"决策卡片"字样，故 getAll）
    const matches = screen.getAllByText(/决策卡片/);
    expect(matches.length).toBeGreaterThanOrEqual(1);
    // 当 content 为空但有 artifacts → 占位提示存在
    expect(screen.getByText(/分析已完成/)).toBeTruthy();
  });
});
