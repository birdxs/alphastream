/**
 * Input: CSS 自定义属性名（含 -- 前缀）与可选 fallback
 * Output: 计算后的色值字符串（仅客户端有效）
 * Pos: charts/artifacts 读 S-UI token，避免硬编码涨跌/语义色
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

/** 读取 document 上的 CSS 变量；SSR 返回 fallback */
export function cssVar(name: string, fallback = ""): string {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return fallback;
  }
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  } catch {
    return fallback;
  }
}

/** 涨跌/状态调色板（跟随 data-color-scheme 与 .dark） */
export function stockPalette(): {
  up: string;
  down: string;
  accent: string;
  warn: string;
  ok: string;
  danger: string;
  muted: string;
  chart1: string;
  chart2: string;
  chart3: string;
  chart4: string;
  chart5: string;
} {
  return {
    up: cssVar("--stock-up", cssVar("--up", "#DC2626")),
    down: cssVar("--stock-down", cssVar("--down", "#16A34A")),
    accent: cssVar("--accent", "#4F46E5"),
    warn: cssVar("--warn", "#D97706"),
    ok: cssVar("--ok", "#059669"),
    danger: cssVar("--danger", "#B91C1C"),
    muted: cssVar("--text-muted", "#94A3B8"),
    chart1: cssVar("--chart-1", cssVar("--accent", "#4F46E5")),
    chart2: cssVar("--chart-2", cssVar("--ok", "#059669")),
    chart3: cssVar("--chart-3", cssVar("--warn", "#D97706")),
    chart4: cssVar("--chart-4", cssVar("--danger", "#B91C1C")),
    chart5: cssVar("--chart-5", "#6B5EE4"),
  };
}
