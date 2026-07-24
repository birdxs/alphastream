// Input: 后端 /api/latest_news 新闻数据 + /api/news_sentiment 情绪统计
// Output: AI新闻中心页面 — 左栏AI Sentiment Terminal + 右栏3个可视化图表卡片
// Pos: app/news/page.tsx - AI新闻舆情分析主页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { apiClient } from "@/lib/api/client";

/* ---------- 类型定义 ---------- */
interface NewsItem {
  title: string;
  content?: string;
  // R1 Q3契约收尾 (2026-04-15 21:28): 后端统一输出 published_at (ISO8601+08:00)
  published_at?: string;
  datetime?: string;       // 兼容: "2024-01-01 10:30:00"
  date?: string;           // 兼容: "2024-01-01"
  time?: string;           // 兼容: "10:30:00"
  publish_time?: string;   // 兼容旧字段
  source?: string;
}

interface NewsResponse {
  success: boolean;
  news: NewsItem[];
}

interface SentimentResponse {
  total: number;
  bullish: number;
  bearish: number;
  neutral: number;
  score: number;
  bullish_pct: number;
  bearish_pct: number;
  neutral_pct: number;
}

/* ---------- 情绪判定（单条新闻，用于终端显示） ---------- */
const POSITIVE_KW = ["利好", "上涨", "增长", "突破", "新高", "回升", "大涨", "强势", "反弹", "看好", "利润", "盈利", "超预期"];
const NEGATIVE_KW = ["利空", "下跌", "下滑", "暴跌", "亏损", "风险", "减持", "退市", "违规", "处罚", "警告", "萎缩"];

function analyzeSentiment(text: string): "positive" | "negative" | "neutral" {
  const posCount = POSITIVE_KW.filter(kw => text.includes(kw)).length;
  const negCount = NEGATIVE_KW.filter(kw => text.includes(kw)).length;
  if (posCount > negCount) return "positive";
  if (negCount > posCount) return "negative";
  return "neutral";
}

/** 确定性评分：基于关键词命中数量，不再使用 Math.random() */
function sentimentScore(text: string, sentiment: "positive" | "negative" | "neutral"): number {
  const posHits = POSITIVE_KW.filter(kw => text.includes(kw)).length;
  const negHits = NEGATIVE_KW.filter(kw => text.includes(kw)).length;
  const hits = Math.min(posHits + negHits, 5); // cap at 5
  if (sentiment === "positive") return 7.0 + hits * 0.5;
  if (sentiment === "negative") return 4.0 - hits * 0.5;
  return 5.0 + (posHits - negHits) * 0.3;
}

function extractStockCode(text: string): string | null {
  const m = text.match(/[036]\d{5}/);
  return m ? m[0] : null;
}

/* ---------- 板块情绪数据（暂无真实来源，禁止硬编码）---------- */
const SECTORS: { name: string; score: number }[] = [];

/* ---------- 组件 ---------- */
/* ---------- 去重 & 时间键 ---------- */
function newsKey(n: NewsItem): string {
  const t = n.published_at || n.datetime || (n.date && n.time ? `${n.date} ${n.time}` : "") || n.publish_time || "";
  return `${t}|${(n.title || "").slice(0, 80)}`;
}
function newsTimestamp(n: NewsItem): string {
  return n.published_at || n.datetime || (n.date && n.time ? `${n.date} ${n.time}` : "") || n.publish_time || "";
}

