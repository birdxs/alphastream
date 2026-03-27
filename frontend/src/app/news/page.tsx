// Input: 后端 /api/latest_news 新闻数据
// Output: AI新闻中心页面 — 左栏AI Sentiment Terminal + 右栏3个可视化图表卡片
// Pos: app/news/page.tsx - AI新闻舆情分析主页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { apiClient } from "@/lib/api/client";

/* ---------- 类型定义 ---------- */
interface NewsItem {
  title: string;
  content?: string;
  publish_time?: string;
  source?: string;
}

interface NewsResponse {
  success: boolean;
  news: NewsItem[];
}

/* ---------- 情绪判定 ---------- */
const POSITIVE_KW = ["利好", "上涨", "增长", "突破", "新高", "回升", "大涨", "强势", "反弹", "看好", "利润", "盈利", "超预期"];
const NEGATIVE_KW = ["利空", "下跌", "下滑", "暴跌", "亏损", "风险", "减持", "退市", "违规", "处罚", "警告", "萎缩"];

function analyzeSentiment(text: string): "positive" | "negative" | "neutral" {
  const combined = text;
  const posCount = POSITIVE_KW.filter(kw => combined.includes(kw)).length;
  const negCount = NEGATIVE_KW.filter(kw => combined.includes(kw)).length;
  if (posCount > negCount) return "positive";
  if (negCount > posCount) return "negative";
  return "neutral";
}

function sentimentScore(sentiment: "positive" | "negative" | "neutral"): number {
  if (sentiment === "positive") return 7.0 + Math.random() * 2.5;
  if (sentiment === "negative") return 1.5 + Math.random() * 2.5;
  return 4.5 + Math.random() * 1.5;
}

function extractStockCode(text: string): string | null {
  const m = text.match(/[036]\d{5}/);
  return m ? m[0] : null;
}

/* ---------- 板块Mock数据 ---------- */
const SECTORS = [
  { name: "军工", score: 7.8 }, { name: "算力", score: 8.2 },
  { name: "黄金", score: 6.5 }, { name: "白酒", score: 5.1 },
  { name: "新能源", score: 4.3 }, { name: "化工", score: 5.8 },
  { name: "存储", score: 7.1 }, { name: "芯片", score: 8.5 },
  { name: "光通信", score: 6.9 }, { name: "保险", score: 4.8 },
  { name: "银行", score: 5.5 }, { name: "地产", score: 3.2 },
];

