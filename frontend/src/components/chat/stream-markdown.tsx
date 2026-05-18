// Input: Markdown文本内容 + 流式状态标志
// Output: 渲染后的Markdown富文本（含代码高亮、表格、列表、金融数据强调）；流式模式下末尾文字有渐现效果+打字光标
// Pos: message-bubble.tsx / chat-panel.tsx 的子组件，负责AI消息的Markdown渲染
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Fragment, useMemo, useRef, useEffect, useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { Copy, Check } from "lucide-react";
// [FIX-9 2026-05-18] mimo/DeepSeek tool_call 文本流模板化渲染
import { parseMessageWithToolCalls, hasToolCallMarkup } from "@/lib/parsers/tool-call-parser";
import { ToolCallCard } from "@/components/chat/tool-call-card";

interface Props {
  content: string;
  isStreaming?: boolean;
}

/** 代码块复制按钮 */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);
  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 bg-foreground/[0.08] dark:bg-white/[0.08] hover:bg-foreground/[0.15] dark:hover:bg-white/[0.15] rounded p-1 transition-colors duration-200"
      aria-label="复制代码"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-[#46BEA3]" /> : <Copy className="h-3.5 w-3.5 text-muted-foreground/70" />}
    </button>
  );
}

const markdownComponents: Components = {
  // 自定义代码块渲染 — glass效果 + 一键复制
  code({ className, children, ...props }) {
    const isInline = !className;
    if (isInline) {
      return (
        <code className="bg-[var(--glass-bg)] border border-[var(--glass-border)] px-1.5 py-0.5 rounded text-xs font-mono text-[var(--brand-primary-light,#4F4FE6)]" {...props}>
          {children}
        </code>
      );
    }
    // 提取纯文本用于复制
    const codeText = String(children).replace(/\n$/, '');
    return (
      <pre className="relative bg-[var(--glass-bg)] border border-[var(--glass-border)] rounded-xl p-3 overflow-x-auto backdrop-blur-sm shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] group">
        <CopyButton text={codeText} />
        <code className="text-xs font-mono leading-relaxed" {...props}>
          {children}
        </code>
      </pre>
    );
  },
  // 表格样式 — glass效果
  table({ children }) {
    return (
      <div className="overflow-x-auto my-2 rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] backdrop-blur-sm">
        <table className="min-w-full text-sm">{children}</table>
      </div>
    );
  },
  th({ children }) {
    return (
      <th className="border-b border-[var(--glass-border)] px-3 py-2 text-left font-semibold bg-foreground/[0.04] dark:bg-white/[0.04] text-xs uppercase tracking-wider text-[var(--text-secondary,#8888A0)]">
        {children}
      </th>
    );
  },
  td({ children }) {
    return <td className="border-b border-[var(--glass-border)] px-3 py-1.5 even:bg-foreground/[0.02] dark:bg-white/[0.02] tabular-nums">{children}</td>;
  },
  tr({ children }) {
    return <tr className="hover:bg-[var(--glass-bg-hover)] transition-colors duration-200">{children}</tr>;
  },
  // 链接 — 品牌色
  a({ href, children }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-[var(--brand-primary-light,#4F4FE6)] hover:text-[var(--brand-primary,#3737CC)] underline underline-offset-2 decoration-[var(--brand-primary,#3737CC)]/30 hover:decoration-[var(--brand-primary,#3737CC)]/60 transition-colors duration-200">
        {children}
      </a>
    );
  },
  // 强调数字（金融数据高亮）
  strong({ children }) {
    return <strong className="text-primary font-semibold">{children}</strong>;
  },
};

/**
 * 流式渲染时，将最后一个词/字符用渐现span包裹，配合 .typing-cursor 光标
 * 非流式模式（历史消息）直接渲染，无任何动画效果
 */
function StreamingWrapper({ content }: { content: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const prevLenRef = useRef(0);

  useEffect(() => {
    if (!containerRef.current) return;
    const len = content.length;
    // 仅在内容增长时为最后一个文本节点添加渐现效果
    if (len > prevLenRef.current) {
      // 找到容器中最后一个文本节点的父元素
      const walker = document.createTreeWalker(
        containerRef.current,
        NodeFilter.SHOW_TEXT,
        null
      );
      let lastTextNode: Text | null = null;
      while (walker.nextNode()) {
        lastTextNode = walker.currentNode as Text;
      }
      if (lastTextNode && lastTextNode.parentElement) {
        const parent = lastTextNode.parentElement;
        // 添加渐现class（如果还没有的话）
        parent.classList.add('streaming-fade-in');
        // 下一帧移除以便再次触发
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            parent.classList.remove('streaming-fade-in');
          });
        });
      }
    }
    prevLenRef.current = len;
  }, [content]);

  return (
    <div ref={containerRef}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

export function StreamMarkdown({ content, isStreaming }: Props) {
  // [FIX-9] 含 <tool_call> 标记走分段渲染，否则保持原 Markdown 路径（零回归）
  const hasTool = hasToolCallMarkup(content);

  const memoizedContent = useMemo(() => (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {content}
    </ReactMarkdown>
  ), [content]);

  // 分段渲染: 文本段走 Markdown, tool_call 段走卡片组件
  const segmentedContent = useMemo(() => {
    if (!hasTool) return null;
    const segs = parseMessageWithToolCalls(content);
    return (
      <>
        {segs.map((s, i) =>
          s.type === "tool_call" ? (
            <ToolCallCard key={`tc-${i}`} segment={s} />
          ) : (
            <Fragment key={`tx-${i}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {s.value}
              </ReactMarkdown>
            </Fragment>
          )
        )}
      </>
    );
  }, [content, hasTool]);

  return (
    <div className="prose prose-sm dark:prose-invert max-w-none">
      {hasTool ? (
        segmentedContent
      ) : isStreaming ? (
        <StreamingWrapper content={content} />
      ) : (
        memoizedContent
      )}
      {isStreaming && !hasTool && (
        <span className="typing-cursor" />
      )}
    </div>
  );
}
