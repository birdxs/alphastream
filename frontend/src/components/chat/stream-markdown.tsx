// Input: Markdown文本内容 + 流式状态标志
// Output: 渲染后的Markdown富文本（含代码高亮、表格、列表、金融数据强调）
// Pos: message-bubble.tsx / chat-panel.tsx 的子组件，负责AI消息的Markdown渲染
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

interface Props {
  content: string;
  isStreaming?: boolean;
}

const markdownComponents: Components = {
  // 自定义代码块渲染
  code({ className, children, ...props }) {
    const isInline = !className;
    if (isInline) {
      return (
        <code className="bg-white/[0.04] border border-white/[0.08] px-1 py-0.5 rounded text-xs font-mono" {...props}>
          {children}
        </code>
      );
    }
    return (
      <pre className="bg-white/[0.04] border border-white/[0.08] rounded-lg p-3 overflow-x-auto">
        <code className="text-xs font-mono" {...props}>
          {children}
        </code>
      </pre>
    );
  },
  // 表格样式
  table({ children }) {
    return (
      <div className="overflow-x-auto my-2 rounded-lg border border-white/[0.08]">
        <table className="min-w-full text-sm">{children}</table>
      </div>
    );
  },
  th({ children }) {
    return (
      <th className="border-b-2 border-white/[0.08] px-3 py-2 text-left font-semibold bg-white/[0.04] text-xs uppercase tracking-wider">
        {children}
      </th>
    );
  },
  td({ children }) {
    return <td className="border-b border-white/[0.08] px-3 py-1.5 even:bg-white/[0.02] tabular-nums">{children}</td>;
  },
  tr({ children }) {
    return <tr className="hover:bg-white/[0.04] transition-colors">{children}</tr>;
  },
  // 强调数字（金融数据高亮）
  strong({ children }) {
    return <strong className="text-primary font-semibold">{children}</strong>;
  },
};

export function StreamMarkdown({ content, isStreaming }: Props) {
  const memoizedContent = useMemo(() => (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {content}
    </ReactMarkdown>
  ), [content]);

  return (
    <div className="prose prose-sm dark:prose-invert max-w-none">
      {isStreaming ? (
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {content}
        </ReactMarkdown>
      ) : (
        memoizedContent
      )}
      {isStreaming && (
        <span className="typing-cursor" />
      )}
    </div>
  );
}
