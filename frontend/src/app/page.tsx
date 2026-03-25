// Input: 无
// Output: Chat+Artifacts双面板主页面
// Pos: 应用首页，核心交互入口
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ArtifactPanel } from "@/components/chat/artifact-panel";

export default function HomePage() {
  return (
    <div className="flex h-full">
      {/* 左侧：AI对话面板 */}
      <div className="w-[35%] min-w-[360px] border-r flex flex-col">
        <ChatPanel />
      </div>
      {/* 右侧：Artifacts工作区 */}
      <div className="flex-1 flex flex-col">
        <ArtifactPanel />
      </div>
    </div>
  );
}
