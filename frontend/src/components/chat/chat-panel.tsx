// Input: chat-store状态 + agent-store状态 + 用户输入
// Output: 完整Chat对话面板UI（消息列表、流式显示、输入框、Follow-up建议、Agent进度）
// Pos: 首页左侧面板，Chat+Artifacts布局的对话侧
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { useChatStore } from "@/lib/stores/chat-store";
import { useAgentStore } from "@/lib/stores/agent-store";
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Send, Loader2 } from "lucide-react";
import { MessageBubble } from "./message-bubble";
import { AgentProgressBar } from "./agent-progress-bar";

export function ChatPanel() {
  const [input, setInput] = useState("");
  const [stockCode, setStockCode] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const { sendMessage } = useChatStream();
  const { messages, isStreaming, streamingContent, followUpQuestions } = useChatStore();
  const { overallProgress, agentProgresses } = useAgentStore();

  // 自动滚动到底部
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || isStreaming) return;
    setInput("");

    // 从消息中提取股票代码（6位数字）
    const codeMatch = msg.match(/(\d{6})/);
    const code = codeMatch ? codeMatch[1] : stockCode;
    if (code) setStockCode(code);

    await sendMessage(msg, { stock_code: code });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFollowUp = (question: string) => {
    setInput(question);
    // 自动发送
    sendMessage(question, { stock_code: stockCode });
  };

  return (
    <div className="flex flex-col h-full">
      {/* 头部 */}
      <div className="p-3 border-b flex items-center justify-between">
        <h2 className="font-semibold text-sm">AI金融分析助手</h2>
        {stockCode && (
          <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded">
            {stockCode}
          </span>
        )}
      </div>

      {/* 消息列表 */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {messages.length === 0 && !isStreaming && (
            <div className="text-center mt-16 space-y-4">
              <p className="text-3xl">🤖</p>
              <p className="text-muted-foreground">你好！我是AI金融分析助手</p>
              <p className="text-sm text-muted-foreground">输入股票代码或问题开始分析</p>
              <div className="flex flex-wrap gap-2 justify-center mt-4">
                {["分析600519贵州茅台", "对比银行板块", "市场今日走势如何"].map((q) => (
                  <Button key={q} variant="outline" size="sm" onClick={() => handleFollowUp(q)}>
                    {q}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.message_id} message={msg} />
          ))}

          {/* 流式内容 */}
          {isStreaming && streamingContent && (
            <div className="flex gap-3">
              <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-xs shrink-0">
                AI
              </div>
              <div className="flex-1 text-sm whitespace-pre-wrap">{streamingContent}<span className="animate-pulse">▌</span></div>
            </div>
          )}

          {/* Agent进度 */}
          {isStreaming && agentProgresses.length > 0 && (
            <AgentProgressBar progresses={agentProgresses} overall={overallProgress} />
          )}

          {/* 加载指示器 */}
          {isStreaming && !streamingContent && (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>AI正在分析...</span>
            </div>
          )}

          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      {/* Follow-up建议 */}
      {followUpQuestions.length > 0 && !isStreaming && (
        <div className="px-3 py-2 border-t flex gap-2 overflow-x-auto">
          {followUpQuestions.map((q, i) => (
            <Button key={i} variant="outline" size="sm" className="whitespace-nowrap text-xs" onClick={() => handleFollowUp(q)}>
              {q}
            </Button>
          ))}
        </div>
      )}

      {/* 输入区域 */}
      <div className="p-3 border-t">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入股票代码或分析问题..."
            rows={1}
            className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            disabled={isStreaming}
          />
          <Button size="icon" onClick={handleSend} disabled={isStreaming || !input.trim()}>
            {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
