// Input: agent-store 实时事件流 (events) + theme-store (light/dark) + 当前时间
// Output: Mac风格终端Agent实时面板 — 毛玻璃主题(backdrop-blur+半透明+主题token) + 三点标题栏 + 等宽字体 + 树形日志
// Pos: 首页第4列, 取代旧AgentSidePanel空态+AgentProgressPanel复合结构
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
// [UI-Q2 2026-04-15 +08:00] 重构为毛玻璃(backdrop-blur-xl + bg-foreground/0.03 + 主题token色彩)，
//   废弃硬编码 #1E1E1E/#F8F8F8 让项目 Dark Glassmorphism 统一。
// [UI-Q4 2026-04-15 +08:00] 增加 TypewriterRow 打字机动画 — reasoning/tool_result/progress 文本逐字流入
//   并识别 type=reasoning 的流式行 (meta.streaming=true) 实时追加 token。仅对最近3条活跃行做动画,
//   更早的直接显示完成态, 避免百行同时打字机拖慢 UI。

"use client";
import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useAgentStore, type AgentEvent } from "@/lib/stores/agent-store";
import { ChevronRight, ChevronLeft, Trash2, Download, Circle } from "lucide-react";
import { PendingApprovalsPanel } from "@/components/agent/pending-approvals";
import { PlanListPanel } from "@/components/agent/plan-list-panel";

const STORAGE_KEY = "agent-panel-collapsed";

/* ---------- 事件→终端行 映射 ---------- */
type TerminalLine = {
  id: string;
  ts: number;
  kind: "prompt" | "start" | "child" | "done" | "info" | "error" | "warn";
  agent?: string;
  text: string;
};

