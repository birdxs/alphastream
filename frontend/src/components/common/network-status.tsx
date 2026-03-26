// Input: 浏览器online/offline事件 + API心跳检测
// Output: 网络断开或API不可达时显示顶部警告条
// Pos: layout.tsx中Navbar下方，全局网络状态提示
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect } from "react";
import { WifiOff, ServerOff } from "lucide-react";

export function NetworkStatus() {
  const [online, setOnline] = useState(true);
  const [apiReachable, setApiReachable] = useState(true);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);

    setOnline(navigator.onLine);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  // API心跳检测，每30秒一次
  useEffect(() => {
    const checkApi = async () => {
      try {
        await fetch('/api/conversations', { method: 'HEAD', signal: AbortSignal.timeout(5000) });
        setApiReachable(true);
      } catch {
        if (navigator.onLine) {
          setApiReachable(false);
        }
      }
    };
    checkApi();
    const heartbeat = setInterval(checkApi, 30000);
    return () => clearInterval(heartbeat);
  }, []);

  if (online && apiReachable) return null;

  return (
    <div className="fixed top-14 left-0 right-0 bg-yellow-500/90 text-yellow-950 text-xs text-center py-1.5 z-50 flex items-center justify-center gap-2 animate-fade-in">
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
