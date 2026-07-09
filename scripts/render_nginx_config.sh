#!/bin/bash
# Input: nginx/*.conf.template + 环境变量
# Output: nginx/*.conf (渲染后配置)
# Pos: nginx 配置模板渲染脚本

set -euo pipefail

# 默认值
: "${BACKEND_TIMEOUT:=600}"
: "${BACKEND_CONNECT_TIMEOUT:=10}"
: "${FRONTEND_TIMEOUT:=300}"

cd "$(dirname "$0")/.."

echo "🔧 开始渲染 nginx 配置..."
echo "   BACKEND_TIMEOUT=${BACKEND_TIMEOUT}"
echo "   BACKEND_CONNECT_TIMEOUT=${BACKEND_CONNECT_TIMEOUT}"
echo "   FRONTEND_TIMEOUT=${FRONTEND_TIMEOUT}"
echo ""

# 检查 envsubst
if ! command -v envsubst &> /dev/null; then
    echo "❌ 错误: envsubst 未安装 (需要 gettext 包)"
    echo "   macOS: brew install gettext"
    echo "   Ubuntu: apt install gettext-base"
    exit 1
fi

# 渲染所有模板
rendered_count=0
for template in nginx/*.conf.template; do
    if [[ ! -f "$template" ]]; then
        continue
    fi

    output="${template%.template}"
    echo "📝 渲染 $(basename "$template") → $(basename "$output")"

    # 使用 perl 替换 ${VAR:-default} 语法
    export BACKEND_TIMEOUT BACKEND_CONNECT_TIMEOUT FRONTEND_TIMEOUT
    perl -pe '
        s/\$\{BACKEND_TIMEOUT:-\d+\}/$ENV{BACKEND_TIMEOUT}/g;
        s/\$\{BACKEND_CONNECT_TIMEOUT:-\d+\}/$ENV{BACKEND_CONNECT_TIMEOUT}/g;
        s/\$\{FRONTEND_TIMEOUT:-\d+\}/$ENV{FRONTEND_TIMEOUT}/g;
    ' "$template" > "$output"

    rendered_count=$((rendered_count + 1))
done

echo ""
echo "✅ 完成 $rendered_count 个配置文件渲染"
ls -lh nginx/*.conf 2>/dev/null || true

# 变量替换完整性检查
echo ""
echo "🔍 检查未替换变量..."
if grep -E '\$\{[A-Z_]+' nginx/*.conf 2>/dev/null | grep -v '#'; then
    echo "❌ 发现未替换的模板变量"
    exit 1
else
    echo "✅ 所有变量已正确替换"
fi
