// Input: 无
// Output: 首页 — 市场ticker + 三栏布局 (sidebar | chat | artifacts)，移动端底部TabBar切换
// Pos: 应用主入口页面

"use client";
import { useState } from "react";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ArtifactPanel } from "@/components/chat/artifact-panel";
import { MarketOverview } from "@/components/market/market-overview";
import { MessageSquare, BarChart3, Menu } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  const [mobileTab, setMobileTab] = useState<"chat" | "artifacts">("chat");

  return (
    <div className="flex flex-col h-full relative overflow-hidden">
      {/* 渐变背景层 — 为毛玻璃提供可模糊内容 */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-[#3737CC]/[0.07] rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-[#6B5EE4]/[0.05] rounded-full blur-[100px]" />
        <div className="absolute top-1/3 right-1/3 w-64 h-64 bg-[#46BEA3]/[0.04] rounded-full blur-[80px]" />
      </div>
      {/* Market ticker — fixed height */}
      <MarketOverview />

      {/* Desktop: three-column layout */}
      <div className="hidden sm:flex flex-1 min-h-0">
        {/* Sidebar */}
        <ConversationSidebar />
        {/* Chat panel — 35% width */}
        <div className="w-[35%] min-w-[320px] max-w-[480px] flex flex-col min-h-0">
          <ChatPanel />
        </div>
        {/* Visual divider */}
        <div className="w-px bg-white/[0.08] shrink-0" />
        {/* Artifacts — fills remaining */}
        <div className="flex-1 flex flex-col min-h-0">
          <ArtifactPanel />
        </div>
      </div>

      {/* Mobile: single panel with bottom padding for TabBar */}
      <div className="flex sm:hidden flex-1 min-h-0 pb-14">
        {mobileTab === "chat" ? (
          <div className="flex-1 flex flex-col min-h-0">
            <ChatPanel />
          </div>
        ) : (
          <div className="flex-1 flex flex-col min-h-0">
            <ArtifactPanel />
          </div>
        )}
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
          onClick={() => setMobileTab("chat")}
          className={`flex flex-col items-center justify-center gap-0.5 flex-1 h-full transition-colors ${
            mobileTab === "chat" ? "text-[#3737CC]" : "text-[#8888A0]"
          }`}
        >
          <MessageSquare className="h-5 w-5" />
          <span className="text-[10px] font-medium">对话</span>
        </button>

        {/* 分析Tab */}
        <button
          onClick={() => setMobileTab("artifacts")}
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
