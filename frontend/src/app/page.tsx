// Input: 无 props；读取 chat-store（messages/isStreaming/artifacts）与 agent-store（isAnalyzing）驱动栏位
// Output: 首页主工作台 — 顶栏指数 + 桌面四栏（历史侧栏 | 对话主区 | 结果坞 | Agent 工位）
// Pos: App Router `/` 入口；S-UI-2 IA：主次清晰（对话>结果>工位）；挂载 ConversationSidebar 恢复「新对话」
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { ArtifactPanel } from "@/components/chat/artifact-panel";
import { AgentSidePanel } from "@/components/agent/agent-side-panel";
import { MarketOverview } from "@/components/market/market-overview";
import { useChatStore } from "@/lib/stores/chat-store";
import { useAgentStore } from "@/lib/stores/agent-store";
import { PanelLeft, PanelRight, MessageSquare, Bot, History } from "lucide-react";

const STORAGE_KEY = "stockanal-chat-width";
/** S-UI-2：对话主区默认略宽，突出主路径 */
const DEFAULT_WIDTH = 38;
const MIN_WIDTH = 22;
const MAX_WIDTH = 58;

export default function HomePage() {
  const [chatWidth, setChatWidth] = useState(DEFAULT_WIDTH);
  const [isDragging, setIsDragging] = useState(false);
  const [agentOpen, setAgentOpen] = useState(false);
  /** 桌面端对话历史侧栏：默认展开，保证「新对话」入口可见（S-UI 改版后曾未挂载） */
  const [historyOpen, setHistoryOpen] = useState(true);
  const [mobileTab, setMobileTab] = useState<"chat" | "artifact">("chat");
  const [mounted, setMounted] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const isStreaming = useChatStore(s => s.isStreaming);
  const hasMessages = useChatStore(s => s.messages.length > 0);
  const hasArtifacts = useChatStore(s => s.artifacts.length > 0);
  const isAnalyzing = useAgentStore(s => s.isAnalyzing);
  const overallProgress = useAgentStore(s => s.overallProgress);

  // S-UI-2：Agent 运行中自动展开工位，便于 HITL/进度可达
  useEffect(() => {
    if (isAnalyzing) setAgentOpen(true);
  }, [isAnalyzing]);

  // 挂载后读取 localStorage，避免 SSR 水合不匹配
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const n = Number(saved);
        if (n >= MIN_WIDTH && n <= MAX_WIDTH) setChatWidth(n);
      }
    } catch { /* SSR/隐私模式忽略 */ }
    setMounted(true);
  }, []);

  // 拖拽逻辑
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setChatWidth(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, pct)));
    };
    const handleMouseUp = () => {
      setIsDragging(false);
      try { localStorage.setItem(STORAGE_KEY, String(chatWidth)); } catch { /* ignore */ }
    };
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isDragging, chatWidth]);

  // 双击重置
  const handleDoubleClick = useCallback(() => {
    setChatWidth(DEFAULT_WIDTH);
    try { localStorage.setItem(STORAGE_KEY, String(DEFAULT_WIDTH)); } catch { /* ignore */ }
  }, []);

  return (
    <div className="flex flex-col h-full overflow-hidden" data-testid="home-workspace">
      {/* 顶部市场概览 — sticky 吸顶 */}
      <div className="shrink-0" data-region="market-ticker">
        <MarketOverview />
      </div>

      {/* S-UI-2：运行态全局状态条（仅进度/状态文案，无假数） */}
      {(isStreaming || isAnalyzing) && (
        <div
          className="shrink-0 flex items-center gap-2 px-3 py-1 border-b border-[#3737CC]/15 bg-[#3737CC]/[0.06] dark:bg-[#3737CC]/10"
          data-testid="home-run-status"
          role="status"
          aria-live="polite"
        >
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inset-0 rounded-full bg-[#3737CC] animate-ping opacity-60" />
            <span className="relative h-1.5 w-1.5 rounded-full bg-[#3737CC]" />
          </span>
          <span className="text-[11px] font-medium text-[#3737CC] dark:text-[#9aa0ff]">
            {isAnalyzing ? "Agent 分析进行中" : "AI 对话生成中"}
          </span>
          {isAnalyzing && overallProgress > 0 && (
            <span className="text-[10px] tabular-nums text-muted-foreground">
              {Math.round(overallProgress)}%
            </span>
          )}
          <div className="flex-1 h-1 max-w-[160px] rounded-full bg-foreground/[0.06] dark:bg-white/[0.08] overflow-hidden">
            <div
              className="h-full rounded-full bg-[#3737CC]/70 transition-all duration-500"
              style={{
                width: isAnalyzing
                  ? `${Math.min(100, Math.max(4, overallProgress || 8))}%`
                  : "40%",
              }}
            />
          </div>
          {!agentOpen && isAnalyzing && (
            <button
              type="button"
              onClick={() => setAgentOpen(true)}
              className="text-[10px] text-[#3737CC] hover:underline ml-auto"
            >
              打开工位
            </button>
          )}
        </div>
      )}

      {/* 桌面端：历史侧栏 + 可拖拽栏 — 对话主区 | 结果坞 | Agent 工位 */}
      <div ref={containerRef} className="hidden md:flex flex-1 min-h-0 relative">
        {/* 对话历史侧栏：含「新对话」主入口（组件既有；此前未挂载导致入口缺失） */}
        {historyOpen ? (
          <aside
            className="h-full min-h-0 shrink-0"
            data-region="conversation-history"
            aria-label="对话历史"
            id="conversation-history-panel"
          >
            <ConversationSidebar />
          </aside>
        ) : (
          <button
            type="button"
            onClick={() => setHistoryOpen(true)}
            className="h-full w-9 shrink-0 border-r border-border/40 dark:border-white/[0.06] flex flex-col items-center pt-3 gap-2 text-muted-foreground hover:text-[#3737CC] hover:bg-[#3737CC]/5 transition-colors"
            title="展开对话历史 / 新对话"
            aria-label="展开对话历史"
            aria-expanded={false}
            aria-controls="conversation-history-panel"
          >
            <History className="h-4 w-4" />
            <span
              className="text-[10px] tracking-wide"
              style={{ writingMode: "vertical-rl" }}
            >
              历史
            </span>
          </button>
        )}

        {/* 对话主区 */}
        <section
          className="h-full min-h-0 overflow-hidden border-r border-border/40 dark:border-white/[0.04] relative"
          style={{ width: `${chatWidth}%`, transition: isDragging ? "none" : "width 0.15s ease" }}
          data-region="chat-primary"
          aria-label="对话主区"
        >
          {historyOpen && (
            <button
              type="button"
              onClick={() => setHistoryOpen(false)}
              className="absolute left-0 top-1/2 -translate-y-1/2 z-20 h-12 w-4 rounded-r-md flex items-center justify-center bg-foreground/[0.04] dark:bg-white/[0.04] text-muted-foreground hover:bg-[#3737CC]/10 hover:text-[#3737CC] transition-colors"
              title="收起对话历史"
              aria-label="收起对话历史"
              aria-expanded={true}
              aria-controls="conversation-history-panel"
            >
              <PanelLeft className="h-3 w-3 rotate-180" />
            </button>
          )}
          <ChatPanel />
        </section>

        {/* 拖拽手柄 */}
        <div
          className={`w-1.5 h-full cursor-col-resize shrink-0 relative group transition-colors duration-150 ${
            isDragging ? "bg-[#3737CC]/40" : "bg-transparent hover:bg-[#3737CC]/20"
          }`}
          onMouseDown={handleMouseDown}
          onDoubleClick={handleDoubleClick}
          title="拖拽调整宽度 · 双击重置"
          role="separator"
          aria-orientation="vertical"
          aria-label="调整对话区宽度"
        >
          <div className={`absolute inset-y-0 left-1/2 -translate-x-1/2 w-px transition-colors duration-150 ${
            isDragging ? "bg-[#3737CC]" : "bg-border group-hover:bg-[#3737CC]/50"
          }`} />
          <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-8 rounded-full transition-all duration-150 ${
            isDragging ? "bg-[#3737CC] opacity-100" : "bg-border opacity-0 group-hover:opacity-100"
          }`} />
        </div>

        {/* 结果坞 */}
        <section
          className="flex-1 h-full min-h-0 overflow-hidden"
          data-region="artifact-dock"
          aria-label="分析结果坞"
        >
          <ArtifactPanel />
        </section>

        {/* Agent 工位 — 独立列，限宽防裁切 */}
        {agentOpen && (
          <aside
            className="w-[300px] lg:w-[320px] h-full min-h-0 shrink-0 border-l border-border/60 dark:border-white/[0.08] flex flex-col"
            data-region="agent-workspace"
            aria-label="Agent 工位"
            id="agent-workspace-panel"
          >
            <AgentSidePanel />
          </aside>
        )}

        {/* Agent 工位折叠按钮 */}
        <button
          onClick={() => setAgentOpen(v => !v)}
          className={`absolute right-0 top-1/2 -translate-y-1/2 z-20 h-16 w-5 rounded-l-md flex items-center justify-center transition-all duration-200 ${
            agentOpen
              ? "bg-[#3737CC]/15 text-[#3737CC] hover:bg-[#3737CC]/25"
              : isAnalyzing
                ? "bg-[#3737CC]/20 text-[#3737CC] hover:bg-[#3737CC]/30 animate-pulse"
                : "bg-foreground/[0.04] dark:bg-white/[0.04] text-muted-foreground hover:bg-[#3737CC]/10 hover:text-[#3737CC]"
          }`}
          title={agentOpen ? "收起 Agent 工位" : "展开 Agent 工位"}
          aria-expanded={agentOpen}
          aria-controls="agent-workspace-panel"
        >
          {agentOpen ? <PanelRight className="h-3.5 w-3.5" /> : <PanelLeft className="h-3.5 w-3.5" />}
        </button>
      </div>

      {/* 移动端：Tab 切换 */}
      <div className="flex md:hidden flex-col flex-1 min-h-0">
        {/* Tab 栏 */}
        <div className="flex border-b border-border/60 dark:border-white/[0.06] shrink-0">
          <button
            onClick={() => setMobileTab("chat")}
            className={`flex-1 flex items-center justify-center gap-1.5 h-10 text-xs font-medium transition-colors ${
              mobileTab === "chat"
                ? "text-[#3737CC] border-b-2 border-[#3737CC]"
                : "text-muted-foreground"
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            对话
            {isStreaming && (
              <span className="w-1.5 h-1.5 rounded-full bg-[#3737CC] animate-pulse" />
            )}
          </button>
          <button
            onClick={() => setMobileTab("artifact")}
            className={`flex-1 flex items-center justify-center gap-1.5 h-10 text-xs font-medium transition-colors ${
              mobileTab === "artifact"
                ? "text-[#3737CC] border-b-2 border-[#3737CC]"
                : "text-muted-foreground"
            }`}
          >
            <Bot className="h-3.5 w-3.5" />
            结果
            {hasArtifacts && (
              <span className="inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-full bg-[#3737CC]/15 text-[10px] text-[#3737CC]">
                {/* artifacts count 在 ArtifactPanel 内读取，此处仅用 hasArtifacts 作指示 */}
                •
              </span>
            )}
          </button>
        </div>

        {/* Tab 内容 */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {mobileTab === "chat" ? <ChatPanel /> : <ArtifactPanel />}
        </div>
      </div>

      {/* 拖拽时的全屏遮罩（防止 iframe/canvas 吞掉 mouseup） */}
      {isDragging && (
        <div className="fixed inset-0 z-50 cursor-col-resize" />
      )}
    </div>
  );
}
