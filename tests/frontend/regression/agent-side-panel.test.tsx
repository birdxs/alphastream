// Input  : 工作区 frontend/src/components/agent/agent-side-panel.tsx 改动
// Output : 基本渲染验证 + UI 调整后可见性
// Pos    : tests/frontend/regression/ - REGR-01

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import React from "react";
import { AgentSidePanel } from "@/components/agent/agent-side-panel";

// 快照测试固定时钟：2026-05-18 16:17:33 CST (UTC+8)
const FIXED_NOW = new Date("2026-05-18T08:17:33.000Z").getTime();

vi.mock("@/lib/api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), sse: vi.fn() },
  extractErrorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/",
}));

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("REGR-01 AgentSidePanel 基本渲染", () => {
  it("默认 props 渲染不抛错", () => {
    const { container } = render(<AgentSidePanel />);
    // 组件可能根据 store 状态返回 null，但函数本身必须能跑通
    expect(container).toBeTruthy();
  });

  it("DOM 快照（含闭合态）", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(FIXED_NOW);
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<AgentSidePanel />));
    });
    expect(container.firstChild).toMatchSnapshot();
  });
});
