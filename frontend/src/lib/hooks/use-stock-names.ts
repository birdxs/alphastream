// Input: 股票代码数组
// Output: {code: name} 映射，自动从后端/api/stock_data补全缺失名称
// Pos: 持仓/自选/对比页共用，解决用户添加时只输入代码名称缺失问题
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { inferMarketType } from "@/lib/utils/stock-code";

// 模块级跨组件名称缓存 — 避免同一代码多次请求
const nameCache: Record<string, string> = {};
// 模块级endpoint可用性探测 — 避免每次都触发/api/stock_name 404
let stockNameEndpointAvailable: boolean | null = null;

async function fetchName(code: string): Promise<string | undefined> {
  if (nameCache[code]) return nameCache[code];

  // 首次探测stock_name endpoint；不可用则永久退到stock_data
  if (stockNameEndpointAvailable !== false) {
    try {
      const r = await apiClient.get<{ stock_name?: string }>("/api/stock_name", { stock_code: code });
      stockNameEndpointAvailable = true;
      if (r.stock_name) {
        nameCache[code] = r.stock_name;
        return r.stock_name;
      }
    } catch {
      stockNameEndpointAvailable = false;
    }
  }

  try {
    const r = await apiClient.get<{ stock_name?: string }>("/api/stock_data", {
      stock_code: code, market_type: inferMarketType(code), period: "1y",
    });
    if (r.stock_name && r.stock_name !== code) {
      nameCache[code] = r.stock_name;
      return r.stock_name;
    }
  } catch {
    // ignore
  }
  return undefined;
}

export function useStockNames(codes: string[], existing: Record<string, string> = {}): Record<string, string> {
  const [names, setNames] = useState<Record<string, string>>(() => ({ ...nameCache, ...existing }));

  useEffect(() => {
    const missing = codes.filter((c) => !nameCache[c] && (!names[c] || names[c] === c));
    if (missing.length === 0) {
      // 合并可能在其他页面刚获取的缓存
      const cached: Record<string, string> = {};
      codes.forEach((c) => { if (nameCache[c]) cached[c] = nameCache[c]; });
      if (Object.keys(cached).some((k) => names[k] !== cached[k])) {
        // microtask 推迟，避免 set-state-in-effect 同步调用规则
        Promise.resolve().then(() => setNames((prev) => ({ ...prev, ...cached })));
      }
      return;
    }

    let cancelled = false;
    (async () => {
      // 并发最多5个，避免一次20个全打爆后端
      const CONCURRENCY = 5;
      const results: Record<string, string> = {};
      for (let i = 0; i < missing.length; i += CONCURRENCY) {
        const batch = missing.slice(i, i + CONCURRENCY);
        const resolved = await Promise.all(batch.map(fetchName));
        batch.forEach((code, idx) => {
          const name = resolved[idx];
          if (name) results[code] = name;
        });
        if (cancelled) return;
        if (Object.keys(results).length > 0) {
          setNames((prev) => ({ ...prev, ...results }));
        }
      }
    })();

    return () => { cancelled = true; };
  }, [codes.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  return names;
}
