// Input: 含 <tool_call> 文本
// Output: 验证 parseMessageWithToolCalls 分段正确
// Pos: frontend/src/lib/parsers/tool-call-parser.spec.ts - FIX-9 配套测试

import { describe, it, expect } from "vitest";
import {
  parseMessageWithToolCalls,
  hasToolCallMarkup,
} from "./tool-call-parser";

describe("parseMessageWithToolCalls", () => {
  it("纯文本不分段", () => {
    const segs = parseMessageWithToolCalls("普通文本无工具调用");
    expect(segs).toHaveLength(1);
    expect(segs[0]).toEqual({ type: "text", value: "普通文本无工具调用" });
  });

  it("识别 mimo XML 格式 tool_call", () => {
    const text = `<tool_call>
<function=search_web>
<parameter=query>比亚迪 2025 战略</parameter>
<parameter=max_results>3</parameter>
</function>
</tool_call>`;
    const segs = parseMessageWithToolCalls(text);
    expect(segs).toHaveLength(1);
    expect(segs[0].type).toBe("tool_call");
    if (segs[0].type === "tool_call") {
      expect(segs[0].name).toBe("search_web");
      expect(segs[0].args).toEqual({
        query: "比亚迪 2025 战略",
        max_results: "3",
      });
      expect(segs[0].partial).toBe(false);
    }
  });

  it("识别 JSON 格式 tool_call", () => {
    const text = `前缀文本<tool_call>{"name":"get_stock","args":{"code":"000001"}}</tool_call>后缀`;
    const segs = parseMessageWithToolCalls(text);
    expect(segs).toHaveLength(3);
    expect(segs[0]).toEqual({ type: "text", value: "前缀文本" });
    expect(segs[1].type).toBe("tool_call");
    if (segs[1].type === "tool_call") {
      expect(segs[1].name).toBe("get_stock");
      expect(segs[1].args).toEqual({ code: "000001" });
      expect(segs[1].partial).toBe(false);
    }
    expect(segs[2]).toEqual({ type: "text", value: "后缀" });
  });

  it("未闭合的 tool_call 标记为 partial", () => {
    const text = "正常文本<tool_call><function=foo>正在流式";
    const segs = parseMessageWithToolCalls(text);
    expect(segs).toHaveLength(2);
    expect(segs[1].type).toBe("tool_call");
    if (segs[1].type === "tool_call") {
      expect(segs[1].partial).toBe(true);
      expect(segs[1].name).toBe("foo");
    }
  });

  it("多个 tool_call 顺序解析", () => {
    const text =
      "<tool_call>{\"name\":\"a\",\"args\":{}}</tool_call>中间<tool_call>{\"name\":\"b\",\"args\":{\"x\":1}}</tool_call>";
    const segs = parseMessageWithToolCalls(text);
    expect(segs).toHaveLength(3);
    expect(segs[0].type).toBe("tool_call");
    expect(segs[1]).toEqual({ type: "text", value: "中间" });
    expect(segs[2].type).toBe("tool_call");
    if (segs[2].type === "tool_call") {
      expect(segs[2].name).toBe("b");
    }
  });

  it("空字符串返回空数组", () => {
    expect(parseMessageWithToolCalls("")).toEqual([]);
  });

  it("JSON 解析失败时仍返回 tool_call 节点（args 为原始字符串）", () => {
    const text = `<tool_call>{破损 JSON</tool_call>`;
    const segs = parseMessageWithToolCalls(text);
    expect(segs).toHaveLength(1);
    expect(segs[0].type).toBe("tool_call");
  });
});

describe("hasToolCallMarkup", () => {
  it("含 <tool_call> 返回 true", () => {
    expect(hasToolCallMarkup("xx<tool_call>foo</tool_call>")).toBe(true);
  });
  it("不含返回 false", () => {
    expect(hasToolCallMarkup("普通对话内容")).toBe(false);
  });
  it("空字符串返回 false", () => {
    expect(hasToolCallMarkup("")).toBe(false);
  });
});
