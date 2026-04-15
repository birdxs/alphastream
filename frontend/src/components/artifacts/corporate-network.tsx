// Input: 公司股权关系网络 (父/子/董事会) + 司法管辖区
// Output: 中心公司卡片 + 父公司/子公司/董事会分栏列表 + 司法管辖区标记
// Pos: artifact-renderer.tsx 子组件, corporate_network 类型 Artifact 渲染器
// 契约: 后端 corporate_adapter.get_company_network 返回 {company_id, parents[], children[], officers[]}
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Building2, ArrowUp, ArrowDown, Users, MapPin, ExternalLink } from "lucide-react";

interface RelatedEntity {
  name?: string;
  jurisdiction_code?: string;
  company_number?: string;
}

interface Officer {
  name?: string;
  position?: string;
  start_date?: string;
  end_date?: string;
}

interface Props {
  data: {
    company_id?: string;
    company_name?: string;
    jurisdiction_code?: string;
    incorporation_date?: string;
    current_status?: string;
    parents?: RelatedEntity[];
    children?: RelatedEntity[];
    officers?: Officer[];
    opencorporates_url?: string;
    [key: string]: unknown;
  };
}

const DEMO_DATA: Props["data"] = {
  company_id: "us_ca/C0806592",
  company_name: "Apple Inc.",
  jurisdiction_code: "us_ca",
  incorporation_date: "1977-01-03",
  current_status: "Active",
  parents: [],
  children: [
    { name: "Apple Operations International Ltd", jurisdiction_code: "ie", company_number: "470672" },
    { name: "Apple Europe Ltd", jurisdiction_code: "gb", company_number: "04905014" },
    { name: "Apple Services LATAM LLC", jurisdiction_code: "us_fl", company_number: "L16000050829" },
    { name: "Beats Electronics, LLC", jurisdiction_code: "us_de", company_number: "4728964" },
  ],
  officers: [
    { name: "Tim Cook", position: "CEO", start_date: "2011-08-24" },
    { name: "Luca Maestri", position: "CFO", start_date: "2014-05-30" },
    { name: "Arthur D. Levinson", position: "Chairman", start_date: "2011-11-15" },
    { name: "Katherine L. Adams", position: "General Counsel", start_date: "2017-10-01" },
  ],
};

// 司法管辖区代码 → 可读短名 + Emoji 国旗
const JURISDICTION_LABELS: Record<string, { label: string; flag: string }> = {
  us_ca: { label: "加州", flag: "🇺🇸" },
  us_de: { label: "特拉华", flag: "🇺🇸" },
  us_ny: { label: "纽约", flag: "🇺🇸" },
  us_fl: { label: "佛州", flag: "🇺🇸" },
  us: { label: "美国", flag: "🇺🇸" },
  gb: { label: "英国", flag: "🇬🇧" },
  ie: { label: "爱尔兰", flag: "🇮🇪" },
  cn: { label: "中国", flag: "🇨🇳" },
  hk: { label: "香港", flag: "🇭🇰" },
  jp: { label: "日本", flag: "🇯🇵" },
  sg: { label: "新加坡", flag: "🇸🇬" },
  de: { label: "德国", flag: "🇩🇪" },
  ky: { label: "开曼", flag: "🇰🇾" },
  bm: { label: "百慕大", flag: "🇧🇲" },
};

function JurisdictionBadge({ code }: { code?: string }) {
  if (!code) return null;
  const key = code.toLowerCase();
  const meta = JURISDICTION_LABELS[key] || { label: code.toUpperCase(), flag: "🏳" };
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-foreground/[0.04] dark:bg-white/[0.05] border border-foreground/[0.06] dark:border-white/[0.08] text-muted-foreground font-mono">
      <span className="text-[11px] leading-none">{meta.flag}</span>
      <span>{meta.label}</span>
    </span>
  );
}

function EntityRow({ entity, icon: Icon }: { entity: RelatedEntity; icon: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="flex items-center justify-between gap-2 py-1.5 px-2 rounded-lg hover:bg-foreground/[0.03] dark:hover:bg-white/[0.03] transition-colors border-b border-foreground/[0.04] dark:border-white/[0.04] last:border-0">
      <div className="flex items-center gap-2 min-w-0">
        <Icon className="h-3 w-3 text-[#6B5EE4] shrink-0" />
        <span className="text-xs text-foreground/90 dark:text-[#E0E0F0] truncate">{entity.name || "—"}</span>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        <JurisdictionBadge code={entity.jurisdiction_code} />
        {entity.company_number && (
          <span className="text-[10px] font-mono text-muted-foreground">#{entity.company_number}</span>
        )}
      </div>
    </div>
  );
}

