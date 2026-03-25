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
  removeItem: (code: string) => void;
  hasItem: (code: string) => boolean;
}

export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set, get) => ({
      items: [],
      addItem: (code, name) => set((s) => ({
        items: s.items.some(i => i.code === code) ? s.items : [
          ...s.items,
          { code, name: name || code, addedAt: new Date().toISOString() }
        ]
      })),
      removeItem: (code) => set((s) => ({
        items: s.items.filter(i => i.code !== code)
      })),
      hasItem: (code) => get().items.some(i => i.code === code),
    }),
    { name: 'watchlist-storage' }
  )
);
