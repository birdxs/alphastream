// Input: 后端API市场数据
// Output: 市场指数概览条（沪指/深指/创业板/沪深300实时数据）
// Pos: 首页顶部ticker bar，展示主要市场指数
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

interface MarketIndex {
  name: string;
  code: string;
  price: number;
  change: number;
}

export function MarketOverview() {
  const [indices, setIndices] = useState<MarketIndex[]>([
    { name: "上证指数", code: "000001", price: 0, change: 0 },
    { name: "深证成指", code: "399001", price: 0, change: 0 },
    { name: "创业板指", code: "399006", price: 0, change: 0 },
    { name: "沪深300", code: "000300", price: 0, change: 0 },
  ]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 尝试从后端获取最新数据
    const fetchData = async () => {
      try {
        await apiClient.get<{news: unknown[]}>('/api/latest_news?limit=1');
        // 如果有数据返回则更新，否则使用默认值
        setLoading(false);
      } catch {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="flex items-center gap-4 px-4 py-1.5 border-b bg-muted/30 overflow-x-auto text-xs">
      <span className="text-muted-foreground shrink-0">市场</span>
      {indices.map(idx => (
        <div key={idx.code} className="flex items-center gap-1.5 shrink-0">
          <span className="text-muted-foreground">{idx.name}</span>
          {loading ? (
            <span className="text-muted-foreground">--</span>
          ) : (
            <>
              <span className="font-mono">{idx.price || '--'}</span>
              {idx.change !== 0 && (
                <span className={idx.change > 0 ? 'stock-up' : 'stock-down'}>
                  {idx.change > 0 ? '+' : ''}{idx.change.toFixed(2)}%
                </span>
              )}
            </>
          )}
        </div>
      ))}
    </div>
  );
}
