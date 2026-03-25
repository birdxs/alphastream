// Input: 新闻列表数据（items数组含title、time、sentiment、source）
// Output: 专业新闻列表组件（情感标签、悬停交互效果）
// Pos: artifact-renderer.tsx的子组件，news_feed类型Artifact渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Badge } from "@/components/ui/badge";

interface NewsItem {
  title?: string;
  time?: string;
  date?: string;
  content?: string;
  sentiment?: number;
  source?: string;
}

interface Props {
  data: {
    items?: NewsItem[];
    [key: string]: unknown;
  };
}

export function NewsFeedArtifact({ data }: Props) {
  const items = Array.isArray(data.items) ? data.items : [];

  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground text-center py-4">暂无相关新闻</p>;
  }

  return (
    <div className="space-y-1">
      {items.slice(0, 8).map((item, i) => {
        const sentiment = item.sentiment || 0;
        const sentimentColor = sentiment > 0.6 ? 'text-green-500' : sentiment < 0.4 ? 'text-red-500' : 'text-muted-foreground';
        const sentimentLabel = sentiment > 0.6 ? '利好' : sentiment < 0.4 ? '利空' : '中性';

        return (
          <div key={i} className="flex items-start gap-3 py-2.5 border-b border-border/30 last:border-0 group hover:bg-muted/30 rounded px-2 -mx-2 transition-colors">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium leading-snug group-hover:text-primary transition-colors line-clamp-2">
                {item.title || '无标题'}
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[10px] text-muted-foreground">
                  {item.time || item.date || ''}
                </span>
                {item.source && (
                  <span className="text-[10px] text-muted-foreground/60">{item.source}</span>
                )}
              </div>
            </div>
            {sentiment !== 0 && (
              <Badge variant="outline" className={`text-[10px] shrink-0 ${sentimentColor}`}>
                {sentimentLabel}
              </Badge>
            )}
          </div>
        );
      })}
    </div>
  );
}
