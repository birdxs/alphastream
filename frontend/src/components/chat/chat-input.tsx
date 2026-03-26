// Input: 用户键盘输入、股票代码选择、市场类型选择、停止生成回调、文件附件、语音输入
// Output: 聊天输入框UI（含股票代码快捷选择、市场切换、自选按钮、停止生成按钮、自动增高、附件预览、语音录入）
// Pos: chat-panel.tsx的子组件，负责用户输入与发送
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useRef, useEffect, useCallback, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { useChatStore } from "@/lib/stores/chat-store";
import { useWatchlistStore } from "@/lib/stores/watchlist-store";
import { useToast } from "@/components/common/toast-provider";
import { CommandPalette } from "./command-palette";
import { Send, Square, Star, Paperclip, Mic, X } from "lucide-react";

// ── 附件类型 ──
interface AttachedFile {
  file: File;
  previewUrl: string | null; // 图片有 objectURL，PDF 为 null
}

// ── 语音识别类型（兼容 webkit 前缀） ──
interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((e: { results: { [index: number]: { [index: number]: { transcript: string } } } }) => void) | null;
  onerror: ((e: unknown) => void) | null;
  onend: (() => void) | null;
}

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

interface Props {
  onSend: (message: string, options: { stock_code?: string; market_type?: string }) => void;
  onStop: () => void;
}

