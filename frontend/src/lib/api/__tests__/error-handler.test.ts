/**
 * Input: extractData() + ApiError 来自 lib/api/client.ts
 * Output: 单元测试覆盖 success 外壳解包、错误外壳、旧格式兼容分支
 * Pos: src/lib/api/__tests__/error-handler.test.ts - API 错误响应解析测试
 * [NEW-FILE:#20260520-S3G] 属 CLAUDE.md 白名单 b 项（缺失且必需的最小单元测试）
 * 一旦此文件修改，请更新所属文件夹的 md。
 */

import { describe, it, expect } from 'vitest';
import { extractData, ApiError } from '../client';

describe('extractData', () => {
  it('新外壳 success=true → 返回 data', () => {
    const resp = { success: true, data: { price: 100.5 } };
    const result = extractData<{ price: number }>(resp);
    expect(result).toEqual({ price: 100.5 });
  });

  it('新外壳 success=false → 返回 null', () => {
    const resp = { success: false, error_code: 'NOT_FOUND', message: '未找到' };
    const result = extractData(resp);
    expect(result).toBeNull();
  });

  it('旧外壳（无 success 字段）→ 原样返回', () => {
    const resp = { indices: [{ code: '000001' }] };
    const result = extractData(resp);
    expect(result).toEqual({ indices: [{ code: '000001' }] });
  });

  it('新外壳 success=true 但 data=undefined → 返回 null', () => {
    const resp = { success: true, data: undefined };
    const result = extractData(resp);
    expect(result).toBeNull();
  });

  it('数组外壳 → 原样返回（旧格式兼容）', () => {
    const resp = [{ code: 'SH600519' }];
    const result = extractData<typeof resp>(resp);
    expect(Array.isArray(result)).toBe(true);
  });

  it('null 输入 → 原样返回 null', () => {
    const result = extractData(null);
    expect(result).toBeNull();
  });

  it('字符串输入 → 原样返回', () => {
    const result = extractData<string>('raw string');
    expect(result).toBe('raw string');
  });
});

describe('ApiError', () => {
  it('构造函数正确设置 status 和 message', () => {
    const err = new ApiError(404, '未找到资源');
    expect(err.status).toBe(404);
    expect(err.message).toBe('未找到资源');
    expect(err instanceof Error).toBe(true);
  });

  it('401 状态码可识别', () => {
    const err = new ApiError(401, 'Unauthorized');
    expect(err.status).toBe(401);
  });

  it('500 状态码可识别', () => {
    const err = new ApiError(500, 'Internal Server Error');
    expect(err.status).toBe(500);
    expect(err instanceof ApiError).toBe(true);
  });

  it('400 状态码可识别', () => {
    const err = new ApiError(400, 'Bad Request: stock_code required');
    expect(err.status).toBe(400);
    expect(err.message).toContain('stock_code');
  });
});
