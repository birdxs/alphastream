// Input: OHLCV数据数组、股票代码、均线指标
// Output: TradingView Lightweight Charts K线图（含成交量、MA均线、时间范围切换、十字线OHLCV信息条）
// Pos: artifact-renderer.tsx的子组件，candlestick_chart类型Artifact渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  ColorType,
  type IChartApi,
  type CandlestickData,
  type Time,
} from "lightweight-charts";
import { useThemeStore } from "@/lib/stores/theme-store";

interface OHLCVData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  amount?: number;
}

interface Props {
  data: {
    ohlcv?: OHLCVData[];
    stock_code?: string;
    stock_name?: string;
    indicators?: {
      ma5?: number[];
      ma20?: number[];
      ma60?: number[];
    };
    [key: string]: unknown;
  };
  onTimeRangeChange?: (days: string) => void;
}

const TIME_RANGES = [
  { label: '1M', days: '30' },
  { label: '3M', days: '90' },
  { label: '6M', days: '180' },
  { label: '1Y', days: '365' },
  { label: '全部', days: '0' },
];

export function CandlestickChartArtifact({ data, onTimeRangeChange }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);
  const theme = useThemeStore(s => s.theme);
  const stockColorScheme = useThemeStore(s => s.stockColorScheme);
  const [timeRange, setTimeRange] = useState('120');
  const [drawMode, setDrawMode] = useState<'none' | 'trendline'>('none');
  const [crosshairData, setCrosshairData] = useState<{
    time: string; open: number; high: number; low: number; close: number; volume?: number;
  } | null>(null);

  // 根据时间范围过滤数据
  const filteredData = timeRange === '0'
    ? data.ohlcv
    : data.ohlcv?.slice(-Number(timeRange));

  // Effect 1: 仅在data变化时创建/重建图表
  useEffect(() => {
    if (!chartRef.current || !filteredData?.length) return;

    // 涨跌颜色（创建时使用当前值）
    const upColor = stockColorScheme === "cn" ? "#ef4444" : "#22c55e";
    const downColor = stockColorScheme === "cn" ? "#22c55e" : "#ef4444";

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 400,
      layout: {
        background: {
          type: ColorType.Solid,
          color: theme === "dark" ? "#0A0A1A" : "#ffffff",
        },
        textColor: theme === "dark" ? "#8888A0" : "#374151",
      },
      grid: {
        vertLines: { color: theme === "dark" ? "rgba(255,255,255,0.04)" : "#e5e7eb" },
        horzLines: { color: theme === "dark" ? "rgba(255,255,255,0.04)" : "#e5e7eb" },
      },
      crosshair: { mode: 0 },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true, axisDoubleClickReset: true },
      timeScale: {
        borderColor: theme === "dark" ? "rgba(255,255,255,0.08)" : "#d1d5db",
      },
    });

    // K线系列（v5 API）
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor,
      downColor,
      borderUpColor: upColor,
      borderDownColor: downColor,
      wickUpColor: upColor,
      wickDownColor: downColor,
    });

    const candleData: CandlestickData<Time>[] = filteredData.map((d) => ({
      time: d.date as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    candleSeries.setData(candleData);

    // 成交量（兼容volume和amount字段）
    if (filteredData.some((d) => d.volume || d.amount)) {
      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeries.setData(
        filteredData.map((d) => ({
          time: d.date as Time,
          value: d.volume || d.amount || 0,
          color: d.close >= d.open ? "rgba(70,190,163,0.5)" : "rgba(255,135,103,0.5)",
        }))
      );
    }

    // MA均线 — 需要对齐到filteredData的索引范围
    const offset = (data.ohlcv?.length || 0) - filteredData.length;
    if (data.indicators?.ma5) {
      const ma5Series = chart.addSeries(LineSeries, {
        color: "#F59E0B",
        lineWidth: 1,
      });
      ma5Series.setData(
        data.indicators.ma5
          .slice(offset)
          .map((v, i) => ({
            time: filteredData[i]?.date as Time,
            value: v,
          }))
          .filter((d) => d.value > 0)
      );
    }
    if (data.indicators?.ma20) {
      const ma20Series = chart.addSeries(LineSeries, {
        color: "#3737CC",
        lineWidth: 1,
      });
      ma20Series.setData(
        data.indicators.ma20
          .slice(offset)
          .map((v, i) => ({
            time: filteredData[i]?.date as Time,
            value: v,
          }))
          .filter((d) => d.value > 0)
      );
    }
    if (data.indicators?.ma60) {
      const ma60Series = chart.addSeries(LineSeries, {
        color: "#6B5EE4",
        lineWidth: 1,
      });
      ma60Series.setData(
        data.indicators.ma60
          .slice(offset)
          .map((v, i) => ({
            time: filteredData[i]?.date as Time,
            value: v,
          }))
          .filter((d) => d.value > 0)
      );
    }

    // 当前最新价格标注线
    const lastBar = filteredData[filteredData.length - 1];
    if (lastBar) {
      candleSeries.createPriceLine({
        price: lastBar.close,
        color: '#3737CC',
        lineWidth: 1,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: '最新',
        axisLabelColor: '#3737CC',
        axisLabelTextColor: '#ffffff',
      });
    }

    // 十字线跟随 — OHLCV信息条（含成交量）
    chart.subscribeCrosshairMove((param) => {
      if (param.time && param.seriesData) {
        const cd = param.seriesData.get(candleSeries);
        if (cd && 'open' in cd) {
          // 查找对应日期的volume数据
          const dateStr = String(param.time);
          const matchedBar = filteredData.find(d => d.date === dateStr);
          setCrosshairData({
            time: dateStr,
            open: cd.open,
            high: cd.high,
            low: cd.low,
            close: cd.close,
            volume: matchedBar?.volume || matchedBar?.amount,
          });
        }
      } else {
        setCrosshairData(null);
      }
    });

    chart.timeScale().fitContent();
    chartInstance.current = chart;

    // 响应容器大小变化（节流~60fps）
    let resizeTimer: ReturnType<typeof setTimeout>;
    const resizeObserver = new ResizeObserver(() => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (chartRef.current) {
          chart.applyOptions({ width: chartRef.current.clientWidth });
        }
      }, 16);
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      clearTimeout(resizeTimer);
      resizeObserver.disconnect();
      chart.remove();
      chartInstance.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, filteredData]);

  // Effect 2: theme/color变化时仅更新样式，避免重建整个图表
  useEffect(() => {
    if (!chartInstance.current) return;
    chartInstance.current.applyOptions({
      layout: {
        background: { type: ColorType.Solid, color: theme === 'dark' ? '#0A0A1A' : '#ffffff' },
        textColor: theme === 'dark' ? '#8888A0' : '#374151',
      },
      grid: {
        vertLines: { color: theme === 'dark' ? 'rgba(255,255,255,0.04)' : '#e5e7eb' },
        horzLines: { color: theme === 'dark' ? 'rgba(255,255,255,0.04)' : '#e5e7eb' },
      },
      timeScale: {
        borderColor: theme === 'dark' ? 'rgba(255,255,255,0.08)' : '#d1d5db',
      },
    });
  }, [theme, stockColorScheme]);

  if (!data.ohlcv?.length) {
    return (
      <div className="text-center text-muted-foreground py-8">暂无K线数据</div>
    );
  }

  const handleTimeRangeChange = (days: string) => {
    setTimeRange(days);
    onTimeRangeChange?.(days);
  };

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1 bg-white/[0.03] rounded-xl p-1">
          {TIME_RANGES.map((r) => (
            <button
              key={r.days}
              onClick={() => handleTimeRangeChange(r.days)}
              className={`px-2 py-0.5 text-[10px] rounded-lg border transition-colors ${
                timeRange === r.days
                  ? 'bg-[#3737CC]/20 text-[#3737CC] border-[#3737CC]/30'
                  : 'bg-transparent text-[#8888A0] border-transparent hover:bg-white/[0.06]'
              }`}
            >
              {r.label}
            </button>
          ))}
          <button
            onClick={() => setDrawMode(drawMode === 'trendline' ? 'none' : 'trendline')}
            className={`px-2 py-0.5 text-[10px] rounded-lg border transition-colors ml-2 ${
              drawMode === 'trendline' ? 'bg-[#3737CC]/20 text-[#3737CC] border-[#3737CC]/30' : 'bg-white/[0.04] text-[#8888A0] border-white/[0.08] hover:bg-white/[0.08]'
            }`}
          >
            趋势线
          </button>
        </div>
      </div>
      {drawMode === 'trendline' && (
        <div className="text-[10px] text-[#3737CC] bg-[#3737CC]/10 rounded-lg px-2 py-1 mb-1 border border-[#3737CC]/20">
          趋势线模式：点击图表两个点绘制趋势线（开发中）
        </div>
      )}
      {crosshairData && (
        <div className="bg-white/[0.04] rounded-lg px-3 py-1 font-mono text-xs flex items-center gap-3 text-[#8888A0] mb-1">
          <span>{crosshairData.time}</span>
          <span>O:<span className={crosshairData.close >= crosshairData.open ? 'text-[#46BEA3]' : 'text-[#FF8767]'}>{crosshairData.open.toFixed(2)}</span></span>
          <span>H:<span className="text-[#46BEA3]">{crosshairData.high.toFixed(2)}</span></span>
          <span>L:<span className="text-[#FF8767]">{crosshairData.low.toFixed(2)}</span></span>
          <span>C:<span className={crosshairData.close >= crosshairData.open ? 'text-[#46BEA3]' : 'text-[#FF8767]'}>{crosshairData.close.toFixed(2)}</span></span>
          {crosshairData.volume != null && (
            <span>V:<span className="text-[#F0F0F5]">{crosshairData.volume >= 1e8 ? (crosshairData.volume / 1e8).toFixed(2) + '亿' : crosshairData.volume >= 1e4 ? (crosshairData.volume / 1e4).toFixed(0) + '万' : crosshairData.volume.toLocaleString()}</span></span>
          )}
        </div>
      )}
      <div className="relative w-full border-b border-[#3737CC]/10">
        {(data.stock_code || data.stock_name) && (
          <div className="absolute top-4 left-4 text-2xl font-bold pointer-events-none select-none z-10" style={{ color: theme === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.06)' }}>
            {data.stock_code || ''} {data.stock_name || ''}
          </div>
        )}
        <div ref={chartRef} className="w-full" role="img" aria-label={`${data.stock_code || ''} ${data.stock_name || ''} K线走势图，显示${filteredData?.length || 0}根K线`} />
      </div>
    </div>
  );
}
