/**
 * Input: GET /api/agent_pending_approvals 轮询结果
 * Output: 待确认 ApprovalCard 列表 + 提交审批
 * Pos: components/agent/pending-approvals.tsx — P0-5 HITL 确认面容器
 * 一旦我被修改，请更新头部注释与所属文件夹 md。
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { ApprovalCard, type ApprovalItem } from "@/components/agent/approval-card";

interface PendingApiItem {
  task_id: string;
  decision?: Record<string, unknown> | null;
  risk_level?: string;
  created_at?: string | null;
  reason?: string;
  action_type?: string;
  confidence?: number | null;
  /** 后端 timeout_seconds；timeout 为兼容 alias */
  timeout_seconds?: number;
  timeout?: number;
  status?: string;
}

function toTimeoutAt(createdAt: string | null | undefined, timeoutSec: number): string {
  const base = createdAt ? Date.parse(createdAt) : Date.now();
  const ms = Number.isFinite(base) ? base : Date.now();
  return new Date(ms + Math.max(1, timeoutSec) * 1000).toISOString();
}

function mapPending(raw: PendingApiItem): ApprovalItem {
  const timeoutSec = Number(raw.timeout_seconds ?? raw.timeout ?? 300) || 300;
  const decision = (raw.decision || {}) as Record<string, unknown>;
  const action =
    (typeof raw.action_type === "string" && raw.action_type) ||
    (typeof decision.action === "string" && decision.action) ||
    (typeof decision.recommendation === "string" && decision.recommendation) ||
    undefined;
  return {
    task_id: raw.task_id,
    risk_level: raw.risk_level || "high",
    reason: raw.reason || "",
    action_type: action,
    confidence: typeof raw.confidence === "number" ? raw.confidence : undefined,
    timeout_at: toTimeoutAt(raw.created_at, timeoutSec),
  };
}

export function PendingApprovalsPanel() {
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/agent_pending_approvals", {
        credentials: "include",
      });
      if (!res.ok) {
        setError(`加载失败 HTTP ${res.status}`);
        return;
      }
      const data = await res.json();
      const list = Array.isArray(data?.approvals) ? data.approvals : [];
      setItems(list.map((x: PendingApiItem) => mapPending(x)));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "网络错误");
    }
  }, []);

  useEffect(() => {
    load();
    const id = window.setInterval(load, 3000);
    return () => window.clearInterval(id);
  }, [load]);

  const submit = async (taskId: string, approved: boolean, feedback: string) => {
    setSubmitting(taskId);
    try {
      const res = await fetch("/api/agent_submit_approval", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: taskId,
          approved,
          feedback,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(
          typeof body?.error === "string"
            ? body.error
            : typeof body?.message === "string"
              ? body.message
              : `提交失败 HTTP ${res.status}`,
        );
        return;
      }
      setItems((prev) => prev.filter((x) => x.task_id !== taskId));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交失败");
    } finally {
      setSubmitting(null);
    }
  };

  if (items.length === 0 && !error) return null;

  return (
    <div className="space-y-2 px-2 py-2 border-b border-border/40" data-testid="hitl-pending-panel">
      <div className="text-[11px] font-medium text-muted-foreground px-1">
        待确认决策（HITL）
      </div>
      {error && (
        <div className="text-[11px] text-destructive px-1" role="alert">
          {error}
        </div>
      )}
      {items.map((item) => (
        <ApprovalCard
          key={item.task_id}
          item={item}
          busy={submitting === item.task_id}
          onApprove={(feedback) => submit(item.task_id, true, feedback)}
          onReject={(feedback) => submit(item.task_id, false, feedback)}
        />
      ))}
    </div>
  );
}
