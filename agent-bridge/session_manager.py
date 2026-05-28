"""
Session 管理器

借鉴 OpenClaude 的 session_id 设计，实现跨调用的会话持久化。

特性：
- 会话创建和恢复
- 消息历史记录
- 上下文窗口管理
- 会话导出和清理

使用方式：
  python session_manager.py create --name "3DGS 实验"
  python session_manager.py add <session_id> --role user --content "开始实验"
  python session_manager.py history <session_id>
  python session_manager.py context <session_id> --max 10
  python session_manager.py list
  python session_manager.py export <session_id>
  python session_manager.py clean --days 7
"""

import argparse
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


class SessionManager:
    """管理跨调用的会话上下文"""
    
    def __init__(self, sessions_file: Path = None):
        self.sessions_file = sessions_file or Path.home() / ".shared-memory" / ".sessions.json"
        self.sessions = self._load()
    
    def _load(self) -> Dict:
        """加载会话数据"""
        if self.sessions_file.exists():
            try:
                return json.loads(self.sessions_file.read_text(encoding="utf-8"))
            except:
                return {"sessions": {}, "active_session": None}
        return {"sessions": {}, "active_session": None}
    
    def _save(self):
        """保存会话数据"""
        self.sessions_file.parent.mkdir(parents=True, exist_ok=True)
        self.sessions_file.write_text(
            json.dumps(self.sessions, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def create(self, name: str = None, session_id: str = None,
               metadata: Dict = None) -> Dict:
        """创建新会话"""
        session_id = session_id or str(uuid.uuid4())[:8]
        name = name or f"Session {session_id}"
        
        session = {
            "id": session_id,
            "name": name,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "messages": [],
            "context_window": [],  # 用于 LLM 的上下文窗口
        }
        
        if "sessions" not in self.sessions:
            self.sessions["sessions"] = {}
        
        self.sessions["sessions"][session_id] = session
        self.sessions["active_session"] = session_id
        self._save()
        
        return session
    
    def get(self, session_id: str) -> Optional[Dict]:
        """获取会话"""
        if "sessions" not in self.sessions:
            return None
        return self.sessions["sessions"].get(session_id)
    
    def get_active(self) -> Optional[Dict]:
        """获取当前活跃会话"""
        active_id = self.sessions.get("active_session")
        if active_id:
            return self.get(active_id)
        return None
    
    def set_active(self, session_id: str) -> bool:
        """设置活跃会话"""
        if "sessions" in self.sessions and session_id in self.sessions["sessions"]:
            self.sessions["active_session"] = session_id
            self._save()
            return True
        return False
    
    def list(self, limit: int = 20) -> List[Dict]:
        """列出最近的会话"""
        if "sessions" not in self.sessions:
            return []
        
        sessions = list(self.sessions["sessions"].values())
        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        
        # 返回摘要信息
        return [
            {
                "id": s["id"],
                "name": s["name"],
                "created_at": s["created_at"],
                "updated_at": s["updated_at"],
                "message_count": len(s.get("messages", [])),
                "is_active": s["id"] == self.sessions.get("active_session")
            }
            for s in sessions[:limit]
        ]
    
    def add_message(self, session_id: str, role: str, content: str,
                    metadata: Dict = None) -> Dict:
        """添加消息到会话"""
        session = self.get(session_id)
        if not session:
            session = self.create(session_id=session_id)
        
        message = {
            "id": str(uuid.uuid4())[:8],
            "role": role,  # user, assistant, system, tool
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        session["messages"].append(message)
        session["updated_at"] = datetime.now().isoformat()
        
        # 更新上下文窗口（保留最近的消息）
        self._update_context_window(session)
        
        self._save()
        return message
    
    def _update_context_window(self, session: Dict, max_messages: int = 20):
        """更新上下文窗口"""
        messages = session.get("messages", [])
        session["context_window"] = messages[-max_messages:]
    
    def get_context(self, session_id: str, max_messages: int = 10) -> List[Dict]:
        """获取会话上下文（用于 LLM 调用）"""
        session = self.get(session_id)
        if not session:
            return []
        
        messages = session.get("messages", [])
        return messages[-max_messages:]
    
    def get_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """获取会话历史"""
        session = self.get(session_id)
        if not session:
            return []
        
        messages = session.get("messages", [])
        return messages[-limit:]
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索会话内容"""
        results = []
        query_lower = query.lower()
        
        if "sessions" not in self.sessions:
            return []
        
        for session in self.sessions["sessions"].values():
            # 搜索会话名称
            if query_lower in session.get("name", "").lower():
                results.append({
                    "session_id": session["id"],
                    "session_name": session["name"],
                    "match_type": "name",
                    "match_content": session["name"]
                })
            
            # 搜索消息内容
            for msg in session.get("messages", []):
                if query_lower in msg.get("content", "").lower():
                    results.append({
                        "session_id": session["id"],
                        "session_name": session["name"],
                        "match_type": "message",
                        "match_content": msg["content"][:100],
                        "message_id": msg["id"],
                        "role": msg["role"]
                    })
                    
                    if len(results) >= limit:
                        return results
        
        return results
    
    def export_markdown(self, session_id: str) -> str:
        """导出会话为 Markdown"""
        session = self.get(session_id)
        if not session:
            return ""
        
        lines = [f"# 会话: {session['name']}\n"]
        lines.append(f"ID: {session['id']}")
        lines.append(f"创建时间: {session['created_at']}")
        lines.append(f"更新时间: {session['updated_at']}")
        lines.append(f"消息数量: {len(session.get('messages', []))}\n")
        
        lines.append("## 消息历史\n")
        
        role_names = {
            "user": "👤 用户",
            "assistant": "🤖 助手",
            "system": "⚙️ 系统",
            "tool": "🔧 工具"
        }
        
        for msg in session.get("messages", []):
            role = role_names.get(msg["role"], msg["role"])
            timestamp = msg["timestamp"][:19]
            lines.append(f"### {role} ({timestamp})\n")
            lines.append(f"{msg['content']}\n")
        
        return "\n".join(lines)
    
    def clean(self, days: int = 7) -> int:
        """清理旧会话"""
        if "sessions" not in self.sessions:
            return 0
        
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        
        to_remove = []
        for session_id, session in self.sessions["sessions"].items():
            if session.get("updated_at", "") < cutoff_str:
                to_remove.append(session_id)
        
        for session_id in to_remove:
            del self.sessions["sessions"][session_id]
        
        # 如果删除了活跃会话，重置
        if self.sessions.get("active_session") in to_remove:
            remaining = list(self.sessions["sessions"].keys())
            self.sessions["active_session"] = remaining[0] if remaining else None
        
        if to_remove:
            self._save()
        
        return len(to_remove)
    
    def delete(self, session_id: str) -> bool:
        """删除会话"""
        if "sessions" in self.sessions and session_id in self.sessions["sessions"]:
            del self.sessions["sessions"][session_id]
            
            if self.sessions.get("active_session") == session_id:
                remaining = list(self.sessions["sessions"].keys())
                self.sessions["active_session"] = remaining[0] if remaining else None
            
            self._save()
            return True
        return False
    
    def rename(self, session_id: str, new_name: str) -> bool:
        """重命名会话"""
        session = self.get(session_id)
        if session:
            session["name"] = new_name
            session["updated_at"] = datetime.now().isoformat()
            self._save()
            return True
        return False
    
    def get_stats(self) -> Dict:
        """获取会话统计"""
        if "sessions" not in self.sessions:
            return {"total": 0, "total_messages": 0}
        
        sessions = list(self.sessions["sessions"].values())
        total_messages = sum(len(s.get("messages", [])) for s in sessions)
        
        return {
            "total": len(sessions),
            "total_messages": total_messages,
            "active_session": self.sessions.get("active_session")
        }


def main():
    parser = argparse.ArgumentParser(description="Session 管理器")
    subparsers = parser.add_subparsers(dest="command")
    
    # create
    create_parser = subparsers.add_parser("create", help="创建新会话")
    create_parser.add_argument("--name", "-n", help="会话名称")
    create_parser.add_argument("--id", help="会话 ID（可选）")
    
    # list
    list_parser = subparsers.add_parser("list", help="列出会话")
    list_parser.add_argument("--limit", "-l", type=int, default=20, help="返回数量")
    
    # add message
    add_parser = subparsers.add_parser("add", help="添加消息")
    add_parser.add_argument("session_id", help="会话 ID")
    add_parser.add_argument("--role", "-r", default="user",
                            choices=["user", "assistant", "system", "tool"],
                            help="角色")
    add_parser.add_argument("--content", "-c", required=True, help="消息内容")
    
    # history
    history_parser = subparsers.add_parser("history", help="查看历史")
    history_parser.add_argument("session_id", help="会话 ID")
    history_parser.add_argument("--limit", "-l", type=int, default=50, help="返回数量")
    
    # context
    context_parser = subparsers.add_parser("context", help="获取上下文")
    context_parser.add_argument("session_id", help="会话 ID")
    context_parser.add_argument("--max", "-m", type=int, default=10, help="最大消息数")
    
    # search
    search_parser = subparsers.add_parser("search", help="搜索会话")
    search_parser.add_argument("query", help="搜索关键词")
    search_parser.add_argument("--limit", "-l", type=int, default=10, help="返回数量")
    
    # export
    export_parser = subparsers.add_parser("export", help="导出会话")
    export_parser.add_argument("session_id", help="会话 ID")
    
    # clean
    clean_parser = subparsers.add_parser("clean", help="清理旧会话")
    clean_parser.add_argument("--days", "-d", type=int, default=7, help="保留天数")
    
    # delete
    delete_parser = subparsers.add_parser("delete", help="删除会话")
    delete_parser.add_argument("session_id", help="会话 ID")
    
    # rename
    rename_parser = subparsers.add_parser("rename", help="重命名会话")
    rename_parser.add_argument("session_id", help="会话 ID")
    rename_parser.add_argument("new_name", help="新名称")
    
    # use (set active)
    use_parser = subparsers.add_parser("use", help="设置活跃会话")
    use_parser.add_argument("session_id", help="会话 ID")
    
    # stats
    subparsers.add_parser("stats", help="查看统计")
    
    args = parser.parse_args()
    
    manager = SessionManager()
    
    if args.command == "create":
        session = manager.create(name=args.name, session_id=args.id)
        print(f"✅ 会话已创建")
        print(f"   ID: {session['id']}")
        print(f"   名称: {session['name']}")
    
    elif args.command == "list":
        sessions = manager.list(limit=args.limit)
        if sessions:
            print(f"📋 会话列表 ({len(sessions)} 个):\n")
            for s in sessions:
                active_mark = " *" if s["is_active"] else ""
                print(f"  • {s['id']}{active_mark}: {s['name']}")
                print(f"    消息: {s['message_count']} | 更新: {s['updated_at'][:19]}")
                print()
        else:
            print("📭 没有会话")
            print("\n创建会话:")
            print('  python session_manager.py create --name "我的会话"')
    
    elif args.command == "add":
        message = manager.add_message(args.session_id, args.role, args.content)
        print(f"✅ 消息已添加")
        print(f"   会话: {args.session_id}")
        print(f"   角色: {args.role}")
        print(f"   ID: {message['id']}")
    
    elif args.command == "history":
        history = manager.get_history(args.session_id, limit=args.limit)
        if history:
            print(f"📜 会话历史 ({len(history)} 条):\n")
            role_names = {"user": "👤", "assistant": "🤖", "system": "⚙️", "tool": "🔧"}
            for msg in history:
                role = role_names.get(msg["role"], "?")
                print(f"  {role} [{msg['timestamp'][:19]}]")
                print(f"    {msg['content'][:100]}...")
                print()
        else:
            print(f"📭 会话 {args.session_id} 没有消息")
    
    elif args.command == "context":
        context = manager.get_context(args.session_id, max_messages=args.max)
        if context:
            print(f"📝 上下文 ({len(context)} 条):\n")
            for msg in context:
                print(f"[{msg['role']}] {msg['content']}")
        else:
            print(f"📭 会话 {args.session_id} 没有上下文")
    
    elif args.command == "search":
        results = manager.search(args.query, limit=args.limit)
        if results:
            print(f"🔍 搜索结果 ({len(results)} 条):\n")
            for r in results:
                print(f"  会话: {r['session_name']} ({r['session_id']})")
                print(f"    匹配: {r['match_content']}")
                print()
        else:
            print(f"❌ 未找到包含 '{args.query}' 的会话")
    
    elif args.command == "export":
        markdown = manager.export_markdown(args.session_id)
        if markdown:
            print(markdown)
        else:
            print(f"❌ 会话 {args.session_id} 不存在")
    
    elif args.command == "clean":
        removed = manager.clean(days=args.days)
        print(f"🧹 已清理 {removed} 个旧会话")
    
    elif args.command == "delete":
        if manager.delete(args.session_id):
            print(f"✅ 会话已删除: {args.session_id}")
        else:
            print(f"❌ 会话不存在: {args.session_id}")
    
    elif args.command == "rename":
        if manager.rename(args.session_id, args.new_name):
            print(f"✅ 会话已重命名: {args.new_name}")
        else:
            print(f"❌ 会话不存在: {args.session_id}")
    
    elif args.command == "use":
        if manager.set_active(args.session_id):
            print(f"✅ 活跃会话已设为: {args.session_id}")
        else:
            print(f"❌ 会话不存在: {args.session_id}")
    
    elif args.command == "stats":
        stats = manager.get_stats()
        print("📊 会话统计:\n")
        print(f"  总会话数: {stats['total']}")
        print(f"  总消息数: {stats['total_messages']}")
        print(f"  活跃会话: {stats['active_session'] or '无'}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
