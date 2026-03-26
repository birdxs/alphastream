// Input: chat-store状态 + useChatStream hook
// Output: 完整Chat对话面板UI（组合MessageList、ChatInput、SuggestedQuestions、WelcomeScreen子组件）
// Pos: 首页左侧面板，Chat+Artifacts布局的对话侧
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useChatStore } from "@/lib/stores/chat-store";
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { MessageList } from "./message-list";
import { ChatInput } from "./chat-input";
import { SuggestedQuestions } from "./suggested-questions";
import { WelcomeScreen } from "./welcome-screen";

export function ChatPanel() {
  const { sendMessage, stopGeneration } = useChatStream();
  const messages = useChatStore(s => s.messages);
  const isStreaming = useChatStore(s => s.isStreaming);

  const handleSend = (message: string, options: { stock_code?: string; market_type?: string }) => {
    sendMessage(message, options);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 头部 */}
      <div className="px-4 py-3 border-b flex items-center justify-between bg-background/95 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <h2 className="font-semibold text-sm">AI金融分析助手</h2>
        </div>
      </div>

      {/* 消息列表或欢迎页 */}
      {messages.length === 0 && !isStreaming ? (
        <WelcomeScreen onQuestionSelect={handleSend} />
      ) : (
        <MessageList />
      )}

      {/* Follow-up建议 */}
      <SuggestedQuestions onSelect={(q) => handleSend(q, {})} />

      {/* 输入框 */}
      <ChatInput onSend={handleSend} onStop={stopGeneration} />
    </div>
  );
}
