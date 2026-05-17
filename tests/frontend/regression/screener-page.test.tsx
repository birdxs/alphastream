// Input  : 工作区 frontend/src/app/screener/page.tsx 改动
// Output : 渲染快照 + 基本骨架可见
// Pos    : tests/frontend/regression/ - REGR-01

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import React from "react";
import ScreenerPage from "@/app/screener/page";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: [], total: 0 }),
    post: vi.fn().mockResolvedValue({}),
    sse: vi.fn(),
  },
  extractErrorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/screener",
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("REGR-01 ScreenerPage 渲染快照", () => {
  it("基本渲染：不抛异常", () => {
    const { container } = render(<ScreenerPage />);
    expect(container.firstChild).toBeTruthy();
  });

  it("DOM 快照", () => {
    const { container } = render(<ScreenerPage />);
    const root = container.firstChild as HTMLElement | null;
    expect(root?.tagName).toBeTruthy();
    expect(root).toMatchSnapshot();
  });
});
