// Input: 浏览器online/offline事件 + API心跳检测
// Output: 网络断开或API不可达时显示顶部警告条
// Pos: layout.tsx中Navbar下方，全局网络状态提示
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect, useRef } from "react";
import { WifiOff, ServerOff } from "lucide-react";
import { useToast } from "./toast-provider";

export function NetworkStatus() {
  const [online, setOnline] = useState(true);
  const [apiReachable, setApiReachable] = useState(true);
  const wasOfflineRef = useRef(false);
  const wasApiUnreachableRef = useRef(false);
  const { toast } = useToast();

  useEffect(() => {
    const handleOnline = () => {
      setOnline(true);
      if (wasOfflineRef.current) {
        toast("网络连接已恢复", "success");
        wasOfflineRef.current = false;
      }
    };
    const handleOffline = () => {
      setOnline(false);
      wasOfflineRef.current = true;
    };

    setOnline(navigator.onLine);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [toast]);

  // API心跳检测，每30秒一次
  useEffect(() => {
    const checkApi = async () => {
      try {
        await fetch('/api/conversations', { method: 'HEAD', signal: AbortSignal.timeout(5000) });
        if (wasApiUnreachableRef.current) {
          toast("后端服务已恢复连接", "success");
          wasApiUnreachableRef.current = false;
        }
        setApiReachable(true);
      } catch {
        if (navigator.onLine) {
          wasApiUnreachableRef.current = true;
          setApiReachable(false);
        }
      }
    };
    checkApi();
    const heartbeat = setInterval(checkApi, 30000);
    return () => clearInterval(heartbeat);
  }, [toast]);

  if (online && apiReachable) return null;

  return (
    <div className="fixed top-14 left-0 right-0 bg-[var(--brand-primary,#3737CC)]/90 text-white/90 text-xs text-center py-1.5 z-50 flex items-center justify-center gap-2 animate-fade-in backdrop-blur-sm border-b border-[var(--glass-border)]">
      {!online ? (
        <>
          <WifiOff className="h-3.5 w-3.5" />
          <span>网络连接已断开，部分功能可能不可用</span>
        </>
      ) : (
        <>
          <ServerOff className="h-3.5 w-3.5" />
          <span>后端服务不可达，正在重试连接...</span>
        </>
      )}
    </div>
  );
}
