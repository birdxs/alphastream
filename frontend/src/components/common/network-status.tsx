// Input: 浏览器 navigator.onLine 状态 + 定期探测 /api/conversations
// Output: 网络断开或API不可达时显示顶部警告条
// Pos: 全局布局组件，layout.tsx 渲染顶部
'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * FIX-E4: 网络状态指示器
 * - 启动后给后端 8s 静默宽限期，不立刻弹横幅
 * - 连续 3 次失败才显示"正在重连"，10+ 次显示"后端服务不可达"
 * - 指数退避: 2s -> 4s -> 8s -> 16s -> 30s 封顶
 * - 探测超时 8s（替代旧的 5s）
 */
export function NetworkStatus() {
  const [status, setStatus] = useState<'ok' | 'reconnecting' | 'down'>('ok');
  const failuresRef = useRef(0);
  const recoveryToastUntilRef = useRef(0);
  const [showRecovery, setShowRecovery] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const RECONNECT_THRESHOLD = 3;
    const DOWN_THRESHOLD = 10;
    const BACKOFF = [2000, 4000, 8000, 16000, 30000];
    const STARTUP_GRACE_MS = 8000;

    let cancelled = false;

    const handleOnline = () => {
      failuresRef.current = 0;
      setStatus('ok');
    };
    const handleOffline = () => {
      // 浏览器明确 offline，直接显示 down
      setStatus('down');
    };
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    const checkApi = async () => {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
        const url = `${baseUrl}/health`;
        const res = await fetch(url, {
          method: 'GET',
          credentials: 'omit',
          cache: 'no-store',
          signal: AbortSignal.timeout(8000),
        });
        if (cancelled) return;
        if (res.ok) {
          const prevFailures = failuresRef.current;
          failuresRef.current = 0;
          if (prevFailures >= RECONNECT_THRESHOLD) {
            // 从可见的失败态恢复 → 弹 3s "已恢复" 提示
            recoveryToastUntilRef.current = Date.now() + 3000;
            setShowRecovery(true);
            setTimeout(() => setShowRecovery(false), 3000);
          }
          setStatus('ok');
        } else {
          failuresRef.current += 1;
          updateStatus();
        }
      } catch {
        if (cancelled) return;
        failuresRef.current += 1;
        updateStatus();
      } finally {
        if (!cancelled) {
          const idx = Math.min(failuresRef.current, BACKOFF.length - 1);
          const delay = failuresRef.current === 0 ? 30000 : BACKOFF[Math.max(0, idx - 1)];
          timerRef.current = setTimeout(checkApi, delay);
        }
      }
    };

    const updateStatus = () => {
      const f = failuresRef.current;
      if (f >= DOWN_THRESHOLD) {
        setStatus('down');
      } else if (f >= RECONNECT_THRESHOLD) {
        setStatus('reconnecting');
      } else {
        setStatus('ok'); // 仍在静默宽限内
      }
    };

    // 启动后给后端 8s 静默宽限再首次探测
    timerRef.current = setTimeout(checkApi, STARTUP_GRACE_MS);

    return () => {
      cancelled = true;
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  if (status === 'ok') {
    if (showRecovery) {
      return (
        <div
          className="fixed top-0 left-0 right-0 bg-emerald-600 text-white text-center py-1.5 text-sm z-50 shadow-md transition"
          role="status"
          aria-live="polite"
        >
          <span>网络已恢复</span>
        </div>
      );
    }
    return null;
  }

  // 浏览器明确 offline → 离线文案；否则按 down/reconnecting 区分
  const offlineHint = typeof navigator !== 'undefined' && !navigator.onLine;
  const text =
    status === 'down'
      ? offlineHint
        ? '网络已断开（离线），请检查网络连接'
        : '后端服务不可达，请检查后端是否启动'
      : '后端响应缓慢，正在重连…';
  const bg = status === 'down' ? 'bg-red-600' : 'bg-amber-500';

  return (
    <div
      className={`fixed top-0 left-0 right-0 ${bg} text-white text-center py-1.5 text-sm z-50 shadow-md`}
      role="alert"
      aria-live="assertive"
    >
      <span>{text}</span>
    </div>
  );
}
