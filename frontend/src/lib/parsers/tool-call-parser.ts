// Input: 含 <tool_call>...</tool_call> 或 <function=name>...</function> 文本的消息内容
// Output: 分段数组 [{type:'text', value} | {type:'tool_call', name, args, partial}]
// Pos: frontend/src/lib/parsers/tool-call-parser.ts - FIX-9 mimo/DeepSeek 工具调用文本流模板化

// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

export type ToolCallSegment = {
  type: "tool_call";
  name: string;
  args: Record<string, unknown> | string;
  partial: boolean; // true = 半段未闭合（流式渲染中）
};

export type TextSegment = { type: "text"; value: string };

export type MessageSegment = TextSegment | ToolCallSegment;

/**
 * 解析消息内容中的工具调用文本。
 *
 * 兼容两种格式:
 *   1. mimo / OpenAI 标准:  <tool_call>{"name":"search_web","args":{...}}</tool_call>
 *   2. mimo 备用:           <tool_call>\n<function=search_web>\n<parameter=query>X</parameter>\n</function>\n</tool_call>
 */
export function parseMessageWithToolCalls(content: string): MessageSegment[] {
  if (!content) return [];

  const segments: MessageSegment[] = [];
  let cursor = 0;
  const openTag = "<tool_call>";
  const closeTag = "</tool_call>";

  while (cursor < content.length) {
    const openIdx = content.indexOf(openTag, cursor);
    if (openIdx === -1) {
      // 剩余全是纯文本
      const tail = content.slice(cursor);
      if (tail) segments.push({ type: "text", value: tail });
      break;
    }

    // 前置文本
    if (openIdx > cursor) {
      segments.push({ type: "text", value: content.slice(cursor, openIdx) });
    }

    const closeIdx = content.indexOf(closeTag, openIdx + openTag.length);
    if (closeIdx === -1) {
      // 半段未闭合 → partial
      const inner = content.slice(openIdx + openTag.length);
      segments.push(parseInner(inner, true));
      cursor = content.length;
      break;
    }

    const inner = content.slice(openIdx + openTag.length, closeIdx);
    segments.push(parseInner(inner, false));
    cursor = closeIdx + closeTag.length;
  }

  return segments;
}

function parseInner(inner: string, partial: boolean): ToolCallSegment {
  const trimmed = inner.trim();

  // 尝试 JSON 格式
  if (trimmed.startsWith("{")) {
    try {
      const obj = JSON.parse(trimmed);
      const name = obj.name ?? obj.function?.name ?? "unknown";
      const args = obj.args ?? obj.arguments ?? obj.parameters ?? obj.function?.arguments ?? {};
      return {
        type: "tool_call",
        name: String(name),
        args: typeof args === "string" ? args : args,
        partial,
      };
    } catch {
      // JSON 解析失败，可能是流式半截
    }
  }

  // 尝试 mimo XML 格式
  const funcMatch = trimmed.match(/<function=([\w-]+)>/);
  if (funcMatch) {
    const name = funcMatch[1];
    const args: Record<string, string> = {};
    const paramRe = /<parameter=([\w-]+)>([\s\S]*?)<\/parameter>/g;
    let m: RegExpExecArray | null;
    while ((m = paramRe.exec(trimmed)) !== null) {
      args[m[1]] = m[2].trim();
    }
    return { type: "tool_call", name, args, partial };
  }

  // 未识别 → 把原文当 args 字符串
  return {
    type: "tool_call",
    name: "unknown",
    args: trimmed,
    partial,
  };
}

/** 判断内容中是否包含 (可能是) 工具调用文本，供调用方决定是否走分段渲染 */
export function hasToolCallMarkup(content: string): boolean {
  return !!content && content.indexOf("<tool_call>") !== -1;
}
