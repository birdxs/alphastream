/**
 * Input: 用户消息文本 + 可选参数（股票代码、市场类型、研究深度）
 * Output: 发送消息函数 + 停止生成函数，自动处理SSE流并更新store，完成时支持浏览器Notification推送
 * Pos: lib/hooks/use-chat-stream.ts - 聊天流式请求Hook，连接API客户端与状态管理
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

import { useCallback, useEffect, useRef } from 'react';
import { apiClient } from '@/lib/api/client';
import { useChatStore } from '@/lib/stores/chat-store';
import { useAgentStore } from '@/lib/stores/agent-store';
// G1/G2/G3 helpers re-exported via store for terminal/provenance/dedupe
import { usePortfolioStore } from '@/lib/stores/portfolio-store';
import type { SSEHandlers, ChatMessage, StreamDone } from '@/lib/types';

// ===== 意图识别规则 =====
// 分析类动词（触发agent路径的语义信号）
const ANALYZE_VERB_RE = /分析|研究|深度|全面|对比|解读|评估|诊断|复盘|解析|探讨|解构|解密|剖析|透视|推演|预测|展望|盘点|梳理|点评|测评|多[aA]gent|agent/;

// 简体中文股票名候选抽取：2-6字连续中文串，过滤常见动词/代词/连词
const STOP_WORDS = new Set([
  '分析', '研究', '深度', '全面', '对比', '解读', '评估', '诊断', '复盘', '解析',
  '探讨', '解构', '解密', '剖析', '透视', '推演', '预测', '展望', '盘点', '梳理',
  '点评', '测评', '你好', '请问', '帮我', '这个', '那个', '一下', '怎么样',
  '巴菲特', '索罗斯', '彼得林奇', '格雷厄姆', '投资', '哲学', '大师', '四位',
  '三位', '两位', '五位', '分别', '思路', '风格', '视角', '角度', '综合',
]);

function extractStockNameCandidates(message: string): string[] {
  // 匹配 2-6 字的连续中文
  const re = /[\u4e00-\u9fa5]{2,6}/g;
  const raw = message.match(re) || [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const w of raw) {
    if (STOP_WORDS.has(w)) continue;
    if (seen.has(w)) continue;
    seen.add(w);
    out.push(w);
  }
  // 长的优先（股票名通常3-4字）
  out.sort((a, b) => b.length - a.length);
  return out.slice(0, 8);
}

async function lookupCodeByName(message: string): Promise<string | null> {
  const cands = extractStockNameCandidates(message);
  // 整体 2.5s 上限避免上游慢响应阻塞 sendMessage
  const overallStart = Date.now();
  const OVERALL_TIMEOUT_MS = 2500;
  for (const q of cands) {
    if (Date.now() - overallStart > OVERALL_TIMEOUT_MS) break;
    try {
      const ctrl = new AbortController();
      const tid = setTimeout(() => ctrl.abort(), 800);
      const resp = await fetch(`/api/stock_name_search?q=${encodeURIComponent(q)}`, { signal: ctrl.signal });
      clearTimeout(tid);
      if (!resp.ok) continue;
      const data = await resp.json();
      const hit = Array.isArray(data?.results) && data.results[0];
      if (hit?.stock_code && /^\d{6}$/.test(hit.stock_code)) {
        const exact = data.results.find((r: { stock_name?: string; stock_code?: string }) => r.stock_name === q);
        if (exact?.stock_code) return exact.stock_code;
        return hit.stock_code;
      }
    } catch { /* ignore, try next */ }
  }
  return null;
}

