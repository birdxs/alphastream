// Input: title, loading, error, height, children
// Output: Card容器（加载态Skeleton / 错误态提示 / 正常态children，children 由 ErrorBoundary 保护）
// Pos: components/charts/chart-container.tsx - 图表统一容器，所有图表组件外层包裹
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
// S3-D4: children 由 ErrorBoundary 包裹，防止 chart 渲染异常冒泡到全局

"use client";
import { ReactNode } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBoundary } from "@/components/common/error-boundary";

interface Props {
  title?: string;
  loading?: boolean;
  error?: string;
  height?: number;
  children: ReactNode;
}

export function ChartContainer({ title, loading, error, height = 300, children }: Props) {
  if (loading) {
    return (
      <Card>
        {title && <CardHeader className="pb-2"><CardTitle className="text-sm">{title}</CardTitle></CardHeader>}
        <CardContent><Skeleton style={{ height }} className="w-full rounded" /></CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        {title && <CardHeader className="pb-2"><CardTitle className="text-sm">{title}</CardTitle></CardHeader>}
        <CardContent>
          <div style={{ height }} className="flex items-center justify-center text-muted-foreground text-sm">
            {error}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      {title && <CardHeader className="pb-2"><CardTitle className="text-sm">{title}</CardTitle></CardHeader>}
      <CardContent>
        <ErrorBoundary fallbackTitle={title ? `"${title}" 渲染出错` : "图表渲染出错"}>
          {children}
        </ErrorBoundary>
      </CardContent>
    </Card>
  );
}