export function ChatInput({ onSend, onStop }: Props) {
  const [input, setInput] = useState("");
  const [stockCode, setStockCode] = useState("");
  const [marketType, setMarketType] = useState("A");
  const [attachments, setAttachments] = useState<AttachedFile[]>([]);
  const [isListening, setIsListening] = useState(false);
  const isStreaming = useChatStore(s => s.isStreaming);
  const { addItem, hasItem } = useWatchlistStore();
  const { toast } = useToast();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  // 检测浏览器是否支持语音识别（延迟到客户端挂载后检测，避免 Hydration mismatch）
  const [speechSupported, setSpeechSupported] = useState(false);
  useEffect(() => {
    setSpeechSupported(getSpeechRecognition() !== null);
  }, []);

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

  // ── 附件处理 ──
  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    const newAttachments: AttachedFile[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const isImage = file.type.startsWith("image/");
      newAttachments.push({
        file,
        previewUrl: isImage ? URL.createObjectURL(file) : null,
      });
    }
    setAttachments((prev) => [...prev, ...newAttachments]);
    // 重置 input 以允许再次选择同一文件
    e.target.value = "";
  }, []);

  const removeAttachment = useCallback((index: number) => {
    setAttachments((prev) => {
      const removed = prev[index];
      if (removed?.previewUrl) URL.revokeObjectURL(removed.previewUrl);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  // 清理 objectURL
  useEffect(() => {
    return () => {
      attachments.forEach((a) => {
        if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 语音识别 ──
  const toggleListening = useCallback(() => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }
    const SpeechRec = getSpeechRecognition();
    if (!SpeechRec) return;
    const recognition = new SpeechRec();
    recognition.lang = "zh-CN";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (e) => {
      const transcript = e.results[0]?.[0]?.transcript ?? "";
      if (transcript) {
        setInput((prev) => prev + transcript);
      }
    };
    recognition.onerror = () => {
      setIsListening(false);
    };
    recognition.onend = () => {
      setIsListening(false);
    };
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, [isListening]);

  const handleSend = () => {
    const msg = input.trim();
    if (!msg || isStreaming) return;
    setInput("");
    // 清理附件（当前仅前端展示，后端暂不支持上传）
    attachments.forEach((a) => { if (a.previewUrl) URL.revokeObjectURL(a.previewUrl); });
    setAttachments([]);
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
    <div className="bg-[rgba(10,10,26,0.8)] backdrop-blur-xl border-t border-white/[0.08]">
      {/* 股票选择行 */}
      <div className="flex items-center gap-1.5 px-3 pt-2">
        <div className="flex items-center gap-0.5 bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1 shadow-sm">
          <input
            type="text"
            value={stockCode}
            onChange={(e) => setStockCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="代码"
            aria-label="股票代码"
            className="w-14 bg-transparent text-[11px] font-mono focus:outline-none placeholder:text-muted-foreground/35"
            maxLength={6}
          />
          <div className="w-px h-3.5 bg-border/60" />
          <select
            value={marketType}
            onChange={(e) => setMarketType(e.target.value)}
            aria-label="市场类型"
            className="bg-transparent text-[11px] focus:outline-none cursor-pointer text-muted-foreground/70 pr-0.5"
          >
            <option value="A">A股</option>
            <option value="HK">港股</option>
            <option value="US">美股</option>
          </select>
        </div>
        {stockCode && stockCode.length === 6 && (
          <Button
            variant="ghost" size="sm" className="h-6 gap-1 text-[11px] px-1.5"
            onClick={() => addItem(stockCode)}
          >
            <Star className={`h-3 w-3 ${hasItem(stockCode) ? 'fill-yellow-500 text-yellow-500' : 'text-muted-foreground/50'}`} />
            {hasItem(stockCode) ? '已自选' : '自选'}
          </Button>
        )}
        <div className="flex gap-0.5 ml-auto">
          {["600519", "000001"].map(code => (
            <button
              key={code}
              onClick={() => setStockCode(code)}
              className={`text-[10px] font-mono px-1.5 py-0.5 rounded-md transition-all duration-150 ${
                stockCode === code ? 'bg-[#3737CC]/15 text-[#3737CC] ring-1 ring-[#3737CC]/20' : 'text-muted-foreground/60 hover:bg-muted hover:text-muted-foreground'
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

        {/* 附件预览区 */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {attachments.map((att, idx) => (
              <div
                key={idx}
                className="relative group flex items-center gap-2 px-2.5 py-1.5 rounded-xl border border-white/[0.1] bg-white/[0.06] backdrop-blur-xl shadow-sm max-w-[180px]"
              >
                {att.previewUrl ? (
                  <img
                    src={att.previewUrl}
                    alt={att.file.name}
                    className="h-10 w-10 rounded-lg object-cover shrink-0"
                  />
                ) : (
                  <div className="h-10 w-10 rounded-lg bg-white/[0.08] flex items-center justify-center text-[10px] font-mono text-muted-foreground/70 shrink-0">
                    PDF
                  </div>
                )}
                <span className="text-[11px] text-muted-foreground/80 truncate">
                  {att.file.name}
                </span>
                <button
                  onClick={() => removeAttachment(idx)}
                  className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-[#0A0A1A] border border-white/[0.15] flex items-center justify-center text-muted-foreground/70 hover:text-[#EF4444] hover:border-[#EF4444]/30 transition-colors opacity-0 group-hover:opacity-100"
                  aria-label="移除附件"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* 语音聆听提示 */}
        {isListening && (
          <div className="flex items-center gap-2 mb-2 px-3 py-1.5 rounded-xl bg-[#EF4444]/10 border border-[#EF4444]/20 text-[#EF4444] text-xs font-medium animate-pulse">
            <Mic className="h-3.5 w-3.5" />
            正在聆听...
          </div>
        )}

        <div className="flex gap-2 items-end">
          {/* 附件按钮 */}
          <button
            className="rounded-2xl h-10 w-10 shrink-0 flex items-center justify-center text-muted-foreground/50 hover:text-muted-foreground hover:bg-white/[0.06] transition-all duration-200"
            onClick={() => fileInputRef.current?.click()}
            aria-label="添加附件"
            title="上传图片或PDF"
          >
            <Paperclip className="h-4 w-4" />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.pdf"
            multiple
            className="hidden"
            onChange={handleFileSelect}
          />

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
              className="w-full resize-none rounded-2xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#3737CC]/20 focus:border-[#3737CC] transition-all duration-200 placeholder:text-muted-foreground/35"
              disabled={isStreaming}
              style={{ minHeight: '40px', maxHeight: '120px' }}
            />
          </div>

          {/* 语音按钮 — 不支持时隐藏 */}
          {speechSupported && (
            <button
              className={`rounded-2xl h-10 w-10 shrink-0 flex items-center justify-center transition-all duration-200 ${
                isListening
                  ? 'bg-[#EF4444] text-white shadow-lg shadow-[#EF4444]/30 animate-pulse'
                  : 'text-muted-foreground/50 hover:text-muted-foreground hover:bg-white/[0.06]'
              }`}
              onClick={toggleListening}
              aria-label={isListening ? "停止录音" : "语音输入"}
              title={isListening ? "停止录音" : "语音输入"}
            >
              <Mic className="h-4 w-4" />
            </button>
          )}

          {isStreaming ? (
            <Button
              size="icon"
              variant="destructive"
              className="rounded-2xl h-10 w-10 shrink-0 shadow-md"
              onClick={onStop}
              aria-label="停止生成"
            >
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <button
              className={`rounded-2xl h-10 w-10 shrink-0 flex items-center justify-center transition-all duration-200 ${
                input.trim()
                  ? 'bg-gradient-to-r from-[#3737CC] to-[#4F4FE6] text-white shadow-lg shadow-[#3737CC]/25 hover:scale-105 transition-transform active:scale-95'
                  : 'bg-muted text-muted-foreground/40 cursor-not-allowed'
              }`}
              onClick={handleSend}
              disabled={!input.trim()}
              aria-label="发送消息"
              tabIndex={11}
            >
              <Send className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
