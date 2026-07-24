/**
 * Input: 后端API响应JSON
 * Output: TypeScript类型定义供前端全局使用
 * Pos: lib/types/index.ts - 全局类型定义，所有模块共享的类型唯一来源
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

// SSE事件处理器
export interface SSEHandlers {
  // [UI-Q4] token事件可带 agent/round 标识 — agent 字段存在时视为"agent推理token", 追加到agent终端流
  onToken?: (data: { content: string; finish_reason?: string | null; agent?: string; round?: number }) => void;
  onToolCallStart?: (data: ToolCallStart) => void;
  onToolCallResult?: (data: ToolCallResult) => void;
  onArtifact?: (data: Artifact) => void;
  onAgentProgress?: (data: AgentProgress) => void;
  onReasoning?: (data: { content: string; agent: string }) => void;
  /** P0-5 HITL 确认面 */
  onApprovalNeeded?: (data: Record<string, unknown>) => void;
  onApprovalResolved?: (data: Record<string, unknown>) => void;
  /** P0-3 辩论轮次证据 */
  onDebateTurn?: (data: DebateTurn) => void;
  /** P0-2 降级可视化（零假值）：agent.degraded */
  onAgentDegraded?: (data: AgentDegradedEvent) => void;
  /** G6 Run scorecard（done 时四维） */
  onRunScorecard?: (data: RunScorecardEvent) => void;
  /** Sprint2: chat 意图路由 meta（无假行情数） */
  onMeta?: (data: ChatIntentMeta) => void;
  /** Plan DAG：plan.created（EventBus → SSE bridge） */
  onPlanCreated?: (data: Record<string, unknown>) => void;
  /** Plan DAG：plan.step 状态推进 */
  onPlanStep?: (data: Record<string, unknown>) => void;
  /** 写仓提案 write_proposal（HITL 桥接） */
  onWriteProposal?: (data: Record<string, unknown>) => void;
  onError?: (data: { code: string; message: string; recoverable?: boolean }) => void;
  onDone?: (data: StreamDone) => void;
  // 流通道关闭时的兜底（无论是否收到 done 事件都会触发，用于强制清理 loading 状态）
  onClose?: () => void;
}

/** Sprint2 意图分类 meta（SSE event: meta） */
export interface ChatIntentMeta {
  intent?: string;
  confidence?: number;
  reasons?: string[];
  stock_codes?: string[];
  inject_portfolio?: boolean;
  router?: string;
  portfolio_count?: number;
  portfolio_source?: string;
  [key: string]: unknown;
}

/** 与 app.core.intent_router.Intent 字面量对齐的意图枚举 */
export type IntentKind =
  | 'single_stock_deep'
  | 'portfolio'
  | 'portfolio_write_blocked'
  | 'cross_market_event'
  | 'market_overview'
  | 'general';

/** G11：chat intent badge 中文标签；未知 intent 不得用 stock_code 冒充 */
export const INTENT_LABELS_ZH: Record<IntentKind, string> = {
  single_stock_deep: '个股深析',
  portfolio: '组合风险',
  portfolio_write_blocked: '组合写入(已拦截)',
  cross_market_event: '跨市场事件',
  market_overview: '市场总览',
  general: '通用问答',
};

// Artifact类型
export interface ArtifactSource {
  name: string;
  type: string;
}

/** G1 数据血统摘要 — 仅 source/tool/ts/digest，禁止嵌入假行情 */
export interface ProvenanceEntry {
  source?: string;
  tool?: string;
  ts?: string;
  digest?: string;
}

/** 假行情/估值字段黑名单（与后端 _PROVENANCE_FAKE_PRICE_KEYS 对齐） */
const PROVENANCE_FAKE_PRICE_KEYS = new Set([
  'price',
  'last_price',
  'close',
  'open',
  'high',
  'low',
  'change_pct',
  'pct_chg',
  'volume',
  'amount',
  'turnover',
  'volume_ratio',
  'pe',
  'pb',
  'pe_ttm',
  'pb_mrq',
  'market_cap',
]);

/**
 * 单条 provenance 归一：仅 dict + 非空 source；剥离假行情字段；拒绝裸 string。
 * 所有前端消费方必须走此函数，禁止直接渲染/合并未清洗条目。
 */
