// Input  : useSettingsStore 的 actions（setResearchDepth/setEnableMemory）
// Output : 测试结果（state shape、action、localStorage 持久化）
// Pos    : tests/frontend/stores/settings-store.test.ts — FE-01 store 单测
//
// 一旦此文件修改，请同步更新 tests/audit/reports/FE-01_stores.md。

import { describe, it, expect, beforeEach } from 'vitest';
import { useSettingsStore } from '@/lib/stores/settings-store';

function resetSettings() {
  useSettingsStore.setState({ researchDepth: 3, enableMemory: true });
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('settings-storage');
  }
}

describe('useSettingsStore', () => {
  beforeEach(() => {
    resetSettings();
  });

  it('初始 state shape 正确（depth=3 / memory=true）', () => {
    const s = useSettingsStore.getState();
    expect(s.researchDepth).toBe(3);
    expect(s.enableMemory).toBe(true);
  });

  it('setResearchDepth 设置研究深度', () => {
    useSettingsStore.getState().setResearchDepth(5);
    expect(useSettingsStore.getState().researchDepth).toBe(5);
    useSettingsStore.getState().setResearchDepth(1);
    expect(useSettingsStore.getState().researchDepth).toBe(1);
  });

  it('setEnableMemory 切换语义记忆开关', () => {
    useSettingsStore.getState().setEnableMemory(false);
    expect(useSettingsStore.getState().enableMemory).toBe(false);
    useSettingsStore.getState().setEnableMemory(true);
    expect(useSettingsStore.getState().enableMemory).toBe(true);
  });

  it('边界：depth 设置为 0 或负值仍按入参写入（无内置校验）', () => {
    useSettingsStore.getState().setResearchDepth(0);
    expect(useSettingsStore.getState().researchDepth).toBe(0);
    useSettingsStore.getState().setResearchDepth(-1);
    expect(useSettingsStore.getState().researchDepth).toBe(-1);
  });

  it('localStorage 持久化：settings-storage 含最新值', () => {
    useSettingsStore.getState().setResearchDepth(7);
    useSettingsStore.getState().setEnableMemory(false);
    const raw = localStorage.getItem('settings-storage');
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw as string);
    expect(parsed.state.researchDepth).toBe(7);
    expect(parsed.state.enableMemory).toBe(false);
  });
});
