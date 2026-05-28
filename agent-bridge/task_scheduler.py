"""
智能任务调度器 — 替代手动 Markdown 任务队列

特性：
  - 优先级队列（urgent > high > medium > low）
  - 自动分配（基于 agent 负载和能力）
  - 状态追踪（pending → in_progress → done/failed）
  - 依赖管理（任务可依赖其他任务）
  - 超时检测（自动标记超时任务）
  - 统计报告（完成率、平均耗时）

使用方式：
  python task_scheduler.py create "跑 3DGS 实验" --priority high --assignee claude-pc1
  python task_scheduler.py list --status pending
  python task_scheduler.py assign <task_id> <agent_id>
  python task_scheduler.py complete <task_id> --result "PSNR=25.8"
  python task_scheduler.py stats
  python task_scheduler.py export  # 导出为 Markdown
"""

import argparse
import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


class TaskScheduler:
    """智能任务调度器"""
    
    def __init__(self, tasks_file: Path = None):
        self.tasks_file = tasks_file or Path.home() / ".shared-memory" / ".tasks.json"
        self.agents_file = Path.home() / ".shared-memory" / ".agents.json"
        self.tasks = self._load_tasks()
        self.agents = self._load_agents()
    
    def _load_tasks(self) -> List[Dict]:
        """加载任务"""
        if self.tasks_file.exists():
            try:
                return json.loads(self.tasks_file.read_text(encoding="utf-8"))
            except:
                return []
        return []
    
    def _save_tasks(self):
        """保存任务"""
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        self.tasks_file.write_text(
            json.dumps(self.tasks, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def _load_agents(self) -> Dict:
        """加载 agent 信息"""
        if self.agents_file.exists():
            try:
                return json.loads(self.agents_file.read_text(encoding="utf-8"))
            except:
                return {}
        return {}
    
    def _save_agents(self):
        """保存 agent 信息"""
        self.agents_file.write_text(
            json.dumps(self.agents, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def create_task(self, title: str, description: str = "", priority: str = "medium",
                    assignee: str = None, tags: List[str] = None,
                    depends_on: List[str] = None, timeout_hours: int = None) -> Dict:
        """创建任务"""
        task = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "description": description,
            "status": "pending",
            "priority": priority,
            "assignee": assignee,
            "tags": tags or [],
            "depends_on": depends_on or [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "timeout_at": None,
            "result": None,
            "attempts": 0
        }
        
        if timeout_hours:
            task["timeout_at"] = (datetime.now() + timedelta(hours=timeout_hours)).isoformat()
        
        self.tasks.append(task)
        self._save_tasks()
        
        # 如果有指派人，自动分配
        if assignee:
            self._update_agent_load(assignee, 1)
        
        return task
    
    def list_tasks(self, status: str = "all", assignee: str = None,
                   priority: str = None, tag: str = None) -> List[Dict]:
        """列出任务"""
        filtered = self.tasks.copy()
        
        if status != "all":
            filtered = [t for t in filtered if t["status"] == status]
        
        if assignee:
            filtered = [t for t in filtered if t.get("assignee") == assignee]
        
        if priority:
            filtered = [t for t in filtered if t.get("priority") == priority]
        
        if tag:
            filtered = [t for t in filtered if tag in t.get("tags", [])]
        
        # 按优先级排序
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        filtered.sort(key=lambda t: priority_order.get(t.get("priority", "medium"), 2))
        
        return filtered
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取单个任务"""
        for task in self.tasks:
            if task["id"] == task_id:
                return task
        return None
    
    def update_task(self, task_id: str, status: str = None, result: str = None,
                    assignee: str = None) -> Dict:
        """更新任务"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        old_status = task["status"]
        
        if status:
            task["status"] = status
            task["updated_at"] = datetime.now().isoformat()
            
            if status == "in_progress" and old_status == "pending":
                task["started_at"] = datetime.now().isoformat()
                task["attempts"] += 1
            
            if status in ("done", "failed"):
                task["completed_at"] = datetime.now().isoformat()
        
        if result:
            task["result"] = result
        
        if assignee:
            # 更新 agent 负载
            if task.get("assignee"):
                self._update_agent_load(task["assignee"], -1)
            task["assignee"] = assignee
            self._update_agent_load(assignee, 1)
        
        self._save_tasks()
        return task
    
    def auto_assign(self, task_id: str) -> Dict:
        """自动分配任务给最空闲的 agent"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        if task.get("assignee"):
            return task  # 已有指派
        
        # 找到负载最低的 agent
        available_agents = [
            (agent_id, info) for agent_id, info in self.agents.items()
            if info.get("active", True)
        ]
        
        if not available_agents:
            return task  # 没有可用 agent
        
        # 按负载排序
        available_agents.sort(key=lambda x: x[1].get("load", 0))
        
        # 选择负载最低的
        best_agent = available_agents[0][0]
        return self.update_task(task_id, assignee=best_agent)
    
    def check_dependencies(self, task_id: str) -> bool:
        """检查任务依赖是否满足"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        for dep_id in task.get("depends_on", []):
            dep_task = self.get_task(dep_id)
            if not dep_task or dep_task["status"] != "done":
                return False
        
        return True
    
    def check_timeouts(self) -> List[Dict]:
        """检查超时任务"""
        now = datetime.now()
        timed_out = []
        
        for task in self.tasks:
            if task["status"] == "in_progress" and task.get("timeout_at"):
                timeout_at = datetime.fromisoformat(task["timeout_at"])
                if now > timeout_at:
                    task["status"] = "failed"
                    task["result"] = "Timeout"
                    task["updated_at"] = now.isoformat()
                    timed_out.append(task)
        
        if timed_out:
            self._save_tasks()
        
        return timed_out
    
    def get_ready_tasks(self) -> List[Dict]:
        """获取可执行的任务（依赖已满足）"""
        ready = []
        for task in self.tasks:
            if task["status"] == "pending" and self.check_dependencies(task["id"]):
                ready.append(task)
        
        # 按优先级排序
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        ready.sort(key=lambda t: priority_order.get(t.get("priority", "medium"), 2))
        
        return ready
    
    def register_agent(self, agent_id: str, capabilities: List[str] = None):
        """注册 agent"""
        self.agents[agent_id] = {
            "capabilities": capabilities or [],
            "load": 0,
            "active": True,
            "registered_at": datetime.now().isoformat()
        }
        self._save_agents()
    
    def _update_agent_load(self, agent_id: str, delta: int):
        """更新 agent 负载"""
        if agent_id not in self.agents:
            self.agents[agent_id] = {"capabilities": [], "load": 0, "active": True}
        
        self.agents[agent_id]["load"] = max(0, self.agents[agent_id].get("load", 0) + delta)
        self._save_agents()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.tasks)
        by_status = Counter(t["status"] for t in self.tasks)
        by_priority = Counter(t.get("priority", "medium") for t in self.tasks)
        
        # 计算完成率
        completed = by_status.get("done", 0)
        failed = by_status.get("failed", 0)
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        # 计算平均耗时
        durations = []
        for task in self.tasks:
            if task.get("started_at") and task.get("completed_at"):
                start = datetime.fromisoformat(task["started_at"])
                end = datetime.fromisoformat(task["completed_at"])
                durations.append((end - start).total_seconds())
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "total": total,
            "by_status": dict(by_status),
            "by_priority": dict(by_priority),
            "completion_rate": round(completion_rate, 1),
            "avg_duration_minutes": round(avg_duration / 60, 1),
            "agents": len(self.agents)
        }
    
    def export_markdown(self) -> str:
        """导出为 Markdown 格式"""
        lines = ["# 任务队列\n"]
        lines.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 统计
        stats = self.get_stats()
        lines.append("## 统计\n")
        lines.append(f"- 总任务数: {stats['total']}")
        lines.append(f"- 完成率: {stats['completion_rate']}%")
        lines.append(f"- 平均耗时: {stats['avg_duration_minutes']} 分钟\n")
        
        # 按状态分组
        for status in ["pending", "in_progress", "done", "failed"]:
            tasks = self.list_tasks(status=status)
            if tasks:
                status_names = {
                    "pending": "待处理",
                    "in_progress": "进行中",
                    "done": "已完成",
                    "failed": "失败"
                }
                lines.append(f"## {status_names.get(status, status)}\n")
                
                for task in tasks:
                    priority_icon = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
                    icon = priority_icon.get(task.get("priority", "medium"), "⚪")
                    
                    lines.append(f"- {icon} [{task['id']}] {task['title']}")
                    if task.get("assignee"):
                        lines.append(f"  - 指派: {task['assignee']}")
                    if task.get("result"):
                        lines.append(f"  - 结果: {task['result']}")
                    lines.append("")
        
        return "\n".join(lines)


# ── CLI 接口 ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="智能任务调度器")
    subparsers = parser.add_subparsers(dest="command")
    
    # create
    create_parser = subparsers.add_parser("create", help="创建任务")
    create_parser.add_argument("title", help="任务标题")
    create_parser.add_argument("--description", "-d", default="", help="详细描述")
    create_parser.add_argument("--priority", "-p", default="medium",
                               choices=["low", "medium", "high", "urgent"], help="优先级")
    create_parser.add_argument("--assignee", "-a", help="指派给谁")
    create_parser.add_argument("--tags", "-t", nargs="*", help="标签")
    create_parser.add_argument("--depends", nargs="*", help="依赖的任务 ID")
    create_parser.add_argument("--timeout", type=int, help="超时时间（小时）")
    
    # list
    list_parser = subparsers.add_parser("list", help="列出任务")
    list_parser.add_argument("--status", "-s", default="all",
                             choices=["pending", "in_progress", "done", "failed", "all"])
    list_parser.add_argument("--assignee", "-a", help="按指派人过滤")
    list_parser.add_argument("--priority", "-p", help="按优先级过滤")
    list_parser.add_argument("--tag", help="按标签过滤")
    
    # update
    update_parser = subparsers.add_parser("update", help="更新任务")
    update_parser.add_argument("task_id", help="任务 ID")
    update_parser.add_argument("--status", "-s",
                               choices=["pending", "in_progress", "done", "failed"])
    update_parser.add_argument("--result", "-r", help="任务结果")
    update_parser.add_argument("--assignee", "-a", help="重新指派")
    
    # assign
    assign_parser = subparsers.add_parser("assign", help="分配任务")
    assign_parser.add_argument("task_id", help="任务 ID")
    assign_parser.add_argument("agent_id", help="Agent ID")
    
    # auto-assign
    auto_parser = subparsers.add_parser("auto-assign", help="自动分配任务")
    auto_parser.add_argument("task_id", help="任务 ID")
    
    # stats
    subparsers.add_parser("stats", help="查看统计")
    
    # export
    subparsers.add_parser("export", help="导出为 Markdown")
    
    # ready
    subparsers.add_parser("ready", help="查看可执行任务")
    
    # register
    reg_parser = subparsers.add_parser("register", help="注册 Agent")
    reg_parser.add_argument("agent_id", help="Agent ID")
    reg_parser.add_argument("--capabilities", "-c", nargs="*", help="能力列表")
    
    args = parser.parse_args()
    
    scheduler = TaskScheduler()
    
    if args.command == "create":
        task = scheduler.create_task(
            title=args.title,
            description=args.description,
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
    
    elif args.command == "list":
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
    
    elif args.command == "update":
        task = scheduler.update_task(
            task_id=args.task_id,
            status=args.status,
            result=args.result,
            assignee=args.assignee
        )
        print(f"✅ 任务已更新: {task['title']}")
        print(f"   状态: {task['status']}")
    
    elif args.command == "assign":
        task = scheduler.update_task(args.task_id, assignee=args.agent_id)
        print(f"✅ 任务已分配: {task['title']} → {args.agent_id}")
    
    elif args.command == "auto-assign":
        task = scheduler.auto_assign(args.task_id)
        if task.get("assignee"):
            print(f"✅ 自动分配: {task['title']} → {task['assignee']}")
        else:
            print("⚠️ 没有可用的 Agent")
    
    elif args.command == "stats":
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
    
    elif args.command == "export":
        markdown = scheduler.export_markdown()
        print(markdown)
    
    elif args.command == "ready":
        tasks = scheduler.get_ready_tasks()
        if tasks:
            print(f"🚀 可执行任务 ({len(tasks)} 个):\n")
            for task in tasks:
                print(f"  [{task['id']}] {task['title']} ({task['priority']})")
        else:
            print("📭 没有可执行的任务")
    
    elif args.command == "register":
        scheduler.register_agent(args.agent_id, args.capabilities or [])
        print(f"✅ Agent 已注册: {args.agent_id}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
