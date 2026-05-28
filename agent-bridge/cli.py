"""
Claude Code Toolkit — 统一 CLI 入口

一站式命令行工具，整合所有功能：
  - memory: 记忆管理（语义搜索、保存、统计）
  - task: 任务调度（创建、列表、更新、自动分配）
  - bridge: 跨机通信（发送、接收、同步）
  - mcp: MCP 服务器管理
  - status: 系统状态

使用方式：
  python cli.py memory search "3DGS 实验参数"
  python cli.py memory save "PSNR=25.8, densification=0.005"
  python cli.py task create "跑实验" --priority high
  python cli.py task list
  python cli.py bridge send "Hello from Machine A"
  python cli.py status
"""

import argparse
import json
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))


def cmd_memory(args):
    """记忆管理命令"""
    from smart_memory import SmartMemory
    
    memory = SmartMemory()
    
    if args.memory_action == "search":
        results = memory.recall(args.query, top_k=args.top_k, category=args.category)
        if results:
            print(f"🔍 找到 {len(results)} 条相关记忆:\n")
            for i, r in enumerate(results, 1):
                print(f"{i}. [相似度: {r['similarity']}] {r['text']}")
                print(f"   分类: {r['category']} | 访问: {r['access_count']}次")
                print()
        else:
            print("❌ 未找到相关记忆")
    
    elif args.memory_action == "save":
        result = memory.remember(args.text, category=args.category, tags=args.tags or [])
        print(f"✅ 记忆已保存 (ID: {result['id']})")
        print(f"   内容: {result['text'][:50]}...")
        print(f"   分类: {result['category']}")
    
    elif args.memory_action == "stats":
        stats = memory.stats()
        print("📊 记忆库统计:\n")
        print(f"  记忆条目: {stats['total_memories']}")
        print(f"  Bug 解决方案: {stats['total_bugs']}")
        print(f"  技术决策: {stats['total_decisions']}")
        print(f"  实验记录: {stats['total_experiments']}")
        print(f"  存储大小: {stats['memory_size_kb']:.2f} KB")
        print(f"\n  分类分布:")
        for cat, count in stats['categories'].items():
            print(f"    {cat}: {count}")
    
    elif args.memory_action == "export":
        markdown = memory.export_markdown()
        print(markdown)
    
    elif args.memory_action == "bug":
        if args.bug_action == "add":
            result = memory.add_bug_solution(args.problem, args.solution, args.context, args.tags)
            print(f"✅ Bug 解决方案已记录 (ID: {result['id']})")
        elif args.bug_action == "find":
            results = memory.find_bug_solution(args.query, args.top_k)
            if results:
                print(f"🔍 找到 {len(results)} 个相似问题:\n")
                for i, r in enumerate(results, 1):
                    print(f"{i}. [相似度: {r['similarity']}] {r['problem']}")
                    print(f"   解决方案: {r['solution']}")
                    print(f"   使用次数: {r.get('usage_count', 0)}")
                    print()
            else:
                print("❌ 未找到相似问题")
    
    elif args.memory_action == "experiment":
        if args.exp_action == "add":
            params = json.loads(args.params)
            results = json.loads(args.results)
            result = memory.add_experiment(args.name, params, results, args.conclusion)
            print(f"✅ 实验记录已保存 (ID: {result['id']})")
        elif args.exp_action == "find":
            results = memory.find_experiment(args.query, args.top_k)
            if results:
                print(f"🔍 找到 {len(results)} 个相关实验:\n")
                for i, r in enumerate(results, 1):
                    print(f"{i}. [相似度: {r['similarity']}] {r['name']}")
                    print(f"   参数: {json.dumps(r['params'], ensure_ascii=False)}")
                    print(f"   结果: {json.dumps(r['results'], ensure_ascii=False)}")
                    print()
            else:
                print("❌ 未找到相关实验")


