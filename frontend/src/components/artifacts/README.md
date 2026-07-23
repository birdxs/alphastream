文件列表：artifact-card.tsx, candlestick-chart.tsx, score-radar.tsx, capital-flow-chart.tsx, decision-card.tsx
- `debate-card.tsx` — P0-3 多空辩论双栏 + 分歧扫读, technical-panel.tsx, investor-personas.tsx, search-results.tsx, fundamental-scorecard.tsx, risk-radar-chart.tsx, news-feed.tsx, alt-data-panel.tsx, shipping-chart.tsx, esg-scorecard.tsx, hiring-signal.tsx, corporate-network.tsx
地位：Artifact图表组件目录（AI Generative UI渲染层）
功能：TradingView K线 | Recharts雷达/柱状图/饼图 | 决策卡 | 投资者对比 | 技术面板 | 基本面 | 风险雷达 | 新闻 | 另类数据聚合；capital-flow-chart 后端输入金额为 yuan、图表展示为万元

P3 另类数据 Artifact (E4 — 2026-04-15):
- alt-data-panel.tsx: Tab式主面板, 聚合4个子Artifact (对应后端 shipping/esg/jobs/corporate adapter)
- shipping-chart.tsx: BDI 折线(lightweight-charts) + 港口吞吐柱状(Recharts) + AIS船舶计数
- esg-scorecard.tsx: E/S/G 雷达 + 综合分 + 多源评级对比表 + SEC 气候披露 tag
- hiring-signal.tsx: 招聘月度趋势 + 技能饼图 + 扩张预警 (high/medium/low)
- corporate-network.tsx: 中心公司卡 + 父/子公司 + 董事会 + 司法管辖区国旗标签

一旦这里的结构发生变化，请务必更新我。

G5-G8 (2026-07-23):
- decision-card.tsx 扩展 scorecard / decision_memo / reflection_summary / memory_context 只读区块；空历史不造假，缺证据显式 missing
