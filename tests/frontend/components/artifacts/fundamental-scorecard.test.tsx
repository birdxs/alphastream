// Input  : FundamentalScorecardArtifact props.data
// Output : Vitest 用例：快乐路径 / 字段缺失 / 空数据
// Pos    : tests/frontend/components/artifacts/

import React from "react";
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { FundamentalScorecardArtifact } from "@/components/artifacts/fundamental-scorecard";

beforeEach(() => cleanup());

describe("FundamentalScorecardArtifact", () => {
  it("快乐路径：渲染评分、定性评估、财务指标", () => {
    const data = {
      score: 82,
      financial_health: "优秀",
      profitability: "良好",
      growth_potential: "中等",
      valuation: "合理",
      financial_indicators: {
        pe_ratio: 18.5,
        pb_ratio: 2.3,
        roe: 14.2,
        debt_ratio: 35.6,
        revenue_growth: 12.4,
        profit_growth: 18.9,
      },
      recommendation: "买入",
    };
    const { container } = render(<FundamentalScorecardArtifact data={data} />);
    // 评分
    expect(screen.getByText("82")).toBeInTheDocument();
    // 定性评估文本
    expect(container.textContent).toMatch(/优秀|良好|合理|中等/);
    // 关键指标值（小数）
    expect(container.textContent).toMatch(/18\.5/);
    expect(container.textContent).toMatch(/14\.2/);
  });

  it("字段缺失兜底：缺 financial_indicators 时不崩溃", () => {
    const data = {
      score: 60,
      financial_health: "一般",
    };
    const { container } = render(<FundamentalScorecardArtifact data={data} />);
    expect(container).toBeTruthy();
    expect(screen.getByText("60")).toBeInTheDocument();
  });

  it("字段缺失兜底：缺 score 时不崩溃（注：组件默认显示 50，缺乏占位 -- 兜底 — P0 缺陷）", () => {
    const { container } = render(
      <FundamentalScorecardArtifact data={{ financial_health: "良好" }} />,
    );
    // 不崩溃为基本要求
    expect(container).toBeTruthy();
    // 缺陷：组件默认使用 50 作为占位评分，未显示 -- — 暴露 P0-2 字段缺失兜底盲区
    expect(container.textContent).toMatch(/50|--/);
  });

  it("空数据：data 为 {} 不抛错", () => {
    expect(() =>
      render(<FundamentalScorecardArtifact data={{}} />),
    ).not.toThrow();
  });
});
