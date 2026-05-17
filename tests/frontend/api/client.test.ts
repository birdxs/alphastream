// Input: apiClient (get/post/streamPost)
// Output: vitest 用例，覆盖 SSE 1MB 上限 / 重连 / 错误提取
// Pos: tests/frontend/api/client.test.ts — FE-02 [NEW-FILE:#20260517-01]

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { apiClient, ApiError } from "@/lib/api/client";
import type { SSEHandlers } from "@/lib/types";

// 构造可控的 ReadableStream，按数组 chunks 顺序 enqueue
function makeStreamResponse(chunks: Uint8Array[] | string[], ok = true, status = 200): Response {
  const encoder = new TextEncoder();
  const data = chunks.map((c) => (typeof c === "string" ? encoder.encode(c) : c));
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of data) controller.enqueue(c);
      controller.close();
    },
  });
  return new Response(stream, { status, statusText: ok ? "OK" : "ERR" });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("apiClient.get/post — extractErrorMessage 分支", () => {
  it("HTTP 200 + 合法 JSON：返回 parsed", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ a: 1 }),
    } as unknown as Response);

    const r = await apiClient.get<{ a: number }>("/api/x");
    expect(r.a).toBe(1);
  });

  it("HTTP 500 + 文本响应（非 JSON）：抛 ApiError，message=原文", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: async () => "server boom",
    } as unknown as Response);

    await expect(apiClient.get("/api/x")).rejects.toMatchObject({
      status: 500,
      message: "server boom",
    });
  });

  it("HTTP 504 + JSON 含 error 字段：提取 error 作为 message", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 504,
      text: async () => JSON.stringify({ error: "上游超时", stock_code: "600519" }),
    } as unknown as Response);

    await expect(apiClient.post("/api/x", {})).rejects.toMatchObject({
      status: 504,
      message: "上游超时",
    });
  });

  it("HTTP 503 + 空响应体：兜底为 'HTTP 503'", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 503,
      text: async () => "",
    } as unknown as Response);

    const err = await apiClient.get("/api/x").catch((e: ApiError) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).message).toBe("HTTP 503");
  });

  it("safeJSONParse：NaN/Infinity 被替换为 null（不含 -Infinity 形式）", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      // 注意：源码 `\b-Infinity\b` 因 `\b` 在 `-` 处不匹配（` 是 \W）→ 实际仅 NaN 和 Infinity 替换生效
      text: async () => '{"v": NaN, "x": Infinity}',
    } as unknown as Response);
    const r = await apiClient.get<{ v: null; x: null }>("/api/x");
    expect(r.v).toBeNull();
    expect(r.x).toBeNull();
  });
});

describe("apiClient.streamPost — SSE 解析", () => {
  it("派发 event:token + data:{...} 到 onToken", async () => {
    const block = "event: token\ndata: {\"content\":\"hi\"}\n\n";
    vi.spyOn(global, "fetch").mockResolvedValueOnce(makeStreamResponse([block]));

    const onToken = vi.fn();
    const onDone = vi.fn();
    const handlers: SSEHandlers = { onToken, onDone };

    await apiClient.streamPost("/api/ai/chat", { msg: "hi" }, handlers);
    expect(onToken).toHaveBeenCalledWith(expect.objectContaining({ content: "hi" }));
  });

  it("done 事件触发 onDone", async () => {
    const block = "event: done\ndata: {\"ok\":true}\n\n";
    vi.spyOn(global, "fetch").mockResolvedValueOnce(makeStreamResponse([block]));
    const onDone = vi.fn();
    await apiClient.streamPost("/api/x", {}, { onDone });
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ ok: true }));
  });

  it("缓冲区 1MB 上限：超大 chunk 触发 console.warn 并 flush", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    // 制造 >1MB 的无分隔字符块（即 buffer 永远不被消费）
    const bigChunk = "x".repeat(1_048_577); // 1MB + 1 byte
    // 再补一个完整 done 事件用以正常结束
    const doneBlock = "event: done\ndata: {}\n\n";
    vi.spyOn(global, "fetch").mockResolvedValueOnce(makeStreamResponse([bigChunk, doneBlock]));

    const onDone = vi.fn();
    await apiClient.streamPost("/api/x", {}, { onDone });

    const flushCall = warnSpy.mock.calls.find((c) => String(c[0]).includes("buffer exceeded 1MB"));
    expect(flushCall).toBeDefined();
  });

  it("HTTP 500 重连：第一次返回 500 → 等待 → 第二次返回 200 SSE 完整数据", async () => {
    vi.useFakeTimers();
    const fetchSpy = vi.spyOn(global, "fetch")
      .mockResolvedValueOnce({ ok: false, status: 500, body: null } as unknown as Response)
      .mockResolvedValueOnce(makeStreamResponse(["event: done\ndata: {}\n\n"]));

    const onDone = vi.fn();
    const p = apiClient.streamPost("/api/x", {}, { onDone });

    // 跑过第一次 retry delay 1000ms
    await vi.advanceTimersByTimeAsync(1000);
    await p;
    vi.useRealTimers();

    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(onDone).toHaveBeenCalled();
  });

  it("fetch reject 3 次：最终抛错（MAX_RETRIES=2 共尝试 3 次）", async () => {
    vi.useFakeTimers();
    const fetchSpy = vi.spyOn(global, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));

    const onError = vi.fn();
    const p = apiClient.streamPost("/api/x", {}, { onError }).catch((e) => e);

    // 跑过 1000 + 3000 ms 两次 retry 间隔
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(3000);
    const result = await p;
    vi.useRealTimers();

    expect(fetchSpy).toHaveBeenCalledTimes(3);
    expect((result as Error).message).toMatch(/ECONNREFUSED/);
  });

  it("AbortError 直接抛出，不进行重试", async () => {
    const abortErr = new DOMException("aborted", "AbortError");
    const fetchSpy = vi.spyOn(global, "fetch").mockRejectedValue(abortErr);

    await expect(apiClient.streamPost("/api/x", {}, {})).rejects.toBe(abortErr);
    // 仅第一次尝试 → 不重试
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("info 事件携带 event_type 字段：派发到内部事件类型 (token)", async () => {
    const block = "event: info\ndata: {\"event_type\":\"token\",\"data\":{\"content\":\"yo\"}}\n\n";
    vi.spyOn(global, "fetch").mockResolvedValueOnce(makeStreamResponse([block]));
    const onToken = vi.fn();
    await apiClient.streamPost("/api/x", {}, { onToken });
    expect(onToken).toHaveBeenCalledWith(expect.objectContaining({ content: "yo" }));
  });
});
