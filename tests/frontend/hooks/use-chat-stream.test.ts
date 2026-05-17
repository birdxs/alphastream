// Input: useChatStream hook
// Output: vitest 用例，覆盖 sendMessage / stopGeneration / 股票名预解析 / error handler
// Pos: tests/frontend/hooks/use-chat-stream.test.ts — FE-02 [NEW-FILE:#20260517-01]

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

// mock apiClient.streamPost — 在导入 hook 前
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
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { useChatStore } from "@/lib/stores/chat-store";
import { useAgentStore } from "@/lib/stores/agent-store";

type Handlers = {
  onToken?: (d: { content: string; agent?: string; finish_reason?: string }) => void;
  onError?: (d: unknown) => void;
  onDone?: (d?: unknown) => void;
  onArtifact?: (d: unknown) => void;
  onToolCallStart?: (d: unknown) => void;
  onToolCallResult?: (d: unknown) => void;
  onAgentProgress?: (d: unknown) => void;
  onReasoning?: (d: unknown) => void;
};

function resetStores() {
  useChatStore.setState({
    conversations: [],
    activeConversationId: null,
    messages: [],
    isStreaming: false,
    streamingContent: "",
    artifacts: [],
    followUpQuestions: [],
    conversationsRefreshTick: 0,
  });
  useAgentStore.getState().reset();
}

beforeEach(() => {
  vi.clearAllMocks();
  resetStores();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useChatStream.sendMessage", () => {
  it("发送普通消息：走 /api/ai/chat，token 事件被 appendStreamContent，done 转为 assistant 消息", async () => {
    (apiClient.streamPost as ReturnType<typeof vi.fn>).mockImplementation(
      async (endpoint: string, _body: unknown, handlers: Handlers) => {
        expect(endpoint).toBe("/api/ai/chat");
        handlers.onToken?.({ content: "你好，" });
        handlers.onToken?.({ content: "这是回答。" });
        handlers.onDone?.({});
      }
    );

    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.sendMessage("市场怎么样");
    });

    const st = useChatStore.getState();
    expect(st.isStreaming).toBe(false);
    const userMsg = st.messages.find((m) => m.role === "user");
    expect(userMsg?.content).toBe("市场怎么样");
    const asst = st.messages.find((m) => m.role === "assistant");
    expect(asst?.content).toContain("你好");
    expect(asst?.content).toContain("这是回答");
  });

  it("含 6 位代码 + 分析动词 → 走 /api/ai/agent-analyze", async () => {
    (apiClient.streamPost as ReturnType<typeof vi.fn>).mockImplementation(
      async (endpoint: string, _body: unknown, handlers: Handlers) => {
        expect(endpoint).toBe("/api/ai/agent-analyze");
        handlers.onDone?.({});
      }
    );

    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.sendMessage("帮我分析 600519");
    });

    expect(apiClient.streamPost).toHaveBeenCalled();
  });

  it("股票名预解析：无代码+分析动词 → fetch /api/stock_name_search → 拿到 code 走 agent-analyze", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ results: [{ code: "600519", name: "贵州茅台" }] }),
    } as unknown as Response);

    (apiClient.streamPost as ReturnType<typeof vi.fn>).mockImplementation(
      async (endpoint: string, body: { stock_code?: string }, handlers: Handlers) => {
        expect(endpoint).toBe("/api/ai/agent-analyze");
        expect(body.stock_code).toBe("600519");
        handlers.onDone?.({});
      }
    );

    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.sendMessage("分析贵州茅台");
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/api/stock_name_search?q="),
      expect.objectContaining({ signal: expect.anything() })
    );
  });

  it("onError handler：在 chat-store 写入 ⚠️ 错误消息并关闭 streaming", async () => {
    (apiClient.streamPost as ReturnType<typeof vi.fn>).mockImplementation(
      async (_e: string, _b: unknown, handlers: Handlers) => {
        handlers.onError?.({ message: "后端炸了" });
      }
    );

    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.sendMessage("hello");
    });

    const st = useChatStore.getState();
    expect(st.isStreaming).toBe(false);
    const errMsg = st.messages.find((m) => m.role === "assistant" && m.content.includes("⚠️"));
    expect(errMsg).toBeDefined();
    expect(errMsg?.content).toContain("后端炸了");
    expect(st.followUpQuestions).toContain("🔄 重试上一个问题");
  });

  it("streamPost reject 非 AbortError：streaming 被清理 + console.error", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    (apiClient.streamPost as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("网络中断"));

    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.sendMessage("hi");
    });

    expect(useChatStore.getState().isStreaming).toBe(false);
    expect(errSpy).toHaveBeenCalled();
  });

  it("stopGeneration：触发 abort，AbortError 路径写入 [已停止] 尾标", async () => {
    let capturedSignal: AbortSignal | null = null;
    (apiClient.streamPost as ReturnType<typeof vi.fn>).mockImplementation(
      async (_e: string, _b: unknown, handlers: Handlers, signal: AbortSignal) => {
        capturedSignal = signal;
        // 先 push 一些流内容，再等待 abort
        handlers.onToken?.({ content: "部分回答..." });
        await new Promise<void>((_, reject) => {
          signal.addEventListener("abort", () => {
            const e = new DOMException("aborted", "AbortError");
            reject(e);
          });
        });
      }
    );

    const { result } = renderHook(() => useChatStream());
    const promise = act(async () => {
      await result.current.sendMessage("长任务");
    });

    // 等待 streamingContent 累积
    await waitFor(() => {
      expect(useChatStore.getState().streamingContent).toContain("部分回答");
    });

    act(() => result.current.stopGeneration());
    await promise;

    expect(capturedSignal).not.toBeNull();
    const st = useChatStore.getState();
    const stoppedMsg = st.messages.find((m) => m.role === "assistant" && m.content.includes("[已停止]"));
    expect(stoppedMsg).toBeDefined();
    expect(st.isStreaming).toBe(false);
  });
});
