// Input: ToolCallCard 组件 — props 渲染与中文名映射
// Output: vitest 用例 — 已知工具名映射 + 未知名兜底 + 状态标签
// Pos: tests/frontend/components/ — FE-03 关键组件测试

import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import React from 'react';

import { ToolCallCard } from '@/components/agent/tool-call-card';

describe('ToolCallCard 组件', () => {
  afterEach(() => cleanup());

  it('已知工具名 get_stock_data → 渲染中文标签"获取K线数据"', () => {
    render(
      <ToolCallCard
        toolCall={{
          type: 'tool_call_start',
          tool_call_id: 't1',
          tool_name: 'get_stock_data',
          arguments: { code: '600519' },
        }}
      />,
    );
    expect(screen.getByText('获取K线数据')).toBeTruthy();
  });

  it('未知工具名 → 兜底显示原名', () => {
    render(
      <ToolCallCard
        toolCall={{
          type: 'tool_call_start',
          tool_call_id: 't2',
          tool_name: 'my_unknown_tool',
          arguments: {},
        }}
      />,
    );
    expect(screen.getByText('my_unknown_tool')).toBeTruthy();
  });

  it('无 result → 显示"执行中..."状态', () => {
    render(
      <ToolCallCard
        toolCall={{
          type: 'tool_call_start',
          tool_call_id: 't3',
          tool_name: 'search_web',
          arguments: {},
        }}
      />,
    );
    expect(screen.getByText(/执行中/)).toBeTruthy();
  });

  it('含成功 result → 显示"完成"', () => {
    render(
      <ToolCallCard
        toolCall={{
          type: 'tool_call_start',
          tool_call_id: 't4',
          tool_name: 'get_stock_news',
          arguments: {},
          result: {
            type: 'tool_call_result',
            tool_call_id: 't4',
            tool_name: 'get_stock_news',
            result_summary: '获取成功 5 条',
            duration_ms: 1234,
          },
        }}
      />,
    );
    expect(screen.getByText(/完成/)).toBeTruthy();
  });

  it('result_summary 含 error → 显示"失败"', () => {
    render(
      <ToolCallCard
        toolCall={{
          type: 'tool_call_start',
          tool_call_id: 't5',
          tool_name: 'get_stock_data',
          arguments: {},
          result: {
            type: 'tool_call_result',
            tool_call_id: 't5',
            tool_name: 'get_stock_data',
            result_summary: 'error: 网络超时',
            duration_ms: 999,
          },
        }}
      />,
    );
    expect(screen.getByText(/失败/)).toBeTruthy();
  });
});
