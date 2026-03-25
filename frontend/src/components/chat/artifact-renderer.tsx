// Input: 单个Artifact对象（含artifact_type、title、data）
// Output: 根据artifact_type路由渲染对应的React组件（K线图、雷达评分、资金流向、决策卡、技术指标、基本面评分卡、风险雷达图、新闻列表、投资者共识、搜索结果等）
// Pos: artifact-panel.tsx的子组件，Artifact路由渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import dynamic from "next/dynamic";
import type { Artifact } from "@/lib/types";
import { ArtifactCard } from "@/components/artifacts/artifact-card";

const CandlestickChartArtifact = dynamic(
  () =>
    import("@/components/artifacts/candlestick-chart").then((m) => ({
      default: m.CandlestickChartArtifact,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[400px] animate-pulse bg-muted rounded" />
    ),
  }
);

const ScoreRadarArtifact = dynamic(
  () =>
    import("@/components/artifacts/score-radar").then((m) => ({
      default: m.ScoreRadarArtifact,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] animate-pulse bg-muted rounded" />
    ),
  }
);

const CapitalFlowArtifact = dynamic(
  () =>
    import("@/components/artifacts/capital-flow-chart").then((m) => ({
      default: m.CapitalFlowArtifact,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[200px] animate-pulse bg-muted rounded" />
    ),
  }
);

const InvestorPersonasArtifact = dynamic(
  () =>
    import("@/components/artifacts/investor-personas").then((m) => ({
      default: m.InvestorPersonasArtifact,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] animate-pulse bg-muted rounded" />
    ),
  }
);

const DecisionCardArtifact = dynamic(
  () =>
    import("@/components/artifacts/decision-card").then((m) => ({
      default: m.DecisionCardArtifact,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[200px] animate-pulse bg-muted rounded" />
    ),
  }
);

const TechnicalPanelArtifact = dynamic(
  () =>
    import("@/components/artifacts/technical-panel").then((m) => ({
      default: m.TechnicalPanelArtifact,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[200px] animate-pulse bg-muted rounded" />
    ),
  }
);

const SearchResultsArtifact = dynamic(
  () =>
    import("@/components/artifacts/search-results").then((m) => ({
      default: m.SearchResultsArtifact,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[150px] animate-pulse bg-muted rounded" />
    ),
  }
);

const FundamentalScorecardArtifact = dynamic(
  () =>
    import("@/components/artifacts/fundamental-scorecard").then((m) => ({
      default: m.FundamentalScorecardArtifact,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[200px] animate-pulse bg-muted rounded" />
    ),
  }
);

const RiskRadarArtifact = dynamic(
  () =>
    import("@/components/artifacts/risk-radar-chart").then((m) => ({
      default: m.RiskRadarArtifact,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] animate-pulse bg-muted rounded" />
    ),
  }
);

const NewsFeedArtifact = dynamic(
  () =>
    import("@/components/artifacts/news-feed").then((m) => ({
      default: m.NewsFeedArtifact,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[200px] animate-pulse bg-muted rounded" />
    ),
  }
);

interface Props {
  artifact: Artifact;
}

export function ArtifactRenderer({ artifact }: Props) {
  return (
    <ArtifactCard title={artifact.title} icon={getArtifactIcon(artifact.artifact_type)}>
      {renderArtifactContent(artifact)}
    </ArtifactCard>
  );
}

function getArtifactIcon(type: string): string {
  const icons: Record<string, string> = {
    candlestick_chart: "\uD83D\uDCC8",
    technical_indicators: "\uD83D\uDCCA",
    fundamental_metrics: "\uD83D\uDCB0",
    capital_flow_chart: "\uD83D\uDCB9",
    news_feed: "\uD83D\uDCF0",
    risk_gauge: "\u26A0\uFE0F",
    search_results: "\uD83D\uDD0D",
    decision_card: "\uD83C\uDFAF",
    investor_consensus: "\uD83D\uDC65",
    agent_pipeline: "\uD83E\uDD16",
  };
  return icons[type] || "\uD83D\uDCCB";
}

function renderArtifactContent(artifact: Artifact) {
  const { artifact_type, data } = artifact;

  switch (artifact_type) {
    case "candlestick_chart":
      return <CandlestickChartArtifact data={data} />;
    case "technical_indicators":
      return (
        <div className="space-y-4">
          <TechnicalPanelArtifact data={data} />
          <ScoreRadarArtifact data={data} />
        </div>
      );
    case "capital_flow_chart":
      return <CapitalFlowArtifact data={data} />;
    case "decision_card":
      return <DecisionCardArtifact data={data} />;
    case "investor_consensus":
      return <InvestorPersonasArtifact data={data} />;
    case "search_results":
      return <SearchResultsArtifact data={data} />;
    case "fundamental_metrics":
      return <FundamentalScorecardArtifact data={data} />;
    case "risk_gauge":
      return <RiskRadarArtifact data={data} />;
    case "news_feed":
      return <NewsFeedArtifact data={data} />;
    default:
      return <GenericDataView data={data} />;
  }
}

// === 内联子组件 ===

function GenericDataView({ data }: { data: Record<string, unknown> }) {
  return (
    <pre className="text-xs bg-muted/50 rounded p-2 overflow-auto max-h-60">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
