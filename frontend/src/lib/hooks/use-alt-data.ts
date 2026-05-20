// Input: ticker 股票代码 (A股 600519 / 美股 AAPL, 无需转换)
// Output: { data: AltDataArtifact|null, loading, error } — 拉取 /api/alt_data/<ticker> 聚合另类数据
// Pos: lib/hooks/use-alt-data.ts — L1 Stock页另类数据Tab数据源 [NEW-FILE:#20260415-50]
// 契约: 后端返回 {success, artifact:{type:"alt_data", title, data:{shipping?,esg?,hiring?,corporate?}}}
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { useEffect, useState } from "react";

export interface AltDataArtifact {
  type?: string;
  title?: string;
  data: {
    shipping?: Record<string, unknown>;
    esg?: Record<string, unknown>;
    hiring?: Record<string, unknown>;
    corporate?: Record<string, unknown>;
    [key: string]: unknown;
  };
  confidence?: number;
  sources?: Array<{ name: string; type: string }>;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

interface UseAltDataResult {
  data: AltDataArtifact | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useAltData(ticker: string): UseAltDataResult {
  const [data, setData] = useState<AltDataArtifact | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;

    const base = process.env.NEXT_PUBLIC_API_URL || "";
    // 通过 microtask 启动 loading，避免 set-state-in-effect 同步调用规则
    Promise.resolve().then(() => {
      if (!cancelled) { setLoading(true); setError(null); }
    });
    fetch(`${base}/api/alt_data/${encodeURIComponent(ticker)}`)
      .then(async (r) => {
        const text = await r.text();
        // 兼容非标 JSON (NaN/Infinity -> null), 与 apiClient.safeJSONParse 对齐
        const sanitized = text
          .replace(/\bNaN\b/g, "null")
          .replace(/\b-Infinity\b/g, "null")
          .replace(/\bInfinity\b/g, "null");
        let json: { success?: boolean; artifact?: AltDataArtifact; error?: string };
        try {
          json = JSON.parse(sanitized);
        } catch {
          throw new Error(`响应解析失败 (HTTP ${r.status})`);
        }
        if (!r.ok) throw new Error(json?.error || `HTTP ${r.status}`);
        return json;
      })
      .then((j) => {
        if (cancelled) return;
        if (j.success && j.artifact) {
          setData(j.artifact);
        } else {
          setError(j.error || "另类数据不可用");
        }
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [ticker, tick]);

  return { data, loading, error, reload: () => setTick((t) => t + 1) };
}
