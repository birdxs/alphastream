// Input: ESG 评分数据 (综合/E/S/G分 + 多源对比 + SEC气候披露)
// Output: E/S/G 三维雷达 + 综合评分头部 + 多源评级对比表 + 气候披露标签
// Pos: artifact-renderer.tsx 子组件, esg 类型 Artifact 渲染器
// 契约: 后端 esg_adapter.get_esg_score/get_climate_disclosure 输出, 字段 esg_score/e_score/s_score/g_score/grade/source
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from "recharts";
import { SafeResponsiveContainer } from "@/components/charts/safe-responsive-container";
import { Badge } from "@/components/ui/badge";
import { Leaf, Users2, Scale, FileText } from "lucide-react";

interface ESGSourceRow {
  source?: string;
  ticker?: string;
  company?: string;
  esg_score?: number | null;
  e_score?: number | null;
  s_score?: number | null;
  g_score?: number | null;
  grade?: string | null;
  as_of?: string | null;
}

interface ClimateDisclosure {
  tag?: string;
  label?: string;
  filing_date?: string;
  url?: string;
}

interface Props {
  data: {
    ticker?: string;
    company?: string;
    primary?: ESGSourceRow;       // 主评分 (通常取 esgbook)
    esg_score?: number | null;    // 顶层扁平
    e_score?: number | null;
    s_score?: number | null;
    g_score?: number | null;
    grade?: string | null;
    source?: string;
    as_of?: string | null;
    sources?: ESGSourceRow[];     // 多源对比
    climate_disclosures?: ClimateDisclosure[];
    [key: string]: unknown;
  };
}

const DEMO_DATA: Props["data"] = {
  ticker: "AAPL",
  company: "Apple Inc.",
  esg_score: 72, e_score: 68, s_score: 75, g_score: 74, grade: "A", source: "esgbook", as_of: "2026-01",
  sources: [
    { source: "esgbook", esg_score: 72, grade: "A", as_of: "2026-01" },
    { source: "cdp", esg_score: 65, grade: "A-", as_of: "2025" },
    { source: "bcorp", esg_score: 58, grade: "B", as_of: "2025-06" },
    { source: "cufe", esg_score: 70, grade: "绿B+", as_of: "2025-12" },
  ],
  climate_disclosures: [
    { tag: "Scope 1+2", label: "范围1+2披露", filing_date: "2026-02-15" },
    { tag: "TCFD", label: "TCFD 框架", filing_date: "2026-01-20" },
    { tag: "Net-Zero", label: "2030净零目标", filing_date: "2025-11-10" },
  ],
};

