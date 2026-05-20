/**
 * Input: GlobalError 组件（error 对象 + reset 回调）
 * Output: 渲染测试 + reset 按钮点击测试
 * Pos: src/app/__tests__/global-error.test.tsx
 * [NEW-FILE:#20260520-S3F] 属 CLAUDE.md 白名单 b 项（缺失且必需的最小单元测试）
 * 一旦此文件修改，请更新所属文件夹的 md。
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import GlobalError from '../global-error';

afterEach(() => {
  cleanup();
});

describe('GlobalError', () => {
  it('渲染时显示"应用发生严重错误"标题', () => {
    const error = new Error('test error') as Error & { digest?: string };
    const reset = vi.fn();
    render(<GlobalError error={error} reset={reset} />);
    expect(screen.getByText('应用发生严重错误')).toBeTruthy();
  });

  it('有 digest 时显示 digest 信息', () => {
    const error = Object.assign(new Error('test'), { digest: 'abc123' }) as Error & { digest?: string };
    const reset = vi.fn();
    render(<GlobalError error={error} reset={reset} />);
    expect(screen.getByText(/abc123/)).toBeTruthy();
  });

  it('无 digest 时显示默认提示文案', () => {
    const error = new Error('no digest') as Error & { digest?: string };
    const reset = vi.fn();
    render(<GlobalError error={error} reset={reset} />);
    expect(screen.getByText(/刷新页面/)).toBeTruthy();
  });

  it('点击"重试"按钮 → 调用 reset 回调', () => {
    const error = new Error('test') as Error & { digest?: string };
    const reset = vi.fn();
    render(<GlobalError error={error} reset={reset} />);
    const btn = screen.getByRole('button', { name: '重试' });
    fireEvent.click(btn);
    expect(reset).toHaveBeenCalledOnce();
  });

  it('reset 回调不同实例互不干扰', () => {
    const error = new Error('test') as Error & { digest?: string };
    const reset1 = vi.fn();
    const reset2 = vi.fn();
    const { unmount } = render(<GlobalError error={error} reset={reset1} />);
    unmount();
    cleanup();
    render(<GlobalError error={error} reset={reset2} />);
    const btn = screen.getByRole('button', { name: '重试' });
    fireEvent.click(btn);
    expect(reset2).toHaveBeenCalledOnce();
    expect(reset1).not.toHaveBeenCalled();
  });
});
