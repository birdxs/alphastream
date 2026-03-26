// Input: 单个Artifact对象（含artifact_type、title、data）
// Output: 根据artifact_type路由渲染对应的React组件（K线图、雷达评分、资金流向、决策卡、技术指标、基本面评分卡、风险雷达图、新闻列表、投资者共识、大师视角、搜索结果等），每个artifact由ErrorBoundary包裹防白屏
// Pos: artifact-panel.tsx的子组件，Artifact路由渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { ReactNode } from "react";
import dynamic from "next/dynamic";
import type { Artifact } from "@/lib/types";
import { ArtifactCard } from "@/components/artifacts/artifact-card";
import { ErrorBoundary } from "@/components/common/error-boundary";
import {
  TrendingUp, BarChart3, DollarSign, ArrowDownUp,
  Newspaper, AlertTriangle, Search, Target, Users, Bot, ClipboardList,
} from "lucide-react";

const CandlestickChartArtifact = dynamic(
  () =>
    import("@/components/artifacts/candlestick-chart").then((m) => ({
      default: m.CandlestickChartArtifact,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[400px] bg-muted rounded relative overflow-hidden">
        <div className="absolute bottom-0 left-0 right-0 h-3/4 flex items-end gap-1 px-4 pb-4">
          {Array.from({length: 20}).map((_, i) => (
            <div key={i} className="flex-1 flex flex-col items-center">
              <div className="w-px bg-muted-foreground/10" style={{height: `${20 + (i * 7 + 13) % 40}%`}} />
              <div className="w-full bg-muted-foreground/10 rounded-sm" style={{height: `${10 + (i * 11 + 7) % 30}%`}} />
              <div className="w-px bg-muted-foreground/10" style={{height: `${10 + (i * 5 + 3) % 20}%`}} />
            </div>
          ))}
        </div>
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-muted-foreground/5 to-transparent animate-pulse" />
      </div>
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
      <div className="h-[300px] bg-muted rounded relative overflow-hidden flex items-center justify-center">
        {/* 六边形轮廓圆形骨架 */}
        <svg viewBox="0 0 200 200" className="w-40 h-40 animate-pulse">
          <polygon
            points="100,20 175,60 175,140 100,180 25,140 25,60"
            fill="none"
            stroke="currentColor"
            className="text-white/[0.08]"
            strokeWidth="2"
          />
          <polygon
            points="100,50 150,75 150,125 100,150 50,125 50,75"
            fill="none"
            stroke="currentColor"
            className="text-white/[0.06]"
            strokeWidth="1.5"
          />
          <polygon
            points="100,80 125,90 125,110 100,120 75,110 75,90"
            fill="none"
            stroke="currentColor"
            className="text-white/[0.04]"
            strokeWidth="1"
          />
          <circle cx="100" cy="100" r="4" className="fill-white/[0.08]" />
        </svg>
      </div>
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
      <div className="h-[200px] bg-muted rounded relative overflow-hidden flex items-end justify-center gap-3 px-6 pb-4 pt-8">
        {/* 资金流向柱状图骨架：5根高低不同的竖条 */}
        {[65, 85, 45, 70, 55].map((h, i) => (
          <div
            key={i}
            className="flex-1 bg-white/[0.04] rounded-t animate-pulse"
            style={{ height: `${h}%` }}
          />
        ))}
      </div>
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
      <div className="h-[300px] bg-muted rounded relative overflow-hidden p-4 animate-pulse">
        {/* 投资者画像：4个并排卡片轮廓 */}
        <div className="grid grid-cols-4 gap-3 h-full">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white/[0.04] rounded-lg p-3 flex flex-col items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-white/[0.06]" />
              <div className="w-3/4 h-2.5 bg-white/[0.06] rounded" />
              <div className="w-full h-2 bg-white/[0.04] rounded" />
              <div className="w-2/3 h-2 bg-white/[0.04] rounded" />
              <div className="mt-auto w-full h-6 bg-white/[0.04] rounded" />
            </div>
          ))}
        </div>
      </div>
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
      <div className="h-[200px] bg-muted rounded relative overflow-hidden p-6 flex flex-col items-center justify-center gap-4 animate-pulse">
        {/* 决策卡：居中大文字 + 进度条 */}
        <div className="w-20 h-10 bg-white/[0.06] rounded-lg" />
        <div className="w-32 h-3 bg-white/[0.04] rounded" />
        <div className="w-48 h-2.5 bg-white/[0.04] rounded-full">
          <div className="w-1/2 h-full bg-white/[0.06] rounded-full" />
        </div>
      </div>
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
      <div className="h-[200px] bg-muted rounded relative overflow-hidden p-4 animate-pulse">
        {/* 技术面板：大数字 + 进度条 + 2x2网格 */}
        <div className="flex flex-col gap-3 h-full">
          <div className="w-24 h-8 bg-white/[0.06] rounded" />
          <div className="w-full h-2 bg-white/[0.04] rounded-full">
            <div className="w-2/3 h-full bg-white/[0.06] rounded-full" />
          </div>
          <div className="grid grid-cols-2 gap-2 flex-1">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-white/[0.04] rounded p-2 flex flex-col gap-1.5">
                <div className="w-1/2 h-2 bg-white/[0.06] rounded" />
                <div className="w-3/4 h-2.5 bg-white/[0.06] rounded" />
              </div>
            ))}
          </div>
        </div>
      </div>
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
      <div className="h-[150px] bg-muted rounded relative overflow-hidden p-4 animate-pulse">
        {/* 搜索结果：3个链接条 */}
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="w-4 h-4 rounded bg-white/[0.06] shrink-0" />
              <div className="flex-1 space-y-1.5">
                <div className="h-2.5 bg-white/[0.06] rounded" style={{ width: `${75 - i * 10}%` }} />
                <div className="h-2 bg-white/[0.04] rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      </div>
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
      <div className="h-[200px] bg-muted rounded relative overflow-hidden p-4 animate-pulse">
        {/* 基本面评分卡：圆形评分 + 3行指标条 */}
        <div className="flex gap-4 h-full items-center">
          <div className="w-20 h-20 rounded-full border-4 border-white/[0.08] shrink-0 flex items-center justify-center">
            <div className="w-10 h-5 bg-white/[0.06] rounded" />
          </div>
          <div className="flex-1 flex flex-col gap-2.5">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="space-y-1">
                <div className="w-16 h-2 bg-white/[0.06] rounded" />
                <div className="w-full h-2.5 bg-white/[0.04] rounded-full">
                  <div className="h-full bg-white/[0.06] rounded-full" style={{ width: `${60 + i * 15}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
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
      <div className="h-[300px] bg-muted rounded relative overflow-hidden p-4 flex flex-col items-center gap-4 animate-pulse">
        {/* 风险雷达：圆形 + 下方2行条 */}
        <svg viewBox="0 0 160 160" className="w-32 h-32">
          <circle cx="80" cy="80" r="60" fill="none" stroke="currentColor" className="text-white/[0.08]" strokeWidth="2" />
          <circle cx="80" cy="80" r="40" fill="none" stroke="currentColor" className="text-white/[0.06]" strokeWidth="1.5" />
          <circle cx="80" cy="80" r="20" fill="none" stroke="currentColor" className="text-white/[0.04]" strokeWidth="1" />
          <circle cx="80" cy="80" r="4" className="fill-white/[0.08]" />
        </svg>
        <div className="w-full space-y-2">
          <div className="w-3/4 h-2.5 bg-white/[0.04] rounded mx-auto" />
          <div className="w-1/2 h-2.5 bg-white/[0.04] rounded mx-auto" />
        </div>
      </div>
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
      <div className="h-[200px] bg-muted rounded relative overflow-hidden p-4 animate-pulse">
        {/* 新闻列表：3行文本骨架（标题+描述+时间） */}
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bg-white/[0.04] rounded p-3 space-y-2">
              <div className="h-3 bg-white/[0.06] rounded" style={{ width: `${80 - i * 8}%` }} />
              <div className="h-2 bg-white/[0.04] rounded w-full" />
              <div className="h-2 bg-white/[0.04] rounded w-20" />
            </div>
          ))}
        </div>
      </div>
    ),
  }
);

interface Props {
  artifact: Artifact;
}

export function ArtifactRenderer({ artifact }: Props) {
  return (
    <ErrorBoundary fallbackTitle={`"${artifact.title}" 渲染出错`}>
      <ArtifactCard title={artifact.title} icon={getArtifactIcon(artifact.artifact_type)} confidence={artifact.confidence}>
        {renderArtifactContent(artifact)}
      </ArtifactCard>
    </ErrorBoundary>
  );
}

function getArtifactIcon(type: string): ReactNode {
  const iconClass = "h-4 w-4";
  const icons: Record<string, ReactNode> = {
    candlestick_chart: <TrendingUp className={iconClass} />,
    technical_indicators: <BarChart3 className={iconClass} />,
    fundamental_metrics: <DollarSign className={iconClass} />,
    capital_flow_chart: <ArrowDownUp className={iconClass} />,
    news_feed: <Newspaper className={iconClass} />,
    risk_gauge: <AlertTriangle className={iconClass} />,
    search_results: <Search className={iconClass} />,
    decision_card: <Target className={iconClass} />,
    investor_consensus: <Users className={iconClass} />,
    investor_opinions: <Users className={iconClass} />,
    agent_pipeline: <Bot className={iconClass} />,
  };
  return icons[type] || <ClipboardList className={iconClass} />;
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
      // 后端直接传consensus对象作为data，需包装为 { consensus: data }
      return <InvestorPersonasArtifact data={data.consensus ? data : { consensus: data }} />;
    case "investor_opinions":
      // 后端直接传opinions对象（含buffett/munger等）作为data，需包装为 { opinions: data }
      return <InvestorPersonasArtifact data={data.opinions ? data : { opinions: data }} />;
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
