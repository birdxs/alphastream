// Input: 另类数据聚合对象 {shipping, esg, hiring, corporate} — 任意子集
// Output: Tab 式主面板, 4 个 Tab (航运&大宗/ESG/招聘扩张/企业关联) 切换显示对应子组件
// Pos: artifact-renderer.tsx 子组件, alt_data 类型 Artifact 渲染器 — 另类数据统一入口
// 契约: 每个子 Tab 对应一个子组件, data 对象可包含任意子集, 缺失子集对应 Tab 置灰
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState } from "react";
import { Ship, Leaf, Briefcase, Network } from "lucide-react";
import { ShippingChartArtifact } from "./shipping-chart";
import { ESGScorecardArtifact } from "./esg-scorecard";
import { HiringSignalArtifact } from "./hiring-signal";
import { CorporateNetworkArtifact } from "./corporate-network";

type TabKey = "shipping" | "esg" | "hiring" | "corporate";

interface Props {
  data: {
    shipping?: Record<string, unknown>;
    esg?: Record<string, unknown>;
    hiring?: Record<string, unknown>;
    corporate?: Record<string, unknown>;
    [key: string]: unknown;
  };
}

const TABS: Array<{ key: TabKey; label: string; icon: React.ComponentType<{ className?: string }>; color: string }> = [
  { key: "shipping", label: "航运 & 大宗", icon: Ship, color: "var(--chart-5)" },
  { key: "esg", label: "ESG 评级", icon: Leaf, color: "var(--ok)" },
  { key: "hiring", label: "招聘扩张", icon: Briefcase, color: "var(--warn)" },
  { key: "corporate", label: "企业关联", icon: Network, color: "var(--accent)" },
];

export function AltDataPanelArtifact({ data }: Props) {
  const available: Record<TabKey, boolean> = {
    shipping: !!(data && data.shipping),
    esg: !!(data && data.esg),
    hiring: !!(data && data.hiring),
    corporate: !!(data && data.corporate),
  };
  const defaultKey = (TABS.find(t => available[t.key])?.key) || "shipping";
  const [activeKey, setActiveKey] = useState<TabKey>(defaultKey);

  const renderContent = () => {
    const sub = (data?.[activeKey] as Record<string, unknown>) || {};
    switch (activeKey) {
      case "shipping":
        return <ShippingChartArtifact data={sub as Parameters<typeof ShippingChartArtifact>[0]["data"]} />;
      case "esg":
        return <ESGScorecardArtifact data={sub as Parameters<typeof ESGScorecardArtifact>[0]["data"]} />;
      case "hiring":
        return <HiringSignalArtifact data={sub as Parameters<typeof HiringSignalArtifact>[0]["data"]} />;
      case "corporate":
        return <CorporateNetworkArtifact data={sub as Parameters<typeof CorporateNetworkArtifact>[0]["data"]} />;
    }
  };

  return (
    <div className="space-y-3">
      {/* Tab 栏 — Dark Glassmorphism */}
      <div className="flex items-center gap-1 p-1 rounded-xl bg-foreground/[0.03] dark:bg-white/[0.03] border border-foreground/[0.06] dark:border-white/[0.06] backdrop-blur-[40px]">
        {TABS.map(tab => {
          const Icon = tab.icon;
          const isActive = activeKey === tab.key;
          const isAvail = available[tab.key];
          return (
            <button
              key={tab.key}
              onClick={() => setActiveKey(tab.key)}
              className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-[11px] font-medium transition-all duration-200 ${
                isActive
                  ? "bg-gradient-to-br from-accent/20 to-accent/10 text-foreground shadow-lg shadow-accent/10 border border-accent/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04] dark:hover:bg-white/[0.04]"
              } ${!isAvail && !isActive ? "opacity-50" : ""}`}
              title={!isAvail ? `${tab.label} (示例数据)` : tab.label}
            >
              <Icon className={`h-3.5 w-3.5 shrink-0 ${isActive ? "" : ""}`} {...(isActive ? ({ style: { color: tab.color } } as unknown as Record<string, unknown>) : {})} />
              <span className="truncate">{tab.label}</span>
              {!isAvail && (
                <span className="w-1 h-1 rounded-full bg-muted-foreground/40 shrink-0" />
              )}
            </button>
          );
        })}
      </div>

      {/* 内容区 */}
      <div className="animate-[glass-enter_200ms_ease-out_both]" key={activeKey}>
        {renderContent()}
      </div>
    </div>
  );
}
