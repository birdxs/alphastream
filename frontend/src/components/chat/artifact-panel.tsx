// Input: chat-store中的artifacts数组
// Output: Artifacts工作区UI，展示AI生成的图表和数据卡片
// Pos: 首页右侧面板，Chat+Artifacts布局的展示侧
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useChatStore } from "@/lib/stores/chat-store";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ArtifactRenderer } from "./artifact-renderer";

export function ArtifactPanel() {
  const { artifacts } = useChatStore();

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b flex items-center justify-between">
        <h2 className="font-semibold text-sm">分析结果</h2>
        {artifacts.length > 0 && (
          <span className="text-xs text-muted-foreground">{artifacts.length}个组件</span>
        )}
      </div>
      <ScrollArea className="flex-1 p-4">
        {artifacts.length === 0 ? (
          <div className="flex items-center justify-center h-full text-center text-muted-foreground">
            <div>
              <p className="text-4xl mb-4">📊</p>
              <p>AI分析结果将在这里展示</p>
              <p className="text-sm mt-2">K线图 · 评分卡 · 资金流向 · 风险评估</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {artifacts.map((artifact, i) => (
              <ArtifactRenderer key={`${artifact.artifact_type}_${i}`} artifact={artifact} />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
