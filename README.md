# Claude Code Toolkit

> **轻量级 Claude Code 协作工具** — 零依赖、60秒上手、100%本地

---

## 解决什么问题？

你用 Claude Code 跨机器工作，每次新会话都要重新解释上下文：

- 记忆不共享 — 机器 A 学到的东西，机器 B 不知道
- 没法通信 — 两个 Claude Code 实例各干各的
- 任务靠手动 — Markdown 文件复制粘贴
- Token 浪费 — 重复解释 = 白花钱

## 怎么解决？

一个工具包，四个模块：

```
┌─────────────────────────────────────────────────────┐
│              ~/.shared-memory/                       │
│                                                     │
│  🧠 Smart Memory    TF-IDF 语义搜索                  │
│  📋 Task Scheduler  优先级队列 + 自动分配             │
│  🤝 Agent Bridge    WebSocket 跨机通信               │
│  🔌 MCP Server      Claude Code 官方协议             │
│                                                     │
├──────────────┬──────────────────────────────────────┤
│  机器 A       │  机器 B                              │
│  Claude Code  │  Claude Code                        │
│  ↕ 共享记忆    │  ↕ 共享记忆                          │
└──────────────┴──────────────────────────────────────┘
```

## 为什么选我们？

市面上有很多多 agent 框架（Ruflo 56k stars、OpenClaude 28k、AgentScope 26k、Strands 6k），它们功能强大但：

- 需要 Docker / 复杂配置
- 学习曲线陡峭
- 偏向"通用框架"，不是专门给 Claude Code 用户的

**我们是"最后一公里"工具**：

| | 大框架 (Ruflo/OpenClaude) | 本工具 |
|---|---|---|
| 安装 | Docker + 配置文件 | `git clone` + `setup.sh` |
| 上手时间 | 30分钟+ | 60秒 |
| 依赖 | Node.js / Python + 多个包 | 零（纯 Python 标准库） |
| 定位 | 通用多 agent 编排 | Claude Code 专属增强 |
| 适合 | 团队/企业 | 个人开发者 |

**不跟大框架竞争，做轻量补充。**

## 快速开始

```bash
# 克隆
git clone https://github.com/dukeandBaron/claude-code-toolkit.git
cd claude-code-toolkit

# 初始化（创建共享记忆目录）
python agent-bridge/cli.py setup

# 开始使用
python agent-bridge/cli.py status
```

## 功能

### 1. 语义记忆

```bash
# 保存
python agent-bridge/cli.py memory save "3DGS truck PSNR=25.8" --category experiment

# 搜索（按语义，不是关键词）
python agent-bridge/cli.py memory search "3DGS 实验参数"

# 记录 Bug 解决方案
python agent-bridge/cli.py memory bug add "CUDA OOM" "减小 batch size 到 4"
python agent-bridge/cli.py memory bug find "显存不足"
```

### 2. 任务调度

```bash
# 创建任务（带优先级）
python agent-bridge/cli.py task create "跑 3DGS 实验" --priority high

# 查看可执行任务
python agent-bridge/cli.py task ready

# 自动分配给最空闲的 agent
python agent-bridge/cli.py task auto-assign <task_id>

# 完成任务
python agent-bridge/cli.py task update <task_id> --status done --result "PSNR=25.8"
```

### 3. 跨机通信

```bash
# 发送消息
python agent-bridge/cli.py bridge send "实验完成，PSNR=25.8"

# 接收消息
python agent-bridge/cli.py bridge recv

# 同步文件
python agent-bridge/cli.py bridge sync MEMORY.md
```

### 4. MCP 集成

在 Claude Code 配置中添加：

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

MCP 工具：
- `memory_search` — 语义搜索记忆
- `memory_save` — 保存记忆
- `task_create` — 创建任务
- `task_list` — 查看任务
- `task_update` — 更新任务
- `bridge_send` / `bridge_recv` — 跨机通信
- `knowledge_query` — 查询知识库

## 真实用例

**场景 1：个人知识库**
```
Session 1: 学习 3DGS，保存关键参数到记忆
Session 2: 搜索 "3DGS 参数"，立刻召回，不用重新解释
```

**场景 2：跨机器协作**
```
机器 A: 跑完实验，发送结果给机器 B
机器 B: 收到消息，继续分析
```

**场景 3：任务管理**
```
创建任务 "写论文实验部分"，优先级 high
系统自动分配给最空闲的 agent
完成后标记 done，记录结果
```

## 安全

- 100% 本地，数据不出机器
- 跨机通信使用 HMAC-SHA256 认证
- 开源，代码可审计

## 路线图

- [x] 语义记忆（TF-IDF）
- [x] 任务调度（优先级队列）
- [x] 跨机通信（WebSocket）
- [x] MCP 集成
- [ ] 集成 OpenClaude API
- [ ] Web UI
- [ ] VS Code 扩展

## 许可证

MIT License

---

**GitHub**: https://github.com/dukeandBaron/claude-code-toolkit
