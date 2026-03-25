// Input: OHLCV数据数组、股票代码、均线指标
// Output: TradingView Lightweight Charts K线图（含成交量和MA均线）
// Pos: artifact-renderer.tsx的子组件，candlestick_chart类型Artifact渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useEffect, useRef } from "react";
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
}

export function CandlestickChartArtifact({ data }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);
  const { theme, stockColorScheme } = useThemeStore();

  useEffect(() => {
    if (!chartRef.current || !data.ohlcv?.length) return;

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

    const candleData: CandlestickData<Time>[] = data.ohlcv.map((d) => ({
      time: d.date as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    candleSeries.setData(candleData);

    // 成交量
    if (data.ohlcv.some((d) => d.volume)) {
      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeries.setData(
        data.ohlcv.map((d) => ({
          time: d.date as Time,
          value: d.volume || 0,
          color: d.close >= d.open ? upColor + "40" : downColor + "40",
        }))
      );
    }

    // MA均线
    if (data.indicators?.ma5) {
      const ma5Series = chart.addSeries(LineSeries, {
        color: "#f59e0b",
        lineWidth: 1,
      });
      ma5Series.setData(
        data.indicators.ma5
          .map((v, i) => ({
            time: data.ohlcv![i]?.date as Time,
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
          .map((v, i) => ({
            time: data.ohlcv![i]?.date as Time,
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
          .map((v, i) => ({
            time: data.ohlcv![i]?.date as Time,
            value: v,
          }))
          .filter((d) => d.value > 0)
      );
    }

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
  }, [data, theme, stockColorScheme]);

  if (!data.ohlcv?.length) {
    return (
      <div className="text-center text-muted-foreground py-8">暂无K线数据</div>
    );
  }

  return <div ref={chartRef} className="w-full" />;
}
