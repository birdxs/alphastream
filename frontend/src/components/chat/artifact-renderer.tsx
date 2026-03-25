// Input: 单个Artifact对象（含artifact_type、title、data）
// Output: 根据artifact_type路由渲染对应的React组件（K线图、雷达评分、资金流向、决策卡、技术指标、基本面、风险仪表、新闻等）
// Pos: artifact-panel.tsx的子组件，Artifact路由渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import dynamic from "next/dynamic";
import type { Artifact } from "@/lib/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

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

interface Props {
  artifact: Artifact;
}

export function ArtifactRenderer({ artifact }: Props) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          {getArtifactIcon(artifact.artifact_type)}
          {artifact.title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {renderArtifactContent(artifact)}
      </CardContent>
    </Card>
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
          <ScoreRadarArtifact data={data} />
          <TechnicalView data={data} />
        </div>
      );
    case "capital_flow_chart":
      return <CapitalFlowArtifact data={data} />;
    case "decision_card":
      return <DecisionCardView data={data} />;
    case "fundamental_metrics":
      return <FundamentalView data={data} />;
    case "risk_gauge":
      return <RiskView data={data} />;
    case "news_feed":
      return <NewsView data={data} />;
    default:
      return <GenericDataView data={data} />;
  }
}

// === 内联子组件 ===

function DecisionCardView({ data }: { data: Record<string, unknown> }) {
  const action = String(data.action || "HOLD");
  const confidence = Number(data.confidence || 0);
  const reasoning = String(data.reasoning || "");

  const colorMap: Record<string, string> = {
    BUY: "text-green-500 bg-green-500/10",
    SELL: "text-red-500 bg-red-500/10",
    HOLD: "text-yellow-500 bg-yellow-500/10",
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className={`text-2xl font-bold px-3 py-1 rounded ${colorMap[action] || ""}`}>
          {action === "BUY" ? "买入" : action === "SELL" ? "卖出" : "持有"}
        </span>
        <span className="text-sm text-muted-foreground">置信度 {(confidence * 100).toFixed(0)}%</span>
      </div>
      <p className="text-sm">{reasoning}</p>
    </div>
  );
}

function TechnicalView({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="grid grid-cols-2 gap-2 text-sm">
      {Object.entries(data).filter(([k]) => !["ai_commentary","tool_calls"].includes(k)).slice(0, 8).map(([k, v]) => (
        <div key={k} className="flex justify-between bg-muted/50 rounded px-2 py-1">
          <span className="text-muted-foreground">{k}</span>
          <span className="font-mono">{String(v).slice(0, 20)}</span>
        </div>
      ))}
    </div>
  );
}

function FundamentalView({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="grid grid-cols-2 gap-2 text-sm">
      {Object.entries(data).filter(([k]) => !["ai_commentary","tool_calls"].includes(k)).slice(0, 8).map(([k, v]) => (
        <div key={k} className="flex justify-between bg-muted/50 rounded px-2 py-1">
          <span className="text-muted-foreground">{k}</span>
          <span className="font-mono">{String(v).slice(0, 20)}</span>
        </div>
      ))}
    </div>
  );
}

function RiskView({ data }: { data: Record<string, unknown> }) {
  const riskScore = Number(data.risk_score || data.overall_risk || 50);
  const riskLevel = String(data.risk_level || "中等");

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <span className="text-2xl font-bold">{riskScore}</span>
        <span className="text-sm text-muted-foreground">/100 风险分 · {riskLevel}</span>
      </div>
      <div className="w-full bg-muted rounded-full h-3">
        <div className={`h-3 rounded-full ${riskScore > 60 ? 'bg-red-500' : riskScore > 30 ? 'bg-yellow-500' : 'bg-green-500'}`}
             style={{ width: `${riskScore}%` }} />
      </div>
    </div>
  );
}

function NewsView({ data }: { data: Record<string, unknown> }) {
  const items = Array.isArray(data.items) ? data.items as Record<string, unknown>[] : [];
  return (
    <div className="space-y-2">
      {items.slice(0, 5).map((item, i) => (
        <div key={i} className="text-sm border-b pb-2">
          <p className="font-medium">{String(item.title || "")}</p>
          <p className="text-xs text-muted-foreground">{String(item.time || item.date || "")}</p>
        </div>
      ))}
      {items.length === 0 && <p className="text-sm text-muted-foreground">暂无新闻</p>}
    </div>
  );
}

function GenericDataView({ data }: { data: Record<string, unknown> }) {
  return (
    <pre className="text-xs bg-muted/50 rounded p-2 overflow-auto max-h-60">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
