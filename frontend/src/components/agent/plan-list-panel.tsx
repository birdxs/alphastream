/**
 * Input: 轮询 GET /api/agent_plans 返回的只读 plan 列表
 * Output: 精简 PlanDAG 列表 UI（plan_id/goal/status/stock_code，无假数）
 * Pos: agent 侧栏只读展示；不抓数、不执行 step
 * 一旦被修改，请更新头部注释，以及所属文件夹的 md。
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, extractData } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { ListTree, RefreshCw } from "lucide-react";

export interface AnalysisPlanItem {
  plan_id: string;
  goal?: string;
  status?: string;
  stock_code?: string | null;
  created_at?: string;
  updated_at?: string;
  steps?: Array<Record<string, unknown>>;
}

interface PlansApiBody {
  plans?: AnalysisPlanItem[];
  count?: number;
  limit?: number;
}

const POLL_MS = 8000;

function asPlans(raw: unknown): AnalysisPlanItem[] {
  if (!raw || typeof raw !== "object") return [];
  const body = raw as PlansApiBody & { data?: PlansApiBody };
  const list = Array.isArray(body.plans)
    ? body.plans
    : Array.isArray(body.data?.plans)
      ? body.data!.plans!
      : [];
  return list
    .filter((p): p is AnalysisPlanItem => !!p && typeof p === "object" && typeof p.plan_id === "string")
    .map((p) => ({
      plan_id: p.plan_id,
      goal: typeof p.goal === "string" ? p.goal : "",
      status: typeof p.status === "string" ? p.status : "unknown",
      stock_code:
        typeof p.stock_code === "string" && p.stock_code.trim()
          ? p.stock_code.trim()
          : null,
      created_at: typeof p.created_at === "string" ? p.created_at : undefined,
      updated_at: typeof p.updated_at === "string" ? p.updated_at : undefined,
      steps: Array.isArray(p.steps) ? p.steps : undefined,
    }));
}

export function PlanListPanel({ className }: { className?: string }) {
  const [plans, setPlans] = useState<AnalysisPlanItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const raw = await apiClient.get<unknown>("/api/agent_plans?limit=20");
      if (!mounted.current) return;
      const data = extractData<PlansApiBody>(raw) ?? (raw as PlansApiBody);
      setPlans(asPlans({ ...(typeof raw === "object" && raw ? raw : {}), data }));
      setError(null);
    } catch (e) {
      if (!mounted.current) return;
      // 空列表时仅静默占位，网络失败才提示
      setError(e instanceof Error ? e.message : "计划列表不可用");
    } finally {
      if (mounted.current && !silent) setLoading(false);
    }
  }, []);

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

  return (
    <div
      className={cn(
        "rounded-lg border border-border/60 bg-card/40 p-2 space-y-2",
        className,
      )}
      data-testid="plan-list-panel"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-xs font-medium text-foreground">
          <ListTree className="h-3.5 w-3.5 text-muted-foreground" />
          分析计划
          <span className="text-[10px] font-normal text-muted-foreground">
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

      {loading && plans.length === 0 ? (
        <p className="text-[11px] text-muted-foreground px-1">加载中…</p>
      ) : null}

      {!loading && error && plans.length === 0 ? (
        <p className="text-[11px] text-muted-foreground px-1">
          暂无计划（{error}）。工具 list_analysis_plans 创建后会出现在此。
        </p>
      ) : null}

      {!loading && !error && plans.length === 0 ? (
        <p className="text-[11px] text-muted-foreground px-1">
          暂无计划。可通过 Agent 工具 create_analysis_plan / list_analysis_plans 查看。
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
                <div className="mt-0.5 flex gap-2 text-[10px] text-muted-foreground">
                  {p.stock_code ? <span>标的 {p.stock_code}</span> : <span>标的 —</span>}
                  {stepCount > 0 ? <span>{stepCount} 步</span> : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
