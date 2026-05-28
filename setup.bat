@echo off
REM Claude Code Toolkit - Windows 快速安装脚本
REM 双击运行即可

echo 🚀 Claude Code Toolkit 安装脚本
echo ================================

REM 创建共享记忆目录
echo 📁 创建共享记忆目录...
if not exist "%USERPROFILE%\.shared-memory" mkdir "%USERPROFILE%\.shared-memory"

REM 复制模板文件
echo 📋 复制模板文件...
if not exist "%USERPROFILE%\.shared-memory\MEMORY.md" copy shared-memory\MEMORY.md "%USERPROFILE%\.shared-memory\"
if not exist "%USERPROFILE%\.shared-memory\TASK_QUEUE.md" copy shared-memory\TASK_QUEUE.md "%USERPROFILE%\.shared-memory\"
if not exist "%USERPROFILE%\.shared-memory\HANDOVER.md" copy shared-memory\HANDOVER.md "%USERPROFILE%\.shared-memory\"
if not exist "%USERPROFILE%\.shared-memory\ACTIVITY_LOG.md" copy shared-memory\ACTIVITY_LOG.md "%USERPROFILE%\.shared-memory\"
if not exist "%USERPROFILE%\.shared-memory\ARCHITECTURE.md" copy shared-memory\ARCHITECTURE.md "%USERPROFILE%\.shared-memory\"
if not exist "%USERPROFILE%\.shared-memory\sync.sh" copy shared-memory\sync.sh "%USERPROFILE%\.shared-memory\"

echo.
echo ✅ 安装完成！
echo.
echo 📖 下一步：
echo   1. 查看 README.md 了解如何使用
echo   2. 在你的项目 CLAUDE.md 中添加通信指令
echo   3. 开始使用！
echo.
echo 💡 快速测试：
echo   python agent-bridge\bridge.py status
echo.
pause
