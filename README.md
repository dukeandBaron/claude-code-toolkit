# 🤖 Claude Code Toolkit

### **Stop Wasting Time on Setup. Start Building.**

**The Missing Piece for Multi-Agent Claude Code Workflows**

---

## 😩 The Problem

You're running Claude Code on multiple machines. Every session starts from zero:

- ❌ **Memory is isolated** — Machine A doesn't know what Machine B learned yesterday
- ❌ **No communication** — Two Claude Code instances can't talk to each other
- ❌ **Repeated context** — You explain the same project setup every. single. time.
- ❌ **No task coordination** — Can't assign work across machines

**You're paying for AI compute, but wasting it on redundant context loading.**

---

## ✅ The Solution

**One toolkit. Three problems solved.**

```
┌─────────────────────────────────────────────────────────────┐
│                    SHARED MEMORY HUB                         │
│                   ~/.shared-memory/                          │
│                                                              │
│  🧠 MEMORY.md      ← What your AI learned (persistent)      │
│  📋 TASK_QUEUE.md   ← What needs to be done (cross-machine)  │
│  🤝 HANDOVER.md     ← Results passed between sessions        │
│  📊 ACTIVITY_LOG.md ← Who did what, when                     │
│                                                              │
├─────────────┬─────────────────┬──────────────────────────────┤
│             │                 │                               │
│  🖥️ Machine A  │   🖥️ Machine B   │   📱 Phone/Tablet           │
│  Claude Code  │   Claude Code   │   Remote Control            │
│             │                 │                               │
│  ↕️ Real-time  │   ↕️ Real-time   │   ↕️ Monitor & Assign        │
│  WebSocket    │   WebSocket     │   via Shared Memory         │
└─────────────┴─────────────────┴──────────────────────────────┘
```

---

## 🚀 Get Started in 60 Seconds

```bash
# 1. Clone
git clone https://github.com/dukeandBaron/claude-code-toolkit.git
cd claude-code-toolkit

# 2. Setup (Windows/Linux/Mac)
./setup.sh  # or setup.bat on Windows

# 3. Start communicating
python agent-bridge/bridge.py send "Machine A: Experiment complete, PSNR=25.8"
python agent-bridge/bridge.py recv  # On Machine B
```

**That's it.** No Docker. No API keys. No cloud services. Pure Python.

---

## 🎯 What You Get

### 1. **Agent Bridge** — Real-time Cross-Machine Communication

```bash
# Machine A: Start listening
python agent-bridge/bridge.py start

# Machine B: Connect and talk
python agent-bridge/bridge.py connect 192.168.1.50:9527
python agent-bridge/bridge.py send "Hey, I finished the 3DGS training"
```

**Features:**
- 🔐 HMAC-SHA256 authentication (no unauthorized access)
- 🌐 LAN auto-discovery (finds other agents on your network)
- 🌍 WAN support (Tailscale/ZeroTier for remote machines)
- 📁 File transfer (send code, models, results)
- 🔄 Auto-sync shared memory files

### 2. **Shared Memory** — Persistent Context Across Sessions

```markdown
# ~/.shared-memory/MEMORY.md (auto-loaded every session)

## User Preferences
- Language: Chinese
- Style: Direct, actionable
- Project: 3DGS paper reproduction

## Environment
- GPU: RTX 4060 8GB
- PyTorch: 2.5.1 + CUDA 12.1

## Key Learnings
- T&T truck dataset: PSNR=25.80 with default settings
- Densification threshold: 0.005 works best for small scenes
```

**No more repeating yourself.** Your AI remembers across sessions, across machines.

### 3. **Task Queue** — Cross-Machine Job Coordination

```markdown
# ~/.shared-memory/TASK_QUEUE.md

[✅] 3DGS training on truck dataset | Machine A | High | Complete
[🔄] Generate visualization plots | Machine B | Medium | In Progress
[ ] Write results section | Machine A | High | Pending
```

**Assign work. Track progress. Get results.** All through shared files.

---

## 💡 Real Use Cases

### 🎓 Research Teams
- **Scenario**: 2 researchers, 3 machines, 1 paper deadline
- **Solution**: Shared memory keeps everyone aligned, task queue distributes work
- **Result**: 40% less context repetition, 2x faster iteration

### 🏢 Solo Developer with Multiple Machines
- **Scenario**: Desktop for training, laptop for writing, phone for monitoring
- **Solution**: Agent bridge syncs progress, shared memory persists context
- **Result**: Pick up exactly where you left off, on any device

### 🤖 AI Agent Orchestration
- **Scenario**: Multiple Claude Code instances working on different parts of a project
- **Solution**: Structured communication protocol, shared knowledge base
- **Result**: True multi-agent collaboration, not just parallel execution

