/**
 * Input: lib/utils/format.ts 中的各格式化函数
 * Output: 单元测试覆盖 formatNumber/formatPrice/formatPercent/formatLargeNumber
 * Pos: src/lib/utils/__tests__/format.test.ts - format 工具单元测试
 * [NEW-FILE:#20260520-S3G] 属 CLAUDE.md 白名单 b 项（缺失且必需的最小单元测试）
 * 一旦此文件修改，请更新所属文件夹的 md。
 */

import { describe, it, expect } from 'vitest';
import {
  formatNumber,
  formatPrice,
  formatPercent,
  formatLargeNumber,
  getPriceColorClass,
} from '../format';

describe('formatNumber', () => {
  it('正常数字 → 千位分隔 + 2位小数', () => {
    const result = formatNumber(1234567.891);
    expect(result).not.toBe('--');
    expect(result).toMatch(/1.{1,3}234/); // 含千位分隔
  });

  it('null → --', () => {
    expect(formatNumber(null)).toBe('--');
  });

  it('undefined → --', () => {
    expect(formatNumber(undefined)).toBe('--');
  });

  it('NaN → --', () => {
    expect(formatNumber(NaN)).toBe('--');
  });

  it('0 → 含 0 的格式化字符串', () => {
    const result = formatNumber(0);
    expect(result).toContain('0');
  });

  it('指定 decimals=4 → 4位小数', () => {
    const result = formatNumber(1.23456, 4);
    // 结果应包含4位小数
    expect(result).toMatch(/\.\d{4}/);
  });
});

describe('formatPrice', () => {
  it('数字输入 → 2位小数格式', () => {
    const result = formatPrice(10.5);
    expect(result).toMatch(/10[,.]?50?/);
  });

  it('字符串数字 → 正常格式化', () => {
    const result = formatPrice('100.1');
    expect(result).not.toBe('--');
    expect(result).toContain('100');
  });

  it('undefined → --', () => {
    expect(formatPrice(undefined)).toBe('--');
  });

  it('null → --', () => {
    // @ts-expect-error 测试边界
    expect(formatPrice(null)).toBe('--');
  });

  it('非数字字符串 → --', () => {
    expect(formatPrice('abc')).toBe('--');
  });
});

describe('formatPercent', () => {
  it('正数 → 含 + 前缀和 % 后缀', () => {
    const result = formatPercent(1.23);
    expect(result).toContain('%');
    expect(result).toContain('+');
  });

  it('负数 → 含 - 前缀和 % 后缀', () => {
    const result = formatPercent(-0.5);
    expect(result).toContain('%');
    expect(result).toContain('-');
  });

  it('0 → 含 % 后缀', () => {
    const result = formatPercent(0);
    expect(result).toContain('%');
  });

  it('undefined → --', () => {
    expect(formatPercent(undefined)).toBe('--');
  });
});

describe('formatLargeNumber', () => {
  it('亿级别数字 → 含"亿"', () => {
    const result = formatLargeNumber(1_200_000_000);
    expect(result).toContain('亿');
  });

  it('万级别数字 → 含"万"', () => {
    const result = formatLargeNumber(12_000);
    expect(result).toContain('万');
  });

  it('undefined → --', () => {
    expect(formatLargeNumber(undefined)).toBe('--');
  });
});

describe('getPriceColorClass', () => {
  it('正数 → stock-up', () => {
    expect(getPriceColorClass(1.5)).toBe('stock-up');
  });

  it('负数 → stock-down', () => {
    expect(getPriceColorClass(-0.5)).toBe('stock-down');
  });

  it('0 → muted class', () => {
    expect(getPriceColorClass(0)).toContain('muted');
  });

  it('undefined → muted class', () => {
    expect(getPriceColorClass(undefined)).toContain('muted');
  });
});