function fmtTs(ts: number): string {
  const d = new Date(ts);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function eventToLine(ev: AgentEvent): TerminalLine {
  const common = { id: ev.id, ts: ev.ts, agent: ev.agent };
  switch (ev.type) {
    case "agent_started":
      return { ...common, kind: "start", text: `${ev.agent || "Agent"} → ${ev.title}` };
    case "agent_completed":
      return { ...common, kind: "done", text: `${ev.agent || "Agent"} completed · ${ev.title}` };
    case "agent_progress":
      return { ...common, kind: "info", text: ev.title };
    case "tool_call_start": {
      // meta: { tool_name, arguments }
      const m = (ev.meta || {}) as { tool_name?: string; arguments?: unknown };
      const name = m.tool_name || ev.title.replace(/^调用工具\s*/, "");
      let argsStr = "";
      try {
        const raw = m.arguments;
        if (raw && typeof raw === "object") {
          const vals = Object.values(raw as Record<string, unknown>)
            .filter((v) => v != null)
            .map((v) => String(v))
            .join(",");
          argsStr = vals.length > 40 ? vals.slice(0, 40) + "…" : vals;
        } else if (typeof raw === "string") {
          argsStr = raw.length > 40 ? raw.slice(0, 40) + "…" : raw;
        }
      } catch { /* ignore */ }
      return { ...common, kind: "child", text: `⚙ ${name}(${argsStr})` };
    }
    case "tool_call_result": {
      const failed = /fail|error|降级|未|timeout/i.test(ev.detail || "");
      const m = (ev.meta || {}) as { duration_ms?: number };
      const dur = m.duration_ms != null ? `${(m.duration_ms / 1000).toFixed(1)}s` : "";
      // [UI-Q4] 零截断 - 完整detail交给TerminalRow渲染, 由Collapsible决定展开
      const summary = ev.detail || "";
      return {
        ...common,
        kind: failed ? "warn" : "done",
        text: failed
          ? `✖ ${ev.title} — ${summary}`
          : `✓ ${dur}${summary ? " · " + summary : ""}`,
      };
    }
    case "reasoning": {
      const detail = ev.detail || ev.title;
      // streaming reasoning: 不截断, 完整展示累积的token流 (由 appendReasoningToken 构建)
      const isStreaming = !!(ev.meta && (ev.meta as { streaming?: boolean }).streaming);
      const text = isStreaming
        ? detail
        : detail.length > 80 ? detail.slice(0, 80) + "…" : detail;
      // [R3 Q4 P2 2026-04-15] 根据 reasoning content 前缀映射 kind:
      //   [APPROVAL]   → warn  (HITL 审批提示, 琥珀色, 🚨)
      //   [RISK_ALERT] level=high → error (红色), 其他 → warn, ⚠
      const raw = detail || "";
      if (raw.startsWith("[APPROVAL]")) {
        return { ...common, kind: "warn", text: `🚨 ${text}` };
      }
      if (raw.startsWith("[RISK_ALERT]")) {
        const meta = (ev.meta || {}) as { level?: string };
        const level = meta.level || (/level=(\w+)/.exec(raw)?.[1] ?? "medium");
        const kind: TerminalLine["kind"] = level === "high" ? "error" : "warn";
        return { ...common, kind, text: `⚠ ${text}` };
      }
      return { ...common, kind: "info", text: `💭 ${text}` };
    }
    default:
      return { ...common, kind: "info", text: ev.title };
  }
}

/* ---------- 行渲染（毛玻璃主题版） ---------- */
// 色彩均用 Tailwind 主题 token（text-foreground/X、品牌紫蓝/琥珀红）; 不再硬编码
const PREFIX: Record<TerminalLine["kind"], string> = {
  prompt: "$ ",
  start: "▶ ",
  child: "  ├─ ",
  done: "  └─ ",
  info: "  · ",
  warn: "  ⚠ ",
  error: "  ✖ ",
};
const PREFIX_CLASS: Record<TerminalLine["kind"], string> = {
  prompt: "text-[#3737CC] dark:text-[#7F7FFF]",      // 品牌紫蓝
  start:  "text-[#7F00FF] dark:text-[#BD93F9]",      // agent 紫
  child:  "text-foreground/60",                       // info 中性
  done:   "text-[#46BEA3]",                           // 成功青绿
  info:   "text-foreground/55",
  warn:   "text-[#F59E0B]",                           // 琥珀
  error:  "text-[#EF4444]",                           // 红
};

/* 打字机动画Hook — 逐字显示text, 速度约 35ms/char (~28 chars/sec)
 * animate=false 直接返回完整text (不动画), 用于"已完成"或"非活跃"行,
 * 这样只有最近3条活跃行会做动画, 百条历史直接静态显示, 性能安全。
 */
const TYPE_SPEED_MS = 35;
function useTypewriter(text: string, animate: boolean): { shown: string; done: boolean } {
  const [len, setLen] = useState<number>(animate ? 0 : text.length);
  const prevTextRef = useRef<string>(text);

  useEffect(() => {
    if (!animate) {
      // 非动画模式：shown 已直接用 text，无需同步 len
      prevTextRef.current = text;
      return;
    }
    // 文本缩短(极少见) → 重置（microtask 推迟避免 set-state-in-effect 规则）
    if (text.length < prevTextRef.current.length) {
      Promise.resolve().then(() => setLen(0));
    }
    prevTextRef.current = text;
    if (len >= text.length) return;
    const id = setTimeout(() => {
      setLen((l) => Math.min(l + 1, text.length));
    }, TYPE_SPEED_MS);
    return () => clearTimeout(id);
  }, [text, len, animate]);

  const shown = animate ? text.slice(0, len) : text;
  return { shown, done: !animate || len >= text.length };
}

// [UI-Q4] 长文本折叠阈值 — 超过3行或300字符时默认折叠, 点击展开
const FOLD_LINE_THRESHOLD = 3;
const FOLD_CHAR_THRESHOLD = 300;

function TerminalRow({
  line,
  isLast,
  animate,
}: {
  line: TerminalLine;
  isLast: boolean;
  animate: boolean;
}) {
  // 仅对文本型行做打字机; start/done/prompt 一行即完整显示
  const canAnimate = animate && (line.kind === "info" || line.kind === "child" || line.kind === "warn");
  const { shown, done } = useTypewriter(line.text, canAnimate);
  const showCursor = isLast || (canAnimate && !done);

  // 折叠控制
  const fullLines = shown.split("\n");
  const isLong = fullLines.length > FOLD_LINE_THRESHOLD || shown.length > FOLD_CHAR_THRESHOLD;
  const [expanded, setExpanded] = useState(false);
  const displayText = !isLong || expanded
    ? shown
    : fullLines.slice(0, FOLD_LINE_THRESHOLD).join("\n") +
      (fullLines.length > FOLD_LINE_THRESHOLD ? "\n..." : "");
  const hiddenCount = isLong
    ? (fullLines.length - FOLD_LINE_THRESHOLD > 0
        ? `${fullLines.length - FOLD_LINE_THRESHOLD}行`
        : `${shown.length - FOLD_CHAR_THRESHOLD}字`)
    : "";

  return (
    <div className="flex items-start gap-2 animate-in fade-in slide-in-from-bottom-1 duration-300 whitespace-pre-wrap break-words rounded px-1 -mx-1 hover:bg-foreground/[0.04] dark:hover:bg-white/[0.04] transition-colors">
      <span className="shrink-0 tabular-nums select-none text-foreground/40 text-[11px] pt-[1px]">
        [{fmtTs(line.ts)}]
      </span>
      <span className="min-w-0 flex-1 text-foreground/85">
        <span className={PREFIX_CLASS[line.kind]}>{PREFIX[line.kind]}</span>
        <span>{displayText}</span>
        {showCursor && (
          <span className="inline-block w-[6px] h-[12px] ml-1 align-middle bg-[#3737CC] dark:bg-[#7F7FFF] animate-[blink_1s_step-end_infinite]" />
        )}
        {isLong && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="ml-2 text-[10px] text-[#3737CC] dark:text-[#7F7FFF] hover:underline select-none"
          >
            {expanded ? "收起" : `展开${hiddenCount}`}
          </button>
        )}
      </span>
    </div>
  );
}

