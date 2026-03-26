// Input: 目标数字 + 配置 (duration, decimals, enabled)
// Output: 动画中的当前值字符串 (toLocaleString格式)
// Pos: lib/hooks/use-count-up.ts - 数字跳动动画Hook
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { useEffect, useRef, useState } from "react";

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

export function useCountUp(
  target: number,
  options?: {
    duration?: number;
    decimals?: number;
    enabled?: boolean;
  }
): string {
  const { duration = 800, decimals = 2, enabled = true } = options ?? {};
  const [current, setCurrent] = useState(enabled ? 0 : target);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled) {
      setCurrent(target);
      return;
    }

    setCurrent(0);
    startTimeRef.current = null;

    const animate = (timestamp: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp;
      }

      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = easeOutCubic(progress);

      setCurrent(target * easedProgress);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [target, duration, enabled]);

  const absVal = Math.abs(current);
  const formatted = absVal.toLocaleString("zh-CN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return current < 0 ? `-${formatted}` : formatted;
}
