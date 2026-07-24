// Input: 新闻列表数据（items数组含title、time、sentiment、source）
// Output: 专业新闻列表组件（情感标签、悬停交互效果）
// Pos: artifact-renderer.tsx的子组件，news_feed类型Artifact渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Newspaper } from "lucide-react";

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
    return (
      <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
        <Newspaper className="h-8 w-8 mb-2 opacity-40" />
        <p className="text-sm">暂无相关新闻</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {items.slice(0, 8).map((item, i) => {
        const sentiment = item.sentiment || 0;
        const sentimentColor = sentiment > 0.6 ? 'text-ok' : sentiment < 0.4 ? 'text-danger' : 'text-muted-foreground';
        const sentimentLabel = sentiment > 0.6 ? '利好' : sentiment < 0.4 ? '利空' : '中性';

        return (
          <div key={i} className="flex items-start gap-3 py-2.5 border-b border-foreground/[0.06] dark:border-white/[0.06] last:border-0 group hover:bg-foreground/[0.04] dark:hover:bg-white/[0.04] rounded px-2 -mx-2 transition-colors">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium leading-snug text-foreground dark:text-foreground group-hover:text-accent transition-colors line-clamp-2">
                {item.title || '无标题'}
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[10px] text-[#555570] font-mono">
                  {item.time || item.date || ''}
                </span>
                {item.source && (
                  <span className="text-[10px] text-[#555570]">{item.source}</span>
                )}
              </div>
            </div>
            {item.sentiment != null && item.sentiment !== 0 && (
              <div className="flex items-center gap-1.5 shrink-0">
                <div className="w-12 h-1.5 bg-foreground/[0.06] dark:bg-white/[0.06] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${(item.sentiment || 0.5) * 100}%`,
                      background: `linear-gradient(90deg, var(--danger), var(--warn), var(--ok))`,
                    }}
                  />
                </div>
                <span className={`text-[10px] ${sentimentColor}`}>{sentimentLabel}</span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
