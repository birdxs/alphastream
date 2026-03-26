// Input: chat-store artifacts数组
// Output: Artifacts工作区 — 头部 + 内容/空态
// Pos: 首页右栏

"use client";
import { useChatStore } from "@/lib/stores/chat-store";
import { Button } from "@/components/ui/button";
import { ArtifactRenderer } from "./artifact-renderer";
import { AgentLogDrawer } from "@/components/agent/agent-log-drawer";
import { Trash2, TrendingUp, DollarSign, Users, Bot } from "lucide-react";

export function ArtifactPanel() {
  const artifacts = useChatStore(s => s.artifacts);

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-10 border-b border-border/40 bg-background shrink-0">
        <span className="text-xs font-medium text-foreground/80">分析结果</span>
        <div className="flex items-center gap-1">
          {artifacts.length > 0 && (
            <>
              <span className="text-[10px] text-muted-foreground">{artifacts.length}</span>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => useChatStore.getState().clearArtifacts()}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </>
          )}
          <AgentLogDrawer />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3">
        {artifacts.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-xs space-y-5">
              <div className="flex justify-center">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <Bot className="h-6 w-6 text-primary" />
                </div>
              </div>
              <div>
                <h3 className="text-sm font-semibold mb-1">AI智能分析</h3>
                <p className="text-xs text-muted-foreground">
                  在左侧输入问题，分析结果将在此展示
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { icon: TrendingUp, title: "K线分析", desc: "技术指标" },
                  { icon: DollarSign, title: "基本面", desc: "财务评估" },
                  { icon: Bot, title: "Agent", desc: "13个协作" },
                  { icon: Users, title: "大师", desc: "四大视角" },
                ].map(item => (
                  <div key={item.title} className="bg-muted/40 rounded-lg p-2.5 text-left">
                    <item.icon className="h-4 w-4 text-muted-foreground mb-1" />
                    <p className="text-xs font-medium">{item.title}</p>
                    <p className="text-[10px] text-muted-foreground">{item.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {artifacts.map((artifact, i) => (
              <ArtifactRenderer key={`${artifact.artifact_type}_${i}`} artifact={artifact} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
