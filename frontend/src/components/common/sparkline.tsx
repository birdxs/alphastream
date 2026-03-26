// Input: 数据数组 + 配置 (width, height, color, showDot, className)
// Output: 内联迷你折线SVG
// Pos: components/common/sparkline.tsx - 内联迷你趋势图
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  showDot?: boolean;
  className?: string;
}

export function Sparkline({
  data,
  width = 80,
  height = 24,
  color,
  showDot = true,
  className = "",
}: SparklineProps) {
  // data为空或长度<2时显示水平虚线
  if (!data || data.length < 2) {
    const midY = height / 2;
    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={className}
        aria-label="趋势数据不足"
      >
        <line
          x1={4}
          y1={midY}
          x2={width - 4}
          y2={midY}
          stroke="#8888A0"
          strokeWidth={1}
          strokeDasharray="3 3"
        />
      </svg>
    );
  }

  // 自动判断颜色
  const resolvedColor =
    color ?? (data[data.length - 1] > data[0] ? "#46BEA3" : "#FF8767");

  const padding = 2;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1; // 防止除零

  const points = data
    .map((v, i) => {
      const x = padding + (i / (data.length - 1)) * (width - padding * 2);
      const y =
        padding + (1 - (v - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");

  const lastX =
    padding + ((data.length - 1) / (data.length - 1)) * (width - padding * 2);
  const lastY =
    padding +
    (1 - (data[data.length - 1] - min) / range) * (height - padding * 2);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      aria-label="趋势迷你图"
    >
      <polyline
        points={points}
        fill="none"
        stroke={resolvedColor}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {showDot && (
        <circle cx={lastX} cy={lastY} r={2} fill={resolvedColor} />
      )}
    </svg>
  );
}
