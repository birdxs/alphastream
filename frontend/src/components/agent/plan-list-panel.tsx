/**
 * Input: 轮询 GET /api/agent_plans（status / conversation_id 过滤）返回的只读 plan 列表
 * Output: PlanDAG 列表 UI + status 芯片 + 可选 conversation 过滤，空态友好（无假数）
 * Pos: agent 侧栏只读展示；不抓数、不执行 step
 * 一旦被修改，请更新头部注释，以及所属文件夹的 md。
 */
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiClient, extractData } from "@/lib/api/client";
import { useChatStore } from "@/lib/stores/chat-store";
import { cn } from "@/lib/utils";
import { ListTree, RefreshCw } from "lucide-react";

export interface AnalysisPlanItem {
  plan_id: string;
  goal?: string;
  status?: string;
  stock_code?: string | null;
  conversation_id?: string | null;
  created_at?: string;
  updated_at?: string;
  steps?: Array<Record<string, unknown>>;
}

interface PlansApiBody {
  plans?: AnalysisPlanItem[];
  count?: number;
  limit?: number;
  conversation_id?: string | null;
  status?: string | null;
}

const POLL_MS = 8000;

/** status 过滤芯片（与 plan_dag STATUS_* 对齐） */
const STATUS_CHIPS: Array<{ id: string; label: string }> = [
  { id: "all", label: "全部" },
  { id: "pending", label: "待执行" },
  { id: "running", label: "进行中" },
  { id: "waiting_hitl", label: "待审批" },
  { id: "completed", label: "已完成" },
  { id: "failed", label: "失败" },
  { id: "cancelled", label: "已取消" },
];

function asPlans(raw: unknown): AnalysisPlanItem[] {
  if (!raw || typeof raw !== "object") return [];
  const body = raw as PlansApiBody & { data?: PlansApiBody };
  const list = Array.isArray(body.plans)
    ? body.plans
    : Array.isArray(body.data?.plans)
      ? body.data!.plans!
      : [];
  return list
    .filter(
      (p): p is AnalysisPlanItem =>
        !!p && typeof p === "object" && typeof p.plan_id === "string",
    )
    .map((p) => ({
      plan_id: p.plan_id,
      goal: typeof p.goal === "string" ? p.goal : "",
      status: typeof p.status === "string" ? p.status : "unknown",
      stock_code:
        typeof p.stock_code === "string" && p.stock_code.trim()
          ? p.stock_code.trim()
          : null,
      conversation_id:
        typeof p.conversation_id === "string" && p.conversation_id.trim()
          ? p.conversation_id.trim()
          : null,
      created_at: typeof p.created_at === "string" ? p.created_at : undefined,
      updated_at: typeof p.updated_at === "string" ? p.updated_at : undefined,
      steps: Array.isArray(p.steps) ? p.steps : undefined,
    }));
}

function buildPlansQuery(params: {
  limit?: number;
  status?: string;
  conversationId?: string | null;
  scopeCurrentOnly?: boolean;
}): string {
  const q = new URLSearchParams();
  q.set("limit", String(params.limit ?? 20));
  if (params.status && params.status !== "all") {
    q.set("status", params.status);
  }
  if (params.scopeCurrentOnly && params.conversationId) {
    q.set("conversation_id", params.conversationId);
  }
  return `/api/agent_plans?${q.toString()}`;
}

