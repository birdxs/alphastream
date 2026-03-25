// Input: 技术分析数据（score/trend/rsi/macd/volume/recommendation/支撑阻力位）
// Output: 技术评分面板，含评分条、指标网格、价格支撑阻力展示
// Pos: artifact-renderer.tsx 的子组件，technical_indicators 类型 Artifact 渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Badge } from "@/components/ui/badge";

interface Props {
  data: {
    score?: number;
    trend?: string;
    rsi?: number;
    macd_signal?: string;
    volume_status?: string;
    recommendation?: string;
    support_level?: number;
    resistance_level?: number;
    price?: number;
    [key: string]: unknown;
  };
}

export function TechnicalPanelArtifact({ data }: Props) {
  const score = Number(data.score || 50);
  const scoreColor =
    score >= 80
      ? "text-green-500"
      : score >= 60
        ? "text-blue-500"
        : score >= 40
          ? "text-yellow-500"
          : "text-red-500";

  const indicators = [
    { label: "RSI", value: data.rsi, format: (v: number) => {
      const color = v > 70 ? 'text-red-500' : v < 30 ? 'text-green-500' : '';
      const label = v > 70 ? ' 超买' : v < 30 ? ' 超卖' : '';
      return <span className={color}>{v?.toFixed(1)}{label}</span>;
    }},
    { label: "MACD", value: data.macd_signal, format: (v: string) => {
      const icon = v === '金叉' ? '🔺' : v === '死叉' ? '🔻' : '';
      return <span>{icon} {v}</span>;
    }},
    { label: "\u8D8B\u52BF", value: data.trend },
    { label: "\u6210\u4EA4\u91CF", value: data.volume_status },
  ].filter((i) => i.value != null);

  return (
    <div className="space-y-3">
      {/* 评分 */}
      <div className="flex items-center justify-between">
        <div>
          <span className={`text-4xl font-bold font-mono ${scoreColor}`}>{score}</span>
          <span className="text-muted-foreground text-sm">/100</span>
        </div>
        {data.recommendation && (
          <Badge variant="outline" className="text-sm">
            {data.recommendation}
          </Badge>
        )}
      </div>

      {/* 评分条 */}
      <div className="w-full bg-muted rounded-full h-2.5">
        <div
          className={`h-2.5 rounded-full transition-all duration-700 ${
            score >= 80
              ? "bg-green-500"
              : score >= 60
                ? "bg-blue-500"
                : score >= 40
                  ? "bg-yellow-500"
                  : "bg-red-500"
          }`}
          style={{ width: `${score}%` }}
        />
      </div>

      {/* 指标网格 */}
      <div className="grid grid-cols-2 gap-2">
        {indicators.map(({ label, value, format }) => (
          <div key={label} className="flex justify-between items-center bg-muted/50 rounded px-3 py-2">
            <span className="text-xs text-muted-foreground">{label}</span>
            <span className="text-sm font-mono font-medium">
              {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
              {format ? (format as (v: any) => React.ReactNode)(value) : String(value)}
            </span>
          </div>
        ))}
      </div>

      {/* 价格&支撑阻力 */}
      {(data.price || data.support_level || data.resistance_level) && (
        <div className="flex justify-between text-sm pt-1 border-t">
          {data.support_level && (
            <span className="stock-down">\u652F\u6491 {data.support_level}</span>
          )}
          {data.price && <span className="font-bold">\u5F53\u524D {data.price}</span>}
          {data.resistance_level && (
            <span className="stock-up">\u963B\u529B {data.resistance_level}</span>
          )}
        </div>
      )}
    </div>
  );
}
