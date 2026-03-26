// Input: 用户键盘事件（?键触发帮助，Cmd+N/Ctrl+N新建对话，Cmd+Shift+Backspace清除对话，Escape关闭面板）
// Output: 快捷键帮助弹窗 + 全局快捷键行为绑定
// Pos: 全局组件，挂载于layout.tsx，按?键唤起帮助面板
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect, useCallback } from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { useChatStore } from "@/lib/stores/chat-store";

const SHORTCUTS = [
  { keys: "⌘K", desc: "全局搜索股票" },
  { keys: "⌘N", desc: "新建对话" },
  { keys: "⌘⇧⌫", desc: "清除当前对话" },
  { keys: "Enter", desc: "发送消息" },
  { keys: "⇧Enter", desc: "换行" },
  { keys: "/", desc: "快捷命令" },
  { keys: "Esc", desc: "关闭弹窗/面板" },
];

export function KeyboardShortcuts() {
  const [open, setOpen] = useState(false);

  const handleNewConversation = useCallback(() => {
    const store = useChatStore.getState();
    store.setActiveConversation(null);
    store.setMessages([]);
    store.clearArtifacts();
    store.resetStreamContent();
    store.setFollowUps([]);
  }, []);

  const handleClearConversation = useCallback(() => {
    const store = useChatStore.getState();
    store.setMessages([]);
    store.clearArtifacts();
    store.resetStreamContent();
    store.setFollowUps([]);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA';

      // ? — 打开快捷键帮助（非输入框时）
      if (e.key === '?' && !e.metaKey && !e.ctrlKey) {
        if (isInput) return;
        e.preventDefault();
        setOpen(true);
        return;
      }

      // Cmd+N / Ctrl+N — 新建对话
      if (e.key === 'n' && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
        e.preventDefault();
        handleNewConversation();
        return;
      }

      // Cmd+Shift+Backspace — 清除当前对话
      if (e.key === 'Backspace' && (e.metaKey || e.ctrlKey) && e.shiftKey) {
        e.preventDefault();
        handleClearConversation();
        return;
      }

      // Escape — 关闭所有打开的面板
      if (e.key === 'Escape') {
        // 关闭快捷键帮助弹窗
        if (open) {
          setOpen(false);
          return;
        }
        // 关闭可能打开的搜索/命令面板 — 通过模拟Escape冒泡，
        // Dialog组件自身会处理，此处确保不阻止默认行为
        return;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, handleNewConversation, handleClearConversation]);

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
