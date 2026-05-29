// Input: 招聘信号数据 (公司近期岗位数量/技能分布/月度趋势)
// Output: 招聘趋势折线 + 技能饼图 + 扩张预警指示器
// Pos: artifact-renderer.tsx 子组件, hiring 类型 Artifact 渲染器
// 契约: 后端 jobs_adapter.search_jobs/get_company_postings 返回 DataFrame → items[{title,company,tags,created_at}]
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { SafeResponsiveContainer } from "@/components/charts/safe-responsive-container";
import { Briefcase, TrendingUp, AlertCircle } from "lucide-react";

interface JobItem {
  title?: string;
  company?: string;
  location?: string;
  tags?: string;
  url?: string;
  created_at?: string;
  source?: string;
}

interface MonthlyTrend { month: string; count: number }
interface SkillDist { name: string; value: number }

interface Props {
  data: {
    company?: string;
    total_postings?: number;
    items?: JobItem[];
    monthly_trend?: MonthlyTrend[];
    skill_distribution?: SkillDist[];
    expansion_level?: "low" | "medium" | "high";
    yoy_change?: number;      // 同比变化 %
    [key: string]: unknown;
  };
}

const SKILL_COLORS = ["#6B5EE4", "#46BEA3", "#F59E0B", "#3737CC", "#FF8767", "#8888A0"];

const DEMO_DATA: Props["data"] = {
  company: "Apple Inc.",
  total_postings: 268,
  yoy_change: 42,
  expansion_level: "high",
  monthly_trend: [
    { month: "2025-10", count: 120 },
    { month: "2025-11", count: 145 },
    { month: "2025-12", count: 158 },
    { month: "2026-01", count: 198 },
    { month: "2026-02", count: 225 },
    { month: "2026-03", count: 268 },
  ],
  skill_distribution: [
    { name: "AI/ML", value: 82 },
    { name: "iOS/Swift", value: 56 },
    { name: "硬件工程", value: 44 },
    { name: "Cloud/基础设施", value: 38 },
    { name: "芯片设计", value: 28 },
    { name: "其他", value: 20 },
  ],
};

// 从 items 派生月度趋势 (回退用)
function deriveMonthlyTrend(items: JobItem[]): MonthlyTrend[] {
  const bucket: Record<string, number> = {};
  items.forEach(it => {
    const d = it.created_at;
    if (!d) return;
    const m = String(d).slice(0, 7);
    bucket[m] = (bucket[m] || 0) + 1;
  });
  return Object.entries(bucket).sort(([a], [b]) => a.localeCompare(b)).map(([month, count]) => ({ month, count }));
}

// 从 tags 派生技能分布
function deriveSkillDist(items: JobItem[]): SkillDist[] {
  const bucket: Record<string, number> = {};
  items.forEach(it => {
    (it.tags || "").split(",").map(s => s.trim()).filter(Boolean).forEach(t => {
      bucket[t] = (bucket[t] || 0) + 1;
    });
  });
  const arr = Object.entries(bucket).sort(([, a], [, b]) => b - a).slice(0, 6).map(([name, value]) => ({ name, value }));
  return arr;
}

