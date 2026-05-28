# 🤖 Claude Code Toolkit

### **The Missing Layer for Multi-Agent Claude Code Workflows**

> **Zero dependencies. 60 seconds setup. 100% local.**

---

## 😩 The Problem

You're running Claude Code on multiple machines. Every session starts from zero:

- ❌ **Memory is isolated** — Machine A doesn't know what Machine B learned yesterday
- ❌ **No communication** — Two Claude Code instances can't talk to each other
- ❌ **No task coordination** — Can't assign work across machines
- ❌ **Token waste** — Re-explaining context every session costs $$$

**You're paying for AI compute, but wasting it on redundant context loading.**

---

## ✅ The Solution

**One toolkit. Four problems solved.**

```
┌─────────────────────────────────────────────────────────────────┐
│                    SHARED MEMORY HUB                             │
│                   ~/.shared-memory/                              │
│                                                                  │
│  🧠 Smart Memory      ← Semantic search (TF-IDF)                │
│  📋 Task Scheduler    ← Priority queue + auto-assign             │
│  🤝 Agent Bridge      ← Real-time WebSocket communication        │
│  🔌 MCP Server        ← Official Claude Code protocol            │
│                                                                  │
├─────────────┬─────────────────┬──────────────────────────────────┤
│             │                 │                                   │
│  🖥️ Machine A  │   🖥️ Machine B   │   📱 Phone/Tablet               │
│  Claude Code  │   Claude Code   │   Remote Control                │
│             │                 │                                   │
│  ↕️ MCP + WS   │   ↕️ MCP + WS   │   ↕️ Monitor & Assign            │
└─────────────┴─────────────────┴──────────────────────────────────┘
```

---

## 🆚 Why This Toolkit?

| Feature | **This Toolkit** | claude-brain | claude-cortex-memory | Ruflo | ccswarm |
|---------|-----------------|--------------|----------------------|-------|---------|
| **Setup Time** | 60 seconds | 5+ min | 5+ min | 10+ min | 10+ min |
| **Dependencies** | Zero (pure Python) | Node.js | Python + DB | Docker | Docker |
| **MCP Support** | ✅ Native | ❌ | ❌ | ❌ | ❌ |
| **Semantic Search** | ✅ TF-IDF | ✅ Vector DB | ✅ Vector DB | ✅ | ✅ |
| **Task Scheduling** | ✅ Priority queue | ❌ | ❌ | ✅ | ✅ |
| **Cross-Machine** | ✅ WebSocket | ❌ | ❌ | ✅ | ✅ |
| **Privacy** | 100% Local | Local | Local | Cloud option | Cloud option |
| **Cost** | Free | Free | Free | Freemium | Freemium |

**Our edge:** We're the only toolkit with **native MCP support** — the official Claude Code protocol. This means zero friction integration and future-proof as Claude Code evolves.

---

## 🚀 Get Started in 60 Seconds

```bash
# 1. Clone
git clone https://github.com/dukeandBaron/claude-code-toolkit.git
cd claude-code-toolkit

# 2. Setup (Windows/Linux/Mac)
./setup.sh  # or setup.bat on Windows

# 3. Start using
python agent-bridge/cli.py status
```

**That's it.** No Docker. No API keys. No cloud services. Pure Python.

---

## 🎯 What You Get

### 1. **Smart Memory** — Semantic Search Across Sessions

Stop re-explaining your project. Your AI remembers.

```bash
# Search memories by meaning, not just keywords
python agent-bridge/cli.py memory search "3DGS experiment parameters"

# Save what you learned
python agent-bridge/cli.py memory save "PSNR=25.8, densification=0.005" --category experiment

# Record bug solutions for future reference
python agent-bridge/cli.py memory bug add "CUDA out of memory" "Reduce batch size to 4"

# Find similar bugs when they recur
python agent-bridge/cli.py memory bug find "GPU memory error"
```

**Under the hood:** TF-IDF vectorization with cosine similarity. Zero dependencies, pure Python.

### 2. **Task Scheduler** — Intelligent Work Distribution

Replace manual markdown task lists with smart scheduling.

