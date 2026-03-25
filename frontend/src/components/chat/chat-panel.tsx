// Input: chat-store状态 + agent-store状态 + 用户输入
// Output: 完整Chat对话面板UI（消息列表、流式Markdown显示、输入框、快捷命令面板、Follow-up建议、Agent进度）
// Pos: 首页左侧面板，Chat+Artifacts布局的对话侧
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { useChatStore } from "@/lib/stores/chat-store";

import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Send, Loader2, Star } from "lucide-react";
import { useWatchlistStore } from "@/lib/stores/watchlist-store";
import { MessageBubble } from "./message-bubble";
import { AgentProgressPanel } from "@/components/agent/agent-progress-panel";
import { StreamMarkdown } from "./stream-markdown";
import { CommandPalette } from "./command-palette";

export function ChatPanel() {
  const [input, setInput] = useState("");
  const [stockCode, setStockCode] = useState("");
  const [marketType, setMarketType] = useState("A");
  const scrollRef = useRef<HTMLDivElement>(null);
  const { sendMessage } = useChatStream();
  const { messages, isStreaming, streamingContent, followUpQuestions } = useChatStore();
  const { addItem, hasItem } = useWatchlistStore();


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

    await sendMessage(msg, { stock_code: code, market_type: marketType });
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
          <div className="flex items-center gap-1">
            <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded">
              {stockCode}
            </span>
            <Button
              variant="ghost" size="icon" className="h-6 w-6"
              onClick={() => addItem(stockCode)}
              title={hasItem(stockCode) ? "已在自选" : "加入自选"}
            >
              <Star className={`h-3 w-3 ${hasItem(stockCode) ? 'fill-yellow-500 text-yellow-500' : ''}`} />
            </Button>
          </div>
        )}
      </div>

      {/* 消息列表 */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {messages.length === 0 && !isStreaming && (
            <div className="text-center mt-12 space-y-6 animate-fade-in">
              <div className="text-4xl">🤖</div>
              <div>
                <h3 className="font-semibold text-lg">AI金融分析助手</h3>
                <p className="text-sm text-muted-foreground mt-1">输入股票代码或问题，开启智能分析</p>
              </div>
              <div className="space-y-2 max-w-xs mx-auto">
                <p className="text-xs text-muted-foreground">快速开始</p>
                {[
                  { icon: "📈", text: "分析600519贵州茅台", desc: "技术面+基本面综合分析" },
                  { icon: "🔍", text: "对比银行板块龙头", desc: "行业对比分析" },
                  { icon: "📊", text: "今日大盘走势如何", desc: "市场概览" },
                  { icon: "⚠️", text: "600519有哪些风险", desc: "风险评估" },
                ].map((q) => (
                  <button
                    key={q.text}
                    onClick={() => handleFollowUp(q.text)}
                    className="w-full text-left flex items-center gap-3 p-2.5 rounded-lg border hover:bg-accent transition-colors"
                  >
                    <span className="text-lg">{q.icon}</span>
                    <div>
                      <p className="text-sm font-medium">{q.text}</p>
                      <p className="text-xs text-muted-foreground">{q.desc}</p>
                    </div>
                  </button>
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
              <div className="flex-1">
                <StreamMarkdown content={streamingContent} isStreaming={true} />
              </div>
            </div>
          )}

          {/* Agent进度 */}
          {isStreaming && <AgentProgressPanel />}

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
      <div className="p-3 border-t relative">
        <CommandPalette
          input={input}
          onSelect={(cmd) => { setInput(cmd); }}
          visible={input.startsWith("/")}
        />
        {/* 股票快捷输入行 */}
        <div className="flex items-center gap-2 mb-2">
          <div className="flex items-center gap-1 bg-muted rounded-md px-2 py-1">
            <input
              type="text"
              value={stockCode}
              onChange={(e) => setStockCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="代码"
              className="w-16 bg-transparent text-xs font-mono focus:outline-none"
              maxLength={6}
            />
            <select
              value={marketType}
              onChange={(e) => setMarketType(e.target.value)}
              className="bg-transparent text-xs focus:outline-none cursor-pointer"
            >
              <option value="A">A股</option>
              <option value="HK">港股</option>
              <option value="US">美股</option>
            </select>
          </div>
          <div className="flex gap-1">
            {["600519", "000001", "000858"].map(code => (
              <button
                key={code}
                onClick={() => setStockCode(code)}
                className={`text-xs px-1.5 py-0.5 rounded ${stockCode === code ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80'}`}
              >
                {code}
              </button>
            ))}
          </div>
        </div>
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
