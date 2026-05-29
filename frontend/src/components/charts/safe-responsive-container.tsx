// Input: width, height, children(Recharts 图表元素), className, aria-label
// Output: 容器实测宽高均 >0 才挂载 Recharts ResponsiveContainer，否则渲染 Skeleton 占位
// Pos: components/charts/safe-responsive-container.tsx - ResponsiveContainer 安全封装，消除 width(-1)/height(-1) 警告
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
// P1: 图表容器被隐藏(display:none)/切换/未完成布局时 Recharts 测得 -1，本封装在尺寸有效前不挂载图表

"use client";
import { ReactElement, useEffect, useRef, useState } from "react";
import { ResponsiveContainer } from "recharts";
import { Skeleton } from "@/components/ui/skeleton";

interface Props {
  /** 与 Recharts ResponsiveContainer 同义：数值或百分比字符串 */
  width?: number | string;
  /** 与 Recharts ResponsiveContainer 同义：数值或百分比字符串 */
  height?: number | string;
  /** 单个 Recharts 图表元素 */
  children: ReactElement;
  className?: string;
  "aria-label"?: string;
}

/**
 * 计算占位骨架的内联高度：height 为数值时用该值，百分比/auto 时用 100% 撑满父容器。
 */
function placeholderStyle(height?: number | string): React.CSSProperties {
  if (typeof height === "number") return { height };
  return { height: "100%", minHeight: 1 };
}

/**
 * SafeResponsiveContainer
 * - 用 ResizeObserver 实测外层 div 的渲染宽高。
 * - 仅当 width>0 且 height>0 时才挂载 Recharts ResponsiveContainer。
 * - 尺寸 <=0（容器隐藏/切换/未完成布局）时渲染 Skeleton 占位，待尺寸有效再渲染图表。
 * - SSR 安全：初始为未就绪态（渲染 Skeleton），ResizeObserver 仅在 useEffect 客户端执行。
 */
export function SafeResponsiveContainer({
  width = "100%",
  height = "100%",
  children,
  className,
  "aria-label": ariaLabel,
}: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const el = ref.current;
    if (!el) return;

    const measure = () => {
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      // 无 ResizeObserver 环境（如老式 jsdom）时无法持续观测，
      // 退化为：只要不是负尺寸即放行，避免图表永久不渲染。
      if (typeof ResizeObserver === "undefined") {
        setReady(w >= 0 && h >= 0);
        return;
      }
      setReady(w > 0 && h > 0);
    };

    // 通过 rAF 在首帧布局完成后再测量，避免在 effect 内同步 setState 触发级联渲染，
    // 同时拿到更准确的渲染尺寸（隐藏容器此时仍为 0）。
    let raf = 0;
    raf = requestAnimationFrame(measure);

    if (typeof ResizeObserver === "undefined") {
      return () => cancelAnimationFrame(raf);
    }

    const ro = new ResizeObserver(() => measure());
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  // 外层 div 继承传入的 width/height，保证布局占位与原 ResponsiveContainer 一致
  const outerStyle: React.CSSProperties = {
    width: typeof width === "number" ? width : "100%",
    height: typeof height === "number" ? height : "100%",
  };

  return (
    <div ref={ref} className={className} style={outerStyle}>
      {ready ? (
        <ResponsiveContainer width="100%" height="100%" aria-label={ariaLabel}>
          {children}
        </ResponsiveContainer>
      ) : (
        <Skeleton className="w-full h-full rounded" style={placeholderStyle(height)} aria-label={ariaLabel} />
      )}
    </div>
  );
}
