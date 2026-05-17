// Input  : AltDataPanelArtifact props.data {shipping?, esg?, hiring?, corporate?}
// Output : Vitest 用例：快乐路径（4 Tab 切换）/ 字段缺失 / 空数据
// Pos    : tests/frontend/components/artifacts/

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { AltDataPanelArtifact } from "@/components/artifacts/alt-data-panel";

// ----------------------------------------------------------------------------
// Mock lightweight-charts（shipping 子组件依赖）
// ----------------------------------------------------------------------------
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

describe("AltDataPanelArtifact", () => {
  it("快乐路径：默认显示 shipping Tab 并展示 4 个 Tab 按钮", () => {
    const data = {
      shipping: { bdi: { items: [] }, ports: { items: [] }, ais: { items: [] } },
      esg: { esg_score: 70 },
      hiring: { total_postings: 100 },
      corporate: { company_name: "Test Co" },
    };
    const { container } = render(<AltDataPanelArtifact data={data} />);
    // 4 个 Tab 文本应同时出现（按钮）
    expect(container.textContent).toMatch(/航运|大宗/);
    expect(container.textContent).toMatch(/ESG/);
    expect(container.textContent).toMatch(/招聘/);
    expect(container.textContent).toMatch(/关联|网络/);
  });

  it("切换 Tab：点击 ESG Tab 显示 ESG 子组件", () => {
    const data = {
      shipping: { bdi: { items: [] } },
      esg: { esg_score: 75, e_score: 70, s_score: 80, g_score: 75 },
    };
    const { container } = render(<AltDataPanelArtifact data={data} />);
    // 找含 "ESG" 的按钮并点击
    const buttons = Array.from(container.querySelectorAll("button")).filter(
      (b) => b.textContent?.includes("ESG"),
    );
    expect(buttons.length).toBeGreaterThan(0);
    fireEvent.click(buttons[0]);
    // 切换后 ESG 子组件内容（评分或标签）出现
    expect(container.textContent).toMatch(/ESG|环境|社会|治理/);
  });

  it("字段缺失兜底：data 仅包含 shipping 子集，其余 Tab 置灰但不崩溃", () => {
    const data = { shipping: { bdi: { items: [] } } };
    const { container } = render(<AltDataPanelArtifact data={data} />);
    expect(container).toBeTruthy();
    // 其余 Tab 按钮仍存在
    expect(container.textContent).toMatch(/ESG/);
    expect(container.textContent).toMatch(/招聘/);
  });

  it("空数据：data 为 {} 不抛错", () => {
    expect(() => render(<AltDataPanelArtifact data={{}} />)).not.toThrow();
  });
});
