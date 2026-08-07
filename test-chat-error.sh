#!/bin/bash

echo "=== Chat 错误修复验证测试 ==="
echo ""

# 测试1：正常的 chat 请求
echo "测试1：发送正常消息"
curl -s -X POST http://127.0.0.1:8888/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "conversation_id": "",
    "research_depth": 3
  }' | head -5
echo ""
echo ""

# 测试2：缺少必需字段（应该返回详细错误）
echo "测试2：缺少必需字段 message"
curl -s -X POST http://127.0.0.1:8888/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": ""
  }'
echo ""
echo ""

# 测试3：无效的 research_depth（应该返回校验错误）
echo "测试3：无效的 research_depth 值"
curl -s -X POST http://127.0.0.1:8888/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "测试",
    "research_depth": 10
  }'
echo ""
echo ""

# 测试4：空消息（应该返回校验错误）
echo "测试4：空消息"
curl -s -X POST http://127.0.0.1:8888/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": ""
  }'
echo ""
echo ""

echo "=== 测试完成 ==="
