// Input: 无
// Output: 首页 — 市场ticker + 三栏布局 (sidebar | chat | artifacts)，移动端底部TabBar切换
// Pos: 应用主入口页面

"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ArtifactPanel } from "@/components/chat/artifact-panel";
import { MarketOverview } from "@/components/market/market-overview";
import { MessageSquare, BarChart3, Menu } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

const STORAGE_KEY = "chat-panel-width-pct";
const DEFAULT_WIDTH = 35;
const MIN_WIDTH = 20;
const MAX_WIDTH = 60;

function getInitialWidth(): number {
  if (typeof window === "undefined") return DEFAULT_WIDTH;
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    const n = parseFloat(saved);
    if (n >= MIN_WIDTH && n <= MAX_WIDTH) return n;
  }
  return DEFAULT_WIDTH;
}

export default function HomePage() {
  const [mobileTab, setMobileTab] = useState<"chat" | "artifacts">("chat");
  const [slideDirection, setSlideDirection] = useState<"left" | "right" | null>(null);
  const [chatWidthPct, setChatWidthPct] = useState(DEFAULT_WIDTH);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // 移动端Tab切换动画
  const handleMobileTabSwitch = useCallback((tab: "chat" | "artifacts") => {
    if (tab === mobileTab) return;
    // 从"对话"切到"分析"：内容从右侧滑入；反之从左侧滑入
    setSlideDirection(tab === "artifacts" ? "right" : "left");
    setMobileTab(tab);
    // 动画结束后清除方向标记
    const timer = setTimeout(() => setSlideDirection(null), 300);
    return () => clearTimeout(timer);
  }, [mobileTab]);

  // 客户端初始化宽度
  useEffect(() => {
    setChatWidthPct(getInitialWidth());
  }, []);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    setIsDragging(true);
  }, []);

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!isDragging || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      // 计算鼠标位置在容器内的百分比（需减去sidebar宽度）
      const sidebarEl = containerRef.current.firstElementChild as HTMLElement;
      const sidebarWidth = sidebarEl?.offsetWidth ?? 0;
      const availableWidth = rect.width - sidebarWidth;
      const relativeX = e.clientX - rect.left - sidebarWidth;
      const pct = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, (relativeX / availableWidth) * 100));
      setChatWidthPct(pct);
    },
    [isDragging]
  );

  const handlePointerUp = useCallback(() => {
    if (!isDragging) return;
    setIsDragging(false);
    setChatWidthPct((pct) => {
      localStorage.setItem(STORAGE_KEY, String(Math.round(pct)));
      return pct;
    });
  }, [isDragging]);

  return (
    <div className="flex flex-col h-full relative overflow-hidden">
      {/* 渐变背景层 — 为毛玻璃提供可模糊内容 */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-[#3737CC]/[0.12] rounded-full blur-[150px]" style={{ animation: 'drift-1 20s ease-in-out infinite' }} />
        <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] bg-[#6B5EE4]/[0.10] rounded-full blur-[120px]" style={{ animation: 'drift-2 25s ease-in-out infinite' }} />
        <div className="absolute top-1/3 right-1/3 w-[350px] h-[350px] bg-[#46BEA3]/[0.08] rounded-full blur-[100px]" style={{ animation: 'drift-3 30s ease-in-out infinite' }} />
        <div className="absolute bottom-1/6 right-1/6 w-[300px] h-[300px] bg-[#FF8767]/[0.05] rounded-full blur-[100px]" style={{ animation: 'drift-4 35s ease-in-out infinite' }} />
      </div>
      {/* Market ticker — fixed height */}
      <MarketOverview />

      {/* Desktop: three-column layout */}
      <div
        ref={containerRef}
        className="hidden sm:flex flex-1 min-h-0"
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        style={isDragging ? { cursor: "col-resize", userSelect: "none" } : undefined}
      >
        {/* Sidebar */}
        <ConversationSidebar />
        {/* Chat panel — resizable width */}
        <div className="flex flex-col min-h-0" style={{ width: `${chatWidthPct}%` }}>
          <ChatPanel />
        </div>
        {/* Draggable divider */}
        <div
          className={`w-1 shrink-0 cursor-col-resize transition-colors ${
            isDragging ? "bg-[#3737CC]/60" : "bg-white/[0.08] hover:bg-[#3737CC]/40"
          }`}
          onPointerDown={handlePointerDown}
          role="separator"
          aria-orientation="vertical"
          aria-label="拖拽调整面板宽度"
          tabIndex={0}
        />
        {/* Artifacts — fills remaining; 超宽屏2列grid */}
        <div className="flex-1 flex flex-col min-h-0 2xl:grid 2xl:grid-cols-2 2xl:gap-2">
          <ArtifactPanel />
        </div>
      </div>

      {/* Mobile: single panel with bottom padding for TabBar + 滑入动画 */}
      <div className="flex sm:hidden flex-1 min-h-0 pb-14 overflow-hidden">
        <div
          className={`flex-1 flex flex-col min-h-0 w-full ${
            slideDirection === "right"
              ? "animate-mobile-slide-right"
              : slideDirection === "left"
              ? "animate-mobile-slide-left"
              : ""
          }`}
        >
          {mobileTab === "chat" ? <ChatPanel /> : <ArtifactPanel />}
        </div>
      </div>

      {/* Mobile: 底部TabBar — 固定在底部 */}
      <div className="flex sm:hidden fixed bottom-0 left-0 right-0 h-14 bg-[rgba(10,10,26,0.95)] backdrop-blur-xl border-t border-white/[0.08] z-50 items-center justify-around px-2">
        {/* 左侧：侧边栏Drawer触发按钮 */}
        <Sheet>
          <SheetTrigger
            render={
              <Button variant="ghost" size="icon" className="h-10 w-10 text-[#8888A0] hover:bg-white/[0.08]" />
            }
          >
            <Menu className="h-5 w-5" />
          </SheetTrigger>
          <SheetContent side="left" className="w-72 p-0 bg-[rgba(15,15,35,0.98)] backdrop-blur-2xl border-r border-white/[0.08]">
            <ConversationSidebar isMobileSheet />
          </SheetContent>
        </Sheet>

        {/* 对话Tab */}
        <button
          onClick={() => handleMobileTabSwitch("chat")}
          className={`flex flex-col items-center justify-center gap-0.5 flex-1 h-full transition-colors ${
            mobileTab === "chat" ? "text-[#3737CC]" : "text-[#8888A0]"
          }`}
        >
          <MessageSquare className="h-5 w-5" />
          <span className="text-[10px] font-medium">对话</span>
        </button>

        {/* 分析Tab */}
        <button
          onClick={() => handleMobileTabSwitch("artifacts")}
          className={`flex flex-col items-center justify-center gap-0.5 flex-1 h-full transition-colors ${
            mobileTab === "artifacts" ? "text-[#3737CC]" : "text-[#8888A0]"
          }`}
        >
          <BarChart3 className="h-5 w-5" />
          <span className="text-[10px] font-medium">分析</span>
        </button>
      </div>
    </div>
  );
}
