// Input: onQuestionSelect回调
// Output: Dark Glassmorphism风格欢迎屏（径向渐变Hero+毛玻璃图标+渐变标题+glass卡片+stagger动画+热门pills）
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
    iconColor: "text-[#3737CC]",
    bgIcon: "bg-[#3737CC]/10",
    borderHover: "hover:border-[#3737CC]/40",
  },
  {
    text: "对比银行板块龙头",
    title: "行业横向对比",
    desc: "龙头筛选·估值对比·竞争格局",
    stock: "",
    icon: BarChart3,
    iconColor: "text-[#46BEA3]",
    bgIcon: "bg-[#46BEA3]/10",
    borderHover: "hover:border-[#46BEA3]/40",
  },
  {
    text: "今日大盘走势",
    title: "市场全景概览",
    desc: "指数动态·板块轮动·资金流向",
    stock: "",
    icon: Activity,
    iconColor: "text-[#6B5EE4]",
    bgIcon: "bg-[#6B5EE4]/10",
    borderHover: "hover:border-[#6B5EE4]/40",
  },
  {
    text: "600519风险评估",
    title: "风险预警评估",
    desc: "风险因子识别·压力测试·预警信号",
    stock: "600519",
    icon: Shield,
    iconColor: "text-[#FF8767]",
    bgIcon: "bg-[#FF8767]/10",
    borderHover: "hover:border-[#FF8767]/40",
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
    <div className="relative flex items-center justify-center h-full p-3 overflow-hidden">
      {/* --- 径向渐变背景（只覆盖上半部分） --- */}
      <div
        className="absolute inset-x-0 top-0 h-[60%] pointer-events-none"
        style={{
          background:
            "radial-gradient(circle at 50% 0%, #3737CC 0%, #212185 40%, transparent 70%)",
        }}
      />

      <div className="relative w-full max-w-[360px] space-y-5 animate-fade-in z-10">
        {/* --- 顶部Hero标识区 --- */}
        <div className="flex flex-col items-center gap-2 pt-2">
          {/* 毛玻璃图标容器 */}
          <div className="flex items-center gap-1.5 rounded-2xl bg-white/[0.05] backdrop-blur-sm border border-white/[0.1] px-4 py-2.5">
            <Brain className="h-5 w-5 text-[#3737CC]" />
            <Sparkles className="h-3.5 w-3.5 text-[#46BEA3]" />
            <Zap className="h-4 w-4 text-[#6B5EE4]" />
          </div>

          {/* 渐变文字标题 */}
          <h2 className="text-lg font-bold bg-gradient-to-r from-[#3737CC] to-[#46BEA3] bg-clip-text text-transparent">
            AI金融分析助手
          </h2>
          <p className="text-[11px] text-muted-foreground text-center leading-relaxed">
            13个智能Agent协同 · 实时市场数据 · 大师级投研视角
          </p>
        </div>

        {/* --- 快速开始卡片 2×2 (glass-card + stagger动画) --- */}
        <div className="grid grid-cols-2 gap-2">
          {QUICK_START.map((q, i) => {
            const Icon = q.icon;
            return (
              <button
                key={q.text}
                onClick={() =>
                  onQuestionSelect(q.text, { stock_code: q.stock })
                }
                className={`group relative text-left p-3 rounded-xl bg-white/[0.04] border border-white/[0.08] ${q.borderHover} hover:bg-white/[0.08] hover:border-white/[0.15] hover:-translate-y-0.5 backdrop-blur-sm transition-all duration-300 animate-fade-in opacity-0`}
                style={{
                  animationDelay: `${i * 60}ms`,
                  animationFillMode: "forwards",
                }}
              >
                <div
                  className={`w-7 h-7 rounded-lg ${q.bgIcon} flex items-center justify-center mb-2`}
                >
                  <Icon className={`h-3.5 w-3.5 ${q.iconColor}`} />
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

        {/* --- 热门话题 pills --- */}
        <div className="space-y-1.5">
          <p className="text-[10px] text-muted-foreground/60 text-center">
            热门话题
          </p>
          <div className="flex gap-1.5 justify-center flex-wrap">
            {HOT_TOPICS.map((topic) => (
              <button
                key={topic}
                onClick={() => onQuestionSelect(topic, {})}
                className="text-[10px] px-2.5 py-1 rounded-full bg-white/[0.05] border border-white/[0.08] text-muted-foreground hover:text-foreground hover:border-[#3737CC]/30 transition-all duration-200"
              >
                {topic}
              </button>
            ))}
          </div>
        </div>

        {/* --- 底部快捷键提示 --- */}
        <p className="text-[9px] text-muted-foreground/50 text-center">
          <kbd className="px-1 py-0.5 rounded bg-white/[0.05] font-mono">
            /
          </kbd>{" "}
          命令 ·{" "}
          <kbd className="px-1 py-0.5 rounded bg-white/[0.05] font-mono">⌘K</kbd>{" "}
          搜索 ·{" "}
          <kbd className="px-1 py-0.5 rounded bg-white/[0.05] font-mono">
            Enter
          </kbd>{" "}
          发送
        </p>
      </div>
    </div>
  );
}
