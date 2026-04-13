// Input: title、icon(ReactNode)、children、defaultExpanded
// Output: 可折叠/全屏/导出的Dark Glassmorphism Artifact卡片容器（glass-enter入场 + 全屏过渡 + ESC退出全屏 + 折叠高度动画 + 导出下拉菜单含复制/截图）
// Pos: artifact-renderer.tsx的外层包装，提供卡片操作能力
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useRef, useEffect, useCallback, ReactNode } from "react";
import { Maximize2, Minimize2, ChevronUp, ChevronDown, Download, Copy, Camera } from "lucide-react";
import { useToast } from "@/components/common/toast-provider";

interface Props {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  defaultExpanded?: boolean;
  confidence?: number;
}

function ConfidenceBadge({ value }: { value: number }) {
  const label = value >= 0.8 ? "高置信" : value >= 0.5 ? "中置信" : "低置信";
  const dotColor = value >= 0.8 ? "text-[#10B981]" : value >= 0.5 ? "text-amber-400" : "text-[#EF4444]";
  const bgColor = value >= 0.8 ? "bg-[#10B981]/10" : value >= 0.5 ? "bg-amber-400/10" : "bg-[#EF4444]/10";
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${bgColor} ${dotColor}`}>
      <span className="text-[8px]">{"\u25CF"}</span>
      {label}
    </span>
  );
}

export function ArtifactCard({ title, icon, children, defaultExpanded = true, confidence }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [fullscreen, setFullscreen] = useState(false);
  const [contentHeight, setContentHeight] = useState<number | undefined>(undefined);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  // 测量内容高度用于折叠动画
  useEffect(() => {
    if (contentRef.current) {
      setContentHeight(contentRef.current.scrollHeight);
    }
  }, [children, expanded]);

  // 全屏模式下 Escape 键退出
  useEffect(() => {
    if (!fullscreen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setFullscreen(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [fullscreen]);

  // 点击外部关闭导出菜单
  useEffect(() => {
    if (!exportMenuOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setExportMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [exportMenuOpen]);

  const handleCopyData = useCallback(() => {
    const text = document.getElementById(`artifact-${title}`)?.innerText;
    if (text) {
      navigator.clipboard.writeText(text).then(
        () => toast("已复制到剪贴板", "success"),
        () => toast("复制失败", "error"),
      );
    }
    setExportMenuOpen(false);
  }, [title, toast]);

  const handleSaveImage = useCallback(async () => {
    setExportMenuOpen(false);
    const el = document.getElementById(`artifact-${title}`);
    if (!el) return;
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const html2canvas = (await import(/* webpackIgnore: true */ "html2canvas" as string)).default as (el: HTMLElement, opts: Record<string, unknown>) => Promise<HTMLCanvasElement>;
      const canvas = await html2canvas(el, { backgroundColor: "#0A0A1A", scale: 2 });
      const link = document.createElement("a");
      link.download = `${title.replace(/\s+/g, "_")}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      toast("图片已保存", "success");
    } catch {
      toast("浏览器不支持截图导出", "error");
    }
  }, [title, toast]);

  return (
    <>
      {/* 全屏遮罩层 — 用 CSS transition 而非条件渲染 */}
      <div
        className={`fixed inset-0 z-50 bg-card dark:bg-[#0A0A1A] overflow-auto transition-all duration-300 ease-in-out ${
          fullscreen
            ? "opacity-100 scale-100 pointer-events-auto"
            : "opacity-0 scale-95 pointer-events-none"
        }`}
      >
        <div className="p-6">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-foreground/[0.08] dark:border-white/[0.08]">
            <h2 className="text-lg font-semibold flex items-center gap-2 text-foreground dark:text-[#F0F0F5]">
              {icon && <span className="text-[#3737CC]/80">{icon}</span>}
              {title}
            </h2>
            <button
              className="h-8 w-8 flex items-center justify-center rounded-lg text-muted-foreground dark:text-[#8888A0] hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08] hover:text-foreground dark:hover:text-[#F0F0F5] transition-all duration-200"
              onClick={() => setFullscreen(false)}
              aria-label="退出全屏"
            >
              <Minimize2 className="h-4 w-4" />
            </button>
          </div>
          <div id={`artifact-${title}-fs`}>{fullscreen && children}</div>
        </div>
      </div>

      {/* 普通卡片 — Dark Glassmorphism */}
      <div
        className="glass-card-elevated glass-gradient-border animate-[glass-enter_300ms_ease-out_both] overflow-hidden rounded-2xl transition-all duration-300"
      >
        {/* 标题栏 — 微弱分层 */}
        <div className="flex items-center justify-between px-4 py-3 bg-foreground/[0.02] dark:bg-white/[0.02] border-b border-foreground/[0.06] dark:border-white/[0.06] rounded-t-2xl">
          <div className="text-sm font-medium flex items-center gap-2 text-foreground dark:text-[#F0F0F5]/90">
            {icon && <span className="text-[#3737CC]/80">{icon}</span>}
            <span className="truncate">{title}</span>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {confidence !== undefined && <ConfidenceBadge value={confidence} />}
            <div className="relative" ref={exportMenuRef}>
              <button
                className="h-6 w-6 flex items-center justify-center rounded-md text-muted-foreground dark:text-[#8888A0] hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08] hover:text-foreground dark:hover:text-[#F0F0F5] transition-all duration-200"
                onClick={() => setExportMenuOpen(!exportMenuOpen)}
                title="导出"
                aria-label="导出菜单"
                aria-expanded={exportMenuOpen}
                aria-haspopup="true"
              >
                <Download className="h-3.5 w-3.5" />
              </button>
              {/* 导出下拉菜单 — 毛玻璃 */}
              {exportMenuOpen && (
                <div className="absolute right-0 top-8 z-50 min-w-[150px] rounded-xl border border-foreground/[0.12] dark:border-white/[0.12] bg-popover/80 dark:bg-[#14142B]/80 backdrop-blur-2xl shadow-2xl shadow-black/40 py-1 animate-[glass-enter_150ms_ease-out_both]">
                  <button
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-[#E0E0F0] hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08] transition-colors"
                    onClick={handleCopyData}
                  >
                    <Copy className="h-3.5 w-3.5 text-muted-foreground dark:text-[#8888A0]" />
                    复制数据
                  </button>
                  <button
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-[#E0E0F0] hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08] transition-colors"
                    onClick={handleSaveImage}
                  >
                    <Camera className="h-3.5 w-3.5 text-muted-foreground dark:text-[#8888A0]" />
                    保存图片
                  </button>
                </div>
              )}
            </div>
            <button
              className="h-6 w-6 flex items-center justify-center rounded-md text-muted-foreground dark:text-[#8888A0] hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08] hover:text-foreground dark:hover:text-[#F0F0F5] transition-all duration-200"
              onClick={() => setFullscreen(true)}
              title="全屏"
              aria-label="全屏查看"
            >
              <Maximize2 className="h-3.5 w-3.5" />
            </button>
            <button
              className="h-6 w-6 flex items-center justify-center rounded-md text-muted-foreground dark:text-[#8888A0] hover:bg-foreground/[0.08] dark:hover:bg-white/[0.08] hover:text-foreground dark:hover:text-[#F0F0F5] transition-all duration-200"
              onClick={() => setExpanded(!expanded)}
              title={expanded ? "折叠" : "展开"}
              aria-label={expanded ? "折叠内容" : "展开内容"}
              aria-expanded={expanded}
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
