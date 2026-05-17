// Input: AgentProgressPanel 组件 — 桥接 useAgentStore
// Output: vitest 用例 — store 状态变化驱动渲染
// Pos: tests/frontend/components/ — FE-03 关键组件测试

import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup, act } from '@testing-library/react';
import React from 'react';

import { AgentProgressPanel } from '@/components/agent/agent-progress-panel';
import { useAgentStore } from '@/lib/stores/agent-store';

describe('AgentProgressPanel 组件', () => {
  afterEach(() => {
    cleanup();
    act(() => {
      useAgentStore.getState().reset();
    });
  });

  it('空状态 → 渲染 null（不抛错）', () => {
    const { container } = render(<AgentProgressPanel />);
    // 空 store 时组件返回 null
    expect(container.firstChild).toBeNull();
  });

  it('isAnalyzing=true → 渲染主标题"Multi-Agent 实时数据流"与百分比', () => {
    act(() => {
      useAgentStore.setState({
        isAnalyzing: true,
        overallProgress: 50,
      });
    });
    render(<AgentProgressPanel />);
    expect(screen.getByText(/Multi-Agent 实时数据流/)).toBeTruthy();
    expect(screen.getByText('50%')).toBeTruthy();
  });

  it('agentProgresses 含完成项 → 显示 "1/N Agent 完成" 计数', () => {
    act(() => {
      useAgentStore.setState({
        isAnalyzing: true,
        overallProgress: 80,
        agentProgresses: [
          {
            type: 'agent_progress',
            agent_name: '基本面分析师',
            status: 'completed',
            progress: 100,
            message: '完成',
          },
        ],
      });
    });
    render(<AgentProgressPanel />);
    expect(screen.getByText(/1\/1 Agent 完成/)).toBeTruthy();
  });

  it('events 流非空 → 显示事件计数', () => {
    act(() => {
      useAgentStore.setState({
        isAnalyzing: true,
        events: [
          { id: 'e1', ts: Date.now(), type: 'agent_started', title: '启动' },
          { id: 'e2', ts: Date.now(), type: 'tool_call_start', title: '调用工具' },
        ],
      });
    });
    render(<AgentProgressPanel />);
    expect(screen.getByText(/2 事件 · 实时/)).toBeTruthy();
  });
});
