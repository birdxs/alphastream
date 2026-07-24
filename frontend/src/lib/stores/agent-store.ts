/**
 * Input: SSE流中的Agent进度、工具调用、降级与辩论事件
 * Output: Agent分析状态（进度、工具调用链、辩论轮次、降级列表、整体进度）
 * Pos: lib/stores/agent-store.ts - Agent分析过程状态管理
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

import { create } from 'zustand';
import type { AgentProgress, ToolCallStart, ToolCallResult, DebateTurn, RunTerminalStatus, ProvenanceEntry } from "@/lib/types";

/** G2: 后端 task/run_terminal 与侧栏 status 映射 */
const TASK_STATUS_ALIASES: Record<string, RunTerminalStatus | string> = {
  done: "completed",
  success: "completed",
  error: "failed",
  fail: "failed",
  canceled: "cancelled",
  cancelled: "cancelled",
  timeout: "timeout_reject",
  timeout_reject: "timeout_reject",
  awaiting: "awaiting_approval",
  awaiting_approval: "awaiting_approval",
  pending_approval: "awaiting_approval",
  rejected: "rejected",
  approved: "approved",
  pending: "pending",
  running: "running",
  completed: "completed",
  failed: "failed",
};

export function normalizeTaskStatus(status?: string | null): string {
  if (!status) return "pending";
  const s = String(status).trim().toLowerCase();
  return TASK_STATUS_ALIASES[s] || s;
}

export function computeRunTerminal(
  taskStatus?: string | null,
  approvalStatus?: string | null,
): string {
  const ts = normalizeTaskStatus(taskStatus);
  const appr = (approvalStatus || "").trim().toLowerCase();
  if (appr === "pending" || appr === "awaiting_approval" || ts === "awaiting_approval") {
    return "awaiting_approval";
  }
  if (appr === "timeout_reject" || ts === "timeout_reject") return "timeout_reject";
  if (appr === "rejected" || ts === "rejected") return "rejected";
  if (appr === "approved" && ts === "running") return "running";
  if (appr === "approved" && ts === "completed") return "completed";
  if (["completed", "failed", "cancelled", "timeout_reject", "rejected", "approved"].includes(ts)) {
    return ts;
  }
  if (ts === "running") return "running";
  return "pending";
}

/** G3 事件去重：role_started ↔ agent.started 等 */
export function canonicalAgentEventName(eventType?: string | null): string {
  const et = (eventType || "").trim();
  const map: Record<string, string> = {
    "agent.role_started": "agent.started",
    "agent.role_finished": "agent.completed",
    agent_role_started: "agent.started",
    agent_role_finished: "agent.completed",
    role_started: "agent.started",
    role_finished: "agent.completed",
    agent_started: "agent.started",
    agent_completed: "agent.completed",
    "agent.started": "agent.started",
    "agent.completed": "agent.completed",
    // Plan / write_proposal 别名归一（时间线去重）
    plan_created: "plan.created",
    "plan.created": "plan.created",
    plan_step: "plan.step",
    "plan.step": "plan.step",
    "write-proposal": "write_proposal",
    write_proposal: "write_proposal",
  };
  return map[et] || et;
}

export function agentEventDedupeKey(
  eventType: string | undefined | null,
  data: {
    agent_name?: string;
    agent?: string;
    role?: string;
    task_id?: string;
    conversation_id?: string;
    progress?: number | string;
    plan_id?: string;
    step_id?: string;
    proposal_id?: string;
    approval_id?: string;
    status?: string;
    id?: string;
  } = {},
): string {
  const canon = canonicalAgentEventName(eventType);
  const agent = data.agent_name || data.agent || data.role || "";
  const task =
    data.task_id ||
    data.plan_id ||
    data.proposal_id ||
    data.approval_id ||
    data.id ||
    data.conversation_id ||
    "";
  // write_proposal 生命周期：同 approval_id 会发 pending→approved/rejected→applied_local
  // 必须把 status 纳入 dedupe key，否则终态事件被 pending 吞掉
  if (canon === "write_proposal") {
    const st = String(data.status ?? "").trim().toLowerCase() || "pending";
    const appr = String(data.approval_id || data.task_id || "").trim();
    const prop = String(data.proposal_id || data.id || "").trim();
    return `write_proposal|${appr || prop || task}|${st}`;
  }
  const seq = data.step_id ?? data.progress ?? "";
  return `${canon}|${agent}|${task}|${seq}`;
}


