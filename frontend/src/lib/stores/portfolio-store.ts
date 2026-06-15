// Input: 用户持仓操作（添加/删除/更新）
// Output: 持久化的投资组合状态
// Pos: lib/stores/portfolio-store.ts - 投资组合Zustand状态管理
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Holding {
  code: string;
  name: string;
  shares: number;
  costPrice: number;
  currentPrice?: number;
}

interface PortfolioState {
  holdings: Holding[];
  addHolding: (h: Holding) => void;
  removeHolding: (code: string) => void;
  updateHolding: (code: string, updates: Partial<Holding>) => void;
}

export const usePortfolioStore = create<PortfolioState>()(
  persist(
    (set) => ({
      holdings: [],
      addHolding: (h) => set((s) => ({
        holdings: s.holdings.some(x => x.code === h.code) ? s.holdings : [...s.holdings, h]
      })),
      removeHolding: (code) => set((s) => ({
        holdings: s.holdings.filter(h => h.code !== code)
      })),
      updateHolding: (code, updates) => set((s) => ({
        holdings: s.holdings.map(h => h.code === code ? { ...h, ...updates } : h)
      })),
    }),
    { name: 'portfolio-storage',
      version: 1,
      // 兼容清洗：旧版本把 code 误存为 name，迁移时清空 name===code 的脏数据
      migrate: (persisted: unknown) => {
        const state = persisted as { holdings?: Holding[] } | undefined;
        if (state?.holdings) {
          state.holdings = state.holdings.map(h => h.name === h.code ? { ...h, name: '' } : h);
        }
        return state as PortfolioState;
      },
    }
  )
);
