// Input: 搜索结果数据（query + items数组，每项含title/url/snippet/source）
// Output: 搜索结果列表展示
// Pos: artifact-renderer.tsx 的子组件，search_results 类型 Artifact 渲染器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

interface Props {
  data: {
    query?: string;
    items?: Array<{
      title: string;
      url?: string;
      snippet?: string;
      source?: string;
    }>;
    [key: string]: unknown;
  };
}

export function SearchResultsArtifact({ data }: Props) {
  if (!data) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        暂无搜索结果数据
      </div>
    );
  }
  const items = data.items || [];
  return (
    <div className="space-y-2">
      {data.query && (
        <p className="text-xs text-muted-foreground">
          \u641C\u7D22: &quot;{data.query}&quot;
        </p>
      )}
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">\u6682\u65E0\u641C\u7D22\u7ED3\u679C</p>
      ) : (
        items.map((item, i) => (
          <div key={i} className="border-b pb-2 last:border-0">
            <p className="text-sm font-medium hover:text-primary cursor-pointer">{item.title}</p>
            {item.snippet && (
              <p className="text-xs text-muted-foreground line-clamp-2">{item.snippet}</p>
            )}
            {item.source && <span className="text-xs text-primary/60">{item.source}</span>}
          </div>
        ))
      )}
    </div>
  );
}