// 实时数据流事件 — 用于AgentProgressPanel时间线视图
export type AgentEventType =
  | 'agent_started'
  | 'agent_progress'
  | 'agent_completed'
  // G3 bus aliases (canonicalized on append, but accepted as input)
  | 'agent.started'
  | 'agent.completed'
  | 'agent.role_started'
  | 'agent.role_finished'
  | 'role_started'
  | 'role_finished'
  | 'tool_call_start'
  | 'tool_call_result'
  | 'reasoning'
  | 'debate_turn'
  | 'degraded'
  | 'scorecard'
  | 'done'
  | 'error'
  | 'plan.created'
  | 'plan.step'
  | 'write_proposal'
  | string;

export interface AgentEvent {
  id: string;             // 唯一id（时间戳+随机）
  ts: number;             // 客户端时间戳ms
  type: AgentEventType;
  agent?: string;         // agent名（如有）
  title: string;          // 一句话摘要
  detail?: string;        // 完整内容（可展开）
  meta?: Record<string, unknown>; // 附加信息（tool params、duration、progress等）
}

/** P0-2 降级条目（零假值可视化） */
export interface DegradationItem {
  id: string;
  level: 'info' | 'warn' | 'critical' | string;
  cause: string;
  message: string;
  confidence_cap?: number;
  source?: string;
  task_id?: string;
  stock_code?: string;
  correlation_id?: string;
  ts: number;
}

interface AgentState {
  agentProgresses: AgentProgress[];
  toolCalls: Array<ToolCallStart & { result?: ToolCallResult; status?: string }>;
  /** P0-3 辩论轮次（bull/bear/summary） */
  debateTurns: DebateTurn[];
  /** P0-2 本 run 降级列表 */
  degradations: DegradationItem[];
  /** 本 run 最紧 confidence 上界；undefined=未封顶 */
  confidenceCap?: number;
  /** G6 Run scorecard */
  scorecard: {
    data_coverage?: number | null;
    tool_success_rate?: number | null;
    role_agreement?: number | null;
    confidence_cap?: number | null;
  } | null;
  /** G5 决策备忘 */
  decisionMemo: Record<string, unknown> | null;
  /** G7 反思只读摘要 */
  reflectionSummary: Record<string, unknown> | null;
  /** G8 Memory 预取 */
  memoryContext: Record<string, unknown> | null;
  events: AgentEvent[];
  /** G3 双发去重键集合（agent.role_* ↔ agent.started/completed） */
  seenEventKeys: string[];
  /** G2 任务 terminal 投影 */
  runTerminal?: string;
  taskStatus?: string;
  approvalStatus?: string;
  /** G1 聚合 provenance */
  provenance: ProvenanceEntry[];
  overallProgress: number;
  isAnalyzing: boolean;

  setAgentProgress: (progress: AgentProgress) => void;
  setScorecard: (sc: {
    data_coverage?: number | null;
    tool_success_rate?: number | null;
    role_agreement?: number | null;
    confidence_cap?: number | null;
  } | null) => void;
  setDecisionMemo: (m: Record<string, unknown> | null) => void;
  setReflectionSummary: (r: Record<string, unknown> | null) => void;
  setMemoryContext: (m: Record<string, unknown> | null) => void;
  setTaskTerminal: (taskStatus?: string | null, approvalStatus?: string | null) => void;
  mergeProvenance: (entries?: ProvenanceEntry[] | null) => void;
  addToolCall: (tc: ToolCallStart) => void;
  setToolCallResult: (id: string, result: ToolCallResult) => void;
  addDebateTurn: (turn: DebateTurn) => void;
  addDegradation: (item: Omit<DegradationItem, 'id' | 'ts'> & Partial<Pick<DegradationItem, 'id' | 'ts'>>) => void;
  appendEvent: (ev: Omit<AgentEvent, 'id' | 'ts'> & { id?: string; ts?: number }) => void;
  /**
   * [UI-Q4] 流式 reasoning token 累积:
   *  - 若最后一条事件是同agent的reasoning且仍标记streaming, 则把token追加到其detail,
   *  - 否则新建一条 reasoning 事件, meta.streaming=true
   *  - 若 finalize=true, 则标记最后一条 reasoning 为完成(streaming=false), 不再追加
   */
  appendReasoningToken: (agent: string | undefined, token: string, finalize?: boolean) => void;
  setOverallProgress: (p: number) => void;
  setAnalyzing: (analyzing: boolean) => void;
  reset: () => void;
}

