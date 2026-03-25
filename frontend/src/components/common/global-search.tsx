/**
 * Input: 键盘事件(Cmd+K / Ctrl+K)
 * Output: 全局搜索对话框，选中后导航到对应股票页面
 * Pos: components/common/global-search.tsx - 全局快捷搜索入口
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */
"use client";
import { useState, useEffect } from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { StockSearch } from "./stock-search";
import { useRouter } from "next/navigation";

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSelect = (code: string) => {
    setOpen(false);
    router.push(`/?stock=${code}`);
  };

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md p-0 overflow-hidden" showCloseButton={false}>
        <div className="p-4">
          <StockSearch onSelect={handleSelect} placeholder="搜索股票代码或名称... (Esc关闭)" />
          <div className="mt-3 text-xs text-muted-foreground text-center">
            <kbd className="px-1.5 py-0.5 rounded bg-muted text-[10px]">&#8984;K</kbd> 打开搜索 · <kbd className="px-1.5 py-0.5 rounded bg-muted text-[10px]">Esc</kbd> 关闭
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
