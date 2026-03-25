// Input: 无（未来接入chat-store的artifact数据）
// Output: Artifacts工作区UI，展示AI分析结果
// Pos: 首页右侧面板，Chat+Artifacts布局的展示侧
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

export function ArtifactPanel() {
  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b">
        <h2 className="font-semibold text-sm">分析结果</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-4 flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <p className="text-4xl mb-4">📊</p>
          <p>AI分析结果将在这里展示</p>
          <p className="text-sm mt-2">K线图 · 评分卡 · 资金流向 · 风险评估</p>
        </div>
      </div>
    </div>
  );
}
