// Input: agent-store 实时事件流 (events) + theme-store (light/dark) + 当前时间
// Output: Mac风格终端Agent实时面板 — 三点标题栏 + 等宽字体 + 树形日志 + 暗/亮双主题
// Pos: 首页第4列, 取代旧AgentSidePanel空态+AgentProgressPanel复合结构
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useAgentStore, type AgentEvent } from "@/lib/stores/agent-store";
import { useThemeStore } from "@/lib/stores/theme-store";
import { ChevronRight, ChevronLeft, Trash2, Download, Circle } from "lucide-react";

const STORAGE_KEY = "agent-panel-collapsed";

/* ---------- 主题色板 ---------- */
type Palette = {
  bg: string; bgHeader: string; bgStatus: string;
  text: string; muted: string;
  prompt: string; info: string; warn: string; error: string; agent: string;
  timestamp: string; border: string; cursor: string;
};
const THEME: { dark: Palette; light: Palette } = {
  dark: {
    bg: "#1E1E1E",
    bgHeader: "#2D2D2D",
    bgStatus: "#181818",
    text: "#D4D4D4",
    muted: "#6A6A6A",
    prompt: "#50FA7B",
    info: "#8BE9FD",
    warn: "#F1FA8C",
    error: "#FF5555",
    agent: "#BD93F9",
    timestamp: "#6272A4",
    border: "rgba(255,255,255,0.08)",
    cursor: "#50FA7B",
  },
  light: {
    bg: "#F8F8F8",
    bgHeader: "#ECECEC",
    bgStatus: "#E5E5E5",
    text: "#333333",
    muted: "#888888",
    prompt: "#28A745",
    info: "#0366D6",
    warn: "#D73A49",
    error: "#D73A49",
    agent: "#6F42C1",
    timestamp: "#6A737D",
    border: "rgba(0,0,0,0.08)",
    cursor: "#28A745",
  },
};

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
    case "tool_call_start":
      return { ...common, kind: "child", text: `fetching (${ev.title})` };
    case "tool_call_result": {
      const failed = /fail|error|降级|未|timeout/i.test(ev.detail || "");
      return {
        ...common,
        kind: failed ? "warn" : "child",
        text: `${ev.title}${failed ? " failed, degraded" : " ok"}`,
      };
    }
    case "reasoning":
      return { ...common, kind: "info", text: ev.title };
    default:
      return { ...common, kind: "info", text: ev.title };
  }
}

/* ---------- 行渲染 ---------- */
function TerminalRow({ line, palette, isLast }: { line: TerminalLine; palette: Palette; isLast: boolean }) {
  const prefixMap = {
    prompt: "$ ",
    start: "▶ ",
    child: "  ├─ ",
    done: "  └─ ",
    info: "  · ",
    warn: "  ⚠ ",
    error: "  ✖ ",
  } as const;
  const colorMap = {
    prompt: palette.prompt,
    start: palette.agent,
    child: palette.info,
    done: palette.prompt,
    info: palette.text,
    warn: palette.warn,
    error: palette.error,
  } as const;

  return (
    <div
      className="flex items-start gap-2 animate-in fade-in slide-in-from-bottom-1 duration-300 whitespace-pre-wrap break-words"
      style={{ color: palette.text }}
    >
      <span className="shrink-0 tabular-nums select-none" style={{ color: palette.timestamp }}>
        [{fmtTs(line.ts)}]
      </span>
      <span className="min-w-0 flex-1">
        <span style={{ color: colorMap[line.kind] }}>{prefixMap[line.kind]}</span>
        {line.kind !== "prompt" && line.agent && line.kind === "start" && (
          <span style={{ color: palette.agent }}>{""}</span>
        )}
        <span>{line.text}</span>
        {isLast && (
          <span
            className="inline-block w-[6px] h-[12px] ml-1 align-middle animate-[blink_1s_step-end_infinite]"
            style={{ background: palette.cursor }}
          />
        )}
      </span>
    </div>
  );
}

