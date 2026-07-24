/**
 * Input: approval sticky 匹配纯函数
 * Output: proposal_id > approval_id > task_id 优先级 + 跨字段防误命中
 * Pos: tests/frontend/components — 对应 approval-card / pending-approvals sticky 同步
 */
import { describe, expect, it } from "vitest";
import {
  matchStickyItem,
  matchesWriteProposalEvent,
  stickyIdsFromWriteProposalEvent,
  type PendingApproval,
} from "@/components/agent/approval-card";
import type { AgentEvent } from "@/lib/stores/agent-store";

function item(partial: Partial<PendingApproval> & { task_id: string }): PendingApproval {
  return {
    kind: "portfolio_write_proposal",
    status: "pending",
    ...partial,
  };
}

function wpEvent(meta: Record<string, unknown>): AgentEvent {
  return {
    id: "e1",
    type: "write_proposal",
    label: "write",
    status: "running",
    ts: Date.now(),
    meta,
  };
}

describe("sticky match priority: proposal_id > approval_id > task_id", () => {
  const pool: PendingApproval[] = [
    item({
      task_id: "task_A",
      approval_id: "appr_A",
      proposal_id: "prop_A",
    }),
    item({
      task_id: "task_B",
      approval_id: "appr_B",
      proposal_id: "prop_B",
    }),
    // task_id 与另一卡 approval_id 故意同名，验证不会跨字段误命中
    item({
      task_id: "appr_A",
      approval_id: "appr_C",
      proposal_id: "prop_C",
    }),
  ];

  it("优先按 proposal_id 命中", () => {
    const hit = matchStickyItem({ proposal_id: "prop_B", approval_id: "appr_A", task_id: "task_A" }, pool);
    expect(hit?.proposal_id).toBe("prop_B");
    expect(hit?.task_id).toBe("task_B");
  });

  it("无 proposal 时按 approval_id 命中", () => {
    const hit = matchStickyItem({ proposal_id: "", approval_id: "appr_B", task_id: "task_A" }, pool);
    expect(hit?.approval_id).toBe("appr_B");
    expect(hit?.proposal_id).toBe("prop_B");
  });

  it("仅 task_id 时命中对应卡", () => {
    const hit = matchStickyItem({ task_id: "task_B" }, pool);
    expect(hit?.task_id).toBe("task_B");
  });

  it("禁止 event.proposal_id 跨字段命中 item.approval_id", () => {
    // event.proposal_id = appr_A 不应命中 item.approval_id=appr_A
    const hit = matchStickyItem({ proposal_id: "appr_A" }, pool);
    expect(hit).toBeNull();
  });

  it("matchesWriteProposalEvent: proposal_id 字段对字段", () => {
    const approval = item({
      task_id: "task_X",
      approval_id: "appr_X",
      proposal_id: "prop_X",
    });
    expect(
      matchesWriteProposalEvent(
        wpEvent({ proposal_id: "prop_X", status: "approved" }),
        approval,
      ),
    ).toBe(true);
    // 跨字段：event.proposal_id 等于 approval.approval_id → 不匹配
    expect(
      matchesWriteProposalEvent(
        wpEvent({ proposal_id: "appr_X", status: "approved" }),
        approval,
      ),
    ).toBe(false);
  });

  it("matchesWriteProposalEvent: approval_id 次优先", () => {
    const approval = item({
      task_id: "task_Y",
      approval_id: "appr_Y",
      proposal_id: "prop_Y",
    });
    expect(
      matchesWriteProposalEvent(
        wpEvent({ approval_id: "appr_Y", status: "applied_local" }),
        approval,
      ),
    ).toBe(true);
  });

  it("matchesWriteProposalEvent: task_id 仅终态", () => {
    const approval = item({
      task_id: "task_Z",
      approval_id: "appr_Z",
      proposal_id: "prop_Z",
    });
    expect(
      matchesWriteProposalEvent(wpEvent({ task_id: "task_Z", status: "pending" }), approval),
    ).toBe(false);
    expect(
      matchesWriteProposalEvent(wpEvent({ task_id: "task_Z", status: "rejected" }), approval),
    ).toBe(true);
  });

  it("stickyIdsFromWriteProposalEvent 抽取 meta", () => {
    const ids = stickyIdsFromWriteProposalEvent(
      wpEvent({ proposal_id: "p1", approval_id: "a1", task_id: "t1", status: "approved" }),
    );
    expect(ids).toEqual({ proposal_id: "p1", approval_id: "a1", task_id: "t1" });
  });

  it("多卡并发：proposal 命中不误绑同 task 前缀卡", () => {
    const concurrent = [
      item({ task_id: "t1", approval_id: "appr_1", proposal_id: "prop_1" }),
      item({ task_id: "t1-other", approval_id: "appr_2", proposal_id: "prop_2" }),
    ];
    const hit = matchStickyItem(
      { proposal_id: "prop_2", approval_id: "appr_1", task_id: "t1" },
      concurrent,
    );
    expect(hit?.proposal_id).toBe("prop_2");
  });
});
