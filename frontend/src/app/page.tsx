// Input: 无
// Output: 首页 — 市场ticker + 三栏布局 (sidebar | chat | artifacts)
// Pos: 应用主入口页面

"use client";
import { useState } from "react";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ArtifactPanel } from "@/components/chat/artifact-panel";
import { MarketOverview } from "@/components/market/market-overview";
import { Button } from "@/components/ui/button";
import { MessageSquare, BarChart3 } from "lucide-react";

export default function HomePage() {
  const [mobileTab, setMobileTab] = useState<"chat" | "artifacts">("chat");

  return (
    <div className="flex flex-col h-full">
      {/* Market ticker — fixed height */}
      <MarketOverview />

      {/* Mobile tab switcher */}
      <div className="flex sm:hidden border-b border-border/60 shrink-0">
        <Button
          variant="ghost"
          className={`flex-1 rounded-none h-9 gap-1.5 text-xs ${mobileTab === "chat" ? "border-b-2 border-primary text-foreground" : "text-muted-foreground"}`}
          onClick={() => setMobileTab("chat")}
        >
          <MessageSquare className="h-3.5 w-3.5" />
          对话
        </Button>
        <Button
          variant="ghost"
          className={`flex-1 rounded-none h-9 gap-1.5 text-xs ${mobileTab === "artifacts" ? "border-b-2 border-primary text-foreground" : "text-muted-foreground"}`}
          onClick={() => setMobileTab("artifacts")}
        >
          <BarChart3 className="h-3.5 w-3.5" />
          分析
        </Button>
      </div>

      {/* Desktop: three-column layout */}
      <div className="hidden sm:flex flex-1 min-h-0">
        {/* Sidebar */}
        <ConversationSidebar />
        {/* Chat panel — fixed 380px */}
        <div className="w-[380px] min-w-[320px] max-w-[480px] border-r border-border/60 flex flex-col min-h-0">
          <ChatPanel />
        </div>
        {/* Artifacts — fills remaining */}
        <div className="flex-1 flex flex-col min-h-0">
          <ArtifactPanel />
        </div>
      </div>

      {/* Mobile: single panel */}
      <div className="flex sm:hidden flex-1 min-h-0">
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
    </div>
  );
}
