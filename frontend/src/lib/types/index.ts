/**
 * Input: 后端API响应JSON
 * Output: TypeScript类型定义供前端全局使用
 * Pos: lib/types/index.ts - 全局类型定义，所有模块共享的类型唯一来源
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

// SSE事件处理器
export interface SSEHandlers {
  onToken?: (data: { content: string; finish_reason?: string | null }) => void;
  onToolCallStart?: (data: ToolCallStart) => void;
  onToolCallResult?: (data: ToolCallResult) => void;
  onArtifact?: (data: Artifact) => void;
  onAgentProgress?: (data: AgentProgress) => void;
  onReasoning?: (data: { content: string; agent: string }) => void;
  onError?: (data: { code: string; message: string; recoverable?: boolean }) => void;
  onDone?: (data: StreamDone) => void;
}

// Artifact类型
export interface ArtifactSource {
  name: string;
  type: string;
}

export interface Artifact {
  type: 'artifact';
  artifact_type: ArtifactType;
  title: string;
  data: Record<string, unknown>;
  confidence?: number;
  sources?: ArtifactSource[];
  metadata?: { source_tool: string; stock_code: string; generated_at: string };
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
  | 'investor_consensus'
  | 'agent_pipeline';

// Agent进度
export interface AgentProgress {
  agent_name: string;
  status: 'started' | 'completed' | 'error';
  progress: number;
  message?: string;
  stock_code?: string;
}

// 工具调用
export interface ToolCallStart {
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  agent?: string;
}

export interface ToolCallResult {
  tool_call_id: string;
  tool_name: string;
  result_summary: string;
  artifact?: Artifact;
  duration_ms?: number;
}

// 流结束
export interface StreamDone {
  conversation_id: string;
  follow_up_questions: string[];
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
}
