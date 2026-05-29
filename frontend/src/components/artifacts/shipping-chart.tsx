// Input: 航运大宗数据 (BDI时序/港口吞吐/AIS船舶快照)
// Output: BDI折线图(lightweight-charts) + 港口吞吐柱状图(Recharts) + AIS船舶实时计数
// Pos: artifact-renderer.tsx 子组件, shipping 类型 Artifact 渲染器
// 契约: 后端 shipping_adapter get_bdi_index/get_port_throughput/get_ais_vessels 输出 DataFrame → 序列化为 items[]
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useEffect, useRef } from "react";
import { createChart, ColorType, LineSeries, type IChartApi, type ISeriesApi, type LineData, type UTCTimestamp } from "lightweight-charts";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
} from "recharts";
import { SafeResponsiveContainer } from "@/components/charts/safe-responsive-container";
import { Ship, Anchor, Waves } from "lucide-react";

interface BDIPoint { date: string; value: number; indicator?: string; source?: string }
interface PortPoint { date: string; port: string; value: number; unit?: string; indicator?: string }
interface AISVessel { mmsi?: string | number; name?: string; ship_type?: string; lat?: number; lon?: number; sog?: number }

interface Props {
  data: {
    bdi_series?: BDIPoint[];
    port_throughput?: PortPoint[];
    ais_vessels?: AISVessel[];
    ais_count?: number;
    port_name?: string;
    [key: string]: unknown;
  };
}

// Demo 数据 (独立渲染预览 + 后端空降级兜底)
const DEMO_DATA: Required<Pick<Props["data"], "bdi_series" | "port_throughput" | "ais_vessels" | "ais_count" | "port_name">> = {
  bdi_series: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 86400000).toISOString().slice(0, 10),
    value: 1200 + Math.round(Math.sin(i / 4) * 120 + i * 6),
    indicator: "BDI",
  })),
  port_throughput: [
    { date: "2026-03", port: "上海", value: 4250, unit: "万TEU" },
    { date: "2026-03", port: "宁波", value: 3180, unit: "万TEU" },
    { date: "2026-03", port: "青岛", value: 2560, unit: "万TEU" },
    { date: "2026-03", port: "深圳", value: 2890, unit: "万TEU" },
  ],
  ais_vessels: [],
  ais_count: 12480,
  port_name: "主要港口",
};

export function ShippingChartArtifact({ data }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const bdiSeries = Array.isArray(data.bdi_series) && data.bdi_series.length > 0 ? data.bdi_series : DEMO_DATA.bdi_series;
  const portThroughput = Array.isArray(data.port_throughput) && data.port_throughput.length > 0 ? data.port_throughput : DEMO_DATA.port_throughput;
  const aisCount = typeof data.ais_count === "number" ? data.ais_count : (Array.isArray(data.ais_vessels) ? data.ais_vessels.length : DEMO_DATA.ais_count);

  useEffect(() => {
    if (!chartContainerRef.current) return;
    const chart = createChart(chartContainerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8888A0", fontSize: 10 },
      grid: { vertLines: { color: "rgba(255,255,255,0.04)" }, horzLines: { color: "rgba(255,255,255,0.04)" } },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
      timeScale: { borderColor: "rgba(255,255,255,0.08)", timeVisible: false },
      width: chartContainerRef.current.clientWidth,
      height: 180,
      crosshair: { mode: 1 },
    });
    const series = chart.addSeries(LineSeries, { color: "#6B5EE4", lineWidth: 2, priceLineVisible: false });
    const lineData: LineData[] = bdiSeries
      .filter(p => p.date && typeof p.value === "number")
      .map(p => ({ time: (Math.floor(new Date(p.date).getTime() / 1000)) as UTCTimestamp, value: p.value }))
      .sort((a, b) => (a.time as number) - (b.time as number));
    series.setData(lineData);
    chart.timeScale().fitContent();
    chartRef.current = chart;
    seriesRef.current = series;

    const onResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [bdiSeries]);

  const lastBdi = bdiSeries[bdiSeries.length - 1]?.value ?? 0;
  const firstBdi = bdiSeries[0]?.value ?? lastBdi;
  const pct = firstBdi > 0 ? ((lastBdi - firstBdi) / firstBdi) * 100 : 0;
  const bdiTrendColor = pct >= 0 ? "text-[#46BEA3]" : "text-[#FF8767]";

  return (
    <div className="space-y-4">
      {/* 顶部摘要 */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-foreground/[0.03] dark:bg-white/[0.03] rounded-lg p-2.5 border-b border-foreground/[0.06] dark:border-white/[0.06]">
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mb-1">
            <Waves className="h-3 w-3" /> BDI 指数
          </div>
          <div className="text-lg font-mono font-bold text-foreground dark:text-[#F0F0F5]">{Math.round(lastBdi)}</div>
          <div className={`text-[10px] font-mono ${bdiTrendColor}`}>{pct >= 0 ? "+" : ""}{pct.toFixed(1)}% 近30日</div>
        </div>
        <div className="bg-foreground/[0.03] dark:bg-white/[0.03] rounded-lg p-2.5 border-b border-foreground/[0.06] dark:border-white/[0.06]">
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mb-1">
            <Anchor className="h-3 w-3" /> 港口吞吐
          </div>
          <div className="text-lg font-mono font-bold text-foreground dark:text-[#F0F0F5]">{portThroughput.length}</div>
          <div className="text-[10px] text-muted-foreground">港口采样</div>
        </div>
        <div className="bg-foreground/[0.03] dark:bg-white/[0.03] rounded-lg p-2.5 border-b border-foreground/[0.06] dark:border-white/[0.06]">
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mb-1">
            <Ship className="h-3 w-3" /> AIS 船舶
          </div>
          <div className="text-lg font-mono font-bold text-[#6B5EE4]">{aisCount.toLocaleString()}</div>
          <div className="text-[10px] text-muted-foreground">实时快照</div>
        </div>
      </div>

      {/* BDI 折线图 */}
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1.5">波罗的海干散货指数 (BDI) · 近30日</div>
        <div ref={chartContainerRef} className="w-full" style={{ height: 180 }} />
      </div>

      {/* 港口吞吐柱状图 */}
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1.5">主要港口月度吞吐量</div>
        <div style={{ height: 160 }}>
          <SafeResponsiveContainer width="100%" height="100%">
            <BarChart data={portThroughput} margin={{ top: 6, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="port" tick={{ fontSize: 10, fill: "#8888A0" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#8888A0" }} axisLine={false} tickLine={false} width={36} />
              <Tooltip
                cursor={{ fill: "rgba(107,94,228,0.08)" }}
                contentStyle={{ background: "rgba(20,20,43,0.95)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, fontSize: 11 }}
                labelStyle={{ color: "#F0F0F5" }}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {portThroughput.map((_, i) => (
                  <Cell key={i} fill={`url(#shipping-grad-${i % 2})`} />
                ))}
              </Bar>
              <defs>
                <linearGradient id="shipping-grad-0" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6B5EE4" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#3737CC" stopOpacity={0.5} />
                </linearGradient>
                <linearGradient id="shipping-grad-1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#46BEA3" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#2A8F7D" stopOpacity={0.5} />
                </linearGradient>
              </defs>
            </BarChart>
          </SafeResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