export function ESGScorecardArtifact({ data }: Props) {
  const effective: Props["data"] = data && (data.esg_score != null || (data.sources && data.sources.length > 0))
    ? data
    : DEMO_DATA;

  const esg = effective.primary?.esg_score ?? effective.esg_score ?? null;
  const e = effective.primary?.e_score ?? effective.e_score ?? null;
  const s = effective.primary?.s_score ?? effective.s_score ?? null;
  const g = effective.primary?.g_score ?? effective.g_score ?? null;
  const grade = effective.primary?.grade ?? effective.grade ?? "--";
  const displayScore = typeof esg === "number" ? Math.round(esg) : null;

  const radarData = [
    { dim: "环境 E", score: typeof e === "number" ? e : 0 },
    { dim: "社会 S", score: typeof s === "number" ? s : 0 },
    { dim: "治理 G", score: typeof g === "number" ? g : 0 },
  ];

  const sources = Array.isArray(effective.sources) ? effective.sources : [];
  const climate = Array.isArray(effective.climate_disclosures) ? effective.climate_disclosures : [];

  const scoreColor = displayScore == null
    ? "from-[#555570] to-[#8888A0]"
    : displayScore >= 70 ? "from-[#46BEA3] to-[#2A8F7D]"
    : displayScore >= 40 ? "from-[#F59E0B] to-[#D97706]"
    : "from-[#FF8767] to-[#E05B3E]";

  return (
    <div className="space-y-4">
      {/* 综合评分头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${scoreColor} flex items-center justify-center shadow-lg`}>
            <span className="text-2xl font-bold font-mono text-white">{displayScore ?? "--"}</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold text-foreground dark:text-[#F0F0F5]">ESG 综合评分</span>
              <Badge variant="outline" className="text-[10px] font-mono">{grade || "--"}</Badge>
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">
              {effective.company || effective.ticker || "—"} · 来源 {effective.primary?.source || effective.source || "—"}
              {effective.as_of && ` · ${effective.as_of}`}
            </div>
          </div>
        </div>
      </div>

      {/* E/S/G 三维雷达 */}
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1.5">
          <Leaf className="h-3 w-3 text-[#46BEA3]" /> E/S/G 三维
        </div>
        <div style={{ height: 200 }}>
          <SafeResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} margin={{ top: 10, right: 20, left: 20, bottom: 0 }}>
              <PolarGrid stroke="rgba(255,255,255,0.08)" />
              <PolarAngleAxis dataKey="dim" tick={{ fontSize: 11, fill: "#8888A0" }} />
              <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 9, fill: "#555570" }} axisLine={false} />
              <Radar dataKey="score" stroke="#6B5EE4" fill="#6B5EE4" fillOpacity={0.35} />
            </RadarChart>
          </SafeResponsiveContainer>
        </div>
        <div className="grid grid-cols-3 gap-2 mt-1">
          {[{ k: "E", v: e, cls: "text-[#46BEA3]", icon: Leaf }, { k: "S", v: s, cls: "text-[#6B5EE4]", icon: Users2 }, { k: "G", v: g, cls: "text-[#F59E0B]", icon: Scale }].map(it => (
            <div key={it.k} className="bg-foreground/[0.03] dark:bg-white/[0.03] rounded-lg p-2 text-center border-b border-foreground/[0.06] dark:border-white/[0.06]">
              <div className="flex items-center justify-center gap-1 text-[10px] text-muted-foreground">
                <it.icon className={`h-3 w-3 ${it.cls}`} /> {it.k}
              </div>
              <div className={`text-sm font-mono font-bold ${it.cls}`}>
                {typeof it.v === "number" ? it.v.toFixed(0) : "--"}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 多源评级对比表 */}
      {sources.length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1.5">多源评级对比</div>
          <div className="rounded-lg border border-foreground/[0.06] dark:border-white/[0.06] overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-foreground/[0.03] dark:bg-white/[0.03]">
                <tr className="text-[10px] text-muted-foreground">
                  <th className="text-left px-2.5 py-1.5 font-medium">来源</th>
                  <th className="text-right px-2.5 py-1.5 font-medium">综合分</th>
                  <th className="text-center px-2.5 py-1.5 font-medium">评级</th>
                  <th className="text-right px-2.5 py-1.5 font-medium">截至</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((row, i) => (
                  <tr key={i} className="border-t border-foreground/[0.04] dark:border-white/[0.04] hover:bg-foreground/[0.02] dark:hover:bg-white/[0.02]">
                    <td className="px-2.5 py-1.5 text-foreground/90 dark:text-[#E0E0F0]">{row.source || "—"}</td>
                    <td className="px-2.5 py-1.5 text-right font-mono">{row.esg_score != null ? Number(row.esg_score).toFixed(0) : "--"}</td>
                    <td className="px-2.5 py-1.5 text-center font-mono text-[10px]">
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-[#3737CC]/10 text-[#6B5EE4]">{row.grade || "--"}</span>
                    </td>
                    <td className="px-2.5 py-1.5 text-right text-muted-foreground font-mono text-[10px]">{row.as_of || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SEC 气候披露标签 */}
      {climate.length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1.5">
            <FileText className="h-3 w-3" /> SEC 气候披露
          </div>
          <div className="flex flex-wrap gap-1.5">
            {climate.map((c, i) => (
              <span key={i} className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] bg-[#46BEA3]/10 border border-[#46BEA3]/20 text-[#46BEA3]">
                <span className="font-mono font-medium">{c.tag || "--"}</span>
                {c.label && <span className="text-[#46BEA3]/80">{c.label}</span>}
                {c.filing_date && <span className="text-muted-foreground font-mono">{c.filing_date}</span>}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
