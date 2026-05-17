// Input  : ShippingChartArtifact props.data {bdi?, ports?, ais?}
// Output : Vitest 用例：快乐路径 / 字段缺失 / 空数据（DEMO 兜底）
// Pos    : tests/frontend/components/artifacts/

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { ShippingChartArtifact } from "@/components/artifacts/shipping-chart";

vi.mock("lightweight-charts", () => ({
  createChart: vi.fn(() => ({
    addLineSeries: vi.fn(() => ({ setData: vi.fn() })),
    addCandlestickSeries: vi.fn(() => ({ setData: vi.fn() })),
    addSeries: vi.fn(() => ({ setData: vi.fn() })),
    remove: vi.fn(),
    applyOptions: vi.fn(),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
  })),
  ColorType: { Solid: "solid" },
  LineSeries: "LineSeries",
}));

vi.mock("recharts", () => {
  const S = ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="recharts-stub">{children}</div>
  );
  return {
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
    BarChart: S, Bar: S, XAxis: S, YAxis: S, CartesianGrid: S,
    Tooltip: S, Cell: S, LineChart: S, Line: S, PieChart: S, Pie: S,
    RadarChart: S, PolarGrid: S, PolarAngleAxis: S, PolarRadiusAxis: S,
    Radar: S, Legend: S,
  };
});

beforeEach(() => cleanup());

describe("ShippingChartArtifact", () => {
  it("快乐路径：渲染 BDI + 港口 + AIS 三段区域", () => {
    const data = {
      bdi: {
        items: [
          { date: "2026-05-10", value: 1500 },
          { date: "2026-05-11", value: 1620 },
        ],
      },
      ports: {
        items: [
          { name: "上海港", throughput: 4250 },
          { name: "宁波港", throughput: 3680 },
        ],
      },
      ais: {
        items: [
          { vessel_type: "container", count: 120 },
          { vessel_type: "bulk", count: 80 },
        ],
      },
    };
    const { container } = render(<ShippingChartArtifact data={data} />);
    expect(container).toBeTruthy();
    // 关键标题/标签存在
    expect(container.textContent).toMatch(/BDI|波罗的海|港口|吞吐|AIS|船舶/);
  });

  it("字段缺失兜底：仅有 bdi 子集时不崩溃", () => {
    const data = { bdi: { items: [{ date: "2026-05-10", value: 1500 }] } };
    expect(() => render(<ShippingChartArtifact data={data} />)).not.toThrow();
  });

  it("空数据：data 为 {} 时回退 DEMO 兜底渲染", () => {
    const { container } = render(<ShippingChartArtifact data={{}} />);
    // DEMO_DATA 兜底：仍渲染主要区块
    expect(container.textContent).toMatch(/BDI|波罗的海|港口|吞吐|AIS|船舶/);
  });

  it("空数据：data 为 null — 当前组件无 ?. 兜底会抛错（P0-2 缺陷记录）", () => {
    // 期望：理想上不应抛错；现状：抛 TypeError —— 暴露字段缺失白屏 P0-2 缺陷
    let crashed = false;
    let msg = "";
    try {
      render(
        <ShippingChartArtifact
          data={null as unknown as Record<string, never>}
        />,
      );
    } catch (e) {
      crashed = true;
      msg = (e as Error).message;
    }
    // 记录现状：组件确实崩溃 (`Cannot read properties of null`)
    expect(crashed).toBe(true);
    expect(msg).toMatch(/null|undefined/);
  });
});
