// Input  : useWatchlistStore 的 actions（addItem/removeItem/hasItem）
// Output : 测试结果（state shape、去重添加、删除、查询）
// Pos    : tests/frontend/stores/watchlist-store.test.ts — FE-01 store 单测
//
// 一旦此文件修改，请同步更新 tests/audit/reports/FE-01_stores.md。

import { describe, it, expect, beforeEach } from 'vitest';
import { useWatchlistStore } from '@/lib/stores/watchlist-store';

function resetWatchlist() {
  useWatchlistStore.setState({ items: [] });
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('watchlist-storage');
  }
}

describe('useWatchlistStore', () => {
  beforeEach(() => {
    resetWatchlist();
  });

  it('初始 state shape 正确（items=[]）', () => {
    expect(useWatchlistStore.getState().items).toEqual([]);
  });

  it('addItem 添加新条目（含 code/name/addedAt）', () => {
    useWatchlistStore.getState().addItem('AAPL', '苹果');
    const items = useWatchlistStore.getState().items;
    expect(items).toHaveLength(1);
    expect(items[0].code).toBe('AAPL');
    expect(items[0].name).toBe('苹果');
    expect(typeof items[0].addedAt).toBe('string');
    expect(items[0].addedAt.length).toBeGreaterThan(0);
  });

  it('addItem 不传 name 时 name 回退为 code', () => {
    useWatchlistStore.getState().addItem('TSLA');
    const items = useWatchlistStore.getState().items;
    expect(items[0].name).toBe('TSLA');
  });

  it('边界：重复添加相同 code 不应创建副本', () => {
    const store = useWatchlistStore.getState();
    store.addItem('AAPL', '苹果');
    store.addItem('AAPL', '苹果2'); // 重复 code
    expect(useWatchlistStore.getState().items).toHaveLength(1);
    expect(useWatchlistStore.getState().items[0].name).toBe('苹果');
  });

  it('removeItem 移除指定 code，其他不受影响', () => {
    const store = useWatchlistStore.getState();
    store.addItem('AAPL');
    store.addItem('GOOG');
    store.addItem('MSFT');
    store.removeItem('GOOG');
    const codes = useWatchlistStore.getState().items.map(i => i.code);
    expect(codes).toEqual(['AAPL', 'MSFT']);
  });

  it('hasItem 查询命中/未命中', () => {
    useWatchlistStore.getState().addItem('AAPL');
    expect(useWatchlistStore.getState().hasItem('AAPL')).toBe(true);
    expect(useWatchlistStore.getState().hasItem('NFLX')).toBe(false);
  });
});
