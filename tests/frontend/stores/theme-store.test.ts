// Input  : useThemeStore 的 actions（toggleTheme/toggleColorScheme）
// Output : 测试结果（state shape、切换、localStorage 持久化）
// Pos    : tests/frontend/stores/theme-store.test.ts — FE-01 store 单测
//
// 一旦此文件修改，请同步更新 tests/audit/reports/FE-01_stores.md。

import { describe, it, expect, beforeEach } from 'vitest';
import { useThemeStore } from '@/lib/stores/theme-store';

function resetTheme() {
  // 直接 reset 到默认值（不能用 useThemeStore.persist.clearStorage 因为有副作用，先回写）
  useThemeStore.setState({ theme: 'dark', stockColorScheme: 'cn' });
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('theme-storage');
  }
}

describe('useThemeStore', () => {
  beforeEach(() => {
    resetTheme();
  });

  it('初始 state shape 正确（默认 dark + cn）', () => {
    const s = useThemeStore.getState();
    expect(s.theme).toBe('dark');
    expect(s.stockColorScheme).toBe('cn');
  });

  it('toggleTheme 在 dark/light 间切换', () => {
    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().theme).toBe('light');
    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().theme).toBe('dark');
  });

  it('toggleColorScheme 在 cn/us 间切换', () => {
    useThemeStore.getState().toggleColorScheme();
    expect(useThemeStore.getState().stockColorScheme).toBe('us');
    useThemeStore.getState().toggleColorScheme();
    expect(useThemeStore.getState().stockColorScheme).toBe('cn');
  });

  it('localStorage 持久化：toggle 后 localStorage 中 theme-storage 包含新值', () => {
    expect(typeof localStorage).not.toBe('undefined');
    useThemeStore.getState().toggleTheme(); // dark -> light
    useThemeStore.getState().toggleColorScheme(); // cn -> us

    const raw = localStorage.getItem('theme-storage');
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw as string);
    // zustand persist 默认结构：{ state: {...}, version: 0 }
    expect(parsed.state.theme).toBe('light');
    expect(parsed.state.stockColorScheme).toBe('us');
  });

  it('边界：连续 toggle 偶数次应回到原值', () => {
    const original = useThemeStore.getState().theme;
    for (let i = 0; i < 4; i += 1) {
      useThemeStore.getState().toggleTheme();
    }
    expect(useThemeStore.getState().theme).toBe(original);
  });
});