export function HiringSignalArtifact({ data }: Props) {
  const effective: Props["data"] = useMemo(() => {
    const hasData = data && ((data.items && data.items.length > 0) || (data.monthly_trend && data.monthly_trend.length > 0));
    if (!hasData) return DEMO_DATA;
    const items = Array.isArray(data.items) ? data.items : [];
    return {
      ...data,
      monthly_trend: data.monthly_trend && data.monthly_trend.length > 0 ? data.monthly_trend : deriveMonthlyTrend(items),
      skill_distribution: data.skill_distribution && data.skill_distribution.length > 0 ? data.skill_distribution : deriveSkillDist(items),
      total_postings: typeof data.total_postings === "number" ? data.total_postings : items.length,
    };
  }, [data]);

  const total = effective.total_postings ?? 0;
  const yoy = typeof effective.yoy_change === "number" ? effective.yoy_change : 0;
  const level = effective.expansion_level || (yoy > 30 ? "high" : yoy > 10 ? "medium" : "low");

  const levelStyle = level === "high"
    ? { bg: "bg-[#46BEA3]/10", text: "text-[#46BEA3]", label: "强扩张" }
    : level === "medium"
    ? { bg: "bg-[#F59E0B]/10", text: "text-[#F59E0B]", label: "温和扩张" }
    : { bg: "bg-[#8888A0]/10", text: "text-[#8888A0]", label: "平稳" };

  return (
    <div className="space-y-4">
      {/* 顶部信号 */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-foreground/[0.03] dark:bg-white/[0.03] rounded-lg p-2.5 border-b border-foreground/[0.06] dark:border-white/[0.06]">
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mb-1">
            <Briefcase className="h-3 w-3" /> 在招岗位
          </div>
          <div className="text-lg font-mono font-bold text-foreground dark:text-[#F0F0F5]">{total.toLocaleString()}</div>
          <div className="text-[10px] text-muted-foreground truncate">{effective.company || "—"}</div>
        </div>
        <div className="bg-foreground/[0.03] dark:bg-white/[0.03] rounded-lg p-2.5 border-b border-foreground/[0.06] dark:border-white/[0.06]">
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mb-1">
            <TrendingUp className="h-3 w-3" /> 同比变化
          </div>
          <div className={`text-lg font-mono font-bold ${yoy >= 0 ? "text-[#46BEA3]" : "text-[#FF8767]"}`}>
            {yoy >= 0 ? "+" : ""}{yoy.toFixed(0)}%
          </div>
          <div className="text-[10px] text-muted-foreground">较去年同期</div>
        </div>
        <div className={`${levelStyle.bg} rounded-lg p-2.5 border-b border-foreground/[0.06] dark:border-white/[0.06]`}>
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mb-1">
            <AlertCircle className="h-3 w-3" /> 扩张信号
          </div>
          <div className={`text-lg font-bold ${levelStyle.text}`}>{levelStyle.label}</div>
          <div className="text-[10px] text-muted-foreground">Jobs proxy</div>
        </div>
      </div>

      {/* 招聘趋势折线 */}
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1.5">招聘数量月度趋势</div>
        <div style={{ height: 180 }}>
          <SafeResponsiveContainer width="100%" height="100%">
            <LineChart data={effective.monthly_trend || []} margin={{ top: 6, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#8888A0" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#8888A0" }} axisLine={false} tickLine={false} width={36} />
              <Tooltip
                cursor={{ stroke: "rgba(107,94,228,0.3)", strokeWidth: 1 }}
                contentStyle={{ background: "rgba(20,20,43,0.95)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, fontSize: 11 }}
                labelStyle={{ color: "#F0F0F5" }}
              />
              <Line type="monotone" dataKey="count" stroke="#6B5EE4" strokeWidth={2} dot={{ r: 3, fill: "#6B5EE4" }} activeDot={{ r: 5 }} />
            </LineChart>
          </SafeResponsiveContainer>
        </div>
      </div>

      {/* 技能分布饼图 */}
      {(effective.skill_distribution && effective.skill_distribution.length > 0) && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1.5">按技能分布</div>
          <div style={{ height: 200 }}>
            <SafeResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={effective.skill_distribution}
                  dataKey="value"
                  nameKey="name"
                  cx="40%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={70}
                  paddingAngle={2}
                >
                  {effective.skill_distribution.map((_, i) => (
                    <Cell key={i} fill={SKILL_COLORS[i % SKILL_COLORS.length]} stroke="rgba(10,10,26,0.6)" strokeWidth={1.5} />
                  ))}
                </Pie>
                <Legend
                  layout="vertical"
                  align="right"
                  verticalAlign="middle"
                  iconSize={8}
                  wrapperStyle={{ fontSize: 10, color: "#8888A0" }}
                />
                <Tooltip
                  contentStyle={{ background: "rgba(20,20,43,0.95)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, fontSize: 11 }}
                  labelStyle={{ color: "#F0F0F5" }}
                />
              </PieChart>
            </SafeResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
