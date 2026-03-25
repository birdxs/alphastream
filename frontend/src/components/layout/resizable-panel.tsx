// Input: left/right ReactNode面板, 宽度配置
// Output: 可拖拽调整宽度的双面板布局
// Pos: components/layout/resizable-panel.tsx - 桌面端可拖拽面板分隔器
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useRef, useCallback, ReactNode } from "react";

interface Props {
  left: ReactNode;
  right: ReactNode;
  defaultLeftWidth?: number; // 百分比
  minLeftWidth?: number;
  maxLeftWidth?: number;
}

export function ResizablePanel({ left, right, defaultLeftWidth = 35, minLeftWidth = 25, maxLeftWidth = 50 }: Props) {
  const [leftWidth, setLeftWidth] = useState(defaultLeftWidth);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const handleMouseDown = useCallback(() => {
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setLeftWidth(Math.max(minLeftWidth, Math.min(maxLeftWidth, pct)));
    };

    const handleMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [minLeftWidth, maxLeftWidth]);

  return (
    <div ref={containerRef} className="flex h-full overflow-hidden">
      <div style={{ width: `${leftWidth}%` }} className="flex-shrink-0 overflow-hidden">
        {left}
      </div>
      <div
        className="w-1 hover:w-1.5 bg-border hover:bg-primary/30 cursor-col-resize transition-all flex-shrink-0 active:bg-primary/50"
        onMouseDown={handleMouseDown}
      />
      <div className="flex-1 overflow-hidden">
        {right}
      </div>
    </div>
  );
}
