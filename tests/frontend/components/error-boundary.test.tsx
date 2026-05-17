// Input: ErrorBoundary 组件
// Output: vitest 用例 — 子组件抛错 fallback 渲染且不传染外层
// Pos: tests/frontend/components/ — FE-03 关键组件测试

import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import React from 'react';

import { ErrorBoundary } from '@/components/common/error-boundary';

function Boom(): JSX.Element {
  throw new Error('component exploded');
}

describe('ErrorBoundary 组件', () => {
  let consoleErrSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    consoleErrSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });
  afterEach(() => {
    consoleErrSpy.mockRestore();
    cleanup();
  });

  it('子组件正常 → 渲染 children', () => {
    render(
      <ErrorBoundary>
        <div>子节点内容</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText('子节点内容')).toBeTruthy();
  });

  it('子组件抛错 → 渲染默认 fallback 标题"组件渲染出错"', () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText('组件渲染出错')).toBeTruthy();
  });

  it('自定义 fallbackTitle → 渲染', () => {
    render(
      <ErrorBoundary fallbackTitle="自定义降级">
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText('自定义降级')).toBeTruthy();
  });

  it('子组件抛错 → 不传染外层兄弟节点', () => {
    render(
      <div>
        <span>外层稳定</span>
        <ErrorBoundary>
          <Boom />
        </ErrorBoundary>
      </div>,
    );
    expect(screen.getByText('外层稳定')).toBeTruthy();
    expect(screen.getByText('组件渲染出错')).toBeTruthy();
  });
});
