// Input  : HiringSignalArtifact props.data {total_postings?, yoy_change?, monthly_trend?, skill_distribution?}
// Output : Vitest 用例：快乐路径 / 字段缺失 / 空数据（DEMO 兜底）
// Pos    : tests/frontend/components/artifacts/

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { HiringSignalArtifact } from "@/components/artifacts/hiring-signal";

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

describe("HiringSignalArtifact", () => {
  it("快乐路径：渲染岗位总数、同比变化、扩张信号", () => {
    const data = {
      total_postings: 1280,
      yoy_change: 23.5,
      expansion_signal: "强扩张",
      monthly_trend: [
        { month: "2026-03", count: 800 },
        { month: "2026-04", count: 1100 },
        { month: "2026-05", count: 1280 },
      ],
      skill_distribution: [
        { skill: "AI", count: 420 },
        { skill: "Cloud", count: 380 },
        { skill: "Frontend", count: 280 },
      ],
    };
    const { container } = render(<HiringSignalArtifact data={data} />);
    // 关键数值
    expect(container.textContent).toMatch(/1280|1,280/);
    expect(container.textContent).toMatch(/23\.5|23%|24%/);
    // 扩张信号文本
    expect(container.textContent).toMatch(/扩张|招聘|岗位/);
  });

  it("字段缺失兜底：缺 monthly_trend / skill_distribution 不崩溃", () => {
    const data = { total_postings: 500, yoy_change: -5.2 };
    expect(() => render(<HiringSignalArtifact data={data} />)).not.toThrow();
  });

  it("空数据：data 为 {} 回退 DEMO 兜底渲染", () => {
    const { container } = render(<HiringSignalArtifact data={{}} />);
    expect(container.textContent).toMatch(/招聘|岗位|扩张|趋势/);
  });

  it("空数据：data 为 null 不抛错", () => {
    expect(() =>
      render(
        <HiringSignalArtifact data={null as unknown as Record<string, never>} />,
      ),
    ).not.toThrow();
  });
});