export function CorporateNetworkArtifact({ data }: Props) {
  const effective: Props["data"] = (data && ((data.parents?.length ?? 0) + (data.children?.length ?? 0) + (data.officers?.length ?? 0) > 0 || data.company_name))
    ? data
    : DEMO_DATA;

  const parents = effective.parents || [];
  const children = effective.children || [];
  const officers = effective.officers || [];

  return (
    <div className="space-y-3">
      {/* 中心公司卡片 */}
      <div className="relative overflow-hidden rounded-xl p-3 bg-gradient-to-br from-[#3737CC]/10 to-[#6B5EE4]/5 border border-[#3737CC]/20">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#3737CC] to-[#6B5EE4] flex items-center justify-center shadow-lg shrink-0">
              <Building2 className="h-5 w-5 text-white" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-bold text-foreground dark:text-[#F0F0F5] truncate">
                {effective.company_name || effective.company_id || "—"}
              </div>
              <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                <JurisdictionBadge code={effective.jurisdiction_code} />
                {effective.current_status && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                    effective.current_status.toLowerCase() === "active"
                      ? "bg-[#46BEA3]/10 text-[#46BEA3]"
                      : "bg-[#8888A0]/10 text-muted-foreground"
                  }`}>
                    {effective.current_status}
                  </span>
                )}
                {effective.incorporation_date && (
                  <span className="text-[10px] text-muted-foreground font-mono">
                    成立 {effective.incorporation_date}
                  </span>
                )}
              </div>
            </div>
          </div>
          {effective.opencorporates_url && (
            <a
              href={effective.opencorporates_url}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 text-[10px] text-[#6B5EE4] hover:text-[#3737CC] flex items-center gap-0.5"
            >
              OpenCorp <ExternalLink className="h-2.5 w-2.5" />
            </a>
          )}
        </div>
      </div>

      {/* 父公司 */}
      {parents.length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1.5">
            <ArrowUp className="h-3 w-3 text-[#F59E0B]" /> 母公司 / 控股实体 ({parents.length})
          </div>
          <div className="bg-foreground/[0.02] dark:bg-white/[0.02] rounded-lg border border-foreground/[0.06] dark:border-white/[0.06] overflow-hidden">
            {parents.map((p, i) => <EntityRow key={i} entity={p} icon={ArrowUp} />)}
          </div>
        </div>
      )}

      {/* 子公司 */}
      {children.length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1.5">
            <ArrowDown className="h-3 w-3 text-[#46BEA3]" /> 子公司 ({children.length})
          </div>
          <div className="bg-foreground/[0.02] dark:bg-white/[0.02] rounded-lg border border-foreground/[0.06] dark:border-white/[0.06] overflow-hidden max-h-60 overflow-y-auto">
            {children.map((c, i) => <EntityRow key={i} entity={c} icon={ArrowDown} />)}
          </div>
        </div>
      )}

      {/* 董事会 / 高管 */}
      {officers.length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1.5">
            <Users className="h-3 w-3 text-[#6B5EE4]" /> 董事会 / 高管 ({officers.length})
          </div>
          <div className="bg-foreground/[0.02] dark:bg-white/[0.02] rounded-lg border border-foreground/[0.06] dark:border-white/[0.06] overflow-hidden max-h-60 overflow-y-auto">
            {officers.map((o, i) => (
              <div key={i} className="flex items-center justify-between gap-2 py-1.5 px-2 border-b border-foreground/[0.04] dark:border-white/[0.04] last:border-0 hover:bg-foreground/[0.03] dark:hover:bg-white/[0.03] transition-colors">
                <div className="flex items-center gap-2 min-w-0">
                  <MapPin className="h-3 w-3 text-[#6B5EE4] shrink-0" />
                  <span className="text-xs text-foreground/90 dark:text-[#E0E0F0] truncate">{o.name || "—"}</span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#3737CC]/10 text-[#6B5EE4] font-mono">{o.position || "—"}</span>
                  {o.start_date && (
                    <span className="text-[10px] text-muted-foreground font-mono">{o.start_date}{o.end_date ? ` – ${o.end_date}` : ""}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {parents.length === 0 && children.length === 0 && officers.length === 0 && (
        <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
          <Building2 className="h-8 w-8 mb-2 opacity-40" />
          <p className="text-xs">暂无股权关系数据</p>
        </div>
      )}
    </div>
  );
}
