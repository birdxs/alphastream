// Input: 无
// Output: 市场概览+桌面端三栏布局+移动端Tab切换(Chat/Artifacts)主页面
// Pos: 应用首页，核心交互入口
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState } from "react";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ArtifactPanel } from "@/components/chat/artifact-panel";
import { MarketOverview } from "@/components/market/market-overview";
import { ResizablePanel } from "@/components/layout/resizable-panel";
import { Button } from "@/components/ui/button";
import { MessageSquare, BarChart3 } from "lucide-react";

export default function HomePage() {
  const [mobileTab, setMobileTab] = useState<'chat' | 'artifacts'>('chat');

  return (
    <div className="flex flex-col h-full">
      <MarketOverview />

      {/* 移动端Tab切换 */}
      <div className="flex sm:hidden border-b">
        <Button
          variant="ghost"
          className={`flex-1 rounded-none h-10 gap-2 text-xs ${mobileTab === 'chat' ? 'border-b-2 border-primary' : ''}`}
          onClick={() => setMobileTab('chat')}
        >
          <MessageSquare className="h-3.5 w-3.5" />
          对话
        </Button>
        <Button
          variant="ghost"
          className={`flex-1 rounded-none h-10 gap-2 text-xs ${mobileTab === 'artifacts' ? 'border-b-2 border-primary' : ''}`}
          onClick={() => setMobileTab('artifacts')}
        >
          <BarChart3 className="h-3.5 w-3.5" />
          分析结果
        </Button>
      </div>

      {/* 桌面端三栏布局 */}
      <div className="hidden sm:flex flex-1 overflow-hidden">
        <ConversationSidebar />
        <ResizablePanel
          left={<ChatPanel />}
          right={<ArtifactPanel />}
          defaultLeftWidth={35}
          minLeftWidth={25}
          maxLeftWidth={50}
        />
      </div>

      {/* 移动端单面板 */}
      <div className="flex sm:hidden flex-1 overflow-hidden">
        {mobileTab === 'chat' ? <ChatPanel /> : <ArtifactPanel />}
      </div>
    </div>
  );
}
