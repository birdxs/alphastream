// Input  : usePortfolioStore 的 actions（addHolding/updateHolding/removeHolding）
// Output : 测试结果（state shape、去重添加、更新、删除）
// Pos    : tests/frontend/stores/portfolio-store.test.ts — FE-01 store 单测
//
// 一旦此文件修改，请同步更新 tests/audit/reports/FE-01_stores.md。
//
// 备注：任务表中将该 store 操作命名为 addItem/updateItem/removeItem,
//       实际源码 API 为 addHolding/updateHolding/removeHolding（与 Holding 类型对齐）。
//       本测试按真实 API 编写，避免修改源码。

import { describe, it, expect, beforeEach } from 'vitest';
import { usePortfolioStore } from '@/lib/stores/portfolio-store';
import type { Holding } from '@/lib/stores/portfolio-store';

function resetPortfolio() {
  usePortfolioStore.setState({ holdings: [] });
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('portfolio-storage');
  }
}

const h = (code: string, overrides: Partial<Holding> = {}): Holding => ({
  code,
  name: overrides.name ?? code,
  shares: overrides.shares ?? 100,
  costPrice: overrides.costPrice ?? 10,
  currentPrice: overrides.currentPrice,
  mode: overrides.mode,
  addedAt: overrides.addedAt ?? Date.now(),
});

describe('usePortfolioStore', () => {
  beforeEach(() => {
    resetPortfolio();
  });

  it('初始 state shape 正确（holdings=[]）', () => {
    expect(usePortfolioStore.getState().holdings).toEqual([]);
  });

  it('addHolding 追加新持仓', () => {
    usePortfolioStore.getState().addHolding(h('AAPL', { shares: 50, costPrice: 150 }));
    const holdings = usePortfolioStore.getState().holdings;
    expect(holdings).toHaveLength(1);
    expect(holdings[0]).toMatchObject({ code: 'AAPL', shares: 50, costPrice: 150 });
  });

  it('边界：重复添加相同 code 不创建副本', () => {
    const store = usePortfolioStore.getState();
    store.addHolding(h('AAPL', { shares: 100 }));
    store.addHolding(h('AAPL', { shares: 999 })); // 重复
    const holdings = usePortfolioStore.getState().holdings;
    expect(holdings).toHaveLength(1);
    expect(holdings[0].shares).toBe(100); // 保持首次值
  });

  it('updateHolding 仅更新匹配项的指定字段', () => {
    const store = usePortfolioStore.getState();
    store.addHolding(h('AAPL', { shares: 100, costPrice: 150 }));
    store.addHolding(h('GOOG', { shares: 10, costPrice: 2800 }));

    store.updateHolding('AAPL', { currentPrice: 180, shares: 120 });
    const holdings = usePortfolioStore.getState().holdings;
    const aapl = holdings.find(x => x.code === 'AAPL');
    const goog = holdings.find(x => x.code === 'GOOG');
    expect(aapl?.currentPrice).toBe(180);
    expect(aapl?.shares).toBe(120);
    expect(aapl?.costPrice).toBe(150); // 未传入 → 保留
    expect(goog?.shares).toBe(10); // 不受影响
  });

  it('updateHolding 对不存在 code 不抛错且不影响其他项', () => {
    const store = usePortfolioStore.getState();
    store.addHolding(h('AAPL'));
    store.updateHolding('NOPE', { shares: 999 });
    const holdings = usePortfolioStore.getState().holdings;
    expect(holdings).toHaveLength(1);
    expect(holdings[0].code).toBe('AAPL');
  });

  it('removeHolding 删除匹配项', () => {
    const store = usePortfolioStore.getState();
    store.addHolding(h('AAPL'));
    store.addHolding(h('GOOG'));
    store.addHolding(h('MSFT'));
    store.removeHolding('GOOG');
    const codes = usePortfolioStore.getState().holdings.map(x => x.code);
    expect(codes).toEqual(['AAPL', 'MSFT']);
  });

  it('setHoldingMode 可标记观察仓，默认 live', () => {
    const store = usePortfolioStore.getState();
    store.addHolding(h('600519', { name: '贵州茅台' }));
    expect(usePortfolioStore.getState().holdings[0].mode).toBe('live');
    store.setHoldingMode('600519', 'watch');
    expect(usePortfolioStore.getState().holdings[0].mode).toBe('watch');
    store.setHoldingMode('600519', 'live');
    expect(usePortfolioStore.getState().holdings[0].mode).toBe('live');
  });

  it('addHolding 可显式写入 watch mode', () => {
    usePortfolioStore.getState().addHolding(h('000001', { name: '平安银行', mode: 'watch' }));
    expect(usePortfolioStore.getState().holdings[0].mode).toBe('watch');
  });
});
