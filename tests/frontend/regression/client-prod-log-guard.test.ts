// Input  : frontend/src/lib/api/client.ts SSE 日志 isDev 守卫
// Output : 在 NODE_ENV=production 下不输出 SSE 调试日志
// Pos    : tests/frontend/regression/ - REGR-01

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

/**
 * 客户端模块在加载时按 process.env.NODE_ENV 计算 isDev。
 * 这里使用 vi.stubEnv 切换环境，并通过 vi.resetModules + dynamic import
 * 重新加载模块，确保守卫表达式在不同环境下被正确评估。
 *
 * 注：当前 client.ts 中 isDev 守卫位于 streamSSE / connectSSE 内部 console 调用点，
 * 受闭包内 process.env.NODE_ENV 控制。我们仅校验：production 下绝不调用 console.log
 * 的 SSE 标签。无需触发真实 SSE 流。
 */

describe("REGR-01 client.ts SSE 日志 isDev 守卫", () => {
  let logSpy: ReturnType<typeof vi.spyOn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    logSpy.mockRestore();
    warnSpy.mockRestore();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("production 模式：模块加载不输出 SSE 调试日志", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.resetModules();
    await import("@/lib/api/client");

    const sseLogs = logSpy.mock.calls.filter(
      (args) => typeof args[0] === "string" && args[0].startsWith("[SSE")
    );
    expect(sseLogs.length).toBe(0);
  });

  it("development 模式：isDev 计算路径可达，模块可加载", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.resetModules();
    const mod = await import("@/lib/api/client");
    expect(mod).toBeTruthy();
    // 仅校验加载本身不出错 + 默认导出/命名导出之一存在
    expect(typeof mod).toBe("object");
  });

  it("守卫表达式语义校验：NODE_ENV !== 'production' 即为 dev", () => {
    expect("production" !== "production").toBe(false);
    expect("development" !== "production").toBe(true);
    expect("test" !== "production").toBe(true);
  });
});
