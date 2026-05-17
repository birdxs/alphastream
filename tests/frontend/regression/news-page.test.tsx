// Input  : 工作区 frontend/src/app/news/page.tsx 改动
// Output : 渲染快照 + 基本骨架可见
// Pos    : tests/frontend/regression/ - REGR-01

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import React from "react";
import NewsPage from "@/app/news/page";

// 屏蔽实际网络请求 / SSE
vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: [], total: 0 }),
    post: vi.fn().mockResolvedValue({}),
    sse: vi.fn(),
  },
  extractErrorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

// next/navigation 在测试环境下需 mock
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/news",
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("REGR-01 NewsPage 渲染快照", () => {
  it("基本渲染：不抛异常 + 输出非空 DOM", () => {
    const { container } = render(<NewsPage />);
    expect(container.firstChild).toBeTruthy();
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it("DOM 快照：保持当前 UI 微调后的结构", () => {
    const { container } = render(<NewsPage />);
    // 仅快照根节点的标签骨架，避免随数据漂移
    const skeleton = container.firstChild as HTMLElement | null;
    expect(skeleton?.tagName).toBeTruthy();
    expect(skeleton).toMatchSnapshot();
  });
});
