/**
 * Input: SSE流中的Agent进度和工具调用事件
 * Output: Agent分析状态（进度、工具调用链、整体进度）
 * Pos: lib/stores/agent-store.ts - Agent分析过程状态管理
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

import { create } from 'zustand';
import type { AgentProgress, ToolCallStart, ToolCallResult } from '@/lib/types';

// 实时数据流事件 — 用于AgentProgressPanel时间线视图
export type AgentEventType =
  | 'agent_started'
  | 'agent_progress'
  | 'agent_completed'
  | 'tool_call_start'
  | 'tool_call_result'
  | 'reasoning';

export interface AgentEvent {
  id: string;             // 唯一id（时间戳+随机）
  ts: number;             // 客户端时间戳ms
  type: AgentEventType;
  agent?: string;         // agent名（如有）
  title: string;          // 一句话摘要
  detail?: string;        // 完整内容（可展开）
  meta?: Record<string, unknown>; // 附加信息（tool params、duration、progress等）
}

interface AgentState {
  agentProgresses: AgentProgress[];
  toolCalls: Array<ToolCallStart & { result?: ToolCallResult }>;
  events: AgentEvent[];
  overallProgress: number;
  isAnalyzing: boolean;

  setAgentProgress: (progress: AgentProgress) => void;
  addToolCall: (tc: ToolCallStart) => void;
  setToolCallResult: (id: string, result: ToolCallResult) => void;
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
  addToolCall: (tc) => set((s) => {
    const next = [...s.toolCalls, tc];
    return { toolCalls: next.length > MAX_EVENTS ? next.slice(next.length - MAX_EVENTS) : next };
  }),
  setToolCallResult: (id, result) =>
    set((s) => ({
      toolCalls: s.toolCalls.map((tc) =>
        tc.tool_call_id === id ? { ...tc, result } : tc
      ),
    })),
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
      const next = s.events.length >= MAX_EVENTS
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
      const next = events.length >= MAX_EVENTS
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
      events: [],
      overallProgress: 0,
      isAnalyzing: false,
    }),
}));

// 调试：暴露store到window，便于playwright/e2e/DevTools直接读取
if (typeof window !== 'undefined') {
  (window as unknown as { __agentStore?: typeof useAgentStore }).__agentStore = useAgentStore;
}
