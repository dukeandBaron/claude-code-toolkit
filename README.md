# Claude Code Toolkit 🛠️

**让 Claude Code 实现多机器协作、记忆共享、任务调度的完整工具包**

[English](#english) | 中文

---

## 🎯 这是什么？

这是一个让多个 Claude Code 实例实现**跨机器通信**和**协作**的工具包。解决了以下痛点：

- ❌ Claude Code 之间无法直接对话
- ❌ 多台电脑的会话记忆互相隔离
- ❌ 无法跨机器分配和追踪任务
- ❌ 每次都要重复配置环境

✅ **现在**：两台电脑的 Claude Code 可以实时通信、共享记忆、协作完成任务！

---

## 📦 包含什么？

| 组件 | 说明 | 用途 |
|------|------|------|
| **[agent-bridge](agent-bridge/)** | WebSocket 通信桥 | 两台机器的 Claude Code 实时对话 |
| **[agentlink](agentlink/)** | AgentLink 协议实现 | P2P 通信协议（mDNS 发现 + Ed25519 加密） |
| **[shared-memory](shared-memory/)** | 共享记忆中心 | 多方共读共写的记忆文件系统 |
| **[scripts](scripts/)** | 实用脚本 | Claude Code 免确认启动等 |

---

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/dukeandBaron/claude-code-toolkit.git
cd claude-code-toolkit
```

### 2. 设置共享记忆目录

```bash
# 创建共享记忆目录
mkdir -p ~/.shared-memory

# 复制模板文件
cp shared-memory/* ~/.shared-memory/
```

### 3. 使用 Agent Bridge（最简单）

```bash
# 方式 A：文件模式（无需网络，适合 Syncthing/Git 同步）
python agent-bridge/bridge.py send "你好，我刚跑完实验"
python agent-bridge/bridge.py recv

# 方式 B：网络模式（实时通信）
# 机器 A：
python agent-bridge/bridge.py start

# 机器 B：
python agent-bridge/bridge.py connect 192.168.1.50:9527
python agent-bridge/bridge.py start
```

### 4. 配置 Claude Code 自动使用

在你的项目根目录创建 `CLAUDE.md`：

```markdown
## 跨机器通信
- 发送消息：`python ~/claude-code-toolkit/agent-bridge/bridge.py send "内容"`
- 读取消息：`python ~/claude-code-toolkit/agent-bridge/bridge.py recv`
- 查看状态：`python ~/claude-code-toolkit/agent-bridge/bridge.py status`

## 共享记忆
- 启动时读取：`~/.shared-memory/MEMORY.md`
- 重要事实写入：`~/.shared-memory/MEMORY.md`
- 任务发布：`~/.shared-memory/TASK_QUEUE.md`
```

---

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────┐
│                   SHARED MEMORY HUB                  │
│                  ~/.shared-memory/                    │
│                                                       │
│  MEMORY.md ← 三方共读共写的长期记忆                   │
│  TASK_QUEUE.md ← 统一任务队列（三方发布/领取）        │
│  HANDOVER.md ← 交接区（任务结果传递）                 │
│  ACTIVITY_LOG.md ← 活动日志（谁干了啥）               │
│                                                       │
├──────────┬──────────────┬────────────────────────────┤
│          │              │                             │
│  WorkBuddy  │  Claude Code  │    Hermes Agent           │
│  (桌面GUI)  │  (编码主力)   │   (自治+调度+监控)        │
│          │              │                             │
│  角色:      │  角色:        │   角色:                   │
│  - 交互入口 │  - 代码实现   │   - 定时任务(cron)        │
│  - 记忆管理 │  - Debug      │   - 论文/新闻监控         │
│  - 任务发布 │  - 重构       │   - 子agent调度           │
└──────────┴──────────────┴────────────────────────────┘
```

---

## 📖 详细文档

### Agent Bridge

[完整文档](agent-bridge/README.md)

- 支持文件模式、网络模式、LAN 自动发现
- HMAC-SHA256 令牌认证
- 时间戳防重放（±5 分钟）
- 路径遍历防护

### AgentLink Protocol

[完整文档](agentlink/PROTOCOL_DESIGN.md)

- 基于 JSON-RPC 2.0 的 P2P 协议
- mDNS 自动发现（LAN）
- Ed25519 密钥交换 + AES-256-GCM 加密
- 支持 Tailscale/ZeroTier（WAN）

### 共享记忆中心

[完整文档](shared-memory/ARCHITECTURE.md)

- MEMORY.md：长期记忆（三方共读共写）
- TASK_QUEUE.md：统一任务队列
- HANDOVER.md：跨工具任务交接
- ACTIVITY_LOG.md：活动日志

---

## 🌐 网络场景

| 场景 | 方案 | 命令 |
|------|------|------|
| 同 WiFi | 直接 IP 连接 | `python bridge.py connect 192.168.x.x:9527` |
| 同 WiFi | UDP 自动发现 | `python bridge.py discover` |
| 不同 WiFi | Tailscale | 两台装 Tailscale → 用虚拟 IP 连接 |
| 不同 WiFi | ngrok | `ngrok tcp 9527` → 用 ngrok 地址连接 |
| 无网络 | Syncthing | 文件自动同步，无需 bridge 网络功能 |

---

## 🔧 依赖

- Python 3.8+
- 无第三方依赖（纯标准库实现）

---

## 📝 License

MIT License - 自由使用、修改、分发

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

<a name="english"></a>

## English

**A complete toolkit for enabling multi-machine collaboration, memory sharing, and task orchestration between Claude Code instances.**

### What's Included?

- **agent-bridge**: WebSocket communication bridge for real-time cross-machine Claude Code dialogue
- **agentlink**: P2P protocol implementation with mDNS discovery and Ed25519 encryption
- **shared-memory**: Shared memory hub for multi-agent read/write access
- **scripts**: Utility scripts for Claude Code automation

### Quick Start

```bash
git clone https://github.com/dukeandBaron/claude-code-toolkit.git
cd claude-code-toolkit

# Set up shared memory
mkdir -p ~/.shared-memory
cp shared-memory/* ~/.shared-memory/

# Start communicating!
python agent-bridge/bridge.py send "Hello from Machine A!"
python agent-bridge/bridge.py recv
```

See [agent-bridge/README.md](agent-bridge/README.md) for detailed documentation.

---

**Made with ❤️ by dukeandBaron**