/* ---------- 组件 ---------- */
export default function NewsPage() {
  const [allNews, setAllNews] = useState<NewsItem[]>([]);
  const [displayedNews, setDisplayedNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [fadeIdx, setFadeIdx] = useState(-1);
  const terminalRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const indexRef = useRef(0);

  /* 获取新闻 */
  const fetchNews = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiClient.get<NewsResponse>("/api/latest_news", {
        limit: "10",
        days: "1",
      });
      if (res?.success && res.news?.length) {
        setAllNews(res.news.slice(0, 10));
      }
    } catch {
      // 静默失败
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchNews(); }, [fetchNews]);

  /* 打字机效果：每3秒逐条添加 */
  useEffect(() => {
    if (allNews.length === 0) return;
    indexRef.current = 0;
    setDisplayedNews([]);

    // 立刻显示第一条
    const showNext = () => {
      if (indexRef.current >= allNews.length) {
        if (timerRef.current) clearInterval(timerRef.current);
        return;
      }
      const idx = indexRef.current;
      setDisplayedNews(prev => [...prev, allNews[idx]]);
      setFadeIdx(idx);
      indexRef.current++;
    };

    showNext();
    timerRef.current = setInterval(showNext, 3000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [allNews]);

  /* 自动滚动到底部 */
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [displayedNews]);

  /* 计算情绪分布 */
  const sentiments = displayedNews.map(n => analyzeSentiment(n.title + (n.content || "")));
  const posCount = sentiments.filter(s => s === "positive").length;
  const negCount = sentiments.filter(s => s === "negative").length;
  const neuCount = sentiments.filter(s => s === "neutral").length;
  const total = sentiments.length || 1;
  const posPct = Math.round((posCount / total) * 100);
  const negPct = Math.round((negCount / total) * 100);
  const neuPct = 100 - posPct - negPct;
  const avgScore = sentiments.length
    ? sentiments.reduce((sum, s) => sum + sentimentScore(s), 0) / sentiments.length
    : 5.0;

  /* 7日趋势Mock */
  const trend7d = Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (6 - i));
    const label = `${d.getMonth() + 1}/${d.getDate()}`;
    const val = 30 + Math.floor(Math.random() * 60);
    return { label, val };
  });
  const trendMax = Math.max(...trend7d.map(t => t.val));

  /* 格式化时间 */
  const fmtTime = (t?: string) => {
    if (!t) return "--:--";
    try {
      const d = new Date(t);
      return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    } catch { return "--:--"; }
  };

  return (
    <div className="flex-1 overflow-auto p-4">
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-4 h-full min-h-[calc(100vh-80px)]">

        {/* ====== 左栏: AI Sentiment Terminal ====== */}
        <div className="bg-white/[0.04] backdrop-blur-[40px] saturate-[180%] border border-white/[0.1] rounded-2xl flex flex-col overflow-hidden">

          {/* macOS 标题栏 */}
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
                <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
                <span className="w-3 h-3 rounded-full bg-[#28c840]" />
              </div>
              <span className="ml-3 text-[11px] font-mono text-white/40 tracking-widest uppercase">
                AI Sentiment Agent
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <span className="text-[10px] font-mono text-emerald-400/80 tracking-wider">LIVE</span>
            </div>
          </div>

          {/* 终端Body */}
          <div
            ref={terminalRef}
            className="flex-1 overflow-y-auto p-4 space-y-1"
            style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace", fontSize: "12.5px", lineHeight: "1.9" }}
          >
            {/* 启动信息 */}
            <div className="text-white/30">
              <p>{">"} sentiment_agent v4.0 initialized</p>
              <p>{">"} scanning financial news feed...</p>
              <p>{">"} connected to data source [OK]</p>
              <p className="mb-3">---</p>
            </div>

            {loading && displayedNews.length === 0 && (
              <div className="text-white/20 animate-pulse">
                {">"} loading news data...
              </div>
            )}

            {displayedNews.map((news, i) => {
              const sentiment = analyzeSentiment(news.title + (news.content || ""));
              const score = sentimentScore(sentiment);
              const code = extractStockCode(news.title + (news.content || ""));
              const isFading = i === fadeIdx;

              const sentimentIcon = sentiment === "positive" ? "\u25B2" : sentiment === "negative" ? "\u25BC" : "\u2014";
              const sentimentLabel = sentiment === "positive" ? "\u5229\u597D" : sentiment === "negative" ? "\u5229\u7A7A" : "\u4E2D\u6027";
              const sentimentColor = sentiment === "positive"
                ? "text-emerald-400"
                : sentiment === "negative"
                  ? "text-rose-400"
                  : "text-white/50";

              return (
                <div
                  key={i}
                  className={`mb-3 transition-all duration-700 ${isFading ? "animate-fade-in" : ""}`}
                  style={isFading ? { animation: "fadeSlideIn 0.6s ease-out" } : {}}
                >
                  <p className="text-cyan-400/70">
                    <span className="text-white/30">[{fmtTime(news.publish_time)}]</span>
                    {" "}
                    <span className="text-cyan-400/90">[SCAN]</span>
                    {" "}
                    <span className="text-white/50">{"\u65B0\u4FE1\u53F7"} \u2193</span>
                  </p>
                  <p className="pl-10">
                    <span className={sentimentColor}>{sentimentIcon}{sentimentLabel}</span>
                    {"  "}
                    <span className="text-white/80">{news.title}</span>
                  </p>
                  <p className="pl-10 text-white/30">
                    <span className="text-amber-400/60">[EVAL]</span>
                    {" "}
                    {"\u8BC4\u5206"} <span className={sentimentColor}>{score.toFixed(1)}/10</span>
                    {code && <>{" \u00B7 \u5173\u8054 "}<span className="text-blue-400/70">{code}</span></>}
                    {news.source && <>{" \u00B7 "}<span className="text-white/20">{news.source}</span></>}
                  </p>
                </div>
              );
            })}

            {/* 底部闪烁光标 */}
            <div className="pt-2 text-white/40">
              <span className="text-emerald-400/60">AGENT $</span>{" "}
              <span>{"\u76D1\u542C\u4E2D..."}</span>
              <span className="typing-cursor inline-block w-[2px] h-[14px] bg-emerald-400 ml-1 align-middle" />
            </div>
          </div>

          {/* 底部情绪分布条 */}
          <div className="px-4 py-2.5 border-t border-white/[0.06]">
            <div className="flex items-center gap-3 text-[10px] font-mono text-white/40 mb-1.5">
              <span>{"\u60C5\u7EEA\u5206\u5E03"}</span>
              <span className="text-emerald-400">{"\u25B2"} {posPct}%</span>
              <span className="text-white/40">{"\u2014"} {neuPct}%</span>
              <span className="text-rose-400">{"\u25BC"} {negPct}%</span>
            </div>
            <div className="flex h-1.5 rounded-full overflow-hidden bg-white/[0.06]">
              <div className="bg-emerald-500/70 transition-all duration-500" style={{ width: `${posPct}%` }} />
              <div className="bg-white/20 transition-all duration-500" style={{ width: `${neuPct}%` }} />
              <div className="bg-rose-500/70 transition-all duration-500" style={{ width: `${negPct}%` }} />
            </div>
          </div>
        </div>

        {/* ====== 右栏: 3个图表卡片 ====== */}
        <div className="flex flex-col gap-4">

          {/* --- 卡片1: 舆情分布环形图 --- */}
          <div className="bg-white/[0.04] backdrop-blur-[40px] saturate-[180%] border border-white/[0.1] rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-4">
              <div className="icon-box w-7 h-7 rounded-lg bg-violet-500/20 flex items-center justify-center">
                <span className="text-violet-400 text-sm">{"\u25C8"}</span>
              </div>
              <span className="text-xs font-medium text-white/70 tracking-wide">{"\u8206\u60C5\u5206\u5E03"}</span>
            </div>

            <div className="flex items-center justify-center">
              <div className="relative w-[140px] h-[140px]">
                {/* Conic gradient 环形图 */}
                <div
                  className="w-full h-full rounded-full"
                  style={{
                    background: `conic-gradient(
                      #34d399 0% ${posPct}%,
                      rgba(255,255,255,0.2) ${posPct}% ${posPct + neuPct}%,
                      #fb7185 ${posPct + neuPct}% 100%
                    )`,
                  }}
                />
                {/* 中心镂空 */}
                <div className="absolute inset-3 rounded-full bg-[#0a0a1a] flex flex-col items-center justify-center">
                  <span className="text-lg font-bold text-white/90">{avgScore.toFixed(1)}</span>
                  <span className="text-[9px] text-white/30 font-mono">{"\u603B\u8BC4\u5206"}</span>
                </div>
              </div>
            </div>

            <div className="flex justify-center gap-4 mt-4 text-[10px] font-mono">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="text-white/40">{"\u5229\u597D"} {posPct}%</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-white/20" />
                <span className="text-white/40">{"\u4E2D\u6027"} {neuPct}%</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-rose-400" />
                <span className="text-white/40">{"\u5229\u7A7A"} {negPct}%</span>
              </span>
            </div>
          </div>

          {/* --- 卡片2: 7日情绪趋势柱状图 --- */}
          <div className="bg-white/[0.04] backdrop-blur-[40px] saturate-[180%] border border-white/[0.1] rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-4">
              <div className="icon-box w-7 h-7 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                <span className="text-cyan-400 text-sm">{"\u25CE"}</span>
              </div>
              <span className="text-xs font-medium text-white/70 tracking-wide">7{"\u65E5\u60C5\u7EEA\u8D8B\u52BF"}</span>
            </div>

            <div className="flex items-end justify-between gap-2 h-[100px]">
              {trend7d.map((d, i) => {
                const pct = (d.val / trendMax) * 100;
                const barColor = d.val >= 65
                  ? "bg-emerald-500/70"
                  : d.val >= 40
                    ? "bg-white/20"
                    : "bg-amber-500/60";
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full flex justify-center">
                      <div
                        className={`w-5 rounded-t-sm ${barColor} transition-all duration-500`}
                        style={{ height: `${pct}%` }}
                      />
                    </div>
                    <span className="text-[9px] text-white/30 font-mono">{d.label}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* --- 卡片3: 板块情绪热力图 --- */}
          <div className="bg-white/[0.04] backdrop-blur-[40px] saturate-[180%] border border-white/[0.1] rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-4">
              <div className="icon-box w-7 h-7 rounded-lg bg-amber-500/20 flex items-center justify-center">
                <span className="text-amber-400 text-sm">{"\u25C6"}</span>
              </div>
              <span className="text-xs font-medium text-white/70 tracking-wide">{"\u677F\u5757\u60C5\u7EEA\u70ED\u529B\u56FE"}</span>
            </div>

            <div className="grid grid-cols-4 gap-1.5">
              {SECTORS.map((sec) => {
                const intensity = sec.score / 10;
                const bg = sec.score >= 6
                  ? `rgba(52,211,153,${0.15 + intensity * 0.4})`
                  : sec.score >= 4.5
                    ? `rgba(255,255,255,${0.04 + intensity * 0.1})`
                    : `rgba(251,113,133,${0.15 + (1 - intensity) * 0.3})`;
                return (
                  <div
                    key={sec.name}
                    className="rounded-lg p-2 text-center transition-colors hover:brightness-125 cursor-default"
                    style={{ background: bg }}
                  >
                    <div className="text-[11px] text-white/70 font-medium">{sec.name}</div>
                    <div className={`text-[10px] font-mono ${sec.score >= 6 ? "text-emerald-400/70" : sec.score >= 4.5 ? "text-white/30" : "text-rose-400/70"}`}>
                      {sec.score.toFixed(1)}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between mt-3 text-[9px] text-white/25 font-mono px-1">
              <span>{"\u2190 \u5229\u7A7A"}</span>
              <div className="flex-1 mx-2 h-1 rounded-full" style={{ background: "linear-gradient(to right, #fb7185, rgba(255,255,255,0.15), #34d399)" }} />
              <span>{"\u5229\u597D \u2192"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 全局动画样式 */}
      <style jsx>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .typing-cursor {
          animation: blink 1s step-end infinite;
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
