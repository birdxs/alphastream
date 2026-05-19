// Input: 浏览器 navigator.onLine 状态 + 定期探测 /api/conversations
// Output: 网络断开或API不可达时显示顶部警告条
// Pos: 全局布局组件，layout.tsx 渲染顶部
'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * FIX-E4 / REAL-01 Q4: 网络状态指示器（强化版退避）
 * - mount 后 25s 启动静默期：期间所有失败都不弹横幅（覆盖后端冷启）
 * - 连续 3 次失败才显示"正在重连"，10+ 次显示"后端服务不可达"
 * - 指数退避: 1s -> 2s -> 4s -> 8s -> 16s 封顶
 * - 探测超时 8s
 * - 状态恢复时清空 failuresRef
 */
export function NetworkStatus() {
  const [status, setStatus] = useState<'ok' | 'reconnecting' | 'down'>('ok');
  const failuresRef = useRef(0);
  const consecutiveFailuresRef = useRef(0);
  const startupAtRef = useRef(Date.now());
  const recoveryToastUntilRef = useRef(0);
  const [showRecovery, setShowRecovery] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const RECONNECT_THRESHOLD = 3;
    const DOWN_THRESHOLD = 10;
    // 指数退避（首次失败到下次重试 1s，逐级翻倍封顶 16s）
    const BACKOFF = [1000, 2000, 4000, 8000, 16000];
    const STARTUP_GRACE_MS = 35000; // mount 后 35s 内即便累计失败也不显示 [REAL-01 2026-05-18 Q4 临界修正]
    const STARTUP_PROBE_DELAY_MS = 8000; // 首次探测延迟，宽限期内不发任何探测
    const PROBE_TIMEOUT_MS = 8000;

    startupAtRef.current = Date.now();
    let cancelled = false;

    const inStartupGrace = () => Date.now() - startupAtRef.current < STARTUP_GRACE_MS;

    const handleOnline = () => {
      failuresRef.current = 0;
      consecutiveFailuresRef.current = 0;
      setStatus('ok');
    };
    const handleOffline = () => {
      // 浏览器明确 offline 才直接显示 down
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
          signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
        });
        if (cancelled) return;
        if (res.ok) {
          const prevFailures = consecutiveFailuresRef.current;
          failuresRef.current = 0;
          consecutiveFailuresRef.current = 0;
          if (prevFailures >= RECONNECT_THRESHOLD) {
            // 从可见的失败态恢复 → 弹 3s "已恢复" 提示
            recoveryToastUntilRef.current = Date.now() + 3000;
            setShowRecovery(true);
            setTimeout(() => setShowRecovery(false), 3000);
          }
          setStatus('ok');
        } else {
          failuresRef.current += 1;
          consecutiveFailuresRef.current += 1;
          updateStatus();
        }
      } catch {
        if (cancelled) return;
        failuresRef.current += 1;
        consecutiveFailuresRef.current += 1;
        updateStatus();
      } finally {
        if (!cancelled) {
          const f = consecutiveFailuresRef.current;
          // 健康时下次 30s 再探；失败时按指数退避
          const delay = f === 0 ? 30000 : BACKOFF[Math.min(f - 1, BACKOFF.length - 1)];
          timerRef.current = setTimeout(checkApi, delay);
        }
      }
    };

    const updateStatus = () => {
      // 启动宽限期内一律保持 ok
      if (inStartupGrace()) {
        setStatus('ok');
        return;
      }
      const f = consecutiveFailuresRef.current;
      if (f >= DOWN_THRESHOLD) {
        setStatus('down');
      } else if (f >= RECONNECT_THRESHOLD) {
        setStatus('reconnecting');
      } else {
        setStatus('ok');
      }
    };

    // 启动后延迟 STARTUP_PROBE_DELAY_MS 再发第一次探测，前 8s 完全静默
    timerRef.current = setTimeout(checkApi, STARTUP_PROBE_DELAY_MS);

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
