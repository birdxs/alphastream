// Input: children ReactNode
// Output: 全局Toast通知系统（Context Provider + 固定定位通知弹窗）
// Pos: layout.tsx的顶层Provider，提供useToast hook给全应用

"use client";
import { useState, useRef, createContext, useContext, useCallback, ReactNode } from "react";

type ToastType = "success" | "error" | "info";
interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

const ToastContext = createContext<{ toast: (msg: string, type?: ToastType) => void }>({
  toast: () => {},
});

export const useToast = () => useContext(ToastContext);

const typeStyles: Record<ToastType, string> = {
  success: "border-[#46BEA3] bg-[#46BEA3]/10 text-[#46BEA3]",
  error: "border-[#FF8767] bg-[#FF8767]/10 text-[#FF8767]",
  info: "border-[#3737CC] bg-[#3737CC]/10 text-[#A5B4FC]",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counterRef = useRef(0);

  const toast = useCallback((message: string, type: ToastType = "info") => {
    const id = ++counterRef.current;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  return (
    <ToastContext value={{ toast }}>
      {children}
      {/* Toast容器 — 固定右下角 */}
      <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto px-4 py-2.5 rounded-lg border backdrop-blur-xl shadow-lg text-sm font-medium animate-[glass-enter_250ms_ease-out_both] ${typeStyles[t.type]}`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext>
  );
}
