// Input: useStockNames hook
// Output: vitest 用例，覆盖 单股/批量/缓存/404 回退
// Pos: tests/frontend/hooks/use-stock-names.test.ts — FE-02 [NEW-FILE:#20260517-01]

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

// mock apiClient — 必须在 import hook 之前
vi.mock("@/lib/api/client", () => {
  return {
    apiClient: {
      get: vi.fn(),
      post: vi.fn(),
      streamPost: vi.fn(),
      delete: vi.fn(),
    },
    ApiError: class extends Error {
      status: number;
      constructor(s: number, m: string) { super(m); this.status = s; }
    },
  };
});

import { apiClient } from "@/lib/api/client";
import { useStockNames } from "@/lib/hooks/use-stock-names";

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useStockNames", () => {
  it("空数组直接返回空 map", async () => {
    const { result } = renderHook(() => useStockNames([]));
    expect(result.current).toEqual({});
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("单股：通过 stock_data 兜底获取名称", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockImplementation((path: string) => {
      if (path === "/api/stock_name") return Promise.reject(new Error("404"));
      if (path === "/api/stock_data") {
        return Promise.resolve({ stock_name: "贵州茅台" });
      }
      return Promise.reject(new Error("unknown path"));
    });

    const { result } = renderHook(() => useStockNames(["600519"]));
    await waitFor(() => {
      expect(result.current["600519"]).toBe("贵州茅台");
    });
  });

  it("批量：并发请求两只票", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockImplementation((path: string, params?: Record<string, string>) => {
      if (path === "/api/stock_name") return Promise.reject(new Error("404"));
      if (path === "/api/stock_data") {
        const code = params?.stock_code;
        const map: Record<string, string> = { "000001": "平安银行", "600036": "招商银行" };
        return Promise.resolve({ stock_name: map[code as string] || "" });
      }
      return Promise.reject(new Error("x"));
    });

    const { result } = renderHook(() => useStockNames(["000001", "600036"]));
    await waitFor(() => {
      expect(result.current["000001"]).toBe("平安银行");
      expect(result.current["600036"]).toBe("招商银行");
    });
  });

  it("缓存命中：第二次渲染同代码不再请求", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockImplementation((path: string) => {
      if (path === "/api/stock_name") return Promise.reject(new Error("404"));
      if (path === "/api/stock_data") return Promise.resolve({ stock_name: "中国平安" });
      return Promise.reject(new Error("x"));
    });

    // 第一次：触发请求
    const first = renderHook(() => useStockNames(["601318"]));
    await waitFor(() => expect(first.result.current["601318"]).toBe("中国平安"));
    const callsAfter1st = (apiClient.get as ReturnType<typeof vi.fn>).mock.calls.length;

    // 第二次：复用模块级 nameCache，不应再调 /api/stock_data
    const second = renderHook(() => useStockNames(["601318"]));
    await waitFor(() => expect(second.result.current["601318"]).toBe("中国平安"));
    const callsAfter2nd = (apiClient.get as ReturnType<typeof vi.fn>).mock.calls.length;
    // 允许 0 次额外调用（命中缓存）
    expect(callsAfter2nd).toBe(callsAfter1st);
  });

  it("两端都失败时：不写入 names 映射（保持空对象）", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("net"));
    const { result } = renderHook(() => useStockNames(["999999"]));
    // 给微任务一点时间
    await new Promise((r) => setTimeout(r, 30));
    expect(result.current["999999"]).toBeUndefined();
  });
});
