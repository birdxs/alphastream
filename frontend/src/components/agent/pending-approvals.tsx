/**
 * Input: GET /api/agent_pending_approvals 轮询结果
 * Output: 待确认 ApprovalCard 列表 + 提交审批
 * Pos: components/agent/pending-approvals.tsx — P0-5 HITL 确认面容器
 * 一旦我被修改，请更新头部注释与所属文件夹 md。
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApprovalCard,
  type PendingApproval,
} from "@/components/agent/approval-card";

export function PendingApprovalsPanel() {
  const [items, setItems] = useState<PendingApproval[]>([]);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
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
      setItems(
        list.map((raw: PendingApproval) => ({
          task_id: raw.task_id,
          decision: raw.decision,
          risk_level: raw.risk_level || "high",
          created_at: raw.created_at,
          reason: raw.reason || "",
          action_type: raw.action_type,
          confidence: raw.confidence ?? null,
          timeout_seconds: raw.timeout_seconds,
          status: raw.status,
        })),
      );
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

  const onResolved = async (taskId: string, approved: boolean) => {
    setSubmittingId(taskId);
    try {
      const res = await fetch("/api/agent_submit_approval", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: taskId,
          approved,
          feedback: "",
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
      setSubmittingId(null);
    }
  };

  if (items.length === 0 && !error) return null;

  return (
    <div
      className="space-y-2 px-2 py-2 border-b border-border/40"
      data-testid="hitl-pending-panel"
    >
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
          approval={item}
          submitting={submittingId === item.task_id}
          onResolved={onResolved}
        />
      ))}
    </div>
  );
}
