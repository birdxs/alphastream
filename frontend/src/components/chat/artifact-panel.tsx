// Input: chat-store中的artifacts数组
// Output: Artifacts工作区UI，展示AI生成的图表和数据卡片
// Pos: 首页右侧面板，Chat+Artifacts布局的展示侧
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useChatStore } from "@/lib/stores/chat-store";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ArtifactRenderer } from "./artifact-renderer";
import { AgentLogDrawer } from "@/components/agent/agent-log-drawer";

export function ArtifactPanel() {
  const { artifacts } = useChatStore();

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b flex items-center justify-between">
        <h2 className="font-semibold text-sm">分析结果</h2>
        <div className="flex items-center gap-2">
          {artifacts.length > 0 && (
            <span className="text-xs text-muted-foreground">{artifacts.length}个组件</span>
          )}
          <AgentLogDrawer />
        </div>
      </div>
      <ScrollArea className="flex-1 p-4">
        {artifacts.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-6 max-w-sm">
              <div className="text-5xl">🤖</div>
              <div>
                <h3 className="font-semibold text-lg mb-2">AI智能金融分析</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  在左侧对话框输入问题，AI将实时生成分析图表
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3 text-left">
                {[
                  { icon: "📈", title: "K线分析", desc: "技术指标+趋势判断" },
                  { icon: "💰", title: "基本面", desc: "财务指标+估值评估" },
                  { icon: "🤖", title: "Multi-Agent", desc: "13个AI Agent协作" },
                  { icon: "👥", title: "投资大师", desc: "巴菲特/芒格/林奇/达摩达兰" },
                ].map(item => (
                  <div key={item.title} className="bg-muted/50 rounded-lg p-3">
                    <span className="text-2xl">{item.icon}</span>
                    <p className="font-medium text-sm mt-1">{item.title}</p>
                    <p className="text-xs text-muted-foreground">{item.desc}</p>
                  </div>
                ))}
              </div>
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