let _eid = 0;
function nextId() {
  _eid += 1;
  return `${Date.now()}_${_eid}`;
}

const MAX_EVENTS = 500; // 防内存膨胀，最多保留500条事件

export const useAgentStore = create<AgentState>((set) => ({
  agentProgresses: [],
  toolCalls: [],
  debateTurns: [],
  degradations: [],
  confidenceCap: undefined,
  scorecard: null,
  decisionMemo: null,
  reflectionSummary: null,
  memoryContext: null,
  events: [],
  seenEventKeys: [],
  provenance: [],
  overallProgress: 0,
  isAnalyzing: false,

  setAgentProgress: (progress) =>
    set((s) => {
      const normalized: AgentProgress = {
        ...progress,
        status: (normalizeTaskStatus(progress.status) as AgentProgress['status']) || progress.status,
      };
      // map completed/failed aliases for role bar
      if (progress.status === 'started' || progress.status === 'running') {
        normalized.status = progress.status === 'running' ? 'started' : progress.status;
      }
      const existing = s.agentProgresses.findIndex(
        (a) => a.agent_name === normalized.agent_name
      );
      const updated = [...s.agentProgresses];
      if (existing >= 0) updated[existing] = { ...updated[existing], ...normalized };
      else updated.push(normalized);
      return { agentProgresses: updated, overallProgress: normalized.progress };
    }),
  setScorecard: (sc) => set({ scorecard: sc }),
  setDecisionMemo: (m) => set({ decisionMemo: m }),
  setReflectionSummary: (r) => set({ reflectionSummary: r }),
  setMemoryContext: (m) => set({ memoryContext: m }),
  setTaskTerminal: (taskStatus, approvalStatus) =>
    set((s) => {
      const ts = taskStatus ?? s.taskStatus;
      const ap = approvalStatus ?? s.approvalStatus;
      return {
        taskStatus: ts ? normalizeTaskStatus(ts) : s.taskStatus,
        approvalStatus: ap ?? s.approvalStatus,
        runTerminal: computeRunTerminal(ts, ap),
      };
    }),
  mergeProvenance: (entries) =>
    set((s) => {
      if (!entries || !entries.length) return {};
      const seen = new Set(
        s.provenance.map((e) => `${e.source||''}|${e.tool||''}|${e.digest||''}`),
      );
      const next = [...s.provenance];
      for (const e of entries) {
        const k = `${e.source||''}|${e.tool||''}|${e.digest||''}`;
        if (seen.has(k)) continue;
        seen.add(k);
        next.push(e);
      }
      return { provenance: next.slice(-64) };
    }),
  addToolCall: (tc) =>
    set((s) => {
      // P0-4：归一 name/tool_name
      const normalized: ToolCallStart & { status?: string } = {
        ...tc,
        name: tc.name || tc.tool_name,
        tool_name: tc.tool_name || tc.name || 'unknown',
        status: 'running',
      };
      const next = [...s.toolCalls, normalized];
      return {
        toolCalls: next.length > MAX_EVENTS ? next.slice(next.length - MAX_EVENTS) : next,
      };
    }),
  setToolCallResult: (id, result) =>
    set((s) => ({
      toolCalls: s.toolCalls.map((tc) =>
        tc.tool_call_id === id
          ? {
              ...tc,
              status: result.ok === false || result.error ? 'error' : 'done',
              result: {
                ...result,
                name: result.name || result.tool_name || tc.name || tc.tool_name,
                result_summary: result.result_summary ?? result.result,
              },
            }
          : tc
      ),
    })),
  addDebateTurn: (turn) =>
    set((s) => {
      // 同 side 覆盖（summary/bull/bear 各一条最新）
      const without = s.debateTurns.filter((t) => t.side !== turn.side);
      return { debateTurns: [...without, turn] };
    }),
  addDegradation: (item) =>
    set((s) => {
      const full: DegradationItem = {
        id: item.id ?? nextId(),
        ts: item.ts ?? Date.now(),
        level: item.level || 'warn',
        cause: item.cause || 'tool_failure',
        message: item.message || '数据源降级，未使用假行情填补。',
        confidence_cap: item.confidence_cap,
        source: item.source,
        task_id: item.task_id,
        stock_code: item.stock_code,
        correlation_id: item.correlation_id,
      };
      // 去重：同 cause+source+message 短窗内不重复堆叠
      const dup = s.degradations.some(
        (d) =>
          d.cause === full.cause &&
          d.source === full.source &&
          d.message === full.message &&
          Math.abs(d.ts - full.ts) < 3000,
      );
      if (dup) return {};
      let nextCap = s.confidenceCap;
      if (typeof full.confidence_cap === 'number' && !Number.isNaN(full.confidence_cap)) {
        nextCap =
          nextCap == null
            ? full.confidence_cap
            : Math.min(nextCap, Math.max(0, Math.min(1, full.confidence_cap)));
      }
      const next =
        s.degradations.length >= 32
          ? [...s.degradations.slice(s.degradations.length - 31), full]
          : [...s.degradations, full];
      return { degradations: next, confidenceCap: nextCap };
    }),
  appendEvent: (ev) =>
    set((s) => {
      // G3: role_started/finished 与 agent.started/completed 双发不双计
      // write_proposal：status/approval_id/proposal_id 必须参与 dedupe（终态可追加）
      const meta = (ev.meta || {}) as {
        progress?: number;
        task_id?: string;
        approval_id?: string;
        proposal_id?: string;
        status?: string;
        id?: string;
        plan_id?: string;
        step_id?: string;
      };
      const dedupeKey = agentEventDedupeKey(ev.type, {
        agent_name: ev.agent,
        agent: ev.agent,
        progress: meta.progress,
        task_id: meta.task_id,
        approval_id: meta.approval_id,
        proposal_id: meta.proposal_id,
        status: meta.status,
        id: meta.id,
        plan_id: meta.plan_id,
        step_id: meta.step_id,
      });
      if (dedupeKey && s.seenEventKeys.includes(dedupeKey)) {
        return {};
      }
      const full: AgentEvent = {
        id: ev.id ?? nextId(),
        ts: ev.ts ?? Date.now(),
        type: (canonicalAgentEventName(ev.type) || ev.type) as AgentEventType,
        agent: ev.agent,
        title: ev.title,
        detail: ev.detail,
        meta: { ...(ev.meta || {}), dedupe_key: dedupeKey, raw_type: ev.type },
      };
      const next =
        s.events.length >= MAX_EVENTS
          ? [...s.events.slice(s.events.length - MAX_EVENTS + 1), full]
          : [...s.events, full];
      const keys = [...s.seenEventKeys, dedupeKey].slice(-MAX_EVENTS);
      return { events: next, seenEventKeys: keys };
    }),
  appendReasoningToken: (agent, token, finalize = false) =>
    set((s) => {
      const events = s.events;
      const lastIdx = events.length - 1;
      const last = lastIdx >= 0 ? events[lastIdx] : undefined;
      const lastStreaming = !!(last?.meta && (last.meta as { streaming?: boolean }).streaming);
      // 最后一条是同agent的流式reasoning → 追加
      if (last && last.type === 'reasoning' && last.agent === agent && lastStreaming) {
        const nextDetail = (last.detail || '') + token;
        const nextMeta = { ...(last.meta || {}), streaming: !finalize };
        const updated: AgentEvent = { ...last, detail: nextDetail, meta: nextMeta };
        const nextEvents = [...events.slice(0, lastIdx), updated];
        return { events: nextEvents };
      }
      // finalize 但最后一条不是 streaming reasoning → 忽略
      if (finalize) return {};
      // 否则新建一条流式 reasoning
      const full: AgentEvent = {
        id: nextId(),
        ts: Date.now(),
        type: 'reasoning',
        agent,
        title: `${agent || '推理'} 思考`,
        detail: token,
        meta: { streaming: true },
      };
      const next =
        events.length >= MAX_EVENTS
          ? [...events.slice(events.length - MAX_EVENTS + 1), full]
          : [...events, full];
      return { events: next };
    }),
  setOverallProgress: (p) => set({ overallProgress: p }),
  setAnalyzing: (analyzing) => set({ isAnalyzing: analyzing }),
  reset: () =>
    set({
      agentProgresses: [],
      toolCalls: [],
      debateTurns: [],
      degradations: [],
      confidenceCap: undefined,
      scorecard: null,
      decisionMemo: null,
      reflectionSummary: null,
      memoryContext: null,
      events: [],
      seenEventKeys: [],
      provenance: [],
      runTerminal: undefined,
      taskStatus: undefined,
      approvalStatus: undefined,
      overallProgress: 0,
      isAnalyzing: false,
    }),
}));

// 调试：暴露store到window，便于playwright/e2e/DevTools直接读取
if (typeof window !== 'undefined') {
  (window as unknown as { __agentStore?: typeof useAgentStore }).__agentStore = useAgentStore;
}
