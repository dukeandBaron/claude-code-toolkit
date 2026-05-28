"""
Claude Code Toolkit — MCP Server
Model Context Protocol 官方协议支持

让 Claude Code 通过标准 MCP 协议访问共享记忆、任务调度、跨机通信。

使用方式：
  在 Claude Code 的 MCP 配置中添加：
  {
    "mcpServers": {
      "claude-toolkit": {
        "command": "python",
        "args": ["path/to/mcp_server.py"],
        "env": {}
      }
    }
  }

然后 Claude Code 就能直接使用以下工具：
  - memory_search: 语义搜索共享记忆
  - memory_save: 保存新记忆
  - task_create: 创建智能任务
  - task_list: 查看任务队列
  - task_update: 更新任务状态
  - bridge_send: 发送跨机消息
  - bridge_recv: 接收跨机消息
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 导入现有模块
sys.path.insert(0, str(Path(__file__).parent))
from smart_memory import SmartMemory, TFIDFVectorizer

# ── MCP 协议实现 ─────────────────────────────────────────

class MCPServer:
    """MCP Server 实现"""
    
    def __init__(self):
        self.memory = SmartMemory()
        self.tasks = TaskManager()
        self.tools = self._register_tools()
    
    def _register_tools(self) -> Dict[str, Dict]:
        """注册所有可用工具"""
        return {
            "memory_search": {
                "name": "memory_search",
                "description": "语义搜索共享记忆库。使用 TF-IDF 向量检索，找到最相关的记忆条目。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词或问题"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "返回结果数量",
                            "default": 5
                        },
                        "category": {
                            "type": "string",
                            "description": "可选：按分类过滤 (general/bug_fix/decision/experiment)"
                        }
                    },
                    "required": ["query"]
                }
            },
            "memory_save": {
                "name": "memory_save",
                "description": "保存新的记忆条目到共享记忆库",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "记忆内容"
                        },
                        "category": {
                            "type": "string",
                            "description": "分类 (general/bug_fix/decision/experiment)",
                            "default": "general"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "标签列表"
                        }
                    },
                    "required": ["text"]
                }
            },
            "task_create": {
                "name": "task_create",
                "description": "创建新的智能任务",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "任务标题"
                        },
                        "description": {
                            "type": "string",
                            "description": "详细描述"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "urgent"],
                            "description": "优先级",
                            "default": "medium"
                        },
                        "assignee": {
                            "type": "string",
                            "description": "指派给谁 (agent_id)"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "标签"
                        }
                    },
                    "required": ["title"]
                }
            },
            "task_list": {
                "name": "task_list",
                "description": "查看任务队列",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "done", "failed", "all"],
                            "description": "按状态过滤",
                            "default": "all"
                        },
                        "assignee": {
                            "type": "string",
                            "description": "按指派人过滤"
                        }
                    }
                }
            },
            "task_update": {
                "name": "task_update",
                "description": "更新任务状态",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "任务 ID"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "done", "failed"],
                            "description": "新状态"
                        },
                        "result": {
                            "type": "string",
                            "description": "任务结果（完成时填写）"
                        }
                    },
                    "required": ["task_id", "status"]
                }
            },
            "bridge_send": {
                "name": "bridge_send",
                "description": "发送消息到另一台机器的 Claude Code",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "消息内容"
                        },
                        "target": {
                            "type": "string",
                            "description": "目标 agent_id（可选，默认广播）"
                        }
                    },
                    "required": ["message"]
                }
            },
            "bridge_recv": {
                "name": "bridge_recv",
                "description": "接收来自其他机器的消息",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "最多返回几条消息",
                            "default": 10
                        }
                    }
                }
            },
            "knowledge_query": {
                "name": "knowledge_query",
                "description": "查询知识库（Bug 解决方案、技术决策、实验记录）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "查询内容"
                        },
                        "type": {
                            "type": "string",
                            "enum": ["bugs", "decisions", "experiments", "all"],
                            "description": "知识类型",
                            "default": "all"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理 MCP 请求"""
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")
        
        try:
            if method == "initialize":
                return self._response(req_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "claude-code-toolkit",
                        "version": "1.0.0"
                    }
                })
            
            elif method == "tools/list":
                return self._response(req_id, {
                    "tools": list(self.tools.values())
                })
            
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                result = await self._call_tool(tool_name, arguments)
                return self._response(req_id, {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]
                })
            
            else:
                return self._error(req_id, -32601, f"Method not found: {method}")
        
        except Exception as e:
            return self._error(req_id, -32000, str(e))
    
    async def _call_tool(self, name: str, args: Dict) -> Any:
        """调用具体工具"""
        if name == "memory_search":
            results = self.memory.recall(
                args["query"],
                top_k=args.get("top_k", 5),
                category=args.get("category")
            )
            return {"results": results, "count": len(results)}
        
        elif name == "memory_save":
            result = self.memory.remember(
                args["text"],
                category=args.get("category", "general"),
                tags=args.get("tags", [])
            )
            return {"success": True, "memory": result}
        
        elif name == "task_create":
            task = self.tasks.create(
                title=args["title"],
                description=args.get("description", ""),
                priority=args.get("priority", "medium"),
                assignee=args.get("assignee"),
                tags=args.get("tags", [])
            )
            return {"success": True, "task": task}
        
        elif name == "task_list":
            tasks = self.tasks.list_tasks(
                status=args.get("status", "all"),
                assignee=args.get("assignee")
            )
            return {"tasks": tasks, "count": len(tasks)}
        
        elif name == "task_update":
            task = self.tasks.update(
                task_id=args["task_id"],
                status=args["status"],
                result=args.get("result")
            )
            return {"success": True, "task": task}
        
        elif name == "bridge_send":
            # 导入 bridge 模块
            from bridge import send_message, get_config
            config = get_config()
            send_message(args["message"], config)
            return {"success": True, "message": "已发送"}
        
        elif name == "bridge_recv":
            from bridge import recv_messages, get_config
            config = get_config()
            messages = recv_messages(config, limit=args.get("limit", 10))
            return {"messages": messages, "count": len(messages)}
        
        elif name == "knowledge_query":
            results = self._query_knowledge(args["query"], args.get("type", "all"))
            return {"results": results, "count": len(results)}
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    def _query_knowledge(self, query: str, kb_type: str) -> List[Dict]:
        """查询知识库"""
        results = []
        
        if kb_type in ("bugs", "all"):
            bugs = self.memory.find_bug_solution(query, top_k=3)
            results.extend([{**b, "type": "bug"} for b in bugs])
        
        if kb_type in ("experiments", "all"):
            exps = self.memory.find_experiment(query, top_k=3)
            results.extend([{**e, "type": "experiment"} for e in exps])
        
        if kb_type in ("decisions", "all"):
            # 搜索决策
            for d in self.memory.knowledge.get("decisions", []):
                if query.lower() in d.get("decision", "").lower() or \
                   query.lower() in d.get("reason", "").lower():
                    results.append({**d, "type": "decision"})
        
        return results[:10]
    
    def _response(self, req_id: Any, result: Any) -> Dict:
        """成功响应"""
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    
    def _error(self, req_id: Any, code: int, message: str) -> Dict:
        """错误响应"""
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


