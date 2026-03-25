// Input: 无
// Output: 市场概览+对话历史+ResizablePanel(Chat+Artifacts)三栏主页面
// Pos: 应用首页，核心交互入口
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ArtifactPanel } from "@/components/chat/artifact-panel";
import { MarketOverview } from "@/components/market/market-overview";
import { ResizablePanel } from "@/components/layout/resizable-panel";

export default function HomePage() {
  return (
    <div className="flex flex-col h-full">
      <MarketOverview />
      <div className="flex flex-1 overflow-hidden chat-layout">
        {/* 左侧：对话历史 */}
        <ConversationSidebar />
        {/* 中间Chat + 右侧Artifacts：可拖拽调整宽度 */}
        <ResizablePanel
          left={
            <div className="border-r flex flex-col h-full chat-panel">
              <ChatPanel />
            </div>
          }
          right={
            <div className="flex-1 flex flex-col h-full artifact-panel">
              <ArtifactPanel />
            </div>
          }
          defaultLeftWidth={35}
          minLeftWidth={25}
          maxLeftWidth={50}
        />
      </div>
    </div>
  );
}