export function normalizeProvenanceItem(raw: unknown): ProvenanceEntry | null {
  if (raw == null || typeof raw === 'string' || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }
  const obj = raw as Record<string, unknown>;
  const src = String(obj.source ?? '').trim();
  if (!src) return null;
  const entry: ProvenanceEntry = { source: src.slice(0, 200) };
  const tool = String(obj.tool ?? '').trim();
  if (tool) entry.tool = tool.slice(0, 120);
  const digest = String(obj.digest ?? '').trim();
  if (digest) entry.digest = digest.slice(0, 64);
  const ts = obj.ts;
  if (ts != null && String(ts).trim()) entry.ts = String(ts).trim().slice(0, 64);
  // 防御：若上游把假价字段误塞进 allowed 名以外，已只取四字段；额外断言不回写黑名单
  for (const k of Object.keys(entry)) {
    if (PROVENANCE_FAKE_PRICE_KEYS.has(k)) {
      delete (entry as Record<string, unknown>)[k];
    }
  }
  return entry;
}

/** 列表归一 + (source,tool,digest) 去重；截断 maxItems */
export function normalizeProvenanceList(
  raw: unknown,
  maxItems = 32,
): ProvenanceEntry[] {
  if (raw == null) return [];
  const items: unknown[] = Array.isArray(raw)
    ? raw
    : typeof raw === 'object'
      ? [raw]
      : [];
  const cap = Math.max(1, Math.min(maxItems || 32, 64));
  const seen = new Set<string>();
  const out: ProvenanceEntry[] = [];
  for (const item of items) {
    const cleaned = normalizeProvenanceItem(item);
    if (!cleaned?.source) continue;
    const key = `${cleaned.source}|${cleaned.tool ?? ''}|${cleaned.digest ?? ''}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(cleaned);
    if (out.length >= cap) break;
  }
  return out;
}

/** G2 统一 terminal 态（与 HITL / web_server 对齐） */
export type RunTerminalStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'awaiting_approval'
  | 'timeout_reject'
  | 'rejected'
  | 'approved';

export type AgentTaskStatus = RunTerminalStatus | 'unknown' | string;

export interface Artifact {
  type: 'artifact';
  artifact_type: ArtifactType;
  title: string;
  data: Record<string, unknown>;
  confidence?: number;
  sources?: ArtifactSource[];
  /** G1 数据血统摘要列表 */
  provenance?: ProvenanceEntry[];
  metadata?: {
    source_tool?: string;
    stock_code?: string;
    stock_name?: string;
    generated_at?: string;
    provenance?: ProvenanceEntry[];
    [key: string]: unknown;
  };
}

export type ArtifactType =
  | 'candlestick_chart'
  | 'technical_indicators'
  | 'fundamental_metrics'
  | 'capital_flow_chart'
  | 'news_feed'
  | 'risk_gauge'
  | 'search_results'
  | 'decision_card'
  | 'debate_card'         // P0-3 多空辩论证据面
  | 'investor_consensus'
  | 'investor_opinions'
  | 'agent_pipeline'
  // P3 另类数据 Artifact (E4 — 2026-04-15)
  | 'alt_data'           // 另类数据聚合主面板 (tab: shipping/esg/hiring/corporate)
  | 'shipping'           // 航运大宗 — BDI/港口吞吐/AIS
  | 'esg'                // ESG 三维评分 + 多源对比 + SEC 气候披露
  | 'hiring'             // 招聘信号 — 岗位数/技能分布/扩张预警
  | 'corporate_network'; // 企业关联网络 — 父/子/董事会/司法管辖区

// Agent进度
export interface AgentProgress {
  agent_name: string;
  status: 'started' | 'completed' | 'error' | 'running' | 'awaiting_approval' | 'timeout_reject' | 'rejected' | 'approved';
  progress: number;
  message?: string;
  stock_code?: string;
}

/** P0-2 降级事件（agent.degraded）— 零假值可视化 */
export type DegradationCause =
  | 'tool_timeout'
  | 'source_degraded'
  | 'guardrail_block'
  | 'network'
  | 'timeout'
  | 'upstream_empty'
  | 'quota'
  | 'auth'
  | 'parse'
  | 'tool_failure'
  | string;

export interface AgentDegradedEvent {
  event_type?: 'agent.degraded' | string;
  level: 'info' | 'warn' | 'critical' | string;
  cause: DegradationCause;
  message: string;
  confidence_cap?: number;
  source?: string;
  task_id?: string;
  stock_code?: string;
  correlation_id?: string;
}

/** G6 Run scorecard 事件（run.scorecard）— 无假行情 */
export interface RunScorecardEvent {
  event_type?: 'run.scorecard' | string;
  data_coverage?: number | null;
  tool_success_rate?: number | null;
  role_agreement?: number | null;
  confidence_cap?: number | null;
  task_id?: string;
  stock_code?: string;
  evidence?: Record<string, unknown> | null;
  decision_memo?: DecisionMemo | null;
  reflection_summary?: ReflectionSummary | null;
  memory_context?: MemoryPrefetch | null;
  [key: string]: unknown;
}

/** G5 决策备忘（action / 否决·风险理由 / evidence 指针） */
export interface DecisionMemo {
  action?: 'BUY' | 'SELL' | 'HOLD' | string;
  confidence?: number | null;
  confidence_cap?: number | null;
  risk_level?: string | null;
  reasoning?: string | null;
  veto_reasons?: string[];
  risk_reasons?: string[];
  evidence_pointers?: Array<{ slot: string; label: string; status: 'present' | 'missing' | string }>;
  /** G1 数据血统摘要（与 final_decision.provenance 对齐，无假行情） */
  provenance?: ProvenanceEntry[];
  scorecard?: {
    data_coverage?: number | null;
    tool_success_rate?: number | null;
    role_agreement?: number | null;
    confidence_cap?: number | null;
  } | null;
  disclaimer?: string;
  stock_code?: string;
  [key: string]: unknown;
}

/** G7 反思只读摘要 */
export interface ReflectionSummary {
  count?: number;
  items?: Array<{
    timestamp?: string;
    accuracy_score?: number | null;
    lessons?: string | null;
    what_went_well?: string | null;
    what_went_wrong?: string | null;
    prediction_summary?: string | null;
  }>;
  readonly?: boolean;
  note?: string;
}

/** G8 Memory 预取（空历史不造假，null 表示无） */
export interface MemoryPrefetch {
  history_count?: number;
  recent?: Array<{
    timestamp?: string;
    action?: string | null;
    confidence?: number | null;
    reasoning?: string | null;
  }>;
  semantic_context?: string | null;
  empty?: boolean;
}

// 工具调用
/** P0-4 工具时间线契约：name/args_digest/ok/error/duration_ms/source（兼容旧 tool_name/arguments/result） */
export interface ToolCallStart {
  tool_call_id: string;
  /** 契约主字段 */
  name?: string;
  tool_name: string;
  args_digest?: string;
  arguments?: Record<string, unknown>;
  source?: string;
  status?: "running" | "done" | "error";
  agent?: string;
  provenance?: ProvenanceEntry[];
}

export interface ToolCallResult {
  tool_call_id: string;
  name?: string;
  tool_name?: string;
  ok?: boolean;
  error?: string | null;
  duration_ms?: number;
  result_summary?: string;
  /** @deprecated 用 result_summary；保留兼容 */
  result?: string;
  source?: string;
  agent?: string;
  artifact?: Artifact;
  provenance?: ProvenanceEntry[];
}

/** P0-3 辩论轮次（bull / bear / summary） */
export interface DebateTurn {
  side: "bull" | "bear" | "summary" | string;
  stock_code?: string;
  thesis?: string;
  confidence?: string;
  divergence_points?: string[];
  agent?: string;
}

// 流结束
export interface StreamDone {
  conversation_id?: string;
  follow_up_questions?: string[];
  // agent-analyze 路径附带：每个Agent执行结果摘要
  execution_log?: Array<{ agent?: string; status?: string; mode?: string; tools_used?: number; timestamp?: string }>;
  stock_code?: string;
  /** Sprint2: chat 路径意图标签 */
  intent?: string;
}

// 对话
export interface Conversation {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
  stock_codes?: string[];
}

export interface ChatMessage {
  message_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  artifacts?: Artifact[];
  tool_calls?: ToolCallStart[];
  created_at: string;
}

// 股票数据
export interface StockDecision {
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  reasoning: string;
  risk_score: number;
  price_targets?: { support: number; resistance: number; target: number };
  /** G1 数据血统 */
  provenance?: ProvenanceEntry[];
  approval_status?: string;
}
