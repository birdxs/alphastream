// Input  : CorporateNetworkArtifact props.data {company_name?, parents?, subsidiaries?, officers?, opencorporates_url?}
// Output : Vitest 用例：快乐路径 / 字段缺失 / 空数据（DEMO 兜底）
// Pos    : tests/frontend/components/artifacts/

import React from "react";
import { describe, it, expect, beforeEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { CorporateNetworkArtifact } from "@/components/artifacts/corporate-network";

beforeEach(() => cleanup());

describe("CorporateNetworkArtifact", () => {
  it("快乐路径：渲染中心公司、父/子公司、董事列表", () => {
    const data = {
      company_name: "Acme Corp",
      jurisdiction: "US-DE",
      parents: [
        { name: "Acme Holdings", role: "parent", jurisdiction: "US-DE" },
      ],
      children: [
        { name: "Acme Asia", role: "subsidiary", jurisdiction: "HK" },
        { name: "Acme EU", role: "subsidiary", jurisdiction: "DE" },
      ],
      officers: [
        { name: "Alice Zhang", position: "CEO" },
        { name: "Bob Lee", position: "CFO" },
      ],
      opencorporates_url: "https://opencorporates.com/companies/us_de/123",
    };
    const { container } = render(<CorporateNetworkArtifact data={data} />);
    // 中心公司名
    expect(container.textContent).toContain("Acme Corp");
    // 父/子公司
    expect(container.textContent).toContain("Acme Holdings");
    expect(container.textContent).toContain("Acme Asia");
    // 董事
    expect(container.textContent).toContain("Alice Zhang");
    expect(container.textContent).toMatch(/CEO|CFO/);
  });

  it("字段缺失兜底：缺 parents / children / officers 时不崩溃", () => {
    const data = { company_name: "Solo Inc" };
    const { container } = render(<CorporateNetworkArtifact data={data} />);
    expect(container).toBeTruthy();
    expect(container.textContent).toContain("Solo Inc");
  });

  it("空数据：data 为 {} 回退 DEMO 兜底渲染", () => {
    const { container } = render(<CorporateNetworkArtifact data={{}} />);
    // DEMO 兜底应渲染示例公司结构
    expect(container.textContent).toMatch(/公司|父|子|董事|关联/);
  });

  it("空数据：data 为 null 不抛错", () => {
    expect(() =>
      render(
        <CorporateNetworkArtifact data={null as unknown as Record<string, never>} />,
      ),
    ).not.toThrow();
  });
});