class TaskManager:
    """智能任务管理器"""
    
    def __init__(self):
        self.tasks_file = Path.home() / ".shared-memory" / ".tasks.json"
        self.tasks = self._load()
    
    def _load(self) -> List[Dict]:
        """加载任务"""
        if self.tasks_file.exists():
            try:
                return json.loads(self.tasks_file.read_text(encoding="utf-8"))
            except:
                return []
        return []
    
    def _save(self):
        """保存任务"""
        self.tasks_file.write_text(
            json.dumps(self.tasks, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def create(self, title: str, description: str = "", priority: str = "medium",
               assignee: str = None, tags: List[str] = None) -> Dict:
        """创建任务"""
        import uuid
        from datetime import datetime
        
        task = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "description": description,
            "status": "pending",
            "priority": priority,
            "assignee": assignee,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "result": None
        }
        
        self.tasks.append(task)
        self._save()
        return task
    
    def list_tasks(self, status: str = "all", assignee: str = None) -> List[Dict]:
        """列出任务"""
        filtered = self.tasks
        
        if status != "all":
            filtered = [t for t in filtered if t["status"] == status]
        
        if assignee:
            filtered = [t for t in filtered if t.get("assignee") == assignee]
        
        # 按优先级排序
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        filtered.sort(key=lambda t: priority_order.get(t.get("priority", "medium"), 2))
        
        return filtered
    
    def update(self, task_id: str, status: str, result: str = None) -> Dict:
        """更新任务"""
        from datetime import datetime
        
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = status
                task["updated_at"] = datetime.now().isoformat()
                if result:
                    task["result"] = result
                self._save()
                return task
        
        raise ValueError(f"Task not found: {task_id}")


# ── stdio 传输 ──────────────────────────────────────────

async def stdio_server():
    """通过 stdio 运行 MCP server"""
    server = MCPServer()
    
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
    
    writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, asyncio.get_event_loop())
    
    buffer = ""
    while True:
        data = await reader.read(4096)
        if not data:
            break
        
        buffer += data.decode("utf-8")
        
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            
            try:
                request = json.loads(line)
                response = await server.handle_request(request)
                writer.write((json.dumps(response) + "\n").encode("utf-8"))
                await writer.drain()
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"}
                }
                writer.write((json.dumps(error_response) + "\n").encode("utf-8"))
                await writer.drain()


if __name__ == "__main__":
    asyncio.run(stdio_server())
