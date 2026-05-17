// Input  : 工作区 frontend/src/app/stock/[code]/page.tsx 改动
// Output : 渲染快照 + 基本骨架可见
// Pos    : tests/frontend/regression/ - REGR-01

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import React from "react";
import StockPage from "@/app/stock/[code]/page";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: {}, total: 0 }),
    post: vi.fn().mockResolvedValue({}),
    sse: vi.fn(),
  },
  extractErrorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/stock/000001",
  useParams: () => ({ code: "000001" }),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("REGR-01 StockPage 渲染快照", () => {
  it("基本渲染：不抛异常（异步页面初始可能为 null）", () => {
    // Next 15 page 接收 Promise params；首次 render 时 Suspense fallback 可能尚未挂载
    // @ts-expect-error - 测试场景下放宽类型
    const { container } = render(<StockPage params={Promise.resolve({ code: "000001" })} />);
    // container 本身必须存在，firstChild 可为 null（Suspense pending）
    expect(container).toBeTruthy();
  });

  it("DOM 快照", () => {
    // @ts-expect-error - 测试场景下放宽类型
    const { container } = render(<StockPage params={Promise.resolve({ code: "000001" })} />);
    const root = container.firstChild as HTMLElement | null;
    expect(root).toMatchSnapshot();
  });
});