export function PlanListPanel({ className }: { className?: string }) {
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const [plans, setPlans] = useState<AnalysisPlanItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  /** 可选：仅显示当前 conversation 的 plan（读 query conversation_id） */
  const [scopeCurrentOnly, setScopeCurrentOnly] = useState(false);
  const mounted = useRef(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const queryPath = useMemo(
    () =>
      buildPlansQuery({
        limit: 20,
        status: statusFilter,
        conversationId: activeConversationId,
        scopeCurrentOnly,
      }),
    [statusFilter, activeConversationId, scopeCurrentOnly],
  );

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        const raw = await apiClient.get<unknown>(queryPath);
        if (!mounted.current) return;
        const data = extractData<PlansApiBody>(raw) ?? (raw as PlansApiBody);
        setPlans(asPlans({ ...(typeof raw === "object" && raw ? raw : {}), data }));
        setError(null);
      } catch (e) {
        if (!mounted.current) return;
        setError(e instanceof Error ? e.message : "计划列表不可用");
      } finally {
        if (mounted.current && !silent) setLoading(false);
      }
    },
    [queryPath],
  );

  useEffect(() => {
    mounted.current = true;
    void load(false);
    const tick = () => {
      timerRef.current = setTimeout(() => {
        void load(true).finally(() => {
          if (mounted.current) tick();
        });
      }, POLL_MS);
    };
    tick();
    return () => {
      mounted.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [load]);

  const emptyHint = useMemo(() => {
    const parts: string[] = [];
    if (statusFilter !== "all") {
      const chip = STATUS_CHIPS.find((c) => c.id === statusFilter);
      parts.push(`状态「${chip?.label || statusFilter}」`);
    }
    if (scopeCurrentOnly) {
      parts.push(
        activeConversationId
          ? `当前会话 ${activeConversationId.slice(0, 8)}…`
          : "当前会话（未选择）",
      );
    }
    if (parts.length === 0) {
      return "暂无计划。可通过 Agent 工具 create_analysis_plan / list_analysis_plans 查看。";
    }
    return `当前筛选（${parts.join(" · ")}）下暂无计划。可切换芯片或关闭会话过滤。`;
  }, [statusFilter, scopeCurrentOnly, activeConversationId]);

  return (
    <div
      className={cn(
        "rounded-lg border border-border/60 bg-card/40 p-2 space-y-2",
        className,
      )}
      data-testid="plan-list-panel"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <ListTree className="h-3.5 w-3.5 text-muted-foreground" />
          分析计划
          <span className="text-[10px] font-normal normal-case tracking-normal text-muted-foreground">
            只读 · 不执行
          </span>
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
          onClick={() => void load(false)}
          aria-label="刷新计划列表"
        >
          <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} />
          刷新
        </button>
      </div>

      {/* status 过滤芯片 */}
      <div
        className="flex flex-wrap gap-1"
        role="tablist"
        aria-label="计划状态过滤"
        data-testid="plan-status-chips"
      >
        {STATUS_CHIPS.map((chip) => {
          const active = statusFilter === chip.id;
          return (
            <button
              key={chip.id}
              type="button"
              role="tab"
              aria-selected={active}
              data-status-chip={chip.id}
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] border transition-colors",
                active
                  ? "border-primary/50 bg-primary/10 text-foreground"
                  : "border-border/50 bg-background/40 text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setStatusFilter(chip.id)}
            >
              {chip.label}
            </button>
          );
        })}
      </div>

      {/* 可选 conversation 过滤 */}
      <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground cursor-pointer select-none">
        <input
          type="checkbox"
          className="h-3 w-3 rounded border-border"
          checked={scopeCurrentOnly}
          onChange={(e) => setScopeCurrentOnly(e.target.checked)}
          data-testid="plan-conversation-filter"
        />
        <span>
          仅当前会话
          {scopeCurrentOnly && !activeConversationId ? (
            <span className="ml-1 text-amber-600/90 dark:text-amber-400/90">
              （尚未选择会话）
            </span>
          ) : null}
        </span>
      </label>

      {loading && plans.length === 0 ? (
        <p className="text-[11px] text-muted-foreground px-1">加载中…</p>
      ) : null}

      {!loading && error && plans.length === 0 ? (
        <p className="text-[11px] text-muted-foreground px-1" data-testid="plan-list-empty-error">
          暂无计划（{error}）。工具 list_analysis_plans 创建后会出现在此。
        </p>
      ) : null}

      {!loading && !error && plans.length === 0 ? (
        <p className="text-[11px] text-muted-foreground px-1" data-testid="plan-list-empty">
          {emptyHint}
        </p>
      ) : null}

      {plans.length > 0 ? (
        <ul className="space-y-1.5 max-h-40 overflow-y-auto">
          {plans.map((p) => {
            const stepCount = Array.isArray(p.steps) ? p.steps.length : 0;
            return (
              <li
                key={p.plan_id}
                className="rounded-md border border-border/40 bg-background/50 px-2 py-1.5 text-[11px]"
                data-plan-id={p.plan_id}
                data-plan-status={p.status || "unknown"}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[10px] text-muted-foreground truncate">
                    {p.plan_id}
                  </span>
                  <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px]">
                    {p.status || "—"}
                  </span>
                </div>
                <div className="mt-0.5 text-foreground/90 line-clamp-2">
                  {p.goal?.trim() ? p.goal : "（无目标文案）"}
                </div>
                <div className="mt-0.5 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                  {p.stock_code ? <span>标的 {p.stock_code}</span> : <span>标的 —</span>}
                  {stepCount > 0 ? <span>{stepCount} 步</span> : null}
                  {p.conversation_id ? (
                    <span className="font-mono truncate max-w-[8rem]" title={p.conversation_id}>
                      conv {p.conversation_id.slice(0, 8)}…
                    </span>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
