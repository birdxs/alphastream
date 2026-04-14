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
  addToolCall: (tc) => set((s) => ({ toolCalls: [...s.toolCalls, tc] })),
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
