// Input: localStorage 'wind_enabled' 状态
// Output: (enabled: boolean, setEnabled: (v: boolean) => void)
// Pos: 全局 Wind 数据源开关 hook
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect } from 'react';

/**
 * 全局 Wind 数据源开关 hook
 *
 * @returns {boolean} enabled - 当前 Wind 是否启用
 * @returns {function} setEnabled - 更新 Wind 启用状态（同步到 localStorage）
 *
 * @example
 * ```tsx
 * const { enabled, setEnabled } = useWindEnabled();
 * if (enabled) {
 *   // 调用带 use_wind=true 参数的 API
 * }
 * ```
 */
export function useWindEnabled() {
  const [enabled, setEnabled] = useState<boolean>(false);

  useEffect(() => {
    // SSR 守卫：仅客户端读取 localStorage
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('wind_enabled');
      // 延迟 setState 避免 cascading renders
      requestAnimationFrame(() => {
        setEnabled(stored === 'true');
      });
    }
  }, []);

  const updateEnabled = (value: boolean) => {
    setEnabled(value);
    if (typeof window !== 'undefined') {
      localStorage.setItem('wind_enabled', String(value));
    }
  };

  return { enabled, setEnabled: updateEnabled };
}
