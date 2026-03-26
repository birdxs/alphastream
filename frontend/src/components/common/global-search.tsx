/**
 * Input: 键盘事件(Cmd+K / Ctrl+K)、用户搜索词
 * Output: 全局搜索对话框，分类显示股票/页面/对话结果，选中后导航
 * Pos: components/common/global-search.tsx - 全局快捷搜索入口
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */
"use client";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { useRouter } from "next/navigation";
import { Search, TrendingUp, LayoutDashboard, MessageSquare } from "lucide-react";
import { COMMON_STOCKS } from "@/lib/utils/stock-code";
import { useChatStore } from "@/lib/stores/chat-store";

/* ── 页面路由映射 ── */
const PAGE_ROUTES: Array<{ keywords: string[]; label: string; path: string }> = [
  { keywords: ["看板", "dashboard", "首页", "home"], label: "看板 / Dashboard", path: "/dashboard" },
  { keywords: ["选股", "screener", "筛选"], label: "选股器 / Screener", path: "/screener" },
  { keywords: ["对话", "chat", "聊天", "ai"], label: "AI 对话", path: "/chat" },
  { keywords: ["设置", "settings", "配置"], label: "设置 / Settings", path: "/settings" },
];

/* ── 搜索结果类型 ── */
interface SearchResult {
  id: string;
  category: "stock" | "page" | "conversation";
  label: string;
  sublabel?: string;
  action: () => void;
}

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const conversations = useChatStore((s) => s.conversations);

  /* 快捷键打开 */
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  /* 打开时聚焦输入框 */
  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIdx(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  /* ── 搜索逻辑 ── */
  const results = useMemo<SearchResult[]>(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];

    const out: SearchResult[] = [];

    /* 股票匹配 */
    const isStockCode = /^\d{1,6}$/.test(q);
    const stockMatches = Object.entries(COMMON_STOCKS)
      .filter(([code, name]) => code.includes(q) || name.toLowerCase().includes(q))
      .slice(0, 5);

    for (const [code, name] of stockMatches) {
      out.push({
        id: `stock-${code}`,
        category: "stock",
        label: `${code} ${name}`,
        sublabel: "查看分析",
        action: () => {
          setOpen(false);
          router.push(`/stock/${code}`);
        },
      });
    }

    /* 6位纯数字但未命中已知股票 → 快捷分析入口 */
    if (/^\d{6}$/.test(q) && !stockMatches.some(([c]) => c === q)) {
      out.push({
        id: `stock-quick-${q}`,
        category: "stock",
        label: `分析 ${q}`,
        sublabel: "快捷跳转",
        action: () => {
          setOpen(false);
          router.push(`/stock/${q}`);
        },
      });
    }

    /* 页面匹配 */
    for (const page of PAGE_ROUTES) {
      if (page.keywords.some((kw) => kw.includes(q) || q.includes(kw))) {
        out.push({
          id: `page-${page.path}`,
          category: "page",
          label: page.label,
          sublabel: page.path,
          action: () => {
            setOpen(false);
            router.push(page.path);
          },
        });
      }
    }

    /* 对话标题模糊匹配 */
    if (conversations.length > 0) {
      const convMatches = conversations
        .filter((c) => c.title?.toLowerCase().includes(q))
        .slice(0, 4);
      for (const conv of convMatches) {
        out.push({
          id: `conv-${conv.conversation_id}`,
          category: "conversation",
          label: conv.title || "未命名对话",
          sublabel: conv.updated_at ? new Date(conv.updated_at).toLocaleDateString() : undefined,
          action: () => {
            setOpen(false);
            router.push(`/chat?id=${conv.conversation_id}`);
          },
        });
      }
    }

    return out;
  }, [query, conversations, router]);

  /* activeIdx 归位 */
  useEffect(() => {
    setActiveIdx(0);
  }, [results.length]);

  /* 键盘导航 */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((i) => (i + 1) % Math.max(results.length, 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((i) => (i - 1 + results.length) % Math.max(results.length, 1));
      } else if (e.key === "Enter" && results.length > 0) {
        e.preventDefault();
        results[activeIdx]?.action();
      }
    },
    [results, activeIdx],
  );

  /* ── 分类分组 ── */
  const grouped = useMemo(() => {
    const map: Record<string, SearchResult[]> = {};
    for (const r of results) {
      (map[r.category] ??= []).push(r);
    }
    return map;
  }, [results]);

  const categoryMeta: Record<string, { icon: typeof TrendingUp; title: string }> = {
    stock: { icon: TrendingUp, title: "股票" },
    page: { icon: LayoutDashboard, title: "页面" },
    conversation: { icon: MessageSquare, title: "对话" },
  };

  /* 计算全局索引 */
  let globalIdx = 0;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="sm:max-w-md p-0 overflow-hidden bg-[#0A0A1A]/80 backdrop-blur-sm border border-white/[0.08] rounded-2xl"
        showCloseButton={false}
      >
        <div className="p-4">
          {/* 搜索输入 */}
          <div className="flex items-center gap-2 bg-white/[0.04] border border-white/[0.08] rounded-2xl px-3 py-2.5">
            <Search className="h-4 w-4 text-muted-foreground shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="搜索股票、页面或对话..."
              className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-muted-foreground/50"
            />
            {query && (
              <button
                onClick={() => {
                  setQuery("");
                  inputRef.current?.focus();
                }}
                className="text-muted-foreground hover:text-foreground text-xs"
              >
                ✕
              </button>
            )}
          </div>

          {/* 搜索结果 */}
          {results.length > 0 && (
            <div className="mt-2 max-h-72 overflow-y-auto">
              {(["stock", "page", "conversation"] as const).map((cat) => {
                const items = grouped[cat];
                if (!items?.length) return null;
                const meta = categoryMeta[cat];
                const Icon = meta.icon;

                return (
                  <div key={cat} className="mb-1">
                    <div className="flex items-center gap-1.5 px-2 py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground/60 font-medium">
                      <Icon className="h-3 w-3" />
                      {meta.title}
                    </div>
                    {items.map((item) => {
                      const idx = globalIdx++;
                      const isActive = idx === activeIdx;
                      return (
                        <button
                          key={item.id}
                          className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                            isActive
                              ? "bg-[#3737CC]/20 text-foreground"
                              : "text-foreground/80 hover:bg-[#3737CC]/10"
                          }`}
                          onClick={item.action}
                          onMouseEnter={() => setActiveIdx(idx)}
                        >
                          <span className="truncate">{item.label}</span>
                          {item.sublabel && (
                            <span className="text-xs text-muted-foreground/50 ml-2 shrink-0">
                              {item.sublabel}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          )}

          {/* 无结果 */}
          {query.trim() && results.length === 0 && (
            <div className="mt-3 text-center text-xs text-muted-foreground/50 py-4">
              无匹配结果
            </div>
          )}

          {/* 底部提示 */}
          <div className="mt-3 text-xs text-muted-foreground text-center">
            <kbd className="px-1.5 py-0.5 bg-white/[0.06] border border-white/[0.1] rounded text-[10px]">
              &#8984;K
            </kbd>{" "}
            打开搜索 ·{" "}
            <kbd className="px-1.5 py-0.5 bg-white/[0.06] border border-white/[0.1] rounded text-[10px]">
              ↑↓
            </kbd>{" "}
            导航 ·{" "}
            <kbd className="px-1.5 py-0.5 bg-white/[0.06] border border-white/[0.1] rounded text-[10px]">
              Enter
            </kbd>{" "}
            确认 ·{" "}
            <kbd className="px-1.5 py-0.5 bg-white/[0.06] border border-white/[0.1] rounded text-[10px]">
              Esc
            </kbd>{" "}
            关闭
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