export function AgentSidePanel() {
  const [collapsed, setCollapsed] = useState(false);
  const [now, setNow] = useState<number>(() => Date.now());
  const [cleared, setCleared] = useState(false);
  const events = useAgentStore((s) => s.events);
  const isAnalyzing = useAgentStore((s) => s.isAnalyzing);
  const agentProgresses = useAgentStore((s) => s.agentProgresses);
  const theme = useThemeStore((s) => s.theme);
  const palette = theme === "dark" ? THEME.dark : THEME.light;
  const scrollRef = useRef<HTMLDivElement>(null);
  const startRef = useRef<number>(Date.now());

  // 初始折叠状态
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "true") setCollapsed(true);
  }, []);

  // 时钟
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

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
      ts: startRef.current,
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
  }, [events, isAnalyzing, agentProgresses.length, cleared]);

  const uptime = Math.floor((now - startRef.current) / 1000);
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

  if (collapsed) {
    return (
      <div
        className="hidden md:flex w-10 shrink-0 flex-col items-center py-2 gap-2 border-l"
        style={{ background: palette.bgStatus, borderColor: palette.border }}
      >
        <button
          onClick={toggle}
          className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
          style={{ color: palette.muted }}
          title="展开 Agent Stream"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="flex flex-col items-center gap-1 mt-2">
          <Circle
            className="h-2.5 w-2.5 fill-current"
            style={{ color: isAnalyzing ? palette.prompt : palette.muted }}
          />
          <span
            className="text-[9px] font-mono rotate-90 origin-center whitespace-nowrap mt-8"
            style={{ color: palette.muted }}
          >
            Agent Stream
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      className="hidden md:flex w-72 xl:w-96 shrink-0 flex-col border-l font-mono"
      style={{ background: palette.bg, borderColor: palette.border }}
    >
      {/* macOS 风格标题栏 */}
      <div
        className="flex items-center justify-between px-3 h-9 shrink-0 border-b"
        style={{ background: palette.bgHeader, borderColor: palette.border }}
      >
        <div className="flex items-center gap-2">
          {/* 三点 */}
          <div className="flex items-center gap-1.5 mr-2">
            <span className="w-3 h-3 rounded-full" style={{ background: "#FF5F57" }} />
            <span className="w-3 h-3 rounded-full" style={{ background: "#FEBC2E" }} />
            <span className="w-3 h-3 rounded-full" style={{ background: "#28C840" }} />
          </div>
          <span className="text-[11px] tracking-wide" style={{ color: palette.text }}>
            ⎔ AGENT STREAM · stock-analysis · zsh
          </span>
        </div>
        <span className="text-[10px] tabular-nums" style={{ color: palette.muted }}>
          {fmtTs(now)}
        </span>
      </div>

      {/* 工具条 */}
      <div
        className="flex items-center justify-between px-3 h-7 shrink-0 border-b"
        style={{ background: palette.bgStatus, borderColor: palette.border }}
      >
        <span className="text-[10px]" style={{ color: palette.muted }}>
          {events.length} events · {agentProgresses.filter((p) => p.status === "completed").length}/
          {agentProgresses.length || 10} agents
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setCleared((c) => !c)}
            className="h-5 w-5 flex items-center justify-center rounded hover:bg-black/10 dark:hover:bg-white/10"
            style={{ color: palette.muted }}
            title={cleared ? "恢复显示" : "清空视图 (不删除store)"}
          >
            <Trash2 className="h-3 w-3" />
          </button>
          <button
            onClick={handleExport}
            className="h-5 w-5 flex items-center justify-center rounded hover:bg-black/10 dark:hover:bg-white/10"
            style={{ color: palette.muted }}
            title="导出日志"
          >
            <Download className="h-3 w-3" />
          </button>
          <button
            onClick={toggle}
            className="h-5 w-5 flex items-center justify-center rounded hover:bg-black/10 dark:hover:bg-white/10"
            style={{ color: palette.muted }}
            title="折叠"
          >
            <ChevronRight className="h-3 w-3" />
          </button>
        </div>
      </div>

      {/* 终端内容 */}
      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto px-3 py-2 space-y-0.5 agent-term-scroll"
        style={{ fontSize: "12px", lineHeight: "1.65" }}
      >
        {lines.map((line, idx) => (
          <TerminalRow
            key={line.id}
            line={line}
            palette={palette}
            isLast={idx === lines.length - 1 && isAnalyzing}
          />
        ))}
      </div>

      {/* 底部状态栏 */}
      <div
        className="flex items-center justify-between px-3 h-6 shrink-0 border-t text-[10px] tabular-nums"
        style={{ background: palette.bgStatus, borderColor: palette.border, color: palette.muted }}
      >
        <span className="flex items-center gap-1.5">
          <span
            className="w-2 h-2 rounded-full"
            style={{
              background: isAnalyzing ? palette.prompt : palette.muted,
              boxShadow: isAnalyzing ? `0 0 6px ${palette.prompt}` : undefined,
            }}
          />
          <span>{isAnalyzing ? "connected · streaming" : "idle"}</span>
        </span>
        <span>uptime {uptimeStr}</span>
      </div>

      {/* 光标闪烁 + 自定义滚动条 */}
      <style jsx>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          50.01%, 100% { opacity: 0; }
        }
        .agent-term-scroll::-webkit-scrollbar { width: 6px; }
        .agent-term-scroll::-webkit-scrollbar-track { background: transparent; }
        .agent-term-scroll::-webkit-scrollbar-thumb {
          background: ${palette.border};
          border-radius: 3px;
        }
        .agent-term-scroll::-webkit-scrollbar-thumb:hover {
          background: ${palette.muted};
        }
      `}</style>
    </div>
  );
}
