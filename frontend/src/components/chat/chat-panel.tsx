// Input: 无（未来接入chat-store）
// Output: AI对话面板UI，含消息列表和输入框
// Pos: 首页左侧面板，Chat+Artifacts布局的对话侧
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

export function ChatPanel() {
  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b">
        <h2 className="font-semibold text-sm">AI金融分析助手</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <p className="text-muted-foreground text-center mt-20">
          输入股票代码或问题开始分析
        </p>
      </div>
      <div className="p-3 border-t">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="分析贵州茅台..."
            className="flex-1 rounded-md border bg-background px-3 py-2 text-sm"
          />
          <button className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground">
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