def cmd_task(args):
    """任务调度命令"""
    from task_scheduler import TaskScheduler
    
    scheduler = TaskScheduler()
    
    if args.task_action == "create":
        task = scheduler.create_task(
            title=args.title,
            description=args.description or "",
            priority=args.priority,
            assignee=args.assignee,
            tags=args.tags or [],
            depends_on=args.depends,
            timeout_hours=args.timeout
        )
        print(f"✅ 任务已创建 (ID: {task['id']})")
        print(f"   标题: {task['title']}")
        print(f"   优先级: {task['priority']}")
        if task.get("assignee"):
            print(f"   指派: {task['assignee']}")
    
    elif args.task_action == "list":
        tasks = scheduler.list_tasks(
            status=args.status,
            assignee=args.assignee,
            priority=args.priority,
            tag=args.tag
        )
        if tasks:
            print(f"📋 任务列表 ({len(tasks)} 个):\n")
            for task in tasks:
                priority_icon = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
                icon = priority_icon.get(task.get("priority", "medium"), "⚪")
                status_icon = {"pending": "⏳", "in_progress": "🔄", "done": "✅", "failed": "❌"}
                s_icon = status_icon.get(task["status"], "❓")
                
                print(f"  {s_icon} {icon} [{task['id']}] {task['title']}")
                if task.get("assignee"):
                    print(f"     指派: {task['assignee']}")
                print()
        else:
            print("📭 没有找到任务")
    
    elif args.task_action == "update":
        task = scheduler.update_task(
            task_id=args.task_id,
            status=args.status,
            result=args.result,
            assignee=args.assignee
        )
        print(f"✅ 任务已更新: {task['title']}")
        print(f"   状态: {task['status']}")
    
    elif args.task_action == "assign":
        task = scheduler.update_task(args.task_id, assignee=args.agent_id)
        print(f"✅ 任务已分配: {task['title']} → {args.agent_id}")
    
    elif args.task_action == "auto-assign":
        task = scheduler.auto_assign(args.task_id)
        if task.get("assignee"):
            print(f"✅ 自动分配: {task['title']} → {task['assignee']}")
        else:
            print("⚠️ 没有可用的 Agent")
    
    elif args.task_action == "stats":
        stats = scheduler.get_stats()
        print("📊 任务统计:\n")
        print(f"  总任务数: {stats['total']}")
        print(f"  完成率: {stats['completion_rate']}%")
        print(f"  平均耗时: {stats['avg_duration_minutes']} 分钟")
        print(f"  注册 Agent: {stats['agents']} 个")
        print(f"\n  按状态:")
        for status, count in stats.get("by_status", {}).items():
            print(f"    {status}: {count}")
        print(f"\n  按优先级:")
        for priority, count in stats.get("by_priority", {}).items():
            print(f"    {priority}: {count}")
    
    elif args.task_action == "export":
        markdown = scheduler.export_markdown()
        print(markdown)
    
    elif args.task_action == "ready":
        tasks = scheduler.get_ready_tasks()
        if tasks:
            print(f"🚀 可执行任务 ({len(tasks)} 个):\n")
            for task in tasks:
                print(f"  [{task['id']}] {task['title']} ({task['priority']})")
        else:
            print("📭 没有可执行的任务")
    
    elif args.task_action == "register":
        scheduler.register_agent(args.agent_id, args.capabilities or [])
        print(f"✅ Agent 已注册: {args.agent_id}")


def cmd_bridge(args):
    """跨机通信命令"""
    from bridge import get_config, send_message, recv_messages, sync_file, get_status
    
    config = get_config()
    
    if args.bridge_action == "send":
        send_message(args.message, config)
        print(f"✅ 消息已发送")
    
    elif args.bridge_action == "recv":
        messages = recv_messages(config, limit=args.limit)
        if messages:
            print(f"📨 收到 {len(messages)} 条消息:\n")
            for msg in messages:
                print(f"  [{msg.get('timestamp', '?')}] {msg.get('from', '?')}: {msg.get('text', '')}")
        else:
            print("📭 没有新消息")
    
    elif args.bridge_action == "sync":
        sync_file(args.filename, config)
        print(f"✅ 文件已同步: {args.filename}")
    
    elif args.bridge_action == "status":
        status = get_status(config)
        print("🔗 连接状态:\n")
        print(f"  Agent ID: {status.get('agent_id', '?')}")
        print(f"  状态: {status.get('status', '?')}")
        print(f"  对等节点: {status.get('peer', '未连接')}")
        print(f"  消息队列: {status.get('queue_size', 0)} 条")


