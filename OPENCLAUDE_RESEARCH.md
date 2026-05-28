# OpenClaude 调研报告

## 基本信息

| 项目 | 详情 |
|------|------|
| 仓库 | Gitlawb/openclaude |
| Stars | 27,962 |
| 语言 | TypeScript |
| 许可证 | MIT |
| 创建时间 | 2026-04-01 |
| 最后更新 | 2026-05-28 |

## 核心特性

### 1. 多后端支持
- OpenAI-compatible APIs (OpenAI, OpenRouter, DeepSeek, Groq, Mistral, LM Studio)
- Gemini
- GitHub Models
- Codex OAuth / Codex
- Ollama (本地模型)
- Atomic Chat
- 小米 MiMo

### 2. Agent 路由
支持将不同 agent 路由到不同模型：
```json
{
  "agentModels": {
    "deepseek-v4-flash": {
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "***"
    }
  },
  "agentRouting": {
    "Explore": "deepseek-v4-flash",
    "Plan": "gpt-4o",
    "default": "gpt-4o"
  }
}
```

### 3. gRPC 服务（关键集成点）
OpenClaude 可以作为 headless gRPC 服务运行：

```bash
# 启动 gRPC 服务器
npm run dev:grpc

# 默认端口: localhost:50051
# 环境变量:
#   GRPC_PORT=50051
#   GRPC_HOST=localhost
```

### 4. gRPC API 定义
```protobuf
service AgentService {
  rpc Chat(stream ClientMessage) returns (stream ServerMessage);
}

// 客户端消息
message ClientMessage {
  oneof payload {
    ChatRequest request = 2;
    UserInput input = 3;
    CancelSignal cancel = 4;
  }
}

// 服务端消息
message ServerMessage {
  oneof event {
    TextChunk text_chunk = 1;
    ToolCallStart tool_start = 2;
    ToolCallResult tool_result = 3;
    ActionRequired action_required = 4;
    FinalResponse done = 5;
    ErrorResponse error = 6;
  }
}
```

### 5. Python 支持
- 仓库中有 `python/` 目录，包含 provider 辅助工具
- 需要从 proto 文件生成 Python gRPC 客户端

## 集成方案

### 方案 1：gRPC 客户端集成（推荐）
```
我们的 Toolkit
  ↓
gRPC 客户端 → OpenClaude gRPC 服务器
  ↓
OpenClaude 执行编码任务
  ↓
结果返回到我们的共享记忆
```

**优点：**
- 直接使用 OpenClaude 的完整功能
- 支持所有 OpenClaude 支持的后端
- 可以利用 OpenClaude 的 agent 路由

**实现步骤：**
1. 从 proto 文件生成 Python gRPC 客户端
2. 在我们的 CLI 中添加 `openclaude` 命令
3. 将 OpenClaude 的结果保存到共享记忆

### 方案 2：MCP 集成
```
OpenClaude (支持 MCP)
  ↓
我们的 MCP Server
  ↓
共享记忆 + 任务调度
```

**优点：**
- 利用现有的 MCP 支持
- 更松耦合

**缺点：**
- 需要 OpenClaude 主动调用我们的 MCP 工具

### 方案 3：文件系统集成
```
OpenClaude
  ↓
读写 ~/.shared-memory/ 目录
  ↓
我们的 Toolkit 读取同一目录
```

**优点：**
- 最简单
- 零代码修改

**缺点：**
- 需要手动配置 OpenClaude 的工作目录

## 建议实施路径

### 阶段 1：快速验证（1-2天）
1. 安装 OpenClaude：`npm install -g @gitlawb/openclaude`
2. 配置 Ollama 后端（本地模型）
3. 测试基本功能

### 阶段 2：gRPC 集成（3-5天）
1. 从 proto 文件生成 Python 客户端
2. 实现 `openclaude` CLI 命令
3. 集成到共享记忆系统

### 阶段 3：深度集成（1-2周）
1. 实现 agent 路由配置
2. 添加任务队列集成
3. 实现跨机器 OpenClaude 协作

## 代码示例：Python gRPC 客户端

```python
import grpc
from openclaude_pb2 import *
from openclaude_pb2_grpc import AgentServiceStub

def chat_with_openclaude(message, working_dir="."):
    channel = grpc.insecure_channel('localhost:50051')
    stub = AgentServiceStub(channel)
    
    def generate_requests():
        yield ClientMessage(request=ChatRequest(
            message=message,
            working_directory=working_dir
        ))
    
    for response in stub.Chat(generate_requests()):
        if response.text_chunk:
            print(response.text_chunk.text, end="")
        elif response.tool_start:
            print(f"\n[Tool: {response.tool_start.tool_name}]")
        elif response.done:
            print(f"\n\nDone! Tokens: {response.done.prompt_tokens} + {response.done.completion_tokens}")

# 使用
chat_with_openclaude("帮我优化这段代码...")
```

## 与我们 Toolkit 的互补性

| 功能 | OpenClaude | 我们的 Toolkit | 互补性 |
|------|-----------|---------------|--------|
| 编码执行 | ✅ 强 | ❌ 弱 | OpenClaude 负责执行 |
| 共享记忆 | ❌ 无 | ✅ 强 | 我们负责记忆 |
| 任务调度 | ❌ 无 | ✅ 强 | 我们负责调度 |
| 多后端 | ✅ 强 | ❌ 无 | OpenClaude 负责后端 |
| MCP 支持 | ✅ 有 | ✅ 有 | 可以互通 |

## 结论

**OpenClaude 是理想的集成对象：**
1. 功能互补：它做编码执行，我们做记忆和调度
2. 技术兼容：gRPC + MCP 双重集成点
3. 社区活跃：28k stars，持续更新
4. 架构清晰：gRPC 服务便于程序化调用

**建议：先快速验证 Ollama 本地模型，再实现 gRPC 集成。**
