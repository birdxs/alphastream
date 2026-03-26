// Input: onQuestionSelect回调
// Output: 视觉冲击力欢迎屏（渐变标题+4卡片grid+热门标签+错开动画）
// Pos: ChatPanel子组件，无消息时显示

"use client";
import {
  Brain,
  TrendingUp,
  Shield,
  BarChart3,
  Activity,
  Sparkles,
  Zap,
} from "lucide-react";

interface Props {
  onQuestionSelect: (message: string, options: { stock_code?: string }) => void;
}

const QUICK_START = [
  {
    text: "分析600519贵州茅台",
    title: "个股深度分析",
    desc: "基本面·技术面·资金面全方位解读",
    stock: "600519",
    icon: TrendingUp,
    color: "text-blue-400",
    borderHover: "hover:border-blue-400/40",
    bgIcon: "bg-blue-400/10",
  },
  {
    text: "对比银行板块龙头",
    title: "行业横向对比",
    desc: "龙头筛选·估值对比·竞争格局",
    stock: "",
    icon: BarChart3,
    color: "text-emerald-400",
    borderHover: "hover:border-emerald-400/40",
    bgIcon: "bg-emerald-400/10",
  },
  {
    text: "今日大盘走势",
    title: "市场全景概览",
    desc: "指数动态·板块轮动·资金流向",
    stock: "",
    icon: Activity,
    color: "text-violet-400",
    borderHover: "hover:border-violet-400/40",
    bgIcon: "bg-violet-400/10",
  },
  {
    text: "600519风险评估",
    title: "风险预警评估",
    desc: "风险因子识别·压力测试·预警信号",
    stock: "600519",
    icon: Shield,
    color: "text-amber-400",
    borderHover: "hover:border-amber-400/40",
    bgIcon: "bg-amber-400/10",
  },
];

const HOT_TOPICS = [
  "沪深300走势",
  "北向资金",
  "板块轮动",
  "融资融券",
  "龙虎榜",
];

export function WelcomeScreen({ onQuestionSelect }: Props) {
  return (
    <div className="flex items-center justify-center h-full p-3">
      <div className="w-full max-w-[360px] space-y-5 animate-fade-in">
        {/* --- 顶部标识区 --- */}
        <div className="flex flex-col items-center gap-2 pt-2">
          <div className="relative flex items-center justify-center">
            <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 blur-xl" />
            <div className="relative flex items-center gap-1.5 rounded-2xl bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border border-white/5 px-4 py-2.5">
              <Brain className="h-5 w-5 text-blue-400" />
              <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
              <Zap className="h-4 w-4 text-blue-300" />
            </div>
          </div>
          <h2 className="text-lg font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
            AI金融分析助手
          </h2>
          <p className="text-[11px] text-muted-foreground text-center leading-relaxed">
            13个智能Agent协同 · 实时市场数据 · 大师级投研视角
          </p>
        </div>

        {/* --- 快速开始卡片 2×2 --- */}
        <div className="grid grid-cols-2 gap-2">
          {QUICK_START.map((q, i) => {
            const Icon = q.icon;
            return (
              <button
                key={q.text}
                onClick={() =>
                  onQuestionSelect(q.text, { stock_code: q.stock })
                }
                className={`group relative text-left p-3 rounded-xl border border-border/30 ${q.borderHover} hover:bg-muted/20 transition-all duration-200 hover:-translate-y-0.5`}
                style={{ animationDelay: `${i * 100}ms` }}
              >
                <div
                  className={`w-7 h-7 rounded-lg ${q.bgIcon} flex items-center justify-center mb-2`}
                >
                  <Icon className={`h-3.5 w-3.5 ${q.color}`} />
                </div>
                <div className="text-xs font-medium leading-tight">
                  {q.title}
                </div>
                <div className="text-[10px] text-muted-foreground mt-0.5 leading-snug">
                  {q.desc}
                </div>
              </button>
            );
          })}
        </div>

        {/* --- 热门话题 --- */}
        <div className="space-y-1.5">
          <p className="text-[10px] text-muted-foreground/60 text-center">
            热门话题
          </p>
          <div className="flex gap-1.5 justify-center flex-wrap">
            {HOT_TOPICS.map((topic) => (
              <button
                key={topic}
                onClick={() => onQuestionSelect(topic, {})}
                className="text-[10px] px-2.5 py-1 rounded-full bg-muted/30 hover:bg-muted/60 text-muted-foreground hover:text-foreground border border-transparent hover:border-border/40 transition-all duration-200"
              >
                {topic}
              </button>
            ))}
          </div>
        </div>

        {/* --- 底部快捷键提示 --- */}
        <p className="text-[9px] text-muted-foreground/50 text-center">
          <kbd className="px-1 py-0.5 rounded bg-muted/50 font-mono">
            /
          </kbd>{" "}
          命令 ·{" "}
          <kbd className="px-1 py-0.5 rounded bg-muted/50 font-mono">⌘K</kbd>{" "}
          搜索 ·{" "}
          <kbd className="px-1 py-0.5 rounded bg-muted/50 font-mono">
            Enter
          </kbd>{" "}
          发送
        </p>
      </div>
    </div>
  );
}
