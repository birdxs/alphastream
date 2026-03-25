/**
 * Input: SSE流中的Agent进度和工具调用事件
 * Output: Agent分析状态（进度、工具调用链、整体进度）
 * Pos: lib/stores/agent-store.ts - Agent分析过程状态管理
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

import { create } from 'zustand';
import type { AgentProgress, ToolCallStart, ToolCallResult } from '@/lib/types';

interface AgentState {
  agentProgresses: AgentProgress[];
  toolCalls: Array<ToolCallStart & { result?: ToolCallResult }>;
  overallProgress: number;
  isAnalyzing: boolean;

  setAgentProgress: (progress: AgentProgress) => void;
  addToolCall: (tc: ToolCallStart) => void;
  setToolCallResult: (id: string, result: ToolCallResult) => void;
  setOverallProgress: (p: number) => void;
  setAnalyzing: (analyzing: boolean) => void;
  reset: () => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  agentProgresses: [],
  toolCalls: [],
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
  setOverallProgress: (p) => set({ overallProgress: p }),
  setAnalyzing: (analyzing) => set({ isAnalyzing: analyzing }),
  reset: () =>
    set({
      agentProgresses: [],
      toolCalls: [],
      overallProgress: 0,
      isAnalyzing: false,
    }),
}));
