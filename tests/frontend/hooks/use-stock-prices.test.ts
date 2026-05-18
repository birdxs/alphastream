// Input: useStockPrices hook
// Output: vitest 用例 — 覆盖批量接口 /api/stock_quote_batch、字段映射、错误兜底回退、并发
// Pos: tests/frontend/hooks/use-stock-prices.test.ts — FE-02 + FIX-E5 重构

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/client", () => {
  return {
    apiClient: {
      get: vi.fn(),
      post: vi.fn(),
      streamPost: vi.fn(),
      delete: vi.fn(),
    },
    ApiError: class extends Error { status = 0; },
  };
});

import { apiClient } from "@/lib/api/client";
import { useStockPrices } from "@/lib/hooks/use-stock-prices";

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.restoreAllMocks());

describe("useStockPrices (FIX-E5 批量接口)", () => {
  it("空数组直接返回空 map，不发请求", () => {
    const { result } = renderHook(() => useStockPrices([]));
    expect(result.current).toEqual({});
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("快乐路径：批量返回 results 数组，映射 latest_price → price", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      results: [
        { code: "600519", latest_price: 1888.88, change_pct: 2.5, change: 46.2, name: "贵州茅台" },
      ],
      errors: [],
      ts: 1700000000,
    });

    const { result } = renderHook(() => useStockPrices(["600519"]));
    await waitFor(() => {
      expect(result.current["600519"]).toBeDefined();
    });
    expect(result.current["600519"].price).toBe(1888.88);
    expect(result.current["600519"].change_pct).toBeCloseTo(2.5, 5);
    expect(result.current["600519"].name).toBe("贵州茅台");
  });

  it("批量两只股票：一次请求拿全", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      results: [
        { code: "000001", latest_price: 11, change_pct: 10, change: 1 },
        { code: "600036", latest_price: 42, change_pct: 5, change: 2 },
      ],
      errors: [],
    });

    const { result } = renderHook(() => useStockPrices(["000001", "600036"]));
    await waitFor(() => {
      expect(result.current["000001"]).toBeDefined();
      expect(result.current["600036"]).toBeDefined();
    });
    expect(result.current["000001"].price).toBe(11);
    expect(result.current["600036"].price).toBe(42);
    // 单次批量请求，而不是 N 次
    expect((apiClient.get as ReturnType<typeof vi.fn>).mock.calls.length).toBe(1);
    expect((apiClient.get as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe("/api/stock_quote_batch");
  });

  it("results 空数组：返回空 map", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({ results: [], errors: [] });
    const { result } = renderHook(() => useStockPrices(["AAA"]));
    await new Promise((r) => setTimeout(r, 30));
    expect(result.current["AAA"]).toBeUndefined();
  });

  it("批量接口 reject → 回退到老接口 /api/stock_data 逐只调", async () => {
    const get = apiClient.get as ReturnType<typeof vi.fn>;
    get.mockImplementation((path: string) => {
      if (path === "/api/stock_quote_batch") {
        return Promise.reject(new Error("batch failed"));
      }
      // legacy fallback
      return Promise.resolve({
        data: [
          { open: 10, close: 10 },
          { open: 10, close: 11 },
        ],
      });
    });
    const { result } = renderHook(() => useStockPrices(["BBB"]));
    await waitFor(() => {
      expect(result.current["BBB"]).toBeDefined();
    });
    expect(result.current["BBB"].price).toBe(11);
    expect(result.current["BBB"].change_pct).toBeCloseTo(10, 5);
  });

  it("批量与老接口都失败：吞错保持空 map", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("net"));
    const { result } = renderHook(() => useStockPrices(["CCC"]));
    await new Promise((r) => setTimeout(r, 30));
    expect(result.current["CCC"]).toBeUndefined();
  });
});
