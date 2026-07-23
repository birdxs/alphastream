// Input  : useAgentStore 的 actions（setAnalyzing/setAgentProgress/addToolCall/setToolCallResult/appendEvent/reset 等）
// Output : 测试结果（state shape、action 行为、滑动窗口 MAX_EVENTS=500）
// Pos    : tests/frontend/stores/agent-store.test.ts — FE-01 store 单测
//
// 一旦此文件修改，请同步更新 tests/audit/reports/FE-01_stores.md。

import { describe, it, expect, beforeEach } from 'vitest';
import { useAgentStore } from '@/lib/stores/agent-store';
import type { AgentProgress, ToolCallStart, ToolCallResult } from '@/lib/types';

function resetStore() {
  useAgentStore.getState().reset();
}

describe('useAgentStore', () => {
  beforeEach(() => {
    resetStore();
  });

  it('初始 state shape 正确', () => {
    const s = useAgentStore.getState();
    expect(s.agentProgresses).toEqual([]);
    expect(s.toolCalls).toEqual([]);
    expect(s.events).toEqual([]);
    expect(s.degradations).toEqual([]);
    expect(s.confidenceCap).toBeUndefined();
    expect(s.overallProgress).toBe(0);
    expect(s.isAnalyzing).toBe(false);
  });

  it('setAnalyzing / setOverallProgress 工作正常', () => {
    useAgentStore.getState().setAnalyzing(true);
    expect(useAgentStore.getState().isAnalyzing).toBe(true);

    useAgentStore.getState().setOverallProgress(42);
    expect(useAgentStore.getState().overallProgress).toBe(42);
  });

  it('setAgentProgress 新增和更新已存在 agent', () => {
    const p1: AgentProgress = {
      agent_name: 'fundamental',
      status: 'running',
      progress: 30,
      message: 'analyzing',
    } as AgentProgress;
    useAgentStore.getState().setAgentProgress(p1);
    expect(useAgentStore.getState().agentProgresses).toHaveLength(1);
    expect(useAgentStore.getState().overallProgress).toBe(30);

    // 同名 agent → 替换而非追加
    const p2: AgentProgress = {
      agent_name: 'fundamental',
      status: 'completed',
      progress: 100,
      message: 'done',
    } as AgentProgress;
    useAgentStore.getState().setAgentProgress(p2);
    expect(useAgentStore.getState().agentProgresses).toHaveLength(1);
    expect(useAgentStore.getState().agentProgresses[0].progress).toBe(100);
    expect(useAgentStore.getState().overallProgress).toBe(100);
  });

  it('addToolCall + setToolCallResult 正确关联', () => {
    const tc: ToolCallStart = {
      tool_call_id: 'tc-1',
      tool_name: 'get_quote',
      agent_name: 'fundamental',
      params: { symbol: 'AAPL' },
    } as ToolCallStart;
    useAgentStore.getState().addToolCall(tc);
    expect(useAgentStore.getState().toolCalls).toHaveLength(1);

    const result: ToolCallResult = {
      tool_call_id: 'tc-1',
      success: true,
      result: { price: 100 },
    } as ToolCallResult;
    useAgentStore.getState().setToolCallResult('tc-1', result);
    const stored = useAgentStore.getState().toolCalls[0];
    expect(stored.status).toBe('done');
    expect(stored.result?.tool_call_id).toBe('tc-1');
    expect(stored.result?.success).toBe(true);
    // P0-4 归一化会补 name/result_summary，不要求与输入对象 deep equal
    expect(stored.result?.result ?? stored.result?.result_summary).toEqual({ price: 100 });
  });

  it('appendEvent 添加 600 条事件 → MAX_EVENTS 滑动窗口生效（events.length === 500）[P0-1]', () => {
    const store = useAgentStore.getState();
    for (let i = 0; i < 600; i += 1) {
      store.appendEvent({
        type: 'agent_progress',
        title: `evt-${i}`,
        agent: 'a',
      });
    }
    const events = useAgentStore.getState().events;
    expect(events.length).toBe(500);
    // 前 100 条应被切除：现存第 0 条 title 应该是 evt-100
    expect(events[0].title).toBe('evt-100');
    // 末尾保留最新一条
    expect(events[events.length - 1].title).toBe('evt-599');
  });

  it('addToolCall 添加 600 次 → 同样应用 MAX_EVENTS 滑动窗口（toolCalls.length === 500）', () => {
    const store = useAgentStore.getState();
    for (let i = 0; i < 600; i += 1) {
      store.addToolCall({
        tool_call_id: `tc-${i}`,
        tool_name: 'noop',
        agent_name: 'a',
        params: {},
      } as ToolCallStart);
    }
    const toolCalls = useAgentStore.getState().toolCalls;
    expect(toolCalls.length).toBe(500);
    expect(toolCalls[0].tool_call_id).toBe('tc-100');
    expect(toolCalls[toolCalls.length - 1].tool_call_id).toBe('tc-599');
  });

  it('reset 清空所有 state', () => {
    const store = useAgentStore.getState();
    store.setAnalyzing(true);
    store.setOverallProgress(80);
    store.appendEvent({ type: 'reasoning', title: 't' });
    store.addToolCall({
      tool_call_id: 'x',
      tool_name: 'y',
      agent_name: 'z',
      params: {},
    } as ToolCallStart);

    store.addDegradation({
      level: 'warn',
      cause: 'network',
      message: 'down',
      confidence_cap: 0.3,
    });
    store.reset();
    const s = useAgentStore.getState();
    expect(s.isAnalyzing).toBe(false);
    expect(s.overallProgress).toBe(0);
    expect(s.events).toEqual([]);
    expect(s.toolCalls).toEqual([]);
    expect(s.agentProgresses).toEqual([]);
    expect(s.degradations).toEqual([]);
    expect(s.confidenceCap).toBeUndefined();
  });

  it('appendReasoningToken 流式追加 + finalize 行为', () => {
    const store = useAgentStore.getState();
    store.appendReasoningToken('fundamental', 'Hello ');
    store.appendReasoningToken('fundamental', 'world');
    let events = useAgentStore.getState().events;
    expect(events).toHaveLength(1);
    expect(events[0].detail).toBe('Hello world');
    expect((events[0].meta as { streaming?: boolean }).streaming).toBe(true);

    store.appendReasoningToken('fundamental', '!', true);
    events = useAgentStore.getState().events;
    expect(events[0].detail).toBe('Hello world!');
    expect((events[0].meta as { streaming?: boolean }).streaming).toBe(false);
  });

  it('P0-2 addDegradation 写入列表并取更紧 confidenceCap', () => {
    const store = useAgentStore.getState();
    store.addDegradation({
      level: 'warn',
      cause: 'tool_timeout',
      message: 'upstream timeout',
      confidence_cap: 0.55,
      source: 'get_stock_data',
    });
    store.addDegradation({
      level: 'critical',
      cause: 'guardrail_block',
      message: 'halt',
      confidence_cap: 0.2,
      source: 'guardrail',
    });
    const s = useAgentStore.getState();
    expect(s.degradations.length).toBe(2);
    expect(s.confidenceCap).toBe(0.2);
  });

  it('P0-2 addDegradation 短窗同 cause/source/message 去重', () => {
    const store = useAgentStore.getState();
    store.addDegradation({
      level: 'warn',
      cause: 'network',
      message: 'proxy fail',
      source: 'akshare',
      confidence_cap: 0.4,
    });
    store.addDegradation({
      level: 'warn',
      cause: 'network',
      message: 'proxy fail',
      source: 'akshare',
      confidence_cap: 0.4,
    });
    expect(useAgentStore.getState().degradations.length).toBe(1);
  });

});
