// Input  : CapitalFlowChartArtifact props.data (daily_flow[] / summary{})
// Output : Vitest 用例：快乐路径 / 字段缺失 / 空数据
// Pos    : tests/frontend/components/artifacts/

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { CapitalFlowChartArtifact } from "@/components/artifacts/capital-flow-chart";

// 全 mock recharts —— 使用 Proxy 自动返回 stub，避免遗漏任何 named import
vi.mock("recharts", () => {
  const S = ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="recharts-stub">{children}</div>
  );
  const RC = ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  );
  return new Proxy(
    { ResponsiveContainer: RC },
    {
      get(target, prop) {
        if (prop in target) return (target as Record<string | symbol, unknown>)[prop];
        if (prop === "__esModule") return true;
        return S;
      },
    },
  );
});

vi.mock("@/lib/stores/theme-store", () => ({
  useThemeStore: () => ({ theme: "dark" }),
}));

// 桩化 lucide-react 中使用的图标，避免 jsdom 下出现 undefined 元素
vi.mock("lucide-react", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("lucide-react");
  const Icon = (props: Record<string, unknown>) => <span {...props} />;
  return { ...actual, TrendingDown: Icon };
});

beforeEach(() => cleanup());

describe("CapitalFlowChartArtifact", () => {
  it("快乐路径：渲染汇总卡 + 柱状图容器", () => {
    const data = {
      daily_flow: [
        { date: "2026-05-10", main_net_inflow: 1.2e8 },
        { date: "2026-05-11", main_net_inflow: -3.4e7 },
        { date: "2026-05-12", main_net_inflow: 5.6e7 },
      ],
      summary: {
        main_net_inflow_5d: 1.4e8,
        super_large_net_inflow_5d: 8.2e7,
        large_net_inflow_5d: 5.8e7,
        retail_net_inflow_5d: -2.3e7,
      },
    };
    const { container } = render(<CapitalFlowChartArtifact data={data} />);
    expect(container).toBeTruthy();
    // 至少出现 "主力" / "净流入" / "散户" 等关键字之一
    expect(container.textContent).toMatch(/主力|净流入|散户|超大单|大单/);
    // 图表容器渲染
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("字段缺失兜底：缺 summary 仅有 daily_flow，不崩溃", () => {
    const data = {
      daily_flow: [{ date: "2026-05-10", main_net_inflow: 1.2e8 }],
    };
    const { container } = render(<CapitalFlowChartArtifact data={data} />);
    expect(container).toBeTruthy();
  });

  it("空数据：data 为 {} 时显示 '暂无资金流向数据' 占位", () => {
    const { container } = render(<CapitalFlowChartArtifact data={{}} />);
    expect(container.textContent).toContain("暂无资金流向数据");
  });

  it("空数据：daily_flow 为 [] 且无 summary 时不抛错", () => {
    expect(() =>
      render(<CapitalFlowChartArtifact data={{ daily_flow: [] }} />),
    ).not.toThrow();
  });
});
