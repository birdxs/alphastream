// Input: 投资者共识数据（consensus + opinions），含巴菲特/芒格/林奇/达摩达兰四位投资者观点
// Output: 共识概要卡 + 四位投资者对比卡片 + 关键共识/分歧展示
// Pos: artifact-renderer.tsx 的子组件，investor_consensus 类型 Artifact 渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface InvestorOpinion {
  recommendation: string;
  confidence: number;
  reasoning: string;
  key_metrics?: Record<string, unknown>;
}

interface Props {
  data: {
    consensus?: {
      final_recommendation: string;
      consensus_confidence: string;
      consensus_confidence_score: number;
      consensus_reasoning: string;
      agreement_level: string;
      key_agreements?: string[];
      key_disagreements?: string[];
      weight_analysis?: string;
    };
    opinions?: {
      buffett?: InvestorOpinion;
      munger?: InvestorOpinion;
      lynch?: InvestorOpinion;
      damodaran?: InvestorOpinion;
    };
  };
}

const INVESTOR_META = {
  buffett: { name: "\u5DF4\u83F2\u7279", emoji: "\uD83C\uDFDB\uFE0F", style: "\u4EF7\u503C\u6295\u8D44", color: "blue" },
  munger: { name: "\u82BD\u683C", emoji: "\uD83E\uDDE0", style: "\u53CD\u5411\u601D\u7EF4", color: "purple" },
  lynch: { name: "\u6797\u5947", emoji: "\uD83D\uDCC8", style: "\u6210\u957F\u6295\u8D44", color: "green" },
  damodaran: { name: "\u8FBE\u6469\u8FBE\u5170", emoji: "\uD83D\uDCCA", style: "\u91CF\u5316\u4F30\u503C", color: "orange" },
};

export function InvestorPersonasArtifact({ data }: Props) {
  const { consensus, opinions } = data;

  const recColor = (rec: string) => {
    const r = rec?.toUpperCase();
    if (r === "BUY") return "bg-green-500/10 text-green-600 border-green-500/30";
    if (r === "SELL") return "bg-red-500/10 text-red-600 border-red-500/30";
    return "bg-yellow-500/10 text-yellow-600 border-yellow-500/30";
  };

  const recText = (rec: string) => {
    const r = rec?.toUpperCase();
    if (r === "BUY") return "\u4E70\u5165";
    if (r === "SELL") return "\u5356\u51FA";
    return "\u6301\u6709";
  };

  return (
    <div className="space-y-4">
      {/* 共识概要 */}
      {consensus && (
        <div className={`rounded-lg border p-4 ${recColor(consensus.final_recommendation)}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-lg font-bold">{recText(consensus.final_recommendation)}</span>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{consensus.agreement_level}</Badge>
              <span className="text-sm">
                \u7F6E\u4FE1\u5EA6 {(consensus.consensus_confidence_score * 100).toFixed(0)}%
              </span>
            </div>
          </div>
          <p className="text-sm">{consensus.consensus_reasoning}</p>
          {consensus.weight_analysis && (
            <p className="text-xs text-muted-foreground mt-2 italic">{consensus.weight_analysis}</p>
          )}
        </div>
      )}

      {/* 四位投资者卡片 */}
      <div className="grid grid-cols-2 gap-3">
        {opinions &&
          Object.entries(opinions).map(([key, opinion]) => {
            const meta = INVESTOR_META[key as keyof typeof INVESTOR_META];
            if (!meta || !opinion) return null;
            return (
              <Card key={key} className="overflow-hidden">
                <CardHeader className="pb-2 pt-3 px-3">
                  <CardTitle className="text-sm flex items-center justify-between">
                    <span>
                      {meta.emoji} {meta.name}
                    </span>
                    <Badge className={recColor(opinion.recommendation)} variant="outline">
                      {recText(opinion.recommendation)}
                    </Badge>
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">{meta.style}</p>
                </CardHeader>
                <CardContent className="px-3 pb-3">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="flex-1 bg-muted rounded-full h-1.5">
                      <div
                        className="bg-primary h-1.5 rounded-full"
                        style={{ width: `${opinion.confidence * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {(opinion.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs line-clamp-3">{opinion.reasoning}</p>
                </CardContent>
              </Card>
            );
          })}
      </div>

      {/* 关键共识/分歧 */}
      {consensus?.key_agreements && consensus.key_agreements.length > 0 && (
        <div className="text-sm space-y-1">
          <p className="font-medium text-green-600">{"\u2705"} \u4E00\u81F4\u8BA4\u540C</p>
          {consensus.key_agreements.map((a, i) => (
            <p key={i} className="text-xs text-muted-foreground pl-5">
              {"\u2022"} {a}
            </p>
          ))}
        </div>
      )}
      {consensus?.key_disagreements && consensus.key_disagreements.length > 0 && (
        <div className="text-sm space-y-1">
          <p className="font-medium text-orange-600">{"\u26A1"} \u4E3B\u8981\u5206\u6B67</p>
          {consensus.key_disagreements.map((d, i) => (
            <p key={i} className="text-xs text-muted-foreground pl-5">
              {"\u2022"} {d}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
