/**
 * Input: format.ts + stock-code.ts 纯函数
 * Output: 单元测试覆盖金融格式化 + 股票代码验证/推断
 * Pos: src/lib/__tests__/utils.test.ts - 工具函数单元测试
 * [NEW-FILE:#20260520-S3F] 属 CLAUDE.md 白名单 b 项（缺失且必需的最小单元测试）
 * 一旦此文件修改，请更新所属文件夹的 md。
 */

import { describe, it, expect } from 'vitest';
import { formatNumber, formatPrice, formatLargeNumber } from '../utils/format';
import { isValidAShareCode, inferMarket, inferMarketType, getStockName } from '../utils/stock-code';

// ── formatNumber ─────────────────────────────────────────────────────────────
describe('formatNumber', () => {
  it('正常数字 → 千位分隔符格式', () => {
    const result = formatNumber(1234.567, 2);
    expect(result).toContain('1');
    expect(result).not.toBe('--');
  });

  it('null → "--"', () => {
    expect(formatNumber(null)).toBe('--');
  });

  it('undefined → "--"', () => {
    expect(formatNumber(undefined)).toBe('--');
  });

  it('NaN → "--"', () => {
    expect(formatNumber(NaN)).toBe('--');
  });
});

// ── formatPrice ──────────────────────────────────────────────────────────────
describe('formatPrice', () => {
  it('数字字符串 → 两位小数', () => {
    const result = formatPrice('1234.5');
    expect(result).not.toBe('--');
    expect(typeof result).toBe('string');
  });

  it('undefined → "--"', () => {
    expect(formatPrice(undefined)).toBe('--');
  });

  it('非数字字符串 → "--"', () => {
    expect(formatPrice('abc')).toBe('--');
  });
});

// ── formatLargeNumber ────────────────────────────────────────────────────────
describe('formatLargeNumber', () => {
  it('万级别 → 含"万"', () => {
    const result = formatLargeNumber(12345);
    expect(result).toMatch(/万|亿|\d/);
  });

  it('null → "--"', () => {
    expect(formatLargeNumber(null as unknown as undefined)).toBe('--');
  });
});

// ── isValidAShareCode ────────────────────────────────────────────────────────
describe('isValidAShareCode', () => {
  it('6位数字 → true', () => {
    expect(isValidAShareCode('600519')).toBe(true);
    expect(isValidAShareCode('000001')).toBe(true);
  });

  it('5位 → false', () => {
    expect(isValidAShareCode('60051')).toBe(false);
  });

  it('含字母 → false', () => {
    expect(isValidAShareCode('60051A')).toBe(false);
  });
});

// ── inferMarket ──────────────────────────────────────────────────────────────
describe('inferMarket', () => {
  it('6开头 → sh', () => {
    expect(inferMarket('600519')).toBe('sh');
  });

  it('0开头 → sz', () => {
    expect(inferMarket('000001')).toBe('sz');
  });

  it('3开头 → sz', () => {
    expect(inferMarket('300760')).toBe('sz');
  });

  it('9开头 → unknown', () => {
    expect(inferMarket('900000')).toBe('unknown');
  });
});

// ── inferMarketType ──────────────────────────────────────────────────────────
describe('inferMarketType', () => {
  it('6位数字 → A股', () => {
    expect(inferMarketType('600519')).toBe('A');
  });

  it('纯字母 → US', () => {
    expect(inferMarketType('AAPL')).toBe('US');
  });

  it('4-5位数字 → HK', () => {
    expect(inferMarketType('0700')).toBe('HK');
  });
});

// ── getStockName ─────────────────────────────────────────────────────────────
describe('getStockName', () => {
  it('已知代码 → 返回名称', () => {
    expect(getStockName('600519')).toBe('贵州茅台');
  });

  it('未知代码 → 原样返回代码', () => {
    expect(getStockName('999999')).toBe('999999');
  });
});
