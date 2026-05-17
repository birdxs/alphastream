// Input: useStockPrices hook
// Output: vitest 用例，覆盖 组合估值/并发请求/错误兜底
// Pos: tests/frontend/hooks/use-stock-prices.test.ts — FE-02 [NEW-FILE:#20260517-01]

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

describe("useStockPrices", () => {
  it("空数组直接返回空 map，不发请求", () => {
    const { result } = renderHook(() => useStockPrices([]));
    expect(result.current).toEqual({});
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("快乐路径：单股取末行 close 和涨跌幅", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [
        { open: 100, close: 110 },
        { open: 110, close: 121 },
      ],
    });

    const { result } = renderHook(() => useStockPrices(["600519"]));
    await waitFor(() => {
      expect(result.current["600519"]).toBeDefined();
    });
    expect(result.current["600519"].price).toBe(121);
    // (121 - 110) / 110 * 100 = 10
    expect(result.current["600519"].change_pct).toBeCloseTo(10, 5);
  });

  it("并发请求：两只票同时下发", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockImplementation((_p: string, params?: Record<string, string>) => {
      const code = params?.stock_code;
      const map: Record<string, { close: number; open: number }> = {
        "000001": { open: 10, close: 11 },
        "600036": { open: 40, close: 42 },
      };
      const row = map[code as string];
      return Promise.resolve({ data: [{ open: row.open - 1, close: row.open }, row] });
    });

    const { result } = renderHook(() => useStockPrices(["000001", "600036"]));
    await waitFor(() => {
      expect(result.current["000001"]).toBeDefined();
      expect(result.current["600036"]).toBeDefined();
    });
    expect(result.current["000001"].price).toBe(11);
    expect(result.current["600036"].price).toBe(42);
  });

  it("空 data：不写入映射", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] });
    const { result } = renderHook(() => useStockPrices(["AAA"]));
    await new Promise((r) => setTimeout(r, 30));
    expect(result.current["AAA"]).toBeUndefined();
  });

  it("apiClient.get reject：吞错不抛", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("net"));
    const { result } = renderHook(() => useStockPrices(["BBB"]));
    await new Promise((r) => setTimeout(r, 30));
    expect(result.current["BBB"]).toBeUndefined();
  });
});
