// Input: 用户自选股操作（添加/删除/查询）
// Output: 持久化的自选股列表状态
// Pos: lib/stores/watchlist-store.ts - 自选股Zustand状态管理
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface WatchItem {
  code: string;
  name: string;
  addedAt: string;
}

interface WatchlistState {
  items: WatchItem[];
  addItem: (code: string, name?: string) => void;
  setName: (code: string, name: string) => void;
  removeItem: (code: string) => void;
  hasItem: (code: string) => boolean;
}

export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set, get) => ({
      items: [],
      addItem: (code, name) => set((s) => ({
        // 无真名（缺省或等于代码）时存空串，禁止把 code 当 name 持久化（铁律 #1）
        items: s.items.some(i => i.code === code) ? s.items : [
          ...s.items,
          { code, name: name && name !== code ? name : '', addedAt: new Date().toISOString() }
        ]
      })),
      setName: (code, name) => set((s) => ({
        // 拿到真名后回填；忽略空名或等于代码的无效名
        items: (name && name !== code)
          ? s.items.map(i => i.code === code ? { ...i, name } : i)
          : s.items
      })),
      removeItem: (code) => set((s) => ({
        items: s.items.filter(i => i.code !== code)
      })),
      hasItem: (code) => get().items.some(i => i.code === code),
    }),
    {
      name: 'watchlist-storage',
      version: 1,
      // 兼容清洗：旧版本把 code 误存为 name，迁移时清空 name===code 的脏数据
      migrate: (persisted: unknown) => {
        const state = persisted as { items?: WatchItem[] } | undefined;
        if (state?.items) {
          state.items = state.items.map(i => i.name === i.code ? { ...i, name: '' } : i);
        }
        return state as WatchlistState;
      },
    }
  )
);
