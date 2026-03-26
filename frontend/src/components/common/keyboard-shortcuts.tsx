// Input: 用户键盘事件（?键触发）
// Output: 快捷键帮助弹窗，展示可用快捷键列表
// Pos: 全局组件，挂载于layout.tsx，按?键唤起
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect } from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";

const SHORTCUTS = [
  { keys: "\u2318K", desc: "全局搜索股票" },
  { keys: "Enter", desc: "发送消息" },
  { keys: "\u21E7Enter", desc: "换行" },
  { keys: "/", desc: "快捷命令" },
  { keys: "Esc", desc: "关闭弹窗" },
];

export function KeyboardShortcuts() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '?' && !e.metaKey && !e.ctrlKey) {
        const target = e.target as HTMLElement;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-sm">
        <h3 className="font-semibold text-sm mb-3">快捷键</h3>
        <div className="space-y-2">
          {SHORTCUTS.map(s => (
            <div key={s.keys} className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{s.desc}</span>
              <kbd className="px-2 py-1 rounded bg-muted text-xs font-mono">{s.keys}</kbd>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-muted-foreground mt-2 text-center">按 ? 再次打开此面板</p>
      </DialogContent>
    </Dialog>
  );
}
