// Input: title、icon(ReactNode)、children、defaultExpanded
// Output: 可折叠/全屏/导出的Dark Glassmorphism Artifact卡片容器（glass-enter入场 + 全屏过渡 + 折叠高度动画）
// Pos: artifact-renderer.tsx的外层包装，提供卡片操作能力
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useRef, useEffect, ReactNode } from "react";
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
        className={`fixed inset-0 z-50 bg-[#0A0A1A] overflow-auto transition-all duration-300 ease-in-out ${
          fullscreen
            ? "opacity-100 scale-100 pointer-events-auto"
            : "opacity-0 scale-95 pointer-events-none"
        }`}
      >
        <div className="p-6">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/[0.08]">
            <h2 className="text-lg font-semibold flex items-center gap-2 text-[#F0F0F5]">
              {icon && <span className="text-[#3737CC]/80">{icon}</span>}
              {title}
            </h2>
            <button
              className="h-8 w-8 flex items-center justify-center rounded-lg text-[#8888A0] hover:bg-white/[0.08] hover:text-[#F0F0F5] transition-all duration-200"
              onClick={() => setFullscreen(false)}
            >
              <Minimize2 className="h-4 w-4" />
            </button>
          </div>
          <div id={`artifact-${title}-fs`}>{fullscreen && children}</div>
        </div>
      </div>

      {/* 普通卡片 — Dark Glassmorphism */}
      <div
        className="animate-[glass-enter_300ms_ease-out_both] overflow-hidden bg-white/[0.04] backdrop-blur-sm border border-white/[0.08] rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.36)] hover:border-white/[0.15] hover:shadow-[0_12px_40px_rgba(0,0,0,0.45)] transition-all duration-300"
      >
        {/* 标题栏 — 微弱分层 */}
        <div className="flex items-center justify-between px-4 py-3 bg-white/[0.02] border-b border-white/[0.06] rounded-t-2xl">
          <div className="text-sm font-medium flex items-center gap-2 text-[#F0F0F5]/90">
            {icon && <span className="text-[#3737CC]/80">{icon}</span>}
            <span className="truncate">{title}</span>
          </div>
          <div className="flex items-center gap-0.5 shrink-0">
            <button
              className="h-6 w-6 flex items-center justify-center rounded-md text-[#8888A0] hover:bg-white/[0.08] hover:text-[#F0F0F5] transition-all duration-200"
              onClick={handleExport}
              title="导出"
            >
              <Download className="h-3.5 w-3.5" />
            </button>
            <button
              className="h-6 w-6 flex items-center justify-center rounded-md text-[#8888A0] hover:bg-white/[0.08] hover:text-[#F0F0F5] transition-all duration-200"
              onClick={() => setFullscreen(true)}
              title="全屏"
            >
              <Maximize2 className="h-3.5 w-3.5" />
            </button>
            <button
              className="h-6 w-6 flex items-center justify-center rounded-md text-[#8888A0] hover:bg-white/[0.08] hover:text-[#F0F0F5] transition-all duration-200"
              onClick={() => setExpanded(!expanded)}
              title={expanded ? "折叠" : "展开"}
            >
              {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>

        {/* 折叠/展开 — overflow-hidden + max-height + opacity transition */}
        <div
          ref={contentRef}
          className="transition-all duration-300 ease-in-out overflow-hidden"
          style={{
            maxHeight: expanded ? (contentHeight ?? 2000) : 0,
            opacity: expanded ? 1 : 0,
          }}
        >
          <div className="px-4 py-3" id={`artifact-${title}`}>
            {children}
          </div>
        </div>
      </div>
    </>
  );
}
