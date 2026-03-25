// Input: left/right ReactNode面板, 宽度配置
// Output: 可拖拽调整宽度的双面板布局（含拖拽视觉反馈、双击重置、触摸支持）
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
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    setIsDragging(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const handlePointerMove = (ev: PointerEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setLeftWidth(Math.max(minLeftWidth, Math.min(maxLeftWidth, pct)));
    };

    const handlePointerUp = () => {
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('pointermove', handlePointerMove);
      document.removeEventListener('pointerup', handlePointerUp);
    };

    document.addEventListener('pointermove', handlePointerMove);
    document.addEventListener('pointerup', handlePointerUp);
  }, [minLeftWidth, maxLeftWidth]);

  return (
    <div ref={containerRef} className="flex h-full overflow-hidden">
      <div style={{ width: `${leftWidth}%` }} className="flex-shrink-0 overflow-hidden">
        {left}
      </div>
      <div
        className={`w-1 cursor-col-resize transition-all flex-shrink-0 ${
          isDragging ? 'w-1 bg-primary shadow-[0_0_8px_rgba(59,130,246,0.5)]' : 'hover:w-1.5 bg-border hover:bg-primary/30'
        }`}
        onPointerDown={handlePointerDown}
        onDoubleClick={() => setLeftWidth(defaultLeftWidth)}
      />
      <div className="flex-1 overflow-hidden">
        {right}
      </div>
    </div>
  );
}