export function AgentSidePanel() {
  const [mounted, setMounted] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [now, setNow] = useState<number | null>(null);
  const [cleared, setCleared] = useState(false);
  const events = useAgentStore((s) => s.events);
  const debateTurns = useAgentStore((s) => s.debateTurns);
  const degradations = useAgentStore((s) => s.degradations);
  const confidenceCap = useAgentStore((s) => s.confidenceCap);
  const scorecard = useAgentStore((s) => s.scorecard);
  const decisionMemo = useAgentStore((s) => s.decisionMemo);
  const reflectionSummary = useAgentStore((s) => s.reflectionSummary);
  const memoryContext = useAgentStore((s) => s.memoryContext);
  const isAnalyzing = useAgentStore((s) => s.isAnalyzing);
  const agentProgresses = useAgentStore((s) => s.agentProgresses);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [startTime, setStartTime] = useState<number>(0);

  // 仅客户端挂载后初始化时间, 根治SSR水化不匹配（microtask 推迟避免 set-state-in-effect 规则）
  useEffect(() => {
    Promise.resolve().then(() => {
      const t = Date.now();
      setCollapsed(localStorage.getItem(STORAGE_KEY) === 'true');
      setStartTime(t);
      setNow(t);
      setMounted(true);
    });
  }, []);


  // 时钟 (仅mounted后启动)
  useEffect(() => {
    if (!mounted) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [mounted]);

  // 事件变化自动滚到底
  useEffect(() => {
    const el = scrollRef.current;
    if (el) requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
  }, [events.length]);

  const toggle = () => {
    setCollapsed((v) => {
      const next = !v;
      localStorage.setItem(STORAGE_KEY, String(next));
      return next;
    });
  };

  // 构造日志行（含顶部prompt行）— cleared时仅显示prompt，不销毁events
  const lines = useMemo<TerminalLine[]>(() => {
    const head: TerminalLine = {
      id: "__head__",
      ts: startTime,
      kind: "prompt",
      text: isAnalyzing
        ? `running 10-agent pipeline · ${agentProgresses.length} active`
        : events.length === 0
          ? "awaiting stock-analysis pipeline... (type a code in chat to begin)"
          : "pipeline idle · last run complete",
    };
    if (cleared) return [head];
    const body = events.map(eventToLine);
    return [head, ...body];
  }, [events, isAnalyzing, agentProgresses.length, cleared, startTime]);

  const uptime = now == null ? 0 : Math.floor((now - startTime) / 1000);
  const uptimeStr = uptime >= 60 ? `${Math.floor(uptime / 60)}m${uptime % 60}s` : `${uptime}s`;

  /* 导出日志 */
  const handleExport = useCallback(() => {
    const text = lines
      .map((l) => `[${fmtTs(l.ts)}] ${l.kind.toUpperCase()} ${l.agent ? `(${l.agent}) ` : ""}${l.text}`)
      .join("\n");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agent-stream-${new Date().toISOString().replace(/[:.]/g, "-")}.log`;
    a.click();
    URL.revokeObjectURL(url);
  }, [lines]);

  // SSR/未挂载时仅输出占位骨架, 避免任何时间戳hydration不匹配
  if (!mounted) {
    return (
      <div className="hidden md:flex w-72 xl:w-96 shrink-0 border-l border-foreground/[0.08] dark:border-white/[0.08] bg-background/70 dark:bg-[rgba(10,10,26,0.65)] backdrop-blur-xl backdrop-saturate-150" />
    );
  }

  if (collapsed) {
    return (
      <div className="hidden md:flex w-10 shrink-0 flex-col items-center py-2 gap-2 border-l border-foreground/[0.08] dark:border-white/[0.08] bg-background/70 dark:bg-[rgba(10,10,26,0.6)] backdrop-blur-xl backdrop-saturate-150">
        <button
          onClick={toggle}
          className="h-8 w-8 flex items-center justify-center rounded-md text-foreground/50 hover:text-foreground hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors"
          title="展开 Agent Stream"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="flex flex-col items-center gap-1 mt-2">
          <Circle
            className={`h-2.5 w-2.5 fill-current ${isAnalyzing ? "text-[#46BEA3]" : "text-foreground/30"}`}
          />
          <span className="text-[9px] font-mono rotate-90 origin-center whitespace-nowrap mt-8 text-foreground/50">
            Agent Stream
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="hidden md:flex w-72 xl:w-96 shrink-0 flex-col font-mono border-l border-foreground/[0.08] dark:border-white/[0.08] bg-background/70 dark:bg-[rgba(10,10,26,0.65)] backdrop-blur-xl backdrop-saturate-150 shadow-2xl shadow-foreground/[0.06] dark:shadow-black/30">
      {/* macOS 风格标题栏（毛玻璃） */}
      <div className="flex items-center justify-between px-3 h-9 shrink-0 border-b border-foreground/[0.08] dark:border-white/[0.08] bg-foreground/[0.03] dark:bg-white/[0.03]">
        <div className="flex items-center gap-2">
          {/* Mac 三点 */}
          <div className="flex items-center gap-1.5 mr-2">
            <span className="w-3 h-3 rounded-full bg-[#FF5F57] shadow-sm" />
            <span className="w-3 h-3 rounded-full bg-[#FEBC2E] shadow-sm" />
            <span className="w-3 h-3 rounded-full bg-[#28C840] shadow-sm" />
          </div>
          <span className="text-[11px] tracking-wide text-foreground/70">
            ⎔ AGENT STREAM · stock-analysis · zsh
          </span>
        </div>
        <span className="text-[10px] tabular-nums text-foreground/45" suppressHydrationWarning>
          {now == null ? '--:--:--' : fmtTs(now)}
        </span>
      </div>

      {/* 工具条 */}
      <div className="flex items-center justify-between px-3 h-7 shrink-0 border-b border-foreground/[0.06] dark:border-white/[0.06] bg-foreground/[0.02] dark:bg-white/[0.02]">
        <span className="text-[10px] text-foreground/50">
          {events.length} events · {agentProgresses.filter((p) => p.status === "completed").length}/
          {agentProgresses.length || 10} agents
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setCleared((c) => !c)}
            className="h-5 w-5 flex items-center justify-center rounded text-foreground/50 hover:text-foreground hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors"
            title={cleared ? "恢复显示" : "清空视图 (不删除store)"}
          >
            <Trash2 className="h-3 w-3" />
          </button>
          <button
            onClick={handleExport}
            className="h-5 w-5 flex items-center justify-center rounded text-foreground/50 hover:text-foreground hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors"
            title="导出日志"
          >
            <Download className="h-3 w-3" />
          </button>
          <button
            onClick={toggle}
            className="h-5 w-5 flex items-center justify-center rounded text-foreground/50 hover:text-foreground hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06] transition-colors"
            title="折叠"
          >
            <ChevronRight className="h-3 w-3" />
          </button>
        </div>
      </div>

      {/* 终端内容（透明，让毛玻璃容器透过） */}
      {/* P0-5 HITL 确认面：轮询 pending / 提交 approve|reject */}
      <div className="px-3 pt-2 shrink-0 space-y-2" data-testid="pending-approvals-host">
        <PlanListPanel />
        <PendingApprovalsPanel />
      </div>

      {/* P0-2 降级可视化条：有 degradation 时吸顶可见，不渲染假数 */}
      {/* G6/G5/G7/G8 评分卡与只读上下文 */}
      {(scorecard ||
        decisionMemo ||
        (reflectionSummary && Array.isArray((reflectionSummary as { items?: unknown[] }).items) &&
          ((reflectionSummary as { items?: unknown[] }).items?.length || 0) > 0) ||
        (memoryContext &&
          ((memoryContext as { history_count?: number }).history_count ||
            (memoryContext as { semantic_context?: string }).semantic_context))) && (
        <div className="mb-3 space-y-2 rounded-lg border border-[#3737CC]/25 bg-[#3737CC]/5 p-2.5 dark:border-[#7F7FFF]/25 dark:bg-[#7F7FFF]/10">
          <div className="text-[10px] font-medium uppercase tracking-wide text-[#3737CC] dark:text-[#7F7FFF]">
            Run Scorecard / 备忘
          </div>
          {scorecard && (
            <div className="grid grid-cols-2 gap-1.5 text-[10px]">
              {(
                [
                  ['覆盖', scorecard.data_coverage],
                  ['工具', scorecard.tool_success_rate],
                  ['一致', scorecard.role_agreement],
                  ['置信帽', scorecard.confidence_cap],
                ] as Array<[string, number | null | undefined]>
              ).map(([label, v]) => (
                <div key={label} className="rounded bg-background/50 px-1.5 py-1">
                  <div className="text-muted-foreground">{label}</div>
                  <div className="font-semibold tabular-nums">
                    {typeof v === 'number' && !Number.isNaN(v)
                      ? `${Math.round(Math.max(0, Math.min(1, v)) * 100)}%`
                      : '—'}
                  </div>
                </div>
              ))}
            </div>
          )}
          {decisionMemo &&
            Array.isArray((decisionMemo as { veto_reasons?: string[] }).veto_reasons) &&
            ((decisionMemo as { veto_reasons?: string[] }).veto_reasons?.length || 0) > 0 && (
              <div className="space-y-0.5 text-[10px] text-muted-foreground">
                <div className="font-medium text-amber-700 dark:text-amber-400">否决/风险</div>
                <ul className="list-disc pl-3">
                  {((decisionMemo as { veto_reasons?: string[] }).veto_reasons || [])
                    .slice(0, 3)
                    .map((r, i) => (
                      <li key={i} className="line-clamp-2">
                        {r}
                      </li>
                    ))}
                </ul>
              </div>
            )}
          {reflectionSummary &&
            Array.isArray((reflectionSummary as { items?: Array<{ lessons?: string }> }).items) &&
            ((reflectionSummary as { items?: unknown[] }).items?.length || 0) > 0 && (
              <div className="text-[10px] text-muted-foreground">
                <div className="mb-0.5 font-medium">反思（只读）</div>
                <p className="line-clamp-3">
                  {(
                    (reflectionSummary as { items?: Array<{ lessons?: string; what_went_wrong?: string }> })
                      .items || []
                  )
                    .map((it) => it.lessons || it.what_went_wrong || '')
                    .filter(Boolean)
                    .slice(0, 2)
                    .join('；') || '—'}
                </p>
              </div>
            )}
          {memoryContext &&
            ((memoryContext as { history_count?: number }).history_count ||
              (memoryContext as { semantic_context?: string }).semantic_context) && (
              <div className="text-[10px] text-muted-foreground">
                <div className="mb-0.5 font-medium">
                  记忆预取
                  {typeof (memoryContext as { history_count?: number }).history_count === 'number'
                    ? ` · ${(memoryContext as { history_count?: number }).history_count} 次`
                    : ''}
                </div>
                {(memoryContext as { semantic_context?: string }).semantic_context && (
                  <p className="line-clamp-2">
                    {(memoryContext as { semantic_context?: string }).semantic_context}
                  </p>
                )}
              </div>
            )}
        </div>
      )}

      {(degradations.length > 0 || confidenceCap != null) && (
        <div
          className="mx-3 mb-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-2 space-y-1"
          data-testid="agent-degradation-banner"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-medium text-amber-700 dark:text-amber-300">
              数据降级（未使用假行情）
            </span>
            {confidenceCap != null && (
              <span className="text-[10px] font-mono text-amber-700/90 dark:text-amber-300/90">
                置信上限 {Math.round(confidenceCap * 100)}%
              </span>
            )}
          </div>
          <ul className="space-y-0.5 max-h-20 overflow-y-auto">
            {degradations.slice(-4).map((d) => (
              <li key={d.id} className="text-[10px] leading-snug text-amber-900/85 dark:text-amber-100/85">
                <span className="font-mono opacity-80">{d.cause}</span>
                {d.source ? ` · ${d.source}` : ""}
                {d.message ? ` — ${d.message}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* P0-3 辩论证据面：双栏扫读分歧（有 turn 才显） */}
      {debateTurns.length > 0 && (
        <div
          className="px-3 pb-2 shrink-0 border-b border-foreground/[0.06] space-y-1.5"
          data-testid="debate-turns-strip"
        >
          <div className="text-[10px] uppercase tracking-wide text-foreground/45">Debate · 分歧扫读</div>
          <div className="grid grid-cols-2 gap-1.5">
            {(["bull", "bear"] as const).map((side) => {
              const turn = debateTurns.find((t) => t.side === side);
              const label = side === "bull" ? "多方" : "空方";
              const tone =
                side === "bull"
                  ? "border-emerald-500/30 text-emerald-500"
                  : "border-rose-500/30 text-rose-500";
              return (
                <div key={side} className={`rounded border ${tone} bg-foreground/[0.03] px-2 py-1.5`}>
                  <div className="flex items-center justify-between gap-1 mb-0.5">
                    <span className="text-[10px] font-semibold">{label}</span>
                    <span className="text-[9px] opacity-70">{turn?.confidence || "—"}</span>
                  </div>
                  <p className="text-[10px] leading-snug text-foreground/70 line-clamp-3">
                    {turn?.thesis || "等待产出…"}
                  </p>
                </div>
              );
            })}
          </div>
          {(() => {
            const summary = debateTurns.find((t) => t.side === "summary");
            if (!summary) return null;
            const pts = summary.divergence_points || [];
            return (
              <div className="rounded border border-amber-500/25 bg-amber-500/5 px-2 py-1.5">
                <div className="text-[10px] font-medium text-amber-600 dark:text-amber-400 mb-0.5">
                  分歧点
                </div>
                {pts.length > 0 ? (
                  <ul className="space-y-0.5">
                    {pts.slice(0, 3).map((pt, i) => (
                      <li key={i} className="text-[10px] text-foreground/70 leading-snug">
                        · {pt}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[10px] text-foreground/70 line-clamp-2">{summary.thesis}</p>
                )}
              </div>
            );
          })()}
        </div>
      )}

      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto px-3 py-2 space-y-0.5 agent-term-scroll bg-transparent"
        style={{ fontSize: "12px", lineHeight: "1.65" }}
      >
        {lines.map((line, idx) => {
          // 仅对"最近3条"做打字机动画, 更早的直接显示完成态, 防止百行同时打字机卡顿
          const animate = isAnalyzing && idx >= lines.length - 3;
          return (
            <TerminalRow
              key={line.id}
              line={line}
              isLast={idx === lines.length - 1 && isAnalyzing}
              animate={animate}
            />
          );
        })}
      </div>

      {/* 底部状态栏 */}
      <div className="flex items-center justify-between px-3 h-6 shrink-0 border-t border-foreground/[0.06] dark:border-white/[0.06] bg-foreground/[0.02] dark:bg-white/[0.02] text-[10px] tabular-nums text-foreground/50">
        <span className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${isAnalyzing ? "bg-[#46BEA3]" : "bg-foreground/30"}`}
            style={isAnalyzing ? { boxShadow: "0 0 6px #46BEA3" } : undefined}
          />
          <span>{isAnalyzing ? "connected · streaming" : "idle"}</span>
        </span>
        <span>uptime {uptimeStr}</span>
      </div>

      {/* 光标闪烁 + 自定义滚动条（细、透明 track） */}
      <style jsx>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          50.01%, 100% { opacity: 0; }
        }
        .agent-term-scroll::-webkit-scrollbar { width: 6px; }
        .agent-term-scroll::-webkit-scrollbar-track { background: transparent; }
        .agent-term-scroll::-webkit-scrollbar-thumb {
          background: rgba(127,127,127,0.25);
          border-radius: 3px;
        }
        .agent-term-scroll::-webkit-scrollbar-thumb:hover {
          background: rgba(127,127,127,0.45);
        }
      `}</style>
    </div>
  );
}
