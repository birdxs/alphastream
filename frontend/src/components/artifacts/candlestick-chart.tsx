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
  const { theme, stockColorScheme } = useThemeStore();
  const [timeRange, setTimeRange] = useState('120');
  const [crosshairData, setCrosshairData] = useState<{
    time: string; open: number; high: number; low: number; close: number; volume?: number;
  } | null>(null);

  // 根据时间范围过滤数据
  const filteredData = timeRange === '0'
    ? data.ohlcv
    : data.ohlcv?.slice(-Number(timeRange));

  useEffect(() => {
    if (!chartRef.current || !filteredData?.length) return;

    // 涨跌颜色
    const upColor = stockColorScheme === "cn" ? "#ef4444" : "#22c55e";
    const downColor = stockColorScheme === "cn" ? "#22c55e" : "#ef4444";

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 400,
      layout: {
        background: {
          type: ColorType.Solid,
          color: theme === "dark" ? "#1a1a2e" : "#ffffff",
        },
        textColor: theme === "dark" ? "#d1d5db" : "#374151",
      },
      grid: {
        vertLines: { color: theme === "dark" ? "#2d2d44" : "#e5e7eb" },
        horzLines: { color: theme === "dark" ? "#2d2d44" : "#e5e7eb" },
      },
      crosshair: { mode: 0 },
      timeScale: {
        borderColor: theme === "dark" ? "#4b5563" : "#d1d5db",
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

    // 成交量
    if (filteredData.some((d) => d.volume)) {
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
          value: d.volume || 0,
          color: d.close >= d.open ? upColor + "40" : downColor + "40",
        }))
      );
    }

    // MA均线 — 需要对齐到filteredData的索引范围
    const offset = (data.ohlcv?.length || 0) - filteredData.length;
    if (data.indicators?.ma5) {
      const ma5Series = chart.addSeries(LineSeries, {
        color: "#f59e0b",
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
        color: "#3b82f6",
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
        color: "#a855f7",
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

    // 十字线跟随 — OHLCV信息条
    chart.subscribeCrosshairMove((param) => {
      if (param.time && param.seriesData) {
        const cd = param.seriesData.get(candleSeries);
        if (cd && 'open' in cd) {
          setCrosshairData({
            time: String(param.time),
            open: cd.open,
            high: cd.high,
            low: cd.low,
            close: cd.close,
          });
        }
      } else {
        setCrosshairData(null);
      }
    });

    chart.timeScale().fitContent();
    chartInstance.current = chart;

    // 响应容器大小变化
    const resizeObserver = new ResizeObserver(() => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth });
      }
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartInstance.current = null;
    };
  }, [data, filteredData, theme, stockColorScheme]);

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
        <div className="flex items-center gap-1">
          {TIME_RANGES.map((r) => (
            <button
              key={r.days}
              onClick={() => handleTimeRangeChange(r.days)}
              className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
                timeRange === r.days
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>
      {crosshairData && (
        <div className="flex items-center gap-3 text-[10px] font-finance text-muted-foreground mb-1">
          <span>日期: {crosshairData.time}</span>
          <span>开: <span className="text-foreground">{crosshairData.open.toFixed(2)}</span></span>
          <span>高: <span className="stock-up">{crosshairData.high.toFixed(2)}</span></span>
          <span>低: <span className="stock-down">{crosshairData.low.toFixed(2)}</span></span>
          <span>收: <span className="text-foreground">{crosshairData.close.toFixed(2)}</span></span>
        </div>
      )}
      <div ref={chartRef} className="w-full" />
    </div>
  );
}
