/**
 * Input: normalizeProvenanceItem / normalizeProvenanceList 契约
 * Output: vitest 断言（拒绝裸 string / 剥离假价 / 去重）
 * Pos: frontend/src/lib/types/__tests__/provenance.test.ts — G1 provenance 消费方单测
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。
 */
import { describe, expect, it } from 'vitest';
import {
  normalizeProvenanceItem,
  normalizeProvenanceList,
} from '@/lib/types';

describe('normalizeProvenanceItem', () => {
  it('rejects bare string / null / array', () => {
    expect(normalizeProvenanceItem('akshare')).toBeNull();
    expect(normalizeProvenanceItem(null)).toBeNull();
    expect(normalizeProvenanceItem([])).toBeNull();
  });

  it('requires non-empty source and strips fake price fields', () => {
    const cleaned = normalizeProvenanceItem({
      source: 'akshare',
      tool: 'get_stock_data',
      price: 1174.06,
      pe: 20.1,
      ts: '2026-07-24T06:00:00+08:00',
    });
    expect(cleaned).toEqual({
      source: 'akshare',
      tool: 'get_stock_data',
      ts: '2026-07-24T06:00:00+08:00',
    });
    expect(cleaned && 'price' in cleaned).toBe(false);
    expect(cleaned && 'pe' in cleaned).toBe(false);
  });

  it('drops entries without source', () => {
    expect(normalizeProvenanceItem({ tool: 'x' })).toBeNull();
    expect(normalizeProvenanceItem({ source: '  ' })).toBeNull();
  });
});

describe('normalizeProvenanceList', () => {
  it('filters dirty items and dedupes by source|tool|digest', () => {
    const out = normalizeProvenanceList([
      'bare',
      { source: 'akshare', tool: 'get_stock_data', price: 1 },
      { source: 'akshare', tool: 'get_stock_data' },
      { source: 'wind', tool: 'fundamentals', pe: 9 },
      null,
    ]);
    expect(out).toHaveLength(2);
    expect(out[0]).toEqual({ source: 'akshare', tool: 'get_stock_data' });
    expect(out[1]).toEqual({ source: 'wind', tool: 'fundamentals' });
  });

  it('caps at 32 entries', () => {
    const raw = Array.from({ length: 80 }, (_, i) => ({
      source: `src-${i}`,
      tool: 't',
    }));
    expect(normalizeProvenanceList(raw)).toHaveLength(32);
  });
});
