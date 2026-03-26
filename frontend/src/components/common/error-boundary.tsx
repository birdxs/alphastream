// Input: children (React组件树)
// Output: 错误时显示毛玻璃错误卡片+重试按钮，正常时透传children
// Pos: components/common/error-boundary.tsx - 防白屏Error Boundary
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

interface Props {
  children: ReactNode;
  /** 出错时显示的回退标题，默认"组件渲染出错" */
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[ErrorBoundary]", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      const title = this.props.fallbackTitle || "组件渲染出错";
      return (
        <div className="bg-white/[0.04] backdrop-blur-md border border-white/[0.08] rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.36)] p-5 flex flex-col items-center gap-3 text-center">
          <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
            <AlertTriangle className="h-5 w-5 text-red-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">{title}</p>
            <p className="text-xs text-muted-foreground mt-1 max-w-xs break-all">
              {this.state.error?.message || "未知错误"}
            </p>
          </div>
          <button
            onClick={this.handleRetry}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-white/[0.06] border border-white/[0.1] hover:bg-white/[0.12] hover:border-white/[0.2] transition-all duration-200 text-foreground"
          >
            <RotateCcw className="h-3 w-3" />
            重试
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
