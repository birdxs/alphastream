// Input  : Vitest 加载每个测试文件前执行
// Output : 全局 jest-dom matcher、Next.js navigation/router mock、window.matchMedia mock
// Pos    : frontend/vitest.setup.ts；由 frontend/vitest.config.ts 的 setupFiles 引用

import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// ---------------------------------------------------------------------------
// Next.js 导航 mock：next/navigation
// ---------------------------------------------------------------------------
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn().mockResolvedValue(undefined),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
  useParams: () => ({}),
  redirect: vi.fn(),
  notFound: vi.fn(),
}));

// ---------------------------------------------------------------------------
// 旧版 next/router mock（兼容仍在使用 pages router 类 API 的代码）
// ---------------------------------------------------------------------------
vi.mock("next/router", () => ({
  useRouter: () => ({
    route: "/",
    pathname: "/",
    query: {},
    asPath: "/",
    push: vi.fn(),
    replace: vi.fn(),
    reload: vi.fn(),
    back: vi.fn(),
    prefetch: vi.fn().mockResolvedValue(undefined),
    events: {
      on: vi.fn(),
      off: vi.fn(),
      emit: vi.fn(),
    },
  }),
}));

// ---------------------------------------------------------------------------
// window.matchMedia
// ---------------------------------------------------------------------------
if (typeof window !== "undefined") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  // ResizeObserver 在 jsdom 中缺失
  if (!("ResizeObserver" in window)) {
    // @ts-expect-error - 注入 polyfill
    window.ResizeObserver = class {
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
    };
  }

  // IntersectionObserver 同理
  if (!("IntersectionObserver" in window)) {
    // @ts-expect-error - 注入 polyfill
    window.IntersectionObserver = class {
      root = null;
      rootMargin = "";
      thresholds = [];
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
      takeRecords = vi.fn().mockReturnValue([]);
    };
  }
}
