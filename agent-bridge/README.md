# Agent Bridge — Claude Code 跨机器通信

让两台电脑上的 Claude Code 实现对话、记忆同步、任务协作。

## 架构

```
Machine A                                Machine B
┌──────────────────┐                    ┌──────────────────┐
│   Claude Code    │                    │   Claude Code    │
│                  │                    │                  │
│ 读写文件 ────────┤                    ├──────── 读写文件  │
│ ~/.shared-memory/│                    │ ~/.shared-memory/ │
│                  │                    │                  │
│ bridge.py        │◄═══ WebSocket ═══►│ bridge.py        │
│ (后台同步)        │    加密通道         │ (后台同步)        │
└──────────────────┘                    └──────────────────┘
```

## Claude Code 怎么用

### 方式 1：文件模式（最简单，无需网络）

两台电脑通过 Syncthing/Git 共享 `~/.shared-memory/` 目录，
Claude Code 直接读写文件即可。bridge.py 只负责消息收发。

```bash
# Claude Code 在终端执行：
python agent-bridge/bridge.py send "3DGS truck 跑完了，PSNR=25.80"
python agent-bridge/bridge.py recv
python agent-bridge/bridge.py status
```

### 方式 2：网络模式（实时同步）

```bash
# 你的电脑：启动后台同步
python agent-bridge/bridge.py start

# 对方电脑：连接你的 IP
python agent-bridge/bridge.py connect 192.168.1.50:9527
python agent-bridge/bridge.py start
```

### 方式 3：LAN 自动发现

```bash
python agent-bridge/bridge.py discover
```

## 完整命令参考

```bash
python bridge.py status                    # 查看状态
python bridge.py send "消息内容"            # 发送消息
python bridge.py recv                      # 读取未读消息
python bridge.py sync MEMORY.md            # 同步指定文件
python bridge.py file report.pdf           # 传输文件
python bridge.py discover                  # LAN 自动发现
python bridge.py start                     # 启动后台同步服务
python bridge.py connect 192.168.1.50:9527 # 配置对端地址
```

## Claude Code 集成

在 CLAUDE.md 中添加指令，让 Claude Code 自动使用 bridge：

```markdown
## 跨机器通信
- 发送消息：`python agent-bridge/bridge.py send "内容"`
- 读取消息：`python agent-bridge/bridge.py recv`
- 查看状态：`python agent-bridge/bridge.py status`
- 收到新消息时自动读取并回复
```

## 同 WiFi vs 不同 WiFi

| 场景 | 方案 | 命令 |
|------|------|------|
| 同 WiFi | 直接 IP 连接 | `python bridge.py connect 192.168.x.x:9527` |
| 同 WiFi | UDP 自动发现 | `python bridge.py discover` |
| 不同 WiFi | Tailscale | 两台装 Tailscale → 用虚拟 IP 连接 |
| 不同 WiFi | ngrok | `ngrok tcp 9527` → 用 ngrok 地址连接 |
| 无网络 | Syncthing | 文件自动同步，无需 bridge 网络功能 |

## 文件说明

| 文件 | 用途 |
|------|------|
| `bridge.py` | **主工具** — Claude Code 直接调用的 CLI |
| `bridge_server.py` | WebSocket 服务器（高级用法） |
| `bridge_client.py` | WebSocket 客户端（高级用法） |
| `protocol.py` | JSON-RPC 2.0 协议层 |
| `config.py` | 配置模块 |
| `PROTOCOL.md` | 协议设计文档 |
| `README.md` | 本文件 |

## 安全

- HMAC-SHA256 令牌认证
- 时间戳防重放（±5 分钟）
- 密钥通过文件交换，不通过网络
- 路径遍历防护
