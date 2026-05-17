// Input: useCountUp hook
// Output: vitest 用例，覆盖 起始→目标 / duration 控制 / cleanup
// Pos: tests/frontend/hooks/use-count-up.test.ts — FE-02 [NEW-FILE:#20260517-01]

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCountUp } from "@/lib/hooks/use-count-up";

// 受控的 requestAnimationFrame：用一个手动时钟驱动
let rafCallbacks: Array<{ id: number; cb: FrameRequestCallback }> = [];
let nextRafId = 1;

function flushFrame(ts: number) {
  const cbs = rafCallbacks;
  rafCallbacks = [];
  for (const c of cbs) c.cb(ts);
}

beforeEach(() => {
  rafCallbacks = [];
  nextRafId = 1;
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    const id = nextRafId++;
    rafCallbacks.push({ id, cb });
    return id;
  });
  vi.stubGlobal("cancelAnimationFrame", (id: number) => {
    rafCallbacks = rafCallbacks.filter((x) => x.id !== id);
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useCountUp", () => {
  it("enabled=false 时直接返回目标值", () => {
    const { result } = renderHook(() => useCountUp(1234.5, { enabled: false, decimals: 2 }));
    // toLocaleString zh-CN 千分位
    expect(result.current).toMatch(/1.?234[.,]50/);
  });

  it("起始为 0，最终收敛到目标", () => {
    const { result } = renderHook(() => useCountUp(100, { duration: 800, decimals: 0 }));

    // 初始：useState(enabled?0:target) → 0
    expect(result.current).toBe("0");

    // 第一帧：startTime 锚定 t=0
    act(() => flushFrame(0));
    // 中间帧 t=400 (50% → easeOutCubic(0.5)≈0.875)
    act(() => flushFrame(400));
    expect(result.current).not.toBe("0");
    // 终点帧
    act(() => flushFrame(800));
    // 最终值贴近 100
    expect(result.current).toBe("100");
  });

  it("decimals 控制小数位", () => {
    const { result } = renderHook(() => useCountUp(3.14, { duration: 100, decimals: 2 }));
    act(() => flushFrame(0));
    act(() => flushFrame(100));
    expect(result.current).toBe("3.14");
  });

  it("负数显示带前导减号", () => {
    const { result } = renderHook(() => useCountUp(-50, { duration: 100, decimals: 0 }));
    act(() => flushFrame(0));
    act(() => flushFrame(100));
    expect(result.current).toBe("-50");
  });

  it("卸载时调用 cancelAnimationFrame 清理", () => {
    const cancelSpy = vi.fn();
    vi.stubGlobal("cancelAnimationFrame", cancelSpy);
    const { unmount } = renderHook(() => useCountUp(10, { duration: 800 }));
    act(() => flushFrame(0)); // 让 rafRef 落地
    unmount();
    expect(cancelSpy).toHaveBeenCalled();
  });
});
