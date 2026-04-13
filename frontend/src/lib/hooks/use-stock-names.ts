// Input: 股票代码数组
// Output: {code: name} 映射，自动从后端/api/stock_data补全缺失名称
// Pos: 持仓/自选/对比页共用，解决用户添加时只输入代码名称缺失问题
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

export function useStockNames(codes: string[], existing: Record<string, string> = {}): Record<string, string> {
  const [names, setNames] = useState<Record<string, string>>(existing);

  useEffect(() => {
    // 只查询name缺失或等于code的项
    const missing = codes.filter((c) => !names[c] || names[c] === c);
    if (missing.length === 0) return;

    let cancelled = false;
    (async () => {
      const updates: Record<string, string> = {};
      for (const code of missing) {
        try {
          // 优先尝试轻量endpoint，失败则退到stock_data
          let resolved: string | undefined;
          try {
            const r = await apiClient.get<{ stock_name?: string }>("/api/stock_name", { stock_code: code });
            resolved = r.stock_name;
          } catch {
            const r = await apiClient.get<{ stock_name?: string }>("/api/stock_data", {
              stock_code: code, market_type: "A", period: "1y",
            });
            resolved = r.stock_name;
          }
          if (resolved && resolved !== code) updates[code] = resolved;
        } catch {
          // 忽略单个失败
        }
      }
      if (!cancelled && Object.keys(updates).length > 0) {
        setNames((prev) => ({ ...prev, ...updates }));
      }
    })();

    return () => { cancelled = true; };
  }, [codes.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  return names;
}
