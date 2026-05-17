// Input  : ESGScorecardArtifact props.data {esg_score, e_score, s_score, g_score, sources?, climate?}
// Output : Vitest 用例：快乐路径 / 字段缺失 / 空数据（DEMO 兜底）
// Pos    : tests/frontend/components/artifacts/

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { ESGScorecardArtifact } from "@/components/artifacts/esg-scorecard";

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

describe("ESGScorecardArtifact", () => {
  it("快乐路径：渲染综合评分、E/S/G 三维标签", () => {
    const data = {
      esg_score: 75,
      e_score: 72,
      s_score: 80,
      g_score: 73,
      grade: "A",
      sources: [
        { source: "MSCI", esg_score: 75, e_score: 72, s_score: 80, g_score: 73, grade: "A" },
        { source: "Sustainalytics", esg_score: 22.5, grade: "Low Risk" },
      ],
      climate: [
        { tag: "Scope1", label: "直接排放", filing_date: "2026-03-15" },
      ],
    };
    const { container } = render(<ESGScorecardArtifact data={data} />);
    expect(container.textContent).toMatch(/ESG|环境|社会|治理|E|S|G/);
    // 评分数值（75 等）至少有其一
    expect(container.textContent).toMatch(/75|72|80|73/);
    // 多源
    expect(container.textContent).toMatch(/MSCI|Sustainalytics/);
  });

  it("字段缺失兜底：缺 sources/climate 不崩溃", () => {
    const data = { esg_score: 60, e_score: 55, s_score: 65, g_score: 58 };
    expect(() => render(<ESGScorecardArtifact data={data} />)).not.toThrow();
  });

  it("空数据：data 为 {} 回退 DEMO 兜底", () => {
    const { container } = render(<ESGScorecardArtifact data={{}} />);
    // DEMO 兜底仍渲染 ESG 主结构
    expect(container.textContent).toMatch(/ESG|环境|社会|治理/);
  });

  it("空数据：data 为 null 不抛错", () => {
    expect(() =>
      render(
        <ESGScorecardArtifact data={null as unknown as Record<string, never>} />,
      ),
    ).not.toThrow();
  });
});