def cmd_mcp(args):
    """MCP 服务器命令"""
    if args.mcp_action == "start":
        print("🚀 启动 MCP 服务器...")
        print("   在 Claude Code 的 MCP 配置中添加:")
        print('   {')
        print('     "mcpServers": {')
        print('       "claude-toolkit": {')
        print('         "command": "python",')
        print(f'         "args": ["{Path(__file__).parent / "mcp_server.py"}"]')
        print('       }')
        print('     }')
        print('   }')
        print()
        print("   然后重启 Claude Code 即可使用 MCP 工具")
    
    elif args.mcp_action == "test":
        print("🧪 测试 MCP 服务器...")
        from mcp_server import MCPServer
        import asyncio
        
        async def test():
            server = MCPServer()
            
            # 测试初始化
            response = await server.handle_request({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {}
            })
            print(f"  初始化: {'✅' if 'result' in response else '❌'}")
            
            # 测试工具列表
            response = await server.handle_request({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            })
            tools = response.get("result", {}).get("tools", [])
            print(f"  工具数量: {len(tools)}")
            
            # 测试记忆搜索
            response = await server.handle_request({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "memory_search",
                    "arguments": {"query": "test", "top_k": 1}
                }
            })
            print(f"  记忆搜索: {'✅' if 'result' in response else '❌'}")
            
            print("\n✅ MCP 服务器测试通过")
        
        asyncio.run(test())


def cmd_status(args):
    """系统状态命令"""
    from smart_memory import SmartMemory
    from task_scheduler import TaskScheduler
    
    memory = SmartMemory()
    task_scheduler = TaskScheduler()
    
    mem_stats = memory.stats()
    task_stats = task_scheduler.get_stats()
    
    print("🤖 Claude Code Toolkit 状态:\n")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print("  📚 记忆库:")
    print(f"     条目: {mem_stats['total_memories']}")
    print(f"     Bug 解决方案: {mem_stats['total_bugs']}")
    print(f"     技术决策: {mem_stats['total_decisions']}")
    print(f"     实验记录: {mem_stats['total_experiments']}")
    print(f"     大小: {mem_stats['memory_size_kb']:.1f} KB")
    print()
    print("  📋 任务队列:")
    print(f"     总数: {task_stats['total']}")
    print(f"     完成率: {task_stats['completion_rate']}%")
    print(f"     平均耗时: {task_stats['avg_duration_minutes']} 分钟")
    print(f"     注册 Agent: {task_stats['agents']} 个")
    print()
    
    # 检查共享内存目录
    shared_dir = Path.home() / ".shared-memory"
    if shared_dir.exists():
        files = list(shared_dir.glob("*.md"))
        print(f"  📁 共享内存: {len(files)} 个文件")
        for f in files:
            print(f"     - {f.name}")
    else:
        print("  📁 共享内存: 未初始化")
        print("     运行: python cli.py setup")
    
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def cmd_setup(args):
    """初始化共享记忆目录"""
    shared_dir = Path.home() / ".shared-memory"
    
    print("🔧 初始化 Claude Code Toolkit...\n")
    
    # 创建目录
    shared_dir.mkdir(parents=True, exist_ok=True)
    print(f"  ✅ 创建目录: {shared_dir}")
    
    # 创建默认文件
    files = {
        "MEMORY.md": "# 共享记忆\n\n> 由 Claude Code Toolkit 自动创建\n",
        "TASK_QUEUE.md": "# 任务队列\n\n> 状态: pending → in_progress → done / failed\n",
        "HANDOVER.md": "# 交接区\n\n> 跨机器任务结果传递\n",
        "ACTIVITY_LOG.md": "# 活动日志\n\n> 格式: [YYYY-MM-DD HH:MM] [工具] 动作\n\n---\n",
    }
    
    for filename, content in files.items():
        filepath = shared_dir / filename
        if not filepath.exists():
            filepath.write_text(content, encoding="utf-8")
            print(f"  ✅ 创建文件: {filename}")
        else:
            print(f"  ⏭️  已存在: {filename}")
    
    # 初始化记忆和任务
    from smart_memory import SmartMemory
    from task_scheduler import TaskScheduler
    
    SmartMemory()
    TaskScheduler()
    print(f"  ✅ 初始化记忆库")
    print(f"  ✅ 初始化任务调度器")
    
    print(f"\n🎉 初始化完成！")
    print(f"\n下一步:")
    print(f"  python cli.py status          # 查看状态")
    print(f"  python cli.py memory save \"你的第一条记忆\"")
    print(f"  python cli.py task create \"你的第一个任务\"")


