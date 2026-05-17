// Input: useAltData hook
// Output: vitest 用例，覆盖 happy / error / loading 状态切换
// Pos: tests/frontend/hooks/use-alt-data.test.ts — FE-02 [NEW-FILE:#20260517-01]

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useAltData } from "@/lib/hooks/use-alt-data";

const okPayload = {
  success: true,
  artifact: {
    type: "alt_data",
    title: "另类数据",
    data: { shipping: { foo: 1 }, esg: { score: 80 } },
  },
};

function mockFetchOnce(body: unknown, ok = true, status = 200) {
  return vi.spyOn(global, "fetch").mockResolvedValueOnce({
    ok,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response);
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useAltData", () => {
  it("ticker 为空时不发请求，loading=false", async () => {
    const spy = vi.spyOn(global, "fetch");
    const { result } = renderHook(() => useAltData(""));
    expect(spy).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBeNull();
  });

  it("快乐路径：拉取成功，data 填充，loading 切换", async () => {
    mockFetchOnce(okPayload);
    const { result } = renderHook(() => useAltData("600519"));

    // 初始 loading 为 true
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.data).toEqual(okPayload.artifact);
    expect(result.current.error).toBeNull();
  });

  it("success=false 时记录 error 文案", async () => {
    mockFetchOnce({ success: false, error: "数据源不可用" });
    const { result } = renderHook(() => useAltData("AAPL"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("数据源不可用");
    expect(result.current.data).toBeNull();
  });

  it("HTTP 500 抛错被捕获", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}),
      text: async () => "boom",
    } as unknown as Response);
    const { result } = renderHook(() => useAltData("AAPL"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toMatch(/HTTP\s*500|另类数据/);
  });

  it("reload 重新触发请求", async () => {
    const spy = vi.spyOn(global, "fetch")
      .mockResolvedValueOnce({
        ok: true, status: 200, json: async () => okPayload, text: async () => JSON.stringify(okPayload),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true, status: 200, json: async () => okPayload, text: async () => JSON.stringify(okPayload),
      } as unknown as Response);

    const { result } = renderHook(() => useAltData("600519"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(spy).toHaveBeenCalledTimes(1);

    result.current.reload();
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
  });
});
