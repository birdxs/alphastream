/**
 * Input: useCountUp(target, options) hook
 * Output: 单元测试覆盖 enabled=false 直取值、负数、零值 分支
 * Pos: src/lib/hooks/__tests__/use-count-up.test.ts - useCountUp hook 单元测试
 * [NEW-FILE:#20260520-S3G] 属 CLAUDE.md 白名单 b 项（缺失且必需的最小单元测试）
 * 一旦此文件修改，请更新所属文件夹的 md。
 */

import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useCountUp } from '../use-count-up';

describe('useCountUp', () => {
  it('enabled=false 时直接返回目标值（无动画）', () => {
    const { result } = renderHook(() =>
      useCountUp(1234.56, { enabled: false, decimals: 2 }),
    );
    // 应直接显示目标值，不为 '0.00'
    expect(result.current).not.toBe('0.00');
    expect(result.current).toContain('1');
  });

  it('目标值为 0 时返回含 0 的字符串', () => {
    const { result } = renderHook(() =>
      useCountUp(0, { enabled: false, decimals: 2 }),
    );
    expect(result.current).toContain('0');
  });

  it('负数目标 enabled=false → 含负号', () => {
    const { result } = renderHook(() =>
      useCountUp(-100.5, { enabled: false, decimals: 2 }),
    );
    expect(result.current).toContain('-');
    expect(result.current).toContain('100');
  });

  it('decimals=0 时结果不含小数点', () => {
    const { result } = renderHook(() =>
      useCountUp(42, { enabled: false, decimals: 0 }),
    );
    expect(result.current).not.toContain('.');
  });

  it('enabled=true 时初始值为 0（动画起点）', () => {
    const { result } = renderHook(() =>
      useCountUp(500, { enabled: true, decimals: 2, duration: 5000 }),
    );
    // 动画从 0 开始，第一帧之前 current=0
    expect(result.current).toContain('0');
  });
});
