// Input: agent-store中的Agent执行状态
// Output: 侧边抽屉展示Agent分析日志（Sheet形式）
// Pos: artifact-panel.tsx头部按钮，打开右侧Agent日志抽屉
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { AgentProgressPanel } from "./agent-progress-panel";
import { Activity } from "lucide-react";

export function AgentLogDrawer() {
  return (
    <Sheet>
      <SheetTrigger
        render={
          <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" />
        }
      >
        <Activity className="h-3 w-3" />
        Agent日志
      </SheetTrigger>
      <SheetContent side="right" className="bg-[var(--bg-surface-0,#0A0A1A)]/95 backdrop-blur-2xl border-l-[var(--glass-border)]">
        <SheetHeader>
          <SheetTitle>Agent 执行日志</SheetTitle>
          <SheetDescription>Multi-Agent分析进度与工具调用详情</SheetDescription>
        </SheetHeader>
        <div className="p-4 overflow-auto flex-1 font-mono text-xs leading-relaxed">
          <AgentProgressPanel />
        </div>
      </SheetContent>
    </Sheet>
  );
}
