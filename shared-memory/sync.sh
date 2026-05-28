#!/bin/bash
# 共享记忆自动同步脚本
# 用法: bash ~/.shared-memory/sync.sh
# 建议: cron 每 5 分钟执行一次

SHARED_DIR="$HOME/.shared-memory"
cd "$SHARED_DIR" || exit 1

# 确保是 git repo
[ -d .git ] || exit 1

# 拉取远程更新（如果有 remote）
git pull --rebase 2>/dev/null || true

# 提交本地变更
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "sync $(hostname) $(date +%Y-%m-%d_%H:%M)"
  # 推送到远程（如果有 remote）
  git push 2>/dev/null || true
fi