---

## 🔧 Technical Details

### Zero Dependencies
```bash
# That's it. No requirements.txt. Just Python 3.8+
python agent-bridge/bridge.py --help
```

### Security First
- **Authentication**: HMAC-SHA256 tokens with timestamp validation
- **Encryption**: Optional TLS for WAN, WireGuard via Tailscale
- **Isolation**: Each machine has its own secret key
- **No cloud**: Everything stays on your network

### Protocol Design
- **JSON-RPC 2.0** over WebSocket (inspired by MCP and Google A2A)
- **mDNS discovery** for zero-config LAN setup
- **Ed25519 key exchange** for secure pairing
- **AES-256-GCM** for encrypted payloads

---

## 📊 Comparison

| Feature | This Toolkit | Manual Setup | Cloud Solutions |
|---------|-------------|--------------|-----------------|
| Setup time | 60 seconds | Hours | Minutes |
| Dependencies | Zero | Many | API keys |
| Privacy | 100% local | Depends | Cloud-hosted |
| Cost | Free | Time | $$ |
| Works offline | ✅ | ✅ | ❌ |
| Multi-machine | ✅ | ❌ | ✅ |

---

## 🛣️ Roadmap

- [ ] Web UI for monitoring (React + WebSocket)
- [ ] Voice notifications (TTS for task completion)
- [ ] Mobile app (Flutter/React Native)
- [ ] Integration with VS Code/Cursor
- [ ] Plugin system for custom protocols

---

## 🤝 Contributing

**We need your help!**

- 🐛 **Found a bug?** Open an issue
- 💡 **Have an idea?** Start a discussion
- 🔧 **Want to code?** Submit a PR

**Areas needing help:**
- macOS testing and optimization
- Windows service integration
- Documentation translation (中文/English/日本語)
- Example projects and tutorials

---

## 📚 Documentation

- **[Agent Bridge Docs](agent-bridge/README.md)** — Complete API reference
- **[Protocol Design](agentlink/PROTOCOL_DESIGN.md)** — Technical deep-dive
- **[Shared Memory Guide](shared-memory/ARCHITECTURE.md)** — Architecture overview
- **[Examples](examples/)** — Real-world use cases (coming soon)

---

## 🌟 Star History

If this project helps you, give it a ⭐! It helps others find it.

---

## 📄 License

MIT License — Use it however you want. Sell it. Fork it. Build on it.

---

## 🙏 Acknowledgments

Built with frustration from:
- Repeating the same context every Claude Code session
- Manually copying files between machines
- Wasting GPU time on redundant setup

**Special thanks to:**
- Anthropic for Claude Code
- The MCP protocol for inspiration
- Every developer who's ever typed "remember this" into a chat

---

**Made with ❤️ and mild annoyance by dukeandBaron**

*If this saves you time, buy yourself a coffee. You deserve it.* ☕

---

## 🇨🇳 中文版

### 解决什么问题？

多台电脑运行 Claude Code 时：
- ❌ 记忆不互通 — A 机器不知道 B 机器昨天学了什么
- ❌ 无法通信 — 两个 Claude Code 实例不能对话
- ❌ 重复配置 — 每次都要重新解释项目背景
- ❌ 无法协作 — 不能跨机器分配任务

### 怎么解决？

```bash
# 1. 克隆
git clone https://github.com/dukeandBaron/claude-code-toolkit.git
cd claude-code-toolkit

# 2. 安装
./setup.sh  # Windows 用 setup.bat

# 3. 开始使用
python agent-bridge/bridge.py send "机器A：实验完成，PSNR=25.8"
python agent-bridge/bridge.py recv  # 在机器B上读取
```

**就这么简单。** 没有 Docker，没有 API Key，没有云服务。纯 Python。

### 包含什么？

| 组件 | 说明 | 用途 |
|------|------|------|
| **agent-bridge** | WebSocket 通信桥 | 两台机器的 Claude Code 实时对话 |
| **agentlink** | P2P 协议实现 | mDNS 发现 + Ed25519 加密 |
| **shared-memory** | 共享记忆中心 | 多方共读共写的记忆文件系统 |
| **scripts** | 实用脚本 | Claude Code 免确认启动等 |

### 适合谁？

- 🎓 **研究团队** — 多人协作写论文、跑实验
- 🏢 **独立开发者** — 多台设备无缝切换
- 🤖 **AI Agent 爱好者** — 构建真正的多智能体系统

---

**Made with ❤️ and mild annoyance by dukeandBaron**

*如果这个项目帮到了你，请给自己买杯咖啡。你值得。* ☕