```bash
# Create a task with priority
python agent-bridge/cli.py task create "Run 3DGS experiment" --priority high --assignee claude-pc1

# See what's ready to execute
python agent-bridge/cli.py task ready

# Auto-assign to the least busy agent
python agent-bridge/cli.py task auto-assign <task_id>

# Mark complete with results
python agent-bridge/cli.py task update <task_id> --status done --result "PSNR=25.8"

# View statistics
python agent-bridge/cli.py task stats
```

**Features:**
- Priority queue (urgent > high > medium > low)
- Auto-assignment based on agent load
- Dependency management (task B waits for task A)
- Timeout detection (auto-fail stale tasks)
- Statistics and reporting

### 3. **Agent Bridge** — Real-time Cross-Machine Communication

Two Claude Code instances talking to each other.

```bash
# Machine A: Send a message
python agent-bridge/cli.py bridge send "Experiment complete, PSNR=25.8"

# Machine B: Receive messages
python agent-bridge/cli.py bridge recv

# Sync a specific file
python agent-bridge/cli.py bridge sync MEMORY.md

# Check connection status
python agent-bridge/cli.py bridge status
```

**Security:** HMAC-SHA256 authentication. Only machines with the shared secret can communicate.

### 4. **MCP Server** — Official Claude Code Protocol

The first toolkit with native MCP support. Zero-friction integration.

```json
{
  "mcpServers": {
    "claude-toolkit": {
      "command": "python",
      "args": ["path/to/agent-bridge/mcp_server.py"]
    }
  }
}
```

**Available MCP Tools:**
- `memory_search` — Semantic search across all memories
- `memory_save` — Save new memories
- `task_create` — Create intelligent tasks
- `task_list` — View task queue
- `task_update` — Update task status
- `bridge_send` — Send cross-machine messages
- `bridge_recv` — Receive cross-machine messages
- `knowledge_query` — Query bug solutions, decisions, experiments

---

## 📊 Real-World Use Cases

### Use Case 1: Research Team Collaboration
```
Machine A (Researcher): Runs experiment, saves results to shared memory
Machine B (Analyst): Searches memory for experiment results, generates report
Machine C (Writer): Queries memory for key findings, writes paper section
```

### Use Case 2: Multi-Environment Development
```
Machine A (Dev): Writes code, creates tasks for testing
Machine B (Test): Picks up tasks, runs tests, reports results
Machine A (Dev): Reviews results, marks tasks complete
```

### Use Case 3: Personal Knowledge Base
```
Session 1: Learn about 3DGS, save key insights
Session 2: Search for "3DGS parameters" — instant recall
Session 3: Build on previous knowledge without re-explaining
```

---

## 🛡️ Privacy & Security

- **100% Local**: No data leaves your machine unless you explicitly sync
- **No Cloud**: No accounts, no API keys, no subscriptions
- **Encrypted Communication**: HMAC-SHA256 for cross-machine messages
- **Open Source**: Full transparency, audit the code yourself

---

## 🔧 Advanced Configuration

### Custom Memory Directory
```python
from smart_memory import SmartMemory
memory = SmartMemory(memory_dir="/path/to/custom/dir")
```

### Task Dependencies
```bash
# Task B depends on Task A
python agent-bridge/cli.py task create "Analyze results" --depends <task_a_id>
```

### Agent Registration
```bash
# Register an agent with capabilities
python agent-bridge/cli.py task register claude-pc1 --capabilities "python,gpu,experiment"
```

---

## 📈 Roadmap

- [x] Smart Memory with semantic search
- [x] Task Scheduler with priority queue
- [x] Agent Bridge with WebSocket
- [x] MCP Server (native protocol)
- [ ] Vector database upgrade (for larger memory stores)
- [ ] Web UI dashboard
- [ ] VS Code extension
- [ ] Cursor/Windsurf integration
- [ ] Mobile app for remote monitoring

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

- Claude Code team for the amazing AI coding assistant
- MCP protocol for standardizing tool integration
- The open-source community for inspiration

---

**Built with ❤️ by developers, for developers.**

[GitHub](https://github.com/dukeandBaron/claude-code-toolkit) | [Issues](https://github.com/dukeandBaron/claude-code-toolkit/issues) | [Discussions](https://github.com/dukeandBaron/claude-code-toolkit/discussions)
