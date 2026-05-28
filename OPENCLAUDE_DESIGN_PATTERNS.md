# OpenClaude 设计思路提炼

> 不安装 OpenClaude，只借鉴其架构设计优化我们的 Toolkit

## 核心设计模式

### 1. Provider Profile 管理
OpenClaude 的 `/provider` 命令可以保存多个后端配置：

```json
{
  "providers": {
    "openai": {
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-xxx",
      "model": "gpt-4o"
    },
    "deepseek": {
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "sk-xxx",
      "model": "deepseek-chat"
    },
    "mimo": {
      "base_url": "https://api.xiaomimimo.com/v1",
      "api_key": "xxx",
      "model": "mimo-v2-pro"
    }
  },
  "default": "openai"
}
```

**借鉴价值**：我们的 Toolkit 可以支持多个 LLM 后端，用户可以切换。

### 2. Agent 路由
OpenClaude 可以将不同 agent 路由到不同模型：

```json
{
  "agentRouting": {
    "Explore": "deepseek",      // 探索用便宜模型
    "Plan": "openai",           // 规划用强模型
    "Code": "deepseek",         // 编码用便宜模型
    "Review": "openai",         // 审查用强模型
    "default": "openai"
  }
}
```

**借鉴价值**：根据任务类型选择不同模型，优化成本。

### 3. Session 持久化
OpenClaude 的 gRPC API 支持 session_id：

```protobuf
message ChatRequest {
  string message = 1;
  string working_directory = 2;
  string session_id = 5;  // 跨流会话持久化
}
```

**借鉴价值**：会话可以跨多次调用保持上下文。

### 4. 工具驱动工作流
OpenClaude 内置工具：
- bash（执行命令）
- file read/write/edit（文件操作）
- grep/glob（搜索）
- agents（子 agent）
- tasks（任务管理）
- MCP（外部工具）
- web（网络搜索）

**借鉴价值**：工具应该标准化、可组合。

### 5. 权限控制
OpenClaude 的 ActionRequired 机制：

```protobuf
message ActionRequired {
  string prompt_id = 1;
  string question = 2;
  ActionType type = 3;  // CONFIRM_COMMAND 或 REQUEST_INFORMATION
}
```

**借鉴价值**：敏感操作需要用户确认。

## 可以应用到我们 Toolkit 的改进

### 改进 1：Provider Profile 管理

在 `~/.shared-memory/.providers.json` 中保存 LLM 配置：

```python
class ProviderManager:
    """管理多个 LLM 后端配置"""
    
    def __init__(self):
        self.config_file = Path.home() / ".shared-memory" / ".providers.json"
        self.providers = self._load()
    
    def add(self, name, base_url, api_key, model):
        """添加 provider"""
        self.providers[name] = {
            "base_url": base_url,
            "api_key": api_key,
            "model": model
        }
        self._save()
    
    def get(self, name=None):
        """获取 provider 配置"""
        name = name or self.providers.get("default", "openai")
        return self.providers.get(name)
    
    def list(self):
        """列出所有 provider"""
        return [k for k in self.providers.keys() if k != "default"]
```

### 改进 2：Agent 路由配置

在 `~/.shared-memory/.routing.json` 中配置任务-模型映射：

```python
class AgentRouter:
    """根据任务类型选择不同模型"""
    
    ROUTING_RULES = {
        "explore": "cheap",      // 探索：用便宜模型
        "plan": "strong",        // 规划：用强模型
        "code": "cheap",         // 编码：用便宜模型
        "review": "strong",      // 审查：用强模型
        "default": "balanced"    // 默认：平衡模型
    }
    
    def route(self, task_type):
        """根据任务类型返回 provider"""
        rule = self.ROUTING_RULES.get(task_type, "default")
        return self._get_provider_by_tier(rule)
```

### 改进 3：Session 管理

```python
class SessionManager:
    """管理跨调用的会话上下文"""
    
    def __init__(self):
        self.sessions_file = Path.home() / ".shared-memory" / ".sessions.json"
        self.sessions = self._load()
    
    def create(self, session_id=None):
        """创建新会话"""
        session_id = session_id or str(uuid.uuid4())[:8]
        self.sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.now().isoformat(),
            "messages": [],
            "context": {}
        }
        self._save()
        return session_id
    
    def add_message(self, session_id, role, content):
        """添加消息到会话"""
        if session_id in self.sessions:
            self.sessions[session_id]["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
            self._save()
    
    def get_context(self, session_id, max_messages=10):
        """获取会话上下文"""
        if session_id not in self.sessions:
            return []
        messages = self.sessions[session_id]["messages"]
        return messages[-max_messages:]
```

### 改进 4：工具注册机制

```python
class ToolRegistry:
    """标准化工具注册"""
    
    def __init__(self):
        self.tools = {}
    
    def register(self, name, description, parameters, handler):
        """注册工具"""
        self.tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "handler": handler
        }
    
    def call(self, name, **kwargs):
        """调用工具"""
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")
        return self.tools[name]["handler"](**kwargs)
    
    def list(self):
        """列出所有工具"""
        return [
            {"name": t["name"], "description": t["description"]}
            for t in self.tools.values()
        ]
```

## 实施优先级

| 优先级 | 改进 | 难度 | 价值 |
|--------|------|------|------|
| P0 | Provider Profile | 低 | 高 |
| P1 | Session 管理 | 中 | 高 |
| P2 | Agent 路由 | 中 | 中 |
| P3 | 工具注册 | 低 | 中 |

## 总结

从 OpenClaude 借鉴的核心思路：
1. **配置驱动**：用 JSON 配置文件管理 provider、routing、session
2. **模块化设计**：工具、provider、agent 都是可插拔的
3. **会话持久化**：跨调用保持上下文
4. **成本优化**：根据任务类型选择不同模型

这些改进都不需要安装 OpenClaude，可以直接应用到我们的 Toolkit。
