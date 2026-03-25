// Input: 无
// Output: 市场概览+对话历史+Chat+Artifacts三栏主页面
// Pos: 应用首页，核心交互入口
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ArtifactPanel } from "@/components/chat/artifact-panel";
import { MarketOverview } from "@/components/market/market-overview";

export default function HomePage() {
  return (
    <div className="flex flex-col h-full">
      <MarketOverview />
      <div className="flex flex-1 overflow-hidden chat-layout">
        {/* 左侧：对话历史 */}
        <ConversationSidebar />
        {/* 中间：AI对话面板 */}
        <div className="w-[35%] min-w-[340px] border-r flex flex-col chat-panel">
          <ChatPanel />
        </div>
        {/* 右侧：Artifacts工作区 */}
        <div className="flex-1 flex flex-col artifact-panel">
          <ArtifactPanel />
        </div>
      </div>
    </div>
  );
}
