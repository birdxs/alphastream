// Input: localStorage 'wind_enabled' 状态
// Output: (enabled: boolean, setEnabled: (v: boolean) => void)
// Pos: 全局 Wind 数据源开关；client.ts 读同 key 注入 X-Use-Wind
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect } from 'react';

/** localStorage key — 与 client.ts windHeaders() 必须一致 */
export const WIND_ENABLED_STORAGE_KEY = 'wind_enabled';

/**
 * 全局 Wind 数据源开关 hook（opt-in）。
 * 开启后 apiClient 自动附 X-Use-Wind: true，后端才允许烧 Wind 积分。
 */
export function useWindEnabled() {
  const [enabled, setEnabled] = useState<boolean>(false);

  useEffect(() => {
    // SSR 守卫：仅客户端读取 localStorage
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(WIND_ENABLED_STORAGE_KEY);
      // 延迟 setState 避免 cascading renders
      requestAnimationFrame(() => {
        setEnabled(stored === 'true');
      });
    }
  }, []);

  const updateEnabled = (value: boolean) => {
    setEnabled(value);
    if (typeof window !== 'undefined') {
      localStorage.setItem(WIND_ENABLED_STORAGE_KEY, String(value));
    }
  };

  return { enabled, setEnabled: updateEnabled };
}