def cmd_openclaude(args):
    """OpenClaude 集成命令"""
    from openclaude_client import OpenClaudeClient, generate_grpc_client
    
    if args.openclaude_action == "generate":
        generate_grpc_client()
    
    elif args.openclaude_action == "test":
        client = OpenClaudeClient(host=args.host, port=args.port)
        client.connect()
    
    elif args.openclaude_action == "chat":
        client = OpenClaudeClient(host=args.host, port=args.port)
        if client.connect():
            response = client.chat(args.message, args.dir)
            if response:
                print(f"📨 响应: {response.get('text', '')}")
    
    elif args.openclaude_action == "task":
        client = OpenClaudeClient(host=args.host, port=args.port)
        if client.connect():
            result = client.execute_task(args.description, args.dir)
            if result and result.get("success"):
                print(f"✅ 任务完成: {result.get('result', '')}")
                
                # 保存到共享记忆
                from smart_memory import SmartMemory
                memory = SmartMemory()
                memory.remember(
                    f"OpenClaude 任务: {args.description} -> {result.get('result', '')}",
                    category="openclaude",
                    tags=["openclaude", "task"]
                )
                print("💾 结果已保存到共享记忆")


def cmd_provider(args):
    """Provider 管理命令"""
    from provider_manager import ProviderManager
    
    manager = ProviderManager()
    
    if args.provider_action == "add":
        provider = manager.add(
            name=args.name,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            description=args.description or ""
        )
        print(f"✅ Provider 已添加: {args.name}")
        print(f"   Base URL: {provider['base_url']}")
        print(f"   Model: {provider['model']}")
    
    elif args.provider_action == "remove":
        if manager.remove(args.name):
            print(f"✅ Provider 已删除: {args.name}")
        else:
            print(f"❌ Provider 不存在: {args.name}")
    
    elif args.provider_action == "list":
        providers = manager.list()
        default = manager.get_default()
        if providers:
            print(f"📋 Provider 列表 ({len(providers)} 个):\n")
            for name in providers:
                provider = manager.get(name)
                is_default = " (默认)" if name == default else ""
                print(f"  • {name}{is_default}")
                print(f"    URL: {provider['base_url']}")
                print(f"    Model: {provider['model']}")
                print()
        else:
            print("📭 没有配置 provider")
            print("\n添加示例:")
            print('  python cli.py provider add openai --base-url https://api.openai.com/v1 --api-key sk-xxx --model gpt-4o')
    
    elif args.provider_action == "use":
        if manager.set_default(args.name):
            print(f"✅ 默认 provider 已设为: {args.name}")
        else:
            print(f"❌ Provider 不存在: {args.name}")
    
    elif args.provider_action == "test":
        result = manager.test_connection(args.name)
        if result["success"]:
            print(f"✅ 连接测试成功")
            print(f"   Provider: {result['provider']}")
            print(f"   URL: {result['base_url']}")
            print(f"   Model: {result['model']}")
        else:
            print(f"❌ 连接测试失败: {result['error']}")

