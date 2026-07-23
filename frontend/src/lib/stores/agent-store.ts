/**
 * Input: SSE流中的Agent进度、工具调用、降级与辩论事件
 * Output: Agent分析状态（进度、工具调用链、辩论轮次、降级列表、整体进度）
 * Pos: lib/stores/agent-store.ts - Agent分析过程状态管理
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

import { create } from 'zustand';
import type { AgentProgress, ToolCallStart, ToolCallResult, DebateTurn } from '@/lib/types';

// 实时数据流事件 — 用于AgentProgressPanel时间线视图
export type AgentEventType =
  | 'agent_started'
  | 'agent_progress'
  | 'agent_completed'
  | 'tool_call_start'
  | 'tool_call_result'
  | 'reasoning'
  | 'debate_turn'
  | 'degraded'
  | 'done'
  | 'error';

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
  events: AgentEvent[];
  overallProgress: number;
  isAnalyzing: boolean;

  setAgentProgress: (progress: AgentProgress) => void;
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
  events: [],
  overallProgress: 0,
  isAnalyzing: false,

  setAgentProgress: (progress) =>
    set((s) => {
      const existing = s.agentProgresses.findIndex(
        (a) => a.agent_name === progress.agent_name
      );
      const updated = [...s.agentProgresses];
      if (existing >= 0) updated[existing] = progress;
      else updated.push(progress);
      return { agentProgresses: updated, overallProgress: progress.progress };
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
      const full: AgentEvent = {
        id: ev.id ?? nextId(),
        ts: ev.ts ?? Date.now(),
        type: ev.type,
        agent: ev.agent,
        title: ev.title,
        detail: ev.detail,
        meta: ev.meta,
      };
      const next =
        s.events.length >= MAX_EVENTS
          ? [...s.events.slice(s.events.length - MAX_EVENTS + 1), full]
          : [...s.events, full];
      return { events: next };
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
      events: [],
      overallProgress: 0,
      isAnalyzing: false,
    }),
}));

// 调试：暴露store到window，便于playwright/e2e/DevTools直接读取
if (typeof window !== 'undefined') {
  (window as unknown as { __agentStore?: typeof useAgentStore }).__agentStore = useAgentStore;
}
