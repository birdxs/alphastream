// Input: title、icon、children、defaultExpanded
// Output: 可折叠/全屏/导出的Artifact卡片容器
// Pos: artifact-renderer.tsx的外层包装，提供卡片操作能力
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, ReactNode } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Maximize2, Minimize2, ChevronUp, ChevronDown, Download } from "lucide-react";

interface Props {
  title: string;
  icon?: string;
  children: ReactNode;
  defaultExpanded?: boolean;
}

export function ArtifactCard({ title, icon, children, defaultExpanded = true }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [fullscreen, setFullscreen] = useState(false);

  const handleExport = () => {
    // 简单的数据导出（复制到剪贴板）
    const text = document.getElementById(`artifact-${title}`)?.innerText;
    if (text) {
      navigator.clipboard.writeText(text).catch(() => {});
    }
  };

  if (fullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-background p-6 overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            {icon && <span>{icon}</span>}{title}
          </h2>
          <Button variant="ghost" size="icon" onClick={() => setFullscreen(false)}>
            <Minimize2 className="h-4 w-4" />
          </Button>
        </div>
        <div id={`artifact-${title}`}>{children}</div>
      </div>
    );
  }

  return (
    <Card className="animate-fade-in overflow-hidden">
      <CardHeader className="pb-2 pt-3 px-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            {icon && <span>{icon}</span>}
            {title}
          </CardTitle>
          <div className="flex items-center gap-0.5">
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleExport} title="导出">
              <Download className="h-3 w-3" />
            </Button>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setFullscreen(true)} title="全屏">
              <Maximize2 className="h-3 w-3" />
            </Button>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setExpanded(!expanded)} title={expanded ? "折叠" : "展开"}>
              {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </Button>
          </div>
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="px-4 pb-4" id={`artifact-${title}`}>
          {children}
        </CardContent>
      )}
    </Card>
  );
}
