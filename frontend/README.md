# AI-Native 金融分析前端

```
Input: 后端SSE流式API + REST数据API
Output: Chat+Artifacts双面板交互界面
Pos: frontend/ - AI-native金融对话产品前端
```

## 技术栈
- Next.js 16 + React 19 + TypeScript
- shadcn/ui + Tailwind CSS
- TradingView Lightweight Charts + Recharts
- Zustand + Jotai

## 开发
```bash
npm install
npm run dev    # http://localhost:3000
npm run build  # 生产构建
```

## 目录结构
- `src/app/` — 页面路由（4个）
- `src/components/` — React组件（5个分类）
- `src/lib/` — 工具库（API/Hooks/Stores/Types）

此项目的任何功能、架构更新，必须在结束后同步更新相关文档。
