// Input: 用户键盘输入、股票代码选择、市场类型选择、停止生成回调
// Output: 聊天输入框UI（含股票代码快捷选择、市场切换、自选按钮、停止生成按钮、自动增高）
// Pos: chat-panel.tsx的子组件，负责用户输入与发送
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { useChatStore } from "@/lib/stores/chat-store";
import { useWatchlistStore } from "@/lib/stores/watchlist-store";
import { CommandPalette } from "./command-palette";
import { Send, Square, Star } from "lucide-react";

interface Props {
  onSend: (message: string, options: { stock_code?: string; market_type?: string }) => void;
  onStop: () => void;
}

export function ChatInput({ onSend, onStop }: Props) {
  const [input, setInput] = useState("");
  const [stockCode, setStockCode] = useState("");
  const [marketType, setMarketType] = useState("A");
  const isStreaming = useChatStore(s => s.isStreaming);
  const { addItem, hasItem } = useWatchlistStore();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // P2: 流式结束后自动聚焦输入框
  useEffect(() => {
    if (!isStreaming) {
      textareaRef.current?.focus();
    }
  }, [isStreaming]);

  // P0-1: 输入框自动增高
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = '40px'; // reset
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
  }, [input]);

  // 移动端虚拟键盘弹出时，确保输入框不被遮挡
  useEffect(() => {
    if (typeof window !== 'undefined' && window.visualViewport) {
      const handleResize = () => {
        const viewport = window.visualViewport!;
        document.documentElement.style.setProperty('--viewport-height', `${viewport.height}px`);
      };
      window.visualViewport.addEventListener('resize', handleResize);
      return () => window.visualViewport?.removeEventListener('resize', handleResize);
    }
  }, []);

  const handleSend = () => {
    const msg = input.trim();
    if (!msg || isStreaming) return;
    setInput("");
    const codeMatch = msg.match(/(\d{6})/);
    const code = codeMatch ? codeMatch[1] : stockCode;
    if (code) setStockCode(code);
    onSend(msg, { stock_code: code, market_type: marketType });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // 当命令面板可见时，不处理Enter（交给CommandPalette处理）
    if (input.startsWith("/") && (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter")) {
      // 这些键由CommandPalette的全局监听处理
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t bg-background/95 backdrop-blur-sm">
      {/* 股票选择行 */}
      <div className="flex items-center gap-2 px-3 pt-2">
        <div className="flex items-center gap-1 bg-muted/70 rounded-lg px-2.5 py-1.5 border border-border/50">
          <input
            type="text"
            value={stockCode}
            onChange={(e) => setStockCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="代码"
            aria-label="股票代码"
            className="w-16 bg-transparent text-xs font-mono focus:outline-none placeholder:text-muted-foreground/50"
            maxLength={6}
          />
          <div className="w-px h-4 bg-border" />
          <select
            value={marketType}
            onChange={(e) => setMarketType(e.target.value)}
            aria-label="市场类型"
            className="bg-transparent text-xs focus:outline-none cursor-pointer text-muted-foreground"
          >
            <option value="A">A股</option>
            <option value="HK">港股</option>
            <option value="US">美股</option>
          </select>
        </div>
        {stockCode && stockCode.length === 6 && (
          <Button
            variant="ghost" size="sm" className="h-7 gap-1 text-xs"
            onClick={() => addItem(stockCode)}
          >
            <Star className={`h-3 w-3 ${hasItem(stockCode) ? 'fill-yellow-500 text-yellow-500' : 'text-muted-foreground'}`} />
            {hasItem(stockCode) ? '已自选' : '自选'}
          </Button>
        )}
        <div className="flex gap-1 ml-auto">
          {["600519", "000001"].map(code => (
            <button
              key={code}
              onClick={() => setStockCode(code)}
              className={`text-[10px] px-1.5 py-0.5 rounded-md transition-colors ${
                stockCode === code ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:bg-muted'
              }`}
            >
              {code}
            </button>
          ))}
        </div>
      </div>

      {/* 输入框 */}
      <div className="p-3 relative">
        <CommandPalette
          input={input}
          onSelect={(cmd) => setInput(cmd)}
          visible={input.startsWith("/")}
        />
        <div className="flex gap-2 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入股票代码或分析问题... (Shift+Enter换行)"
              aria-label="消息输入框"
              rows={1}
              tabIndex={10}
              className="w-full resize-none rounded-xl border border-border/60 bg-muted/30 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary/40 transition-all placeholder:text-muted-foreground/50"
              disabled={isStreaming}
              style={{ minHeight: '40px', maxHeight: '120px' }}
            />
          </div>
          {isStreaming ? (
            <Button
              size="icon"
              variant="destructive"
              className="rounded-xl h-10 w-10 shrink-0"
              onClick={onStop}
              aria-label="停止生成"
            >
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              className="rounded-xl h-10 w-10 shrink-0"
              onClick={handleSend}
              disabled={!input.trim()}
              aria-label="发送消息"
              tabIndex={11}
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