export function useChatStream() {
  // 不订阅store — 通过getState()在回调内获取最新状态，避免全量重渲染
  const abortRef = useRef<AbortController | null>(null);
  // C4(Hunt4): 保存 stopBlink 清理函数，组件卸载时调用避免 timer 泄漏
  const blinkCleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      blinkCleanupRef.current?.();
      blinkCleanupRef.current = null;
    };
  }, []);

  const sendMessage = useCallback(
    async (
      message: string,
      options: {
        stock_code?: string;
        market_type?: string;
        research_depth?: number;
      } = {}
    ) => {
      // 取消之前的请求，并清理上一次 blink timer
      blinkCleanupRef.current?.();
      blinkCleanupRef.current = null;
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      const chatStore = useChatStore.getState();
      const agentStore = useAgentStore.getState();

      // 添加用户消息
      const userMsg: ChatMessage = {
        message_id: `user_${Date.now()}`,
        role: 'user',
        content: message,
        created_at: new Date().toISOString(),
      };
      chatStore.addMessage(userMsg);

      // 新对话第一条消息：自动设置对话标题为前20个字符
      const isFirstMessage = chatStore.messages.filter((m) => m.role === 'user').length === 0;
      if (isFirstMessage && chatStore.activeConversationId) {
        const autoTitle = message.slice(0, 20) + (message.length > 20 ? '...' : '');
        chatStore.updateConversationTitle(chatStore.activeConversationId, autoTitle);
      }

      chatStore.setStreaming(true);
      chatStore.resetStreamContent();
      chatStore.clearArtifacts();
      agentStore.reset();
      // 意图预判：同步判断是否有6位代码或 options.stock_code；若无代码但有分析意图动词，稍后异步反查股票名
      const _codeMatch0 = message.match(/\b(\d{6})\b/);
      const _hasAnalyzeVerb = ANALYZE_VERB_RE.test(message);
      const _directAgent = _hasAnalyzeVerb && (_codeMatch0 || options.stock_code);
      if (_directAgent) agentStore.setAnalyzing(true);

      // 累积完整内容（不受打字动画影响），用于onDone时生成最终消息
      let fullContentBuffer = '';

      const handlers: SSEHandlers = {
        onMeta: (data) => {
          // Sprint2: 意图 meta（无假行情数）→ chat-store badge
          chatStore.setLastIntentMeta(data || null);
        },
        onToken: (data) => {
          const content = data.content;
          // [UI-Q4] token 带 agent 字段 → 视为agent推理token, 追加到agent-store的流式reasoning行
          //   (不进入 chat 正文 streamingContent)
          if (data.agent) {
            const finalize = data.finish_reason === 'stop';
            agentStore.appendReasoningToken(data.agent, content, finalize);
            return;
          }
          fullContentBuffer += content;
          if (content.length <= 5) {
            // 短token直接追加
            chatStore.appendStreamContent(content);
          } else {
            // 长文本直接追加（避免requestAnimationFrame导致onDone时内容不完整）
            chatStore.appendStreamContent(content);
          }
        },
        onToolCallStart: (data) => {
          agentStore.addToolCall(data);
          // P0-4：时间线只消费契约字段 name/args_digest/source
          const toolName = data.name || data.tool_name || 'tool';
          const digest = data.args_digest ? ` · ${data.args_digest}` : '';
          let argsPreview = data.args_digest || '';
          if (!argsPreview) {
            try {
              argsPreview = JSON.stringify(data.arguments ?? {});
            } catch {
              argsPreview = String(data.arguments ?? '');
            }
          }
          agentStore.appendEvent({
            type: 'tool_call_start',
            agent: data.agent || data.source,
            title: `调用工具 ${toolName}${digest}`,
            detail: argsPreview,
            meta: {
              tool_call_id: data.tool_call_id,
              name: toolName,
              args_digest: data.args_digest,
              source: data.source,
            },
          });
        },
        onToolCallResult: (data) => {
          agentStore.setToolCallResult(data.tool_call_id, data);
          if (Array.isArray((data as any).provenance)) {
            agentStore.mergeProvenance((data as any).provenance);
          } else if (Array.isArray((data as any).artifact?.provenance)) {
            agentStore.mergeProvenance((data as any).artifact.provenance);
          }
          if (data.artifact) {
            chatStore.addArtifact(data.artifact);
          }
          // P0-4：ok / error / duration_ms / result_summary
          const toolName = data.name || data.tool_name || 'tool';
          const dur = data.duration_ms != null ? ` · ${data.duration_ms}ms` : '';
          const okMark = data.ok === false || data.error ? '失败' : '完成';
          agentStore.appendEvent({
            type: 'tool_call_result',
            agent: data.agent || data.source,
            title: `${toolName} ${okMark}${dur}`,
            detail:
              data.error ||
              data.result_summary ||
              data.result ||
              (data.artifact ? `生成 artifact: ${data.artifact.title}` : ''),
            meta: {
              tool_call_id: data.tool_call_id,
              name: toolName,
              ok: data.ok,
              error: data.error,
              duration_ms: data.duration_ms,
              source: data.source,
            },
          });
        },
        onDebateTurn: (data) => {
          agentStore.addDebateTurn(data);
          const sideLabel =
            data.side === 'bull' ? '多方' : data.side === 'bear' ? '空方' : '辩论摘要';
          agentStore.appendEvent({
            type: 'debate_turn',
            agent: data.agent,
            title: `${sideLabel}${data.confidence ? ` · 置信${data.confidence}` : ''}`,
            detail: data.thesis || (data.divergence_points || []).join('；'),
            meta: {
              side: data.side,
              confidence: data.confidence,
              divergence_points: data.divergence_points,
            },
          });
        },
        // P0-2 降级可视化（agent.degraded / agent_degraded）
        onAgentDegraded: (data) => {
          agentStore.addDegradation({
            level: data.level || 'warn',
            cause: data.cause || 'tool_failure',
            message: data.message || '数据源降级，未使用假行情填补。',
            confidence_cap: data.confidence_cap,
            source: data.source,
            task_id: data.task_id,
            stock_code: data.stock_code,
            correlation_id: data.correlation_id,
          });
          const capTxt =
            typeof data.confidence_cap === 'number'
              ? ` · 置信上限${Math.round(data.confidence_cap * 100)}%`
              : '';
          agentStore.appendEvent({
            type: 'degraded',
            title: `降级${data.cause ? ` · ${data.cause}` : ''}${capTxt}`,
            detail: data.message || '数据源降级，未使用假行情填补。',
            meta: {
              level: data.level,
              cause: data.cause,
              confidence_cap: data.confidence_cap,
              source: data.source,
            },
          });
        },
        onRunScorecard: (data) => {
          const sc = {
            data_coverage: data.data_coverage ?? null,
            tool_success_rate: data.tool_success_rate ?? null,
            role_agreement: data.role_agreement ?? null,
            confidence_cap: data.confidence_cap ?? null,
          };
          agentStore.setScorecard(sc);
          if (data.decision_memo && typeof data.decision_memo === 'object') {
            agentStore.setDecisionMemo(data.decision_memo as Record<string, unknown>);
          }
          if (data.reflection_summary && typeof data.reflection_summary === 'object') {
            agentStore.setReflectionSummary(
              data.reflection_summary as Record<string, unknown>,
            );
          }
          if (data.memory_context && typeof data.memory_context === 'object') {
            agentStore.setMemoryContext(data.memory_context as Record<string, unknown>);
          }
          agentStore.appendEvent({
            type: 'scorecard',
            agent: 'system',
            title: '运行评分卡',
            detail: [
              data.data_coverage != null
                ? `覆盖 ${Math.round(Number(data.data_coverage) * 100)}%`
                : null,
              data.tool_success_rate != null
                ? `工具 ${Math.round(Number(data.tool_success_rate) * 100)}%`
                : null,
              data.role_agreement != null
                ? `角色一致 ${Math.round(Number(data.role_agreement) * 100)}%`
                : null,
              data.confidence_cap != null
                ? `置信帽 ${Math.round(Number(data.confidence_cap) * 100)}%`
                : null,
            ]
              .filter(Boolean)
              .join(' · '),
            meta: {
              ...sc,
              task_id: data.task_id,
              stock_code: data.stock_code,
            },
          });
        },

        onArtifact: (data) => {
          chatStore.addArtifact(data);
        },
        onAgentProgress: (data) => {
          // G3 payload 可能是 {event_type,data:{...}} 或扁平 AgentProgress
          const flat: any = (data as any)?.data && typeof (data as any).data === 'object'
            ? { ...(data as any).data, ...(data as any) }
            : data;
          const agentName = flat.agent_name || flat.agent || flat.role || 'agent';
          const status = flat.status || (
            String((data as any)?.event_type || '').includes('completed') ||
            String((data as any)?.event_type || '').includes('finished')
              ? 'completed'
              : String((data as any)?.event_type || '').includes('started')
                ? 'started'
                : 'started'
          );
          const progressNum = typeof flat.progress === 'number' ? flat.progress : (status === 'completed' ? 1 : 0);
          agentStore.setAgentProgress({
            agent_name: agentName,
            status: status === 'error' ? 'error' : status === 'completed' ? 'completed' : 'started',
            progress: progressNum,
            message: flat.detail || flat.message,
            stock_code: flat.stock_code,
          });
          // G1: 若进度事件携带 provenance 则合并
          if (Array.isArray(flat.provenance)) {
            agentStore.mergeProvenance(flat.provenance);
          }
          const rawType = (data as any)?.event_type || (data as any)?.canonical || '';
          const evType =
            status === 'completed' || String(rawType).includes('completed') || String(rawType).includes('finished')
              ? (String(rawType).includes('role') ? 'agent.role_finished' : 'agent.completed')
              : status === 'started' || String(rawType).includes('started')
                ? (String(rawType).includes('role') ? 'agent.role_started' : 'agent.started')
                : 'agent_progress';
          agentStore.appendEvent({
            type: evType,
            agent: agentName,
            title: status === 'started'
              ? `${agentName} 启动`
              : status === 'completed'
                ? `${agentName} 完成`
                : `${agentName} ${Math.round(progressNum * (progressNum <= 1 ? 100 : 1))}%`,
            detail: flat.detail || flat.message,
            meta: { progress: progressNum, status, raw_type: rawType, task_id: flat.task_id },
          });
        },
        onReasoning: (data) => {
          agentStore.appendEvent({
            type: 'reasoning',
            agent: data.agent,
            title: `${data.agent || '推理'} 思考`,
            detail: data.content,
          });
        },
        onApprovalNeeded: (data) => {
          const d = (data || {}) as Record<string, unknown>;
          const nested = (d.data && typeof d.data === 'object' ? d.data : {}) as Record<string, unknown>;
          const content =
            (typeof nested.content === 'string' && nested.content) ||
            (typeof d.content === 'string' && d.content) ||
            `[APPROVAL] 等待人工确认 task=${String(d.task_id || '')}`;
          agentStore.appendEvent({
            id: `approval_${String(d.task_id || Date.now())}`,
            type: 'agent_started',
            agent: typeof d.agent === 'string' ? d.agent : '审批闸门',
            title: content,
            detail: typeof d.reason === 'string' ? d.reason : undefined,
            ts: Date.now(),
            meta: { ...d, level: 'warn' },
          });
        },
        onApprovalResolved: (data) => {
          const d = (data || {}) as Record<string, unknown>;
          const status = String(d.status || d.approval_type || 'resolved');
          agentStore.appendEvent({
            id: `approval_res_${String(d.task_id || Date.now())}`,
            type: 'agent_completed',
            agent: typeof d.agent === 'string' ? d.agent : '审批闸门',
            title: `[APPROVAL] 审批结果: ${status}`,
            ts: Date.now(),
            meta: d,
          });
        },
        onPlanCreated: (data) => {
          const d = (data || {}) as Record<string, unknown>;
          const nested =
            d.data && typeof d.data === 'object'
              ? (d.data as Record<string, unknown>)
              : d;
          const planId = String(nested.plan_id || nested.id || d.plan_id || '');
          const goal = String(nested.goal || nested.title || '').slice(0, 120);
          agentStore.appendEvent({
            id: `plan_created_${planId || Date.now()}`,
            type: 'plan.created',
            agent: 'Plan',
            title: goal ? `计划已创建: ${goal}` : `计划已创建${planId ? ` #${planId.slice(0, 8)}` : ''}`,
            detail: planId || undefined,
            ts: Date.now(),
            meta: nested,
          });
        },
        onPlanStep: (data) => {
          const d = (data || {}) as Record<string, unknown>;
          const nested =
            d.data && typeof d.data === 'object'
              ? (d.data as Record<string, unknown>)
              : d;
          const stepId = String(nested.step_id || nested.id || '');
          const status = String(nested.status || nested.state || 'updated');
          const name = String(nested.name || nested.title || stepId || 'step');
          agentStore.appendEvent({
            id: `plan_step_${stepId || Date.now()}_${status}`,
            type: 'plan.step',
            agent: 'Plan',
            title: `步骤 ${name}: ${status}`,
            detail:
              typeof nested.message === 'string'
                ? nested.message
                : typeof nested.detail === 'string'
                  ? nested.detail
                  : undefined,
            ts: Date.now(),
            meta: nested,
          });
        },
        onWriteProposal: (data) => {
          const d = (data || {}) as Record<string, unknown>;
          const nested =
            d.data && typeof d.data === 'object'
              ? (d.data as Record<string, unknown>)
              : d;
          // 与 EVENT_WRITE_PROPOSAL / ApprovalCard 对齐：kind / approval_id / proposal_id / status
          const proposalId = String(
            nested.proposal_id || nested.id || '',
          );
          const approvalId = String(
            nested.approval_id || nested.task_id || '',
          );
          const kind = String(
            nested.kind || 'portfolio_write_proposal',
          );
          const action = String(
            nested.action || nested.side || 'write',
          );
          const code = String(nested.stock_code || nested.code || '');
          // 生命周期 status：pending | approved | rejected | applied_local
          let status = String(nested.status ?? 'pending').trim().toLowerCase() || 'pending';
          if (status === 'applied') status = 'applied_local';
          // 只读摘要（零假数）：优先服务端 summary，否则 action+code，不拼价格
          const summaryFromServer =
            typeof nested.summary === 'string' && nested.summary.trim()
              ? nested.summary.trim()
              : '';
          const summaryLocal = [action, code].filter(Boolean).join(' ');
          const summary = summaryFromServer || summaryLocal;
          const reason =
            typeof nested.reason === 'string' ? nested.reason : '';
          const statusLabel =
            status === 'approved'
              ? '已通过 · 未成交'
              : status === 'rejected'
                ? '已拒绝 · 未成交'
                : status === 'applied_local'
                  ? '本地标记 applied · 未成交'
                  : '待审批 · 未成交';
          const titlePrefix =
            status === 'approved'
              ? '提案已通过'
              : status === 'rejected'
                ? '提案已拒绝'
                : status === 'applied_local'
                  ? '提案已本地标记'
                  : '写仓提案';
          // id 含 status，配合 store dedupe key 允许同 proposal 终态并存
          agentStore.appendEvent({
            id: `write_proposal_${proposalId || approvalId || Date.now()}_${status}`,
            type: 'write_proposal',
            agent: '写仓',
            title: summary
              ? `${titlePrefix} ${summary}`
              : `${titlePrefix}${proposalId ? ` #${proposalId.slice(0, 8)}` : ''}`,
            detail: [
              reason || undefined,
              summary && summary !== reason ? summary : undefined,
              approvalId && `审批 ${approvalId.slice(0, 14)}`,
              proposalId && `提案 ${proposalId.slice(0, 14)}`,
              statusLabel,
            ]
              .filter(Boolean)
              .join(' · '),
            ts: Date.now(),
            meta: {
              ...nested,
              kind,
              proposal_id: proposalId || undefined,
              approval_id: approvalId || undefined,
              task_id: approvalId || undefined,
              action: action || undefined,
              code: code || undefined,
              summary: summary || undefined,
              status,
              // 铁律#1：apply 永不 executed=true 成交语义
              executed: false,
              apply_mode:
                nested.apply_mode != null
                  ? String(nested.apply_mode)
                  : status === 'applied_local'
                    ? 'local_mark_only'
                    : undefined,
            },
          });
        },
        onError: (data) => {
          const errText = typeof data === 'string' ? data : (data?.message || (data as { error?: string })?.error || JSON.stringify(data));
          console.error('Stream error:', errText, data);
          const errorMsg: ChatMessage = {
            message_id: `error_${Date.now()}`,
            role: 'assistant',
            content: `⚠️ ${errText || '分析服务暂时不可用（后端超时/断开）'}\n\n请检查后端服务状态，或点击"重试"。`,
            created_at: new Date().toISOString(),
          };
          chatStore.addMessage(errorMsg);
          chatStore.resetStreamContent();
          chatStore.setStreaming(false); agentStore.setAnalyzing(false);
          // 保存重试建议
          chatStore.setFollowUps(['🔄 重试上一个问题']);
        },
        onDone: (data) => {
          // 将流式内容转为正式消息，优先使用完整缓冲内容避免打字动画导致内容不完整
          let finalContent = fullContentBuffer || useChatStore.getState().streamingContent;
          const finalArtifacts = [...useChatStore.getState().artifacts];
          // agent-analyze 路径不发 token 事件 → finalContent 为空 → 渲染 "(正在生成...)" 占位
          // 这里基于 artifacts + execution_log 自动合成一段总结，避免空消息
          if (!finalContent) {
            const stockCode = options.stock_code || /\b(\d{6})\b/.exec(message)?.[1] || '';
            const decisionArt = finalArtifacts.find(a => a.artifact_type === 'decision_card');
            const decision = decisionArt?.data as { action?: string; confidence?: number; reasoning?: string; risk_level?: string; position_suggestion?: string; price_targets?: { support?: string; resistance?: string; target?: string } } | undefined;
            const lines: string[] = [`### ${stockCode} 多Agent分析完成`];
            if (decision?.action) {
              const conf = decision.confidence != null ? `${Math.round(decision.confidence * 100)}%` : '—';
              lines.push(`- **建议操作**：${decision.action}（置信度 ${conf}）`);
              if (decision.risk_level) lines.push(`- **风险等级**：${decision.risk_level}`);
              if (decision.position_suggestion) lines.push(`- **建议仓位**：${decision.position_suggestion}`);
              const pt = decision.price_targets;
              if (pt && (pt.support || pt.resistance || pt.target)) {
                const seg: string[] = [];
                if (pt.support) seg.push(`支撑 ${pt.support}`);
                if (pt.resistance) seg.push(`阻力 ${pt.resistance}`);
                if (pt.target) seg.push(`目标 ${pt.target}`);
                lines.push(`- **关键价位**：${seg.join(' · ')}`);
              }
              if (decision.reasoning) lines.push(`\n${decision.reasoning}`);
            } else {
              lines.push(`已完成全部 Agent 执行。详见右侧实时进度面板与下方决策卡片。`);
            }
            const execLog = (data?.execution_log || []) as Array<{ agent?: string; status?: string }>;
            if (execLog.length > 0) {
              const ok = execLog.filter(e => e.status === 'success').length;
              lines.push(`\n_执行日志：${ok}/${execLog.length} Agent 成功_`);
            }
            finalContent = lines.join('\n');
          }
          const assistantMsg: ChatMessage = {
            message_id: `assistant_${Date.now()}`,
            role: 'assistant',
            content: finalContent,
            artifacts: finalArtifacts,
            created_at: new Date().toISOString(),
          };
          chatStore.addMessage(assistantMsg);
          chatStore.resetStreamContent();
          chatStore.setStreaming(false); agentStore.setAnalyzing(false);
          chatStore.setFollowUps(data?.follow_up_questions || []);

          // Q2(2026-04-15): 对话自动入 sidebar
          //   1) 后端 done 事件附带 conversation_id（新建会话亦返回）；若当前 activeId 为空则写入 store
          //   2) 递增 refreshTick 触发 sidebar 重新拉取 /api/conversations，使新会话/更新时间立即可见
          const doneConvId = (data as StreamDone | undefined)?.conversation_id;
          if (doneConvId && !useChatStore.getState().activeConversationId) {
            useChatStore.getState().setActiveConversation(doneConvId);
          }
          useChatStore.getState().bumpConversationsRefresh();

          // Tab标题闪烁提醒 + 浏览器通知
          if (document.hidden) {
            const originalTitle = document.title;
            let blinking = true;
            const interval = setInterval(() => {
              document.title = blinking ? '\u2705 分析完成!' : originalTitle;
              blinking = !blinking;
            }, 1000);
            const stopBlink = () => {
              clearInterval(interval);
              clearTimeout(blinkAutoStopId);
              document.title = originalTitle;
              document.removeEventListener('visibilitychange', stopBlink);
              blinkCleanupRef.current = null;
            };
            document.addEventListener('visibilitychange', stopBlink);
            const blinkAutoStopId = setTimeout(stopBlink, 10000);
            // C4(Hunt4): 注册清理函数到 ref，保证组件卸载时 timer/listener 不泄漏
            blinkCleanupRef.current = stopBlink;

            // 浏览器Notification推送
            const stockLabel = options.stock_code || '分析';
            if (typeof Notification !== 'undefined') {
              if (Notification.permission === 'granted') {
                new Notification(`AI分析完成 — ${stockLabel}`, {
                  body: '点击返回查看结果',
                  icon: '/favicon.ico',
                });
              } else if (Notification.permission === 'default') {
                Notification.requestPermission().then((perm) => {
                  if (perm === 'granted') {
                    new Notification(`AI分析完成 — ${stockLabel}`, {
                      body: '点击返回查看结果',
                      icon: '/favicon.ico',
                    });
                  }
                });
              }
            }
          }
        },
        // 兜底：流通道关闭时强制清理 loading 状态——防止后端 done 事件丢失/handler 抛错时 UI 卡死在"AI正在分析中"
        onClose: () => {
          const cs = useChatStore.getState();
          const ags = useAgentStore.getState();
          if (cs.isStreaming) {
            // 若 streamingContent 有内容但未通过 onDone 入库，补一条 assistant 消息
            const remaining = fullContentBuffer || cs.streamingContent;
            const arts = [...cs.artifacts];
            if (remaining) {
              cs.addMessage({
                message_id: `assistant_${Date.now()}`,
                role: 'assistant',
                content: remaining,
                artifacts: arts,
                created_at: new Date().toISOString(),
              });
              cs.resetStreamContent();
            } else if (arts.length > 0) {
              // 流断开但已收到artifacts（典型agent-analyze路径）— 给一条简短占位消息
              cs.addMessage({
                message_id: `assistant_${Date.now()}`,
                role: 'assistant',
                content: '分析已完成，请查看下方决策卡片与右侧 Agent 进度面板。',
                artifacts: arts,
                created_at: new Date().toISOString(),
              });
              cs.resetStreamContent();
            }
            cs.setStreaming(false);
          }
          if (ags.isAnalyzing) ags.setAnalyzing(false);
          // Q2(2026-04-15): 兜底刷新 sidebar — agent-analyze/错误/超时路径无 done 事件时仍保证列表同步
          useChatStore.getState().bumpConversationsRefresh();
        },
      };

      // 意图路由（两阶段）：
      // Stage1: 6位代码 或 options.stock_code → 直走agent
      // Stage2: 无代码但有分析动词 → 反查股票名得代码 → 走agent
      // 否则 → 走普通 /api/ai/chat
      const codeMatch = _codeMatch0;
      let resolvedCode = options.stock_code || codeMatch?.[1] || '';
      let isAnalyze = _hasAnalyzeVerb && !!resolvedCode;

      if (!isAnalyze && _hasAnalyzeVerb && !resolvedCode) {
        // Stage2: 股票名反查
        const lookedUp = await lookupCodeByName(message);
        if (lookedUp) {
          resolvedCode = lookedUp;
          isAnalyze = true;
          agentStore.setAnalyzing(true);
        }
      }

      const endpoint = isAnalyze ? '/api/ai/agent-analyze' : '/api/ai/chat';
      if ((process.env.NODE_ENV ?? 'development') !== 'production') {
        console.log('[chat-stream] sendMessage', { endpoint, isAnalyze, resolvedCode, _hasAnalyzeVerb, msgLen: message.length });
      }
      const body = isAnalyze
        ? {
            stock_code: resolvedCode,
            market_type: options.market_type || 'A',
            research_depth: options.research_depth ?? 3,
            user_message: message,
            conversation_id: chatStore.activeConversationId || '',
          }
        : (() => {
            // Sprint2: chat 路径附带 portfolio-store 真仓（name===code → name 空串）
            const base: Record<string, unknown> = {
              message,
              conversation_id: chatStore.activeConversationId || '',
              ...options,
            };
            try {
              const holdings = usePortfolioStore.getState().holdings || [];
              if (Array.isArray(holdings) && holdings.length > 0) {
                base.portfolio_snapshot = {
                  source: 'portfolio-store',
                  as_of: new Date().toISOString(),
                  holdings: holdings
                    .map((h) => {
                      const code = (h.code || '').trim();
                      const rawName = (h.name || '').trim();
                      const name = rawName && rawName !== code ? rawName : '';
                      const row: Record<string, unknown> = {
                        code,
                        name,
                        market_type: 'A',
                      };
                      if (typeof h.shares === 'number') row.shares = h.shares;
                      if (typeof h.costPrice === 'number') row.cost = h.costPrice;
                      return row;
                    })
                    .filter((h) => typeof h.code === 'string' && !!h.code),
                };
              }
            } catch {
              // store 不可用则不附带
            }
            return base;
          })();

      try {
        await apiClient.streamPost(
          endpoint,
          body,
          handlers,
          abortRef.current.signal
        );
      } catch (e) {
        if (e instanceof DOMException && e.name === 'AbortError') {
          // 用户主动取消，正常处理
          const currentContent = useChatStore.getState().streamingContent;
          if (currentContent) {
            const stoppedMsg: ChatMessage = {
              message_id: `assistant_${Date.now()}`,
              role: 'assistant',
              content: currentContent + '\n\n[已停止]',
              artifacts: [...useChatStore.getState().artifacts],
              created_at: new Date().toISOString(),
            };
            chatStore.addMessage(stoppedMsg);
          }
          chatStore.resetStreamContent();
          chatStore.setStreaming(false); agentStore.setAnalyzing(false);
          return;
        }
        chatStore.setStreaming(false); agentStore.setAnalyzing(false);
        console.error('Chat stream error:', e);
      }
    },
    []
  );

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { sendMessage, stopGeneration };
}
