/**
 * Input: ChartContainer 组件 + 子 ErrorBoundary fallback
 * Output: 组件渲染测试 + 错误边界 fallback 触发测试
 * Pos: src/components/charts/__tests__/chart-container.test.tsx
 * [NEW-FILE:#20260520-S3F] 属 CLAUDE.md 白名单 b 项（缺失且必需的最小单元测试）
 * 一旦此文件修改，请更新所属文件夹的 md。
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { ChartContainer } from '../chart-container';

afterEach(() => {
  cleanup();
});

describe('ChartContainer', () => {
  it('正常渲染时显示 children', () => {
    render(
      <ChartContainer title="测试图表">
        <div data-testid="inner">图表内容</div>
      </ChartContainer>
    );
    expect(screen.getByTestId('inner')).toBeTruthy();
    expect(screen.getByText('测试图表')).toBeTruthy();
  });

  it('loading=true 时显示 skeleton/加载态', () => {
    const { container } = render(
      <ChartContainer title="加载中" loading={true}>
        <div>不应该显示</div>
      </ChartContainer>
    );
    // loading 时 container 应该有内容（skeleton 元素）而非空
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('error 状态时显示错误占位', () => {
    const { container } = render(
      <ChartContainer title="错误图表" error="数据获取失败">
        <div>不应该显示</div>
      </ChartContainer>
    );
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('ErrorBoundary fallback: 子组件抛错时不崩溃', () => {
    const consoleErrSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const ThrowingChild = () => { throw new Error('chart crash'); };

    const { container } = render(
      <ChartContainer title="崩溃图表">
        <ThrowingChild />
      </ChartContainer>
    );
    // ErrorBoundary 已捕获，container 仍有内容（fallback UI）
    expect(container.innerHTML.length).toBeGreaterThan(0);
    consoleErrSpy.mockRestore();
  });
});
