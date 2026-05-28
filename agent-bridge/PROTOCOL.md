# Agent Bridge Protocol — 两个 Claude Code 实例的网络通信协议

**设计日期**：2026-05-28
**作者**：Hermes Agent

---

## 协议概览

```
┌─────────────┐    HTTP/WebSocket    ┌─────────────┐
│  Agent A    │◄────────────────────►│  Agent B    │
│  (你的电脑)  │    加密通道 (TLS)     │  (对方电脑)  │
│             │                      │             │
│  Hermes     │    JSON-RPC 2.0      │  Hermes     │
│  Claude Code│    消息格式            │  Claude Code│
│  shared-    │                      │  shared-    │
│  memory     │                      │  memory     │
└─────────────┘                      └─────────────┘
```

## 核心设计原则

1. **简单优先**：一个 Python 文件就能跑，不依赖复杂框架
2. **安全第一**：API key 认证 + 可选 TLS 加密
3. **双模支持**：LAN 直连 + WAN 穿透
4. **消息驱动**：JSON-RPC 2.0 标准格式
5. **渐进式**：先跑通，再加功能

---

## 第一部分：协议设计

### 1.1 握手流程

```
Agent A                              Agent B
  │                                    │
  │─── DISCOVER (UDP broadcast) ──────►│  [LAN only]
  │◄── ANNOUNCE (UDP reply) ──────────│  [LAN only]
  │                                    │
  │─── CONNECT (HTTP POST) ──────────►│
  │    { agent_id, token, version }    │
  │                                    │
  │◄── ACCEPT (HTTP 200) ────────────│
  │    { session_id, capabilities }    │
  │                                    │
  │◄═══ WebSocket upgrade ═══════════►│
  │                                    │
  │◄──► 双向消息通道 ◄──────────────►│
  │    (JSON-RPC 2.0 over WebSocket)   │
```

### 1.2 消息格式 (JSON-RPC 2.0)

```json
{
  "jsonrpc": "2.0",
  "method": "agent.query",
  "params": {
    "type": "memory_sync",
    "content": {
      "file": "MEMORY.md",
      "operation": "append",
      "data": "- [2026-05-28] 新增条目"
    }
  },
  "id": "msg_001"
}
```

### 1.3 支持的方法

| 方法 | 说明 | 方向 |
|------|------|------|
| `agent.hello` | 握手 | A→B |
| `agent.heartbeat` | 心跳 | 双向 |
| `memory.read` | 读取共享记忆 | A→B |
| `memory.write` | 写入共享记忆 | A→B |
| `memory.sync` | 同步整个文件 | 双向 |
| `task.publish` | 发布任务 | A→B |
| `task.claim` | 领取任务 | A→B |
| `task.complete` | 完成任务 | A→B |
| `message.send` | 自由消息 | 双向 |
| `file.transfer` | 传输文件 | A→B |

### 1.4 认证

```
请求头：
  X-Agent-ID: hermes-agent-a
  X-Agent-Token: sha256(agent_id + shared_secret + timestamp)
  X-Timestamp: 2026-05-28T16:30:00+08:00

验证规则：
  1. 检查 timestamp 在 ±5 分钟内
  2. 重新计算 token，比对一致
  3. 检查 agent_id 在白名单中
```

---

## 第二部分：LAN 实现（同 WiFi）

### 2.1 发现机制

方案 A：UDP 广播（自动发现）
```
Agent A 广播: "I am hermes-agent-a, port 9527"
Agent B 收到: "I am hermes-agent-b, port 9528"
双方自动建立连接
```

方案 B：静态 IP（手动配置）
```
Agent A 配置: peer = 192.168.1.100:9527
Agent B 配置: peer = 192.168.1.50:9528
直接连接
```

### 2.2 端口选择

默认端口：9527（可配置）
备用端口：9528-9530

---

## 第三部分：WAN 实现（不同 WiFi）

### 3.1 方案对比

| 方案 | 延迟 | 安全性 | 复杂度 | 成本 |
|------|------|--------|--------|------|
| Tailscale | 低 | 高（WireGuard） | 低 | 免费 |
| ZeroTier | 低 | 高 | 低 | 免费 |
| frp 自建 | 中 | 中 | 高 | 服务器费 |
| ngrok | 中 | 高 | 低 | 免费/付费 |
| 中继服务器 | 高 | 中 | 高 | 服务器费 |

### 3.2 推荐：Tailscale（最简单）

```
1. 两台电脑都装 Tailscale
2. 登录同一个账号
3. 自动获得虚拟 IP（100.x.x.x）
4. 用虚拟 IP 直接通信，和 LAN 一样简单
5. WireGuard 加密，安全可靠
```

---

## 第四部分：安全模型

### 4.1 传输安全
- LAN：可选 TLS（自签名证书）
- WAN：必须 TLS（Tailscale 自带 WireGuard）

### 4.2 认证安全
- 共享密钥（手动交换，不通过网络）
- 时间戳防重放
- Agent ID 白名单

### 4.3 数据安全
- 不传输 API Key
- 不传输 Session 历史
- 只传输共享记忆和任务数据
- 敏感字段可选加密

---

## 第五部分：实现代码

见 `agent_bridge_server.py` 和 `agent_bridge_client.py`