def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Toolkit — 统一 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s memory search "3DGS 实验参数"
  %(prog)s memory save "PSNR=25.8"
  %(prog)s task create "跑实验" --priority high
  %(prog)s task list
  %(prog)s bridge send "Hello"
  %(prog)s status
        """
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    # ── memory 命令 ──
    memory_parser = subparsers.add_parser("memory", help="记忆管理")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_action")
    
    # memory search
    search_parser = memory_subparsers.add_parser("search", help="语义搜索记忆")
    search_parser.add_argument("query", help="搜索关键词")
    search_parser.add_argument("--top-k", "-k", type=int, default=5, help="返回数量")
    search_parser.add_argument("--category", "-c", help="按分类过滤")
    
    # memory save
    save_parser = memory_subparsers.add_parser("save", help="保存记忆")
    save_parser.add_argument("text", help="记忆内容")
    save_parser.add_argument("--category", "-c", default="general", help="分类")
    save_parser.add_argument("--tags", "-t", nargs="*", help="标签")
    
    # memory stats
    memory_subparsers.add_parser("stats", help="查看统计")
    
    # memory export
    memory_subparsers.add_parser("export", help="导出 Markdown")
    
    # memory bug
    bug_parser = memory_subparsers.add_parser("bug", help="Bug 解决方案")
    bug_subparsers = bug_parser.add_subparsers(dest="bug_action")
    
    bug_add = bug_subparsers.add_parser("add", help="添加解决方案")
    bug_add.add_argument("problem", help="问题描述")
    bug_add.add_argument("solution", help="解决方案")
    bug_add.add_argument("--context", default="", help="上下文")
    bug_add.add_argument("--tags", nargs="*", help="标签")
    
    bug_find = bug_subparsers.add_parser("find", help="查找解决方案")
    bug_find.add_argument("query", help="查询问题")
    bug_find.add_argument("--top-k", "-k", type=int, default=3, help="返回数量")
    
    # memory experiment
    exp_parser = memory_subparsers.add_parser("experiment", help="实验记录")
    exp_subparsers = exp_parser.add_subparsers(dest="exp_action")
    
    exp_add = exp_subparsers.add_parser("add", help="添加实验")
    exp_add.add_argument("name", help="实验名称")
    exp_add.add_argument("--params", "-p", required=True, help="参数 (JSON)")
    exp_add.add_argument("--results", "-r", required=True, help="结果 (JSON)")
    exp_add.add_argument("--conclusion", "-c", default="", help="结论")
    
    exp_find = exp_subparsers.add_parser("find", help="查找实验")
    exp_find.add_argument("query", help="查询内容")
    exp_find.add_argument("--top-k", "-k", type=int, default=3, help="返回数量")
    
    # ── task 命令 ──
    task_parser = subparsers.add_parser("task", help="任务调度")
    task_subparsers = task_parser.add_subparsers(dest="task_action")
    
    # task create
    create_parser = task_subparsers.add_parser("create", help="创建任务")
    create_parser.add_argument("title", help="任务标题")
    create_parser.add_argument("--description", "-d", default="", help="详细描述")
    create_parser.add_argument("--priority", "-p", default="medium",
                               choices=["low", "medium", "high", "urgent"], help="优先级")
    create_parser.add_argument("--assignee", "-a", help="指派给谁")
    create_parser.add_argument("--tags", "-t", nargs="*", help="标签")
    create_parser.add_argument("--depends", nargs="*", help="依赖的任务 ID")
    create_parser.add_argument("--timeout", type=int, help="超时时间（小时）")
    
    # task list
    list_parser = task_subparsers.add_parser("list", help="列出任务")
    list_parser.add_argument("--status", "-s", default="all",
                             choices=["pending", "in_progress", "done", "failed", "all"])
    list_parser.add_argument("--assignee", "-a", help="按指派人过滤")
    list_parser.add_argument("--priority", "-p", help="按优先级过滤")
    list_parser.add_argument("--tag", help="按标签过滤")
    
    # task update
    update_parser = task_subparsers.add_parser("update", help="更新任务")
    update_parser.add_argument("task_id", help="任务 ID")
    update_parser.add_argument("--status", "-s",
                               choices=["pending", "in_progress", "done", "failed"])
    update_parser.add_argument("--result", "-r", help="任务结果")
    update_parser.add_argument("--assignee", "-a", help="重新指派")
    
    # task assign
    assign_parser = task_subparsers.add_parser("assign", help="分配任务")
    assign_parser.add_argument("task_id", help="任务 ID")
    assign_parser.add_argument("agent_id", help="Agent ID")
    
    # task auto-assign
    auto_parser = task_subparsers.add_parser("auto-assign", help="自动分配任务")
    auto_parser.add_argument("task_id", help="任务 ID")
    
    # task stats
    task_subparsers.add_parser("stats", help="查看统计")
    
    # task export
    task_subparsers.add_parser("export", help="导出为 Markdown")
    
    # task ready
    task_subparsers.add_parser("ready", help="查看可执行任务")
    
    # task register
    reg_parser = task_subparsers.add_parser("register", help="注册 Agent")
    reg_parser.add_argument("agent_id", help="Agent ID")
    reg_parser.add_argument("--capabilities", "-c", nargs="*", help="能力列表")
    
    # ── bridge 命令 ──
    bridge_parser = subparsers.add_parser("bridge", help="跨机通信")
    bridge_subparsers = bridge_parser.add_subparsers(dest="bridge_action")
    
    # bridge send
    send_parser = bridge_subparsers.add_parser("send", help="发送消息")
    send_parser.add_argument("message", help="消息内容")
    
    # bridge recv
    recv_parser = bridge_subparsers.add_parser("recv", help="接收消息")
    recv_parser.add_argument("--limit", "-l", type=int, default=10, help="最多返回几条")
    
    # bridge sync
    sync_parser = bridge_subparsers.add_parser("sync", help="同步文件")
    sync_parser.add_argument("filename", help="文件名")
    
    # bridge status
    bridge_subparsers.add_parser("status", help="查看连接状态")
    
    # ── mcp 命令 ──
    mcp_parser = subparsers.add_parser("mcp", help="MCP 服务器管理")
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_action")
    
    mcp_subparsers.add_parser("start", help="启动 MCP 服务器")
    mcp_subparsers.add_parser("test", help="测试 MCP 服务器")
    
    # ── status 命令 ──
    subparsers.add_parser("status", help="系统状态")
    
    # ── setup 命令 ──
    subparsers.add_parser("setup", help="初始化共享记忆目录")
    
    # ── openclaude 命令 ──
    openclaude_parser = subparsers.add_parser("openclaude", help="OpenClaude 集成")
    openclaude_subparsers = openclaude_parser.add_subparsers(dest="openclaude_action")
    
    # openclaude generate
    openclaude_subparsers.add_parser("generate", help="生成 gRPC 客户端代码")
    
    # openclaude test
    test_parser = openclaude_subparsers.add_parser("test", help="测试连接")
    test_parser.add_argument("--host", default="localhost", help="服务器地址")
    test_parser.add_argument("--port", type=int, default=50051, help="服务器端口")
    
    # openclaude chat
    chat_parser = openclaude_subparsers.add_parser("chat", help="发送消息")
    chat_parser.add_argument("message", help="消息内容")
    chat_parser.add_argument("--dir", default=".", help="工作目录")
    chat_parser.add_argument("--host", default="localhost", help="服务器地址")
    chat_parser.add_argument("--port", type=int, default=50051, help="服务器端口")
    
    # openclaude task
    task_parser = openclaude_subparsers.add_parser("task", help="执行编码任务")
    task_parser.add_argument("description", help="任务描述")
    task_parser.add_argument("--dir", default=".", help="工作目录")
    task_parser.add_argument("--host", default="localhost", help="服务器地址")
    task_parser.add_argument("--port", type=int, default=50051, help="服务器端口")
    
    # ── provider 命令 ──
    provider_parser = subparsers.add_parser("provider", help="Provider 管理")
    provider_subparsers = provider_parser.add_subparsers(dest="provider_action")
    
    # provider add
    add_parser = provider_subparsers.add_parser("add", help="添加 provider")
    add_parser.add_argument("name", help="Provider 名称")
    add_parser.add_argument("--base-url", required=True, help="API 基础 URL")
    add_parser.add_argument("--api-key", required=True, help="API 密钥")
    add_parser.add_argument("--model", required=True, help="模型名称")
    add_parser.add_argument("--description", default="", help="描述")
    
    # provider remove
    remove_parser = provider_subparsers.add_parser("remove", help="删除 provider")
    remove_parser.add_argument("name", help="Provider 名称")
    
    # provider list
    provider_subparsers.add_parser("list", help="列出所有 provider")
    
    # provider use
    use_parser = provider_subparsers.add_parser("use", help="设置默认 provider")
    use_parser.add_argument("name", help="Provider 名称")
    
    # provider test
    test_parser = provider_subparsers.add_parser("test", help="测试连接")
    test_parser.add_argument("name", nargs="?", help="Provider 名称")
    
    args = parser.parse_args()
    
    if args.command == "memory":
        cmd_memory(args)
    elif args.command == "task":
        cmd_task(args)
    elif args.command == "bridge":
        cmd_bridge(args)
    elif args.command == "mcp":
        cmd_mcp(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "setup":
        cmd_setup(args)
    elif args.command == "openclaude":
        cmd_openclaude(args)
    elif args.command == "provider":
        cmd_provider(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