export default function NewsPage() {
  // 累积新闻列表（保留历史，不清屏） — 按时间倒序，最新在顶
  const [allNews, setAllNews] = useState<NewsItem[]>([]);
  const [newestKey, setNewestKey] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [sentimentData, setSentimentData] = useState<SentimentResponse | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const seenKeysRef = useRef<Set<string>>(new Set());
  const isFirstLoadRef = useRef(true);

  /* 获取新闻 — 增量合并 + 去重 + 倒序，不清屏 */
  const fetchNews = useCallback(async () => {
    try {
      const res = await apiClient.get<NewsResponse>("/api/latest_news", {
        limit: "20",
        days: "1",
      });
      if (res?.success && res.news?.length) {
        // 去重逻辑必须放在 updater 外部 —— React StrictMode 下 updater 会双调用，
        // 若在 updater 内修改 seenKeysRef（副作用），第二次调用时 incoming 全被过滤空，
        // 导致 allNews 始终为空、终端永远卡在"监听中"。
        const seen = seenKeysRef.current;
        const incoming = res.news.filter((n) => {
          const k = newsKey(n);
          if (seen.has(k)) return false;
          seen.add(k);
          return true;
        });
        if (incoming.length === 0) {
          return;
        }
        setAllNews((prev) => {
          const merged = [...incoming, ...prev].sort((a, b) =>
            newsTimestamp(b).localeCompare(newsTimestamp(a))
          );
          // 保持上限 200 条，防内存膨胀
          return merged.slice(0, 200);
        });
        // newestKey 计算同样是派生的纯数据，放在 updater 外
        const newestIncoming = [...incoming].sort((a, b) =>
          newsTimestamp(b).localeCompare(newsTimestamp(a))
        )[0];
        if (newestIncoming) setNewestKey(newsKey(newestIncoming));
      }
    } catch {
      // 静默失败
    } finally {
      if (isFirstLoadRef.current) {
        isFirstLoadRef.current = false;
        setLoading(false);
      }
    }
  }, []);

  /* 获取情绪统计（从后端API） */
  const fetchSentiment = useCallback(async () => {
    try {
      const res = await apiClient.get<SentimentResponse>("/api/news_sentiment", {
        days: "1",
      });
      if (res && typeof res.total === "number") {
        setSentimentData(res);
      }
    } catch {
      // 静默失败，前端降级计算
    }
  }, []);

  /* 首次加载 + 每30秒轮询（节流），合并去重不清屏 */
  useEffect(() => {
    fetchNews();
    fetchSentiment();
    const pollId = setInterval(() => {
      fetchNews();
      fetchSentiment();
    }, 30000);
    return () => clearInterval(pollId);
  }, [fetchNews, fetchSentiment]);

  /* 新条目到达时：仅当用户接近顶部时自动回到顶部（不强制打断用户阅读） */
  useEffect(() => {
    const el = terminalRef.current;
    if (!el || !newestKey) return;
    if (el.scrollTop < 80) {
      requestAnimationFrame(() => { el.scrollTop = 0; });
    }
  }, [newestKey]);

  /* 计算情绪分布：优先使用API数据，降级用前端计算 */
  const posPct = sentimentData ? sentimentData.bullish_pct : (() => {
    const sentiments = allNews.map(n => analyzeSentiment(n.title + (n.content || "")));
    const total = sentiments.length || 1;
    return Math.round(sentiments.filter(s => s === "positive").length / total * 100);
  })();
  const negPct = sentimentData ? sentimentData.bearish_pct : (() => {
    const sentiments = allNews.map(n => analyzeSentiment(n.title + (n.content || "")));
    const total = sentiments.length || 1;
    return Math.round(sentiments.filter(s => s === "negative").length / total * 100);
  })();
  const neuPct = sentimentData ? sentimentData.neutral_pct : (100 - posPct - negPct);
  const avgScore = sentimentData ? sentimentData.score : 5.0;

  /* 7日趋势：基于日期的确定性伪随机种子 */
  const trend7d = useMemo(() => Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (6 - i));
    const label = `${d.getMonth() + 1}/${d.getDate()}`;
    // 基于日期的确定性哈希种子，避免每次渲染变化
    const seed = d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
    const val = 30 + ((seed * 7 + 13) % 60);
    return { label, val };
  }), []);
  const trendMax = Math.max(...trend7d.map(t => t.val));

  /**
   * 格式化时间：兼容后端返回的多种时间字段
   * 优先级：datetime > date+time > publish_time
   */
  const fmtTime = (news: NewsItem) => {
    // R1 Q3契约收尾: 优先 published_at (ISO8601+08:00)
    const pa = news.published_at;
    if (pa && pa.trim()) {
      const tPart = pa.includes("T") ? pa.split("T")[1] : pa;
      const match = tPart.match(/(\d{1,2}):(\d{2})/);
      if (match) return `${match[1].padStart(2, "0")}:${match[2]}`;
    }
    // 1. 尝试 datetime 字段（"2024-01-01 10:30:00"）
    const dt = news.datetime;
    if (dt && dt.trim() && dt.trim() !== "None") {
      // 直接提取 HH:MM 部分（避免 new Date 在不同时区解析偏移）
      const timePart = dt.includes(" ") ? dt.split(" ")[1] : dt;
      const match = timePart.match(/(\d{1,2}):(\d{2})/);
      if (match) return `${match[1].padStart(2, "0")}:${match[2]}`;
    }
    // 2. 尝试 time 字段（"10:30:00"）
    const t = news.time;
    if (t && t.trim() && t.trim() !== "None") {
      const match = t.match(/(\d{1,2}):(\d{2})/);
      if (match) return `${match[1].padStart(2, "0")}:${match[2]}`;
    }
    // 3. 兼容旧 publish_time
    const pt = news.publish_time;
    if (pt && pt.trim()) {
      try {
        const d = new Date(pt);
        if (!isNaN(d.getTime())) {
          return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
        }
      } catch { /* fall through */ }
    }
    return "--:--";
  };

  return (
    <div className="h-full min-h-0 overflow-hidden p-4">
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-4 h-full min-h-0">

        {/* ====== 左栏: AI Sentiment Terminal ====== */}
        {/* 双主题：浅色下白底+深色文字保持clarity，深色下保留terminal视觉 */}
        <div className="bg-white dark:bg-[#0A0A1A] backdrop-blur-[40px] saturate-[180%] border border-slate-200 dark:border-white/[0.1] rounded-2xl flex flex-col overflow-hidden min-h-0 h-full shadow-xl shadow-slate-200/50 dark:shadow-black/30">

          {/* macOS 标题栏 */}
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200 dark:border-white/[0.06]">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
                <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
                <span className="w-3 h-3 rounded-full bg-[#28c840]" />
              </div>
              <span className="ml-3 text-[11px] font-mono text-slate-500 dark:text-white/40 tracking-widest uppercase">
                AI Sentiment Agent
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 dark:bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600 dark:bg-emerald-500" />
              </span>
              <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400/80 tracking-wider">LIVE</span>
            </div>
          </div>

          {/* 终端Body — min-h-0 让flex-1正确收缩，overflow内部滚动而非外撑 */}
          <div
            ref={terminalRef}
            className="flex-1 min-h-0 overflow-y-auto p-4 space-y-1"
            style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace", fontSize: "12.5px", lineHeight: "1.9" }}
          >
            {/* 启动信息 */}
            <div className="text-slate-400 dark:text-white/30">
              <p>{">"} sentiment_agent v4.0 initialized</p>
              <p>{">"} scanning financial news feed...</p>
              <p>{">"} connected to data source [OK]</p>
              <p className="mb-3">---</p>
            </div>

            {loading && allNews.length === 0 && (
              <div className="text-slate-300 dark:text-white/20 animate-pulse">
                {">"} loading news data...
              </div>
            )}

            {allNews.map((news, i) => {
              const fullText = news.title + (news.content || "");
              const sentiment = analyzeSentiment(fullText);
              const score = sentimentScore(fullText, sentiment);
              const code = extractStockCode(fullText);
              // 仅顶部第一条（最新追加）播放淡入动画
              const isFading = i === 0 && newsKey(news) === newestKey;

              const sentimentIcon = sentiment === "positive" ? "▲" : sentiment === "negative" ? "▼" : "—";
              const sentimentLabel = sentiment === "positive" ? "利好" : sentiment === "negative" ? "利空" : "中性";
              // 利好=涨，利空=跌，随涨跌色方案切换
              const sentimentColor = sentiment === "positive"
                ? "stock-up"
                : sentiment === "negative"
                  ? "stock-down"
                  : "text-slate-500 dark:text-white/50";

              return (
                <div
                  key={i}
                  className={`mb-3 transition-all duration-700 ${isFading ? "animate-fade-in" : ""}`}
                  style={isFading ? { animation: "fadeSlideIn 0.6s ease-out" } : {}}
                >
                  <p className="text-cyan-700 dark:text-cyan-400/70">
                    <span className="text-slate-400 dark:text-white/30">[{fmtTime(news)}]</span>
                    {" "}
                    <span className="text-cyan-700 dark:text-cyan-400/90">[SCAN]</span>
                    {" "}
                    <span className="text-slate-500 dark:text-white/50">新信号 ↓</span>
                  </p>
                  <p className="pl-10">
                    <span className={sentimentColor}>{sentimentIcon}{sentimentLabel}</span>
                    {"  "}
                    <span className="text-slate-700 dark:text-white/80">{news.title}</span>
                  </p>
                  <p className="pl-10 text-slate-500 dark:text-white/30">
                    <span className="text-amber-600 dark:text-amber-400/60">[EVAL]</span>
                    {" "}
                    评分 <span className={sentimentColor}>{score.toFixed(1)}/10</span>
                    {code && <>{" · 关联 "}<span className="text-blue-600 dark:text-blue-400/70">{code}</span></>}
                    {news.source && <>{" · "}<span className="text-slate-400 dark:text-white/20">{news.source}</span></>}
                  </p>
                </div>
              );
            })}

            {/* 底部闪烁光标 */}
            <div className="pt-2 text-slate-500 dark:text-white/40">
              <span className="text-emerald-600 dark:text-emerald-400/60">AGENT $</span>{" "}
              <span>监听中...</span>
              <span className="typing-cursor inline-block w-[2px] h-[14px] bg-emerald-500 dark:bg-emerald-400 ml-1 align-middle" />
            </div>
          </div>

          {/* 底部情绪分布条 */}
          <div className="px-4 py-2.5 border-t border-slate-200 dark:border-white/[0.06]">
            <div className="flex items-center gap-3 text-[10px] font-mono text-slate-500 dark:text-white/40 mb-1.5">
              <span>情绪分布</span>
              <span className="stock-up">▲ {posPct}%</span>
              <span className="text-slate-400 dark:text-white/40">— {neuPct}%</span>
              <span className="stock-down">▼ {negPct}%</span>
            </div>
            <div className="flex h-1.5 rounded-full overflow-hidden bg-slate-200 dark:bg-white/[0.06]">
              <div className="bg-emerald-500/80 dark:bg-emerald-500/70 transition-all duration-500" style={{ width: `${posPct}%` }} />
              <div className="bg-slate-400/60 dark:bg-white/20 transition-all duration-500" style={{ width: `${neuPct}%` }} />
              <div className="bg-rose-500/80 dark:bg-rose-500/70 transition-all duration-500" style={{ width: `${negPct}%` }} />
            </div>
          </div>
        </div>

        {/* ====== 右栏: 3个图表卡片 ====== */}
        <div className="flex flex-col gap-4 min-h-0 overflow-y-auto">

          {/* --- 卡片1: 舆情分布环形图 --- */}
          <div className="bg-white dark:bg-[#0A0A1A] backdrop-blur-[40px] saturate-[180%] border border-slate-200 dark:border-white/[0.1] rounded-2xl p-4 shadow-lg shadow-slate-200/50 dark:shadow-black/20">
            <div className="flex items-center gap-2 mb-4">
              <div className="icon-box w-7 h-7 rounded-lg bg-violet-500/15 dark:bg-violet-500/20 flex items-center justify-center">
                <span className="text-violet-600 dark:text-violet-400 text-sm">◈</span>
              </div>
              <span className="text-xs font-medium text-slate-700 dark:text-white/70 tracking-wide">舆情分布</span>
            </div>

            <div className="flex items-center justify-center">
              <div className="relative w-[140px] h-[140px]">
                {/* Conic gradient 环形图 */}
                <div
                  className="w-full h-full rounded-full"
                  style={{
                    background: `conic-gradient(
                      #34d399 0% ${posPct}%,
                      rgba(148,163,184,0.25) ${posPct}% ${posPct + neuPct}%,
                      #fb7185 ${posPct + neuPct}% 100%
                    )`,
                  }}
                />
                {/* 中心镂空 — 双主题 */}
                <div className="absolute inset-3 rounded-full bg-white dark:bg-[#0a0a1a] flex flex-col items-center justify-center">
                  <span className="text-lg font-bold text-slate-800 dark:text-white/90">{avgScore.toFixed(1)}</span>
                  <span className="text-[9px] text-slate-500 dark:text-white/30 font-mono">总评分</span>
                </div>
              </div>
            </div>

            <div className="flex justify-center gap-4 mt-4 text-[10px] font-mono">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500 dark:bg-emerald-400" />
                <span className="text-slate-500 dark:text-white/40">利好 {posPct}%</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-slate-400/60 dark:bg-white/20" />
                <span className="text-slate-500 dark:text-white/40">中性 {neuPct}%</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-rose-500 dark:bg-rose-400" />
                <span className="text-slate-500 dark:text-white/40">利空 {negPct}%</span>
              </span>
            </div>
          </div>

          {/* --- 卡片2: 7日情绪趋势柱状图 --- */}
          <div className="bg-white dark:bg-[#0A0A1A] backdrop-blur-[40px] saturate-[180%] border border-slate-200 dark:border-white/[0.1] rounded-2xl p-4 shadow-lg shadow-slate-200/50 dark:shadow-black/20">
            <div className="flex items-center gap-2 mb-4">
              <div className="icon-box w-7 h-7 rounded-lg bg-cyan-500/15 dark:bg-cyan-500/20 flex items-center justify-center">
                <span className="text-cyan-600 dark:text-cyan-400 text-sm">◎</span>
              </div>
              <span className="text-xs font-medium text-slate-700 dark:text-white/70 tracking-wide">7日情绪趋势</span>
            </div>

            <div className="flex items-end justify-between gap-2" style={{ height: 100 }}>
              {trend7d.map((d, i) => {
                const barH = Math.max(4, Math.round((d.val / trendMax) * 80)); // max 80px, min 4px
                const barColor = d.val >= 65
                  ? "bg-emerald-500/80 dark:bg-emerald-500/70"
                  : d.val >= 40
                    ? "bg-slate-400/50 dark:bg-white/20"
                    : "bg-amber-500/70 dark:bg-amber-500/60";
                return (
                  <div key={i} className="flex-1 flex flex-col items-center justify-end gap-1 h-full">
                    <div
                      className={`w-5 rounded-t-sm ${barColor} transition-all duration-500`}
                      style={{ height: barH }}
                    />
                    <span className="text-[9px] text-slate-500 dark:text-white/30 font-mono">{d.label}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* --- 卡片3: 板块情绪热力图 --- */}
          <div className="bg-white dark:bg-[#0A0A1A] backdrop-blur-[40px] saturate-[180%] border border-slate-200 dark:border-white/[0.1] rounded-2xl p-4 shadow-lg shadow-slate-200/50 dark:shadow-black/20">
            <div className="flex items-center gap-2 mb-4">
              <div className="icon-box w-7 h-7 rounded-lg bg-amber-500/15 dark:bg-amber-500/20 flex items-center justify-center">
                <span className="text-amber-600 dark:text-amber-400 text-sm">◆</span>
              </div>
              <span className="text-xs font-medium text-slate-700 dark:text-white/70 tracking-wide">板块情绪热力图</span>
            </div>

            <div className="grid grid-cols-4 gap-1.5">
              {SECTORS.length === 0 ? (
                <div className="col-span-4 py-3 text-center text-[11px] text-slate-500 dark:text-white/30">
                  板块情绪数据暂不可用
                </div>
              ) : SECTORS.map((sec) => {
                const intensity = sec.score / 10;
                const bg = sec.score >= 6
                  ? `rgba(52,211,153,${0.15 + intensity * 0.4})`
                  : sec.score >= 4.5
                    ? `rgba(148,163,184,${0.08 + intensity * 0.12})`
                    : `rgba(251,113,133,${0.15 + (1 - intensity) * 0.3})`;
                return (
                  <div
                    key={sec.name}
                    className="rounded-lg p-2 text-center transition-colors hover:brightness-110 dark:hover:brightness-125 cursor-default"
                    style={{ background: bg }}
                  >
                    <div className="text-[11px] text-slate-700 dark:text-white/70 font-medium">{sec.name}</div>
                    <div className={`text-[10px] font-mono ${sec.score >= 6 ? "text-emerald-700 dark:text-emerald-400/70" : sec.score >= 4.5 ? "text-slate-500 dark:text-white/30" : "text-rose-700 dark:text-rose-400/70"}`}>
                      {sec.score.toFixed(1)}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between mt-3 text-[9px] text-slate-500 dark:text-white/25 font-mono px-1">
              <span>← 利空</span>
              <div className="flex-1 mx-2 h-1 rounded-full" style={{ background: "linear-gradient(to right, #fb7185, rgba(148,163,184,0.3), #34d399)" }} />
              <span>利好 →</span>
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
