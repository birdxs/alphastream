// Input: 用户键盘输入、停止生成回调、文件附件（图片上传至后端/api/upload_image）、语音输入
// Output: 聊天输入框UI（单行textarea + 附件/语音/发送按钮；股票代码从消息内自动提取6位数字，市场类型默认A股）
// Pos: chat-panel.tsx的子组件，负责用户输入与发送（含多模态图片上传）
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useRef, useEffect, useCallback, KeyboardEvent } from "react";
import { useChatStore } from "@/lib/stores/chat-store";
import { useToast } from "@/components/common/toast-provider";
import { CommandPalette } from "./command-palette";
import { Send, Paperclip, Mic, X, Loader2 } from "lucide-react";
import { inferMarketType } from "@/lib/utils/stock-code";

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
  const [attachments, setAttachments] = useState<AttachedFile[]>([]);
  const [isListening, setIsListening] = useState(false);
  const [shaking, setShaking] = useState(false);
  const isStreaming = useChatStore(s => s.isStreaming);
  const { toast } = useToast();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  const activeConversationId = useChatStore(s => s.activeConversationId);

  // 首屏固定为不显示语音按钮，挂载后再检测浏览器能力，避免 SSR/CSR 首帧按钮树不一致。
  const [speechSupported, setSpeechSupported] = useState(false);

  // 页面加载后自动聚焦
  useEffect(() => {
    Promise.resolve().then(() => setSpeechSupported(getSpeechRecognition() !== null));
    textareaRef.current?.focus();
  }, []);

  // 切换对话后自动聚焦
  useEffect(() => {
    textareaRef.current?.focus();
  }, [activeConversationId]);

  // P2: 流式结束后自动聚焦输入框
  useEffect(() => {
    if (!isStreaming) {
      textareaRef.current?.focus();
    }
  }, [isStreaming]);

  // 监听 chat-prefill 事件，预填输入框文本
  useEffect(() => {
    const handler = (e: Event) => {
      const text = (e as CustomEvent<string>).detail;
      if (text) {
        setInput(text);
        setTimeout(() => textareaRef.current?.focus(), 100);
      }
    };
    window.addEventListener("chat-prefill", handler);
    return () => window.removeEventListener("chat-prefill", handler);
  }, []);

  // P0-1: 输入框自动增高 + 仅满高度时显示滚动条
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = '40px'; // reset
      const next = Math.min(ta.scrollHeight, 120);
      ta.style.height = next + 'px';
      // 未达 max-h 时隐藏滚动条，达到才显示
      ta.style.overflowY = ta.scrollHeight > 120 ? 'auto' : 'hidden';
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

  // 清理 objectURL — 用ref追踪最新attachments，unmount时revoke所有
  const attachmentsRef = useRef(attachments);
  useEffect(() => {
    attachmentsRef.current = attachments;
  });
  useEffect(() => {
    return () => {
      attachmentsRef.current.forEach((a) => {
        if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
      });
    };
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

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || isStreaming) {
      if (!msg && !isStreaming) {
        // 空消息 shake 动画
        setShaking(true);
        setTimeout(() => setShaking(false), 300);
      }
      return;
    }
    setInput("");
    // 发送后输入框微缩放过渡
    const ta = textareaRef.current;
    if (ta) {
      ta.style.transform = 'scale(0.98)';
      ta.style.opacity = '0.7';
      requestAnimationFrame(() => {
        setTimeout(() => {
          ta.style.transform = 'scale(1)';
          ta.style.opacity = '1';
        }, 80);
      });
    }

    // 上传图片附件到后端
    const uploadedFiles: { filename: string; size: number; filepath: string }[] = [];
    const imageAttachments = attachments.filter((a) => a.file.type.startsWith("image/"));
    if (imageAttachments.length > 0) {
      for (const att of imageAttachments) {
        try {
          const formData = new FormData();
          formData.append("file", att.file);
          const res = await fetch("/api/upload_image", { method: "POST", body: formData });
          if (!res.ok) {
            const err = await res.json().catch(() => ({ error: "上传失败" }));
            toast(`图片上传失败: ${err.error || "未知错误"}`, "error");
            continue;
          }
          const result = await res.json();
          if (result.success) {
            uploadedFiles.push({ filename: result.filename, size: result.size, filepath: result.filepath });
          }
        } catch {
          toast("图片上传失败: 网络错误", "error");
        }
      }
    }

    // 清理附件
    attachments.forEach((a) => { if (a.previewUrl) URL.revokeObjectURL(a.previewUrl); });
    setAttachments([]);
    const codeMatch = msg.match(/(\d{6})/);
    const code = codeMatch ? codeMatch[1] : undefined;

    // 将上传文件信息附加到消息中
    let finalMsg = msg;
    if (uploadedFiles.length > 0) {
      const fileInfo = uploadedFiles.map((f) => `[图片: ${f.filename}]`).join(" ");
      finalMsg = `${msg}\n${fileInfo}`;
    }
    onSend(finalMsg, { stock_code: code, market_type: code ? inferMarketType(code) : "A" });
    // 发送消息后自动聚焦
    setTimeout(() => textareaRef.current?.focus(), 50);
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
    <div className="bg-background/80 dark:bg-[rgba(10,10,26,0.8)] backdrop-blur-xl border-t border-foreground/[0.08] dark:border-white/[0.08]">
      {isStreaming && (
        <div
          className="flex items-center gap-2 px-3 pt-2 text-xs text-muted-foreground"
          role="status"
          aria-live="polite"
          data-testid="chat-input-waiting-status"
        >
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#3737CC] animate-pulse" />
          <span>AI 正在回复，可点停止中断</span>
        </div>
      )}
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
                className="relative group flex items-center gap-2 px-2.5 py-1.5 rounded-xl border border-foreground/[0.1] dark:border-white/[0.1] bg-foreground/[0.06] dark:bg-white/[0.06] backdrop-blur-xl shadow-sm max-w-[180px]"
              >
                {att.previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element -- blob URL, Next/Image 不支持 objectURL
                  <img
                    src={att.previewUrl}
                    alt={att.file.name}
                    className="h-10 w-10 rounded-lg object-cover shrink-0"
                  />
                ) : (
                  <div className="h-10 w-10 rounded-lg bg-foreground/[0.08] dark:bg-white/[0.08] flex items-center justify-center text-[10px] font-mono text-muted-foreground/70 shrink-0">
                    PDF
                  </div>
                )}
                <span className="text-[11px] text-muted-foreground/80 truncate">
                  {att.file.name}
                </span>
                <button
                  onClick={() => removeAttachment(idx)}
                  className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-card dark:bg-[#0A0A1A] border border-foreground/[0.15] dark:border-white/[0.15] flex items-center justify-center text-muted-foreground/70 hover:text-[#EF4444] hover:border-[#EF4444]/30 transition-colors opacity-0 group-hover:opacity-100"
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
            className="rounded-2xl h-10 w-10 shrink-0 flex items-center justify-center text-muted-foreground/50 hover:text-muted-foreground hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-all duration-200"
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

          <div className={`flex-1 relative ${shaking ? 'animate-shake' : ''}`}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入股票代码或分析问题... (Shift+Enter换行)"
              aria-label="消息输入框"
              rows={1}
              tabIndex={10}
              className="textarea-thin-scroll ui-chat-input w-full resize-none px-4 py-2.5 focus:outline-none transition-all duration-200 placeholder:text-[var(--text-muted)]"
              disabled={isStreaming}
              style={{ minHeight: '40px', maxHeight: '120px', overflowY: 'hidden' }}
            />
          </div>

          {/* 语音按钮 — 不支持时隐藏 */}
          {speechSupported && (
            <button
              className={`rounded-2xl h-10 w-10 shrink-0 flex items-center justify-center transition-all duration-200 ${
                isListening
                  ? 'bg-[#EF4444] text-white shadow-lg shadow-[#EF4444]/30 animate-pulse'
                  : 'text-muted-foreground/50 hover:text-muted-foreground hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06]'
              }`}
              onClick={toggleListening}
              aria-label={isListening ? "停止录音" : "语音输入"}
              title={isListening ? "停止录音" : "语音输入"}
            >
              <Mic className="h-4 w-4" />
            </button>
          )}

          {isStreaming ? (
            <button
              className="rounded-[var(--radius-lg)] h-10 w-10 shrink-0 flex items-center justify-center bg-[var(--accent)] text-white shadow-[var(--shadow-md)] transition-all duration-200 hover:scale-105 active:scale-95"
              onClick={onStop}
              aria-label="停止生成"
              title="停止生成"
            >
              <Loader2 className="h-4 w-4 animate-spin" />
            </button>
          ) : (
            <button
              className={`rounded-2xl h-10 w-10 shrink-0 flex items-center justify-center transition-all duration-200 ${
                input.trim()
                  ? 'bg-[var(--accent)] text-white shadow-[var(--shadow-md)] hover:scale-105 transition-transform active:scale-95'
                  : 'bg-muted text-muted-foreground/40 cursor-not-allowed'
              }`}
              onClick={handleSend}
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
