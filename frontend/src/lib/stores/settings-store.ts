/**
 * Input: 用户设置交互（研究深度、语义记忆开关等）
 * Output: 持久化的用户偏好设置状态
 * Pos: lib/stores/settings-store.ts - 设置状态管理
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SettingsState {
  researchDepth: number;
  enableMemory: boolean;
  setResearchDepth: (d: number) => void;
  setEnableMemory: (e: boolean) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      researchDepth: 3,
      enableMemory: true,
      setResearchDepth: (d) => set({ researchDepth: d }),
      setEnableMemory: (e) => set({ enableMemory: e }),
    }),
    { name: 'settings-storage' }
  )
);
