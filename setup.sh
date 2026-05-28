#!/bin/bash
# Claude Code Toolkit - 快速安装脚本
# 使用方法：chmod +x setup.sh && ./setup.sh

set -e

echo "🚀 Claude Code Toolkit 安装脚本"
echo "================================"

# 检测操作系统
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    OS="windows"
    HOME_DIR="$USERPROFILE"
    SHARED_MEMORY_DIR="$HOME/.shared-memory"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    HOME_DIR="$HOME"
    SHARED_MEMORY_DIR="$HOME/.shared-memory"
else
    OS="linux"
    HOME_DIR="$HOME"
    SHARED_MEMORY_DIR="$HOME/.shared-memory"
fi

echo "📍 检测到系统: $OS"
echo "📍 主目录: $HOME_DIR"
echo "📍 共享记忆目录: $SHARED_MEMORY_DIR"
echo ""

# 创建共享记忆目录
echo "📁 创建共享记忆目录..."
mkdir -p "$SHARED_MEMORY_DIR"

# 复制模板文件
echo "📋 复制模板文件..."
cp -n shared-memory/MEMORY.md "$SHARED_MEMORY_DIR/" 2>/dev/null || true
cp -n shared-memory/TASK_QUEUE.md "$SHARED_MEMORY_DIR/" 2>/dev/null || true
cp -n shared-memory/HANDOVER.md "$SHARED_MEMORY_DIR/" 2>/dev/null || true
cp -n shared-memory/ACTIVITY_LOG.md "$SHARED_MEMORY_DIR/" 2>/dev/null || true
cp -n shared-memory/ARCHITECTURE.md "$SHARED_MEMORY_DIR/" 2>/dev/null || true
cp -n shared-memory/sync.sh "$SHARED_MEMORY_DIR/" 2>/dev/null || true

# 设置执行权限
chmod +x "$SHARED_MEMORY_DIR/sync.sh" 2>/dev/null || true

echo ""
echo "✅ 安装完成！"
echo ""
echo "📖 下一步："
echo "  1. 查看 README.md 了解如何使用"
echo "  2. 在你的项目 CLAUDE.md 中添加通信指令"
echo "  3. 开始使用！"
echo ""
echo "💡 快速测试："
echo "  python agent-bridge/bridge.py status"
echo ""
