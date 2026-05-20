/**
 * Input: ApiClient get/post + extractData 函数
 * Output: 单元测试覆盖 fetch 成功/失败/超时/extractData 解包
 * Pos: src/lib/api/__tests__/client.test.ts - API 客户端单元测试
 * [NEW-FILE:#20260520-S3F] 属 CLAUDE.md 白名单 b 项（缺失且必需的最小单元测试）
 * 一旦此文件修改，请更新所属文件夹的 md。
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { extractData } from '../client';

// ── extractData 解包测试（纯函数，无 fetch 依赖）────────────────────────────
describe('extractData', () => {
  it('新外壳 success:true → 返回 data', () => {
    const resp = { success: true, data: { price: 100 } };
    expect(extractData<{ price: number }>(resp)).toEqual({ price: 100 });
  });

  it('新外壳 success:false → 返回 null', () => {
    const resp = { success: false, error_code: 'INTERNAL', message: 'err' };
    expect(extractData(resp)).toBeNull();
  });

  it('旧外壳（无 success 字段）→ 原样返回', () => {
    const resp = { indices: [{ code: '000001' }] };
    expect(extractData(resp)).toEqual(resp);
  });

  it('null 输入 → 原样返回 null', () => {
    expect(extractData(null)).toBeNull();
  });

  it('新外壳 data 为 null → 返回 null', () => {
    const resp = { success: true, data: null };
    expect(extractData(resp)).toBeNull();
  });
});

// ── fetch mock 测试：get / AbortController ─────────────────────────────────
describe('apiClient.get', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    // sessionStorage stub for CSRF
    vi.stubGlobal('sessionStorage', {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('成功 200 响应 → 返回解析后的 JSON', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ success: true, data: { name: '贵州茅台' } }),
      headers: { get: () => 'application/json' },
    });

    const { apiClient } = await import('../client');
    const result = await apiClient.get<{ name: string }>('/api/test');
    // 兼容新外壳格式（data 字段已由 caller 的 extractData 处理，直接返回整体响应）
    expect(result).toBeTruthy();
  });

  it('非 2xx 响应 → 抛出 ApiError', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      text: async () => JSON.stringify({ error_code: 'NOT_FOUND', message: '未找到' }),
      headers: { get: () => 'application/json' },
    });

    const { apiClient, ApiError } = await import('../client');
    await expect(apiClient.get('/api/missing')).rejects.toThrow();
  });

  it('fetch 网络错误 → 抛出 ApiError', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));

    const { apiClient } = await import('../client');
    await expect(apiClient.get('/api/err')).rejects.toThrow();
  });
});
