// Input: title、icon(ReactNode)、children、defaultExpanded
// Output: 可折叠/全屏/导出的Artifact卡片容器（slide-in-right入场 + 全屏过渡 + 折叠高度动画）
// Pos: artifact-renderer.tsx的外层包装，提供卡片操作能力
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useRef, useEffect, ReactNode } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Maximize2, Minimize2, ChevronUp, ChevronDown, Download } from "lucide-react";

interface Props {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  defaultExpanded?: boolean;
}

export function ArtifactCard({ title, icon, children, defaultExpanded = true }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [fullscreen, setFullscreen] = useState(false);
  const [contentHeight, setContentHeight] = useState<number | undefined>(undefined);
  const contentRef = useRef<HTMLDivElement>(null);

  // 测量内容高度用于折叠动画
  useEffect(() => {
    if (contentRef.current) {
      setContentHeight(contentRef.current.scrollHeight);
    }
  }, [children, expanded]);

  const handleExport = () => {
    const text = document.getElementById(`artifact-${title}`)?.innerText;
    if (text) {
      navigator.clipboard.writeText(text).catch(() => {});
    }
  };

  return (
    <>
      {/* 全屏遮罩层 — 用 CSS transition 而非条件渲染 */}
      <div
        className={`fixed inset-0 z-50 bg-background overflow-auto transition-all duration-300 ease-in-out ${
          fullscreen
            ? "opacity-100 scale-100 pointer-events-auto"
            : "opacity-0 scale-95 pointer-events-none"
        }`}
      >
        <div className="p-6">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-border/40">
            <h2 className="text-lg font-semibold flex items-center gap-2 text-foreground">
              {icon && <span className="text-primary">{icon}</span>}
              {title}
            </h2>
            <Button variant="ghost" size="icon" onClick={() => setFullscreen(false)}>
              <Minimize2 className="h-4 w-4" />
            </Button>
          </div>
          <div id={`artifact-${title}-fs`}>{fullscreen && children}</div>
        </div>
      </div>

      {/* 普通卡片 */}
      <Card className="animate-slide-in-right overflow-hidden border border-border/50 hover:border-border hover:shadow-md transition-all duration-300">
        <CardHeader className="pb-0 pt-0 px-0">
          <div className="flex items-center justify-between px-3 py-2 bg-muted/30 border-b border-border/20">
            <CardTitle className="text-sm font-medium flex items-center gap-2 text-foreground/90">
              {icon && <span className="text-primary/80">{icon}</span>}
              <span className="truncate">{title}</span>
            </CardTitle>
            <div className="flex items-center gap-0.5 shrink-0">
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-foreground"
                onClick={handleExport}
                title="导出"
              >
                <Download className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-foreground"
                onClick={() => setFullscreen(true)}
                title="全屏"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-foreground"
                onClick={() => setExpanded(!expanded)}
                title={expanded ? "折叠" : "展开"}
              >
                {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </Button>
            </div>
          </div>
        </CardHeader>

        {/* 折叠/展开有高度过渡动画 */}
        <div
          ref={contentRef}
          className="transition-all duration-300 ease-in-out overflow-hidden"
          style={{
            maxHeight: expanded ? (contentHeight ?? 2000) : 0,
            opacity: expanded ? 1 : 0,
          }}
        >
          <CardContent className="px-4 py-3" id={`artifact-${title}`}>
            {children}
          </CardContent>
        </div>
      </Card>
    </>
  );
}
