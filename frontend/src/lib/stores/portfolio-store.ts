// Input: 用户持仓操作（添加/删除/更新价格/观察标记）
// Output: 持久化到 localStorage 的持仓列表（含 mode: live|watch）
// Pos: Zustand store — 投资组合状态；agent 工具只读，不写仓
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/** live=实盘持仓；watch=观察组合（仅 UI 标记，agent 不写仓） */
export type HoldingMode = 'live' | 'watch';

export interface Holding {
  code: string;
  name: string;
  shares: number;
  costPrice: number;
  currentPrice?: number;
  addedAt: number;
  /** 可选：默认 live；watch 仅作观察标签 */
  mode?: HoldingMode;
}

interface PortfolioState {
  holdings: Holding[];
  addHolding: (item: Omit<Holding, 'addedAt'>) => void;
  updateHolding: (code: string, patch: Partial<Omit<Holding, 'code' | 'addedAt'>>) => void;
  removeHolding: (code: string) => void;
  updatePrice: (code: string, price: number) => void;
  /** 切换 live/watch 观察标记（仅 UI，agent 不得自动写仓） */
  setHoldingMode: (code: string, mode: HoldingMode) => void;
  getTotalValue: () => number;
  getTotalCost: () => number;
  getTotalPnl: () => number;
}

export const usePortfolioStore = create<PortfolioState>()(
  persist(
    (set, get) => ({
      holdings: [],

      addHolding: (item) =>
        set((state) => {
          // 重复 code 不创建副本，保持首次值（与既有单测契约一致）
          if (state.holdings.some((h) => h.code === item.code)) return state;
          return {
            holdings: [
              ...state.holdings,
              { ...item, mode: item.mode ?? 'live', addedAt: Date.now() },
            ],
          };
        }),

      updateHolding: (code, patch) =>
        set((state) => ({
          holdings: state.holdings.map((h) =>
            h.code === code ? { ...h, ...patch } : h
          ),
        })),

      removeHolding: (code) =>
        set((state) => ({
          holdings: state.holdings.filter((h) => h.code !== code),
        })),

      updatePrice: (code, price) =>
        set((state) => ({
          holdings: state.holdings.map((h) =>
            h.code === code ? { ...h, currentPrice: price } : h
          ),
        })),

      setHoldingMode: (code, mode) =>
        set((state) => ({
          holdings: state.holdings.map((h) =>
            h.code === code ? { ...h, mode } : h
          ),
        })),

      getTotalValue: () => {
        const { holdings } = get();
        return holdings.reduce(
          (sum, h) => sum + (h.currentPrice ?? h.costPrice) * h.shares,
          0
        );
      },

      getTotalCost: () => {
        const { holdings } = get();
        return holdings.reduce((sum, h) => sum + h.costPrice * h.shares, 0);
      },

      getTotalPnl: () => {
        const state = get();
        return state.getTotalValue() - state.getTotalCost();
      },
    }),
    {
      name: 'stockanal-portfolio',
      version: 2,
      migrate: (persisted: unknown) => {
        const state = persisted as { holdings?: Holding[] } | null;
        if (!state || !Array.isArray(state.holdings)) return state as PortfolioState;
        return {
          ...state,
          holdings: state.holdings.map((h) => ({
            ...h,
            name: h.name && h.name !== h.code ? h.name : '',
            mode: h.mode === 'watch' ? 'watch' : 'live',
          })),
        };
      },
    }
  )
);
