"""
Agent Bridge — CLI for Claude Code
让 Claude Code 通过命令行与另一台机器的 Claude Code 通信。

Claude Code 使用方式：
  python bridge.py send "你好，我刚跑完 3DGS truck 实验"
  python bridge.py recv
  python bridge.py sync MEMORY.md
  python bridge.py status
  python bridge.py start  (后台启动同步服务)

放在 ~/.shared-memory/ 或项目根目录，Claude Code 直接调用。
"""

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import pathlib
import socket
import sys
import time
from datetime import datetime

# ── 配置 ──────────────────────────────────────────────────

SHARED_DIR = pathlib.Path.home() / ".shared-memory"
CONFIG_FILE = SHARED_DIR / ".bridge_config.json"
SECRET_FILE = SHARED_DIR / ".bridge_secret"
INBOX_FILE = SHARED_DIR / "inbox.json"
OUTBOX_FILE = SHARED_DIR / "outbox.json"
SYNC_DIR = SHARED_DIR

DEFAULT_PORT = 9527
TIMESTAMP_WINDOW = 300  # 5 minutes

# ── 工具函数 ──────────────────────────────────────────────

def get_config():
    """读取或生成配置"""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    
    # 生成默认配置
    secret = os.urandom(32).hex()
    agent_id = f"claude-{socket.gethostname()}"
    
    config = {
        "agent_id": agent_id,
        "secret": secret,
        "port": DEFAULT_PORT,
        "peer": None,
        "auto_sync": True,
        "sync_interval": 5,
        "sync_files": ["MEMORY.md", "TASK_QUEUE.md", "HANDOVER.md", "ACTIVITY_LOG.md"],
    }
    
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    SECRET_FILE.write_text(secret, encoding="utf-8")
    
    print(f"配置已生成: {CONFIG_FILE}")
    print(f"Agent ID: {agent_id}")
    print(f"密钥已保存: {SECRET_FILE}")
    print(f"请将 .bridge_secret 复制到对方机器的同一位置")
    
    return config

def make_token(agent_id: str, secret: str) -> tuple[str, str]:
    """生成 HMAC 认证令牌"""
    ts = str(int(time.time()))
    msg = f"{agent_id}:{ts}"
    token = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return token, ts

def verify_token(agent_id: str, token: str, ts: str, secret: str) -> bool:
    """验证令牌"""
    try:
        if abs(time.time() - int(ts)) > TIMESTAMP_WINDOW:
            return False
        expected = hmac.new(secret.encode(), f"{agent_id}:{ts}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(token, expected)
    except (ValueError, TypeError):
        return False

def log(msg: str):
    """带时间戳的日志"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

# ── 文件收件箱（Claude Code 直接读写）─────────────────────

def send_message(text: str, config: dict):
    """发送消息到收件箱（供对方 Claude Code 读取）"""
    inbox = []
    if INBOX_FILE.exists():
        try:
            inbox = json.loads(INBOX_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            inbox = []
    
    msg = {
        "from": config["agent_id"],
        "time": datetime.now().isoformat(),
        "text": text,
        "read": False,
    }
    inbox.append(msg)
    
    # 只保留最近 100 条
    if len(inbox) > 100:
        inbox = inbox[-100:]
    
    INBOX_FILE.write_text(json.dumps(inbox, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"消息已发送: {text[:50]}...")

def recv_messages(unread_only: bool = True):
    """读取消息"""
    if not INBOX_FILE.exists():
        print("收件箱为空")
        return []
    
    try:
        inbox = json.loads(INBOX_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        print("收件箱为空")
        return []
    
    if unread_only:
        messages = [m for m in inbox if not m.get("read")]
    else:
        messages = inbox
    
    if not messages:
        print("没有新消息")
        return []
    
    for i, msg in enumerate(messages):
        ts = msg.get("time", "?")[:19]
        frm = msg.get("from", "?")
        txt = msg.get("text", "")
        print(f"[{ts}] {frm}: {txt}")
        # 标记已读
        msg["read"] = True
    
    # 回写
    INBOX_FILE.write_text(json.dumps(inbox, indent=2, ensure_ascii=False), encoding="utf-8")
    return messages

def send_file(filepath: str, config: dict):
    """发送文件内容到共享记忆"""
    p = pathlib.Path(filepath)
    if not p.exists():
        print(f"文件不存在: {filepath}")
        return
    
    content = p.read_text(encoding="utf-8", errors="replace")
    filename = p.name
    
    # 写入共享目录
    target = SHARED_DIR / f"transfer_{filename}"
    target.write_text(content, encoding="utf-8")
    
    # 也发一条消息通知
    send_message(f"[FILE] {filename} 已传输，路径: {target}", config)
    log(f"文件已传输: {filename} → {target}")

def sync_file(filename: str, config: dict):
    """同步单个文件（通过 git）"""
    target = SHARED_DIR / filename
    if not target.exists():
        print(f"文件不存在: {target}")
        return
    
    # git add + commit
    os.system(f'cd "{SHARED_DIR}" && git add "{filename}" && git commit -m "sync {filename} from {config["agent_id"]}" 2>/dev/null')
    log(f"文件已同步: {filename}")

def show_status(config: dict):
    """显示状态"""
    print(f"Agent ID:  {config['agent_id']}")
    print(f"端口:      {config['port']}")
    print(f"对端:      {config.get('peer', '未配置')}")
    print(f"共享目录:  {SHARED_DIR}")
    print(f"自动同步:  {'开启' if config.get('auto_sync') else '关闭'}")
    print(f"同步间隔:  {config.get('sync_interval', 5)} 秒")
    print(f"同步文件:  {', '.join(config.get('sync_files', []))}")
    
    # 显示收件箱状态
    if INBOX_FILE.exists():
        try:
            inbox = json.loads(INBOX_FILE.read_text(encoding="utf-8"))
            unread = sum(1 for m in inbox if not m.get("read"))
            print(f"收件箱:    {len(inbox)} 条消息，{unread} 条未读")
        except:
            print("收件箱:    读取错误")
    else:
        print("收件箱:    空")
    
    # 显示共享文件
    print(f"\n共享记忆文件:")
    for f in sorted(SHARED_DIR.glob("*.md")):
        size = f.stat().st_size
        print(f"  {f.name} ({size} bytes)")

# ── 网络同步（后台服务）──────────────────────────────────

async def start_sync_service(config: dict):
    """启动后台同步服务"""
    try:
        import websockets
    except ImportError:
        print("需要安装 websockets: pip install websockets")
        return
    
    peer = config.get("peer")
    if not peer:
        print("未配置对端地址。请先设置:")
        print(f"  编辑 {CONFIG_FILE}")
        print(f'  设置 "peer": "对方IP:{DEFAULT_PORT}"')
        print()
        print("或者使用文件模式（无需网络）:")
        print("  python bridge.py send '消息'")
        print("  python bridge.py recv")
        return
    
    agent_id = config["agent_id"]
    secret = config["secret"]
    port = config["port"]
    
    # 文件变更追踪
    file_hashes = {}
    sync_files = config.get("sync_files", [])
    for f in sync_files:
        fp = SHARED_DIR / f
        if fp.exists():
            file_hashes[f] = hashlib.md5(fp.read_bytes()).hexdigest()
    
    log(f"启动同步服务: {agent_id}")
    log(f"对端: {peer}")
    log(f"同步文件: {', '.join(sync_files)}")
    
    async def sync_loop(ws):
        """同步循环"""
        while True:
            try:
                # 检查文件变更
                for f in sync_files:
                    fp = SHARED_DIR / f
                    if fp.exists():
                        new_hash = hashlib.md5(fp.read_bytes()).hexdigest()
                        if file_hashes.get(f) != new_hash:
                            content = fp.read_text(encoding="utf-8")
                            await ws.send(json.dumps({
                                "jsonrpc": "2.0",
                                "method": "memory.write",
                                "params": {"file": f, "content": content},
                                "id": f"sync_{int(time.time())}"
                            }))
                            file_hashes[f] = new_hash
                            log(f"同步发送: {f}")
                
                await asyncio.sleep(config.get("sync_interval", 5))
            except websockets.exceptions.ConnectionClosed:
                log("连接断开，尝试重连...")
                break
            except Exception as e:
                log(f"同步错误: {e}")
                await asyncio.sleep(5)
    
    async def handle_messages(ws):
        """处理接收到的消息"""
        async for raw in ws:
            try:
                msg = json.loads(raw)
                method = msg.get("method", "")
                params = msg.get("params", {})
                
                if method == "memory.write":
                    filename = params.get("file")
                    content = params.get("content")
                    if filename and content:
                        fp = SHARED_DIR / filename
                        fp.write_text(content, encoding="utf-8")
                        file_hashes[filename] = hashlib.md5(content.encode()).hexdigest()
                        log(f"接收同步: {filename}")
                
                elif method == "message.send":
                    text = params.get("text", "")
                    sender = params.get("from", "unknown")
                    # 写入收件箱
                    inbox = []
                    if INBOX_FILE.exists():
                        try:
                            inbox = json.loads(INBOX_FILE.read_text(encoding="utf-8"))
                        except:
                            inbox = []
                    inbox.append({
                        "from": sender,
                        "time": datetime.now().isoformat(),
                        "text": text,
                        "read": False,
                    })
                    INBOX_FILE.write_text(json.dumps(inbox, indent=2, ensure_ascii=False), encoding="utf-8")
                    log(f"收到消息: {sender}: {text[:50]}")
                
                elif method == "agent.heartbeat":
                    pass  # 静默处理心跳
                
            except json.JSONDecodeError:
                pass
    
    async def connect_with_retry():
        """带重连的连接"""
        while True:
            try:
                token, ts = make_token(agent_id, secret)
                uri = f"ws://{peer}"
                
                async with websockets.connect(uri) as ws:
                    # 发送握手
                    await ws.send(json.dumps({
                        "jsonrpc": "2.0",
                        "method": "agent.hello",
                        "params": {
                            "agent_id": agent_id,
                            "token": token,
                            "timestamp": ts,
                            "version": "1.0.0",
                        },
                        "id": "hello"
                    }))
                    
                    # 等待响应
                    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                    if resp.get("result", {}).get("status") == "accepted":
                        log(f"已连接到 {peer}")
                        
                        # 并行运行同步和消息处理
                        await asyncio.gather(
                            sync_loop(ws),
                            handle_messages(ws),
                        )
                    else:
                        log(f"握手被拒绝: {resp}")
                
            except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                log(f"连接失败: {e}，10秒后重试...")
                await asyncio.sleep(10)
            except Exception as e:
                log(f"错误: {e}，10秒后重试...")
                await asyncio.sleep(10)
    
    await connect_with_retry()

# ── LAN 发现 ──────────────────────────────────────────────

def discover_lan(config: dict):
    """UDP 广播发现局域网内的其他 Agent"""
    port = config["port"]
    agent_id = config["agent_id"]
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(3)
    
    beacon = json.dumps({
        "type": "discover",
        "agent_id": agent_id,
        "port": port,
        "time": datetime.now().isoformat(),
    })
    
    print(f"正在搜索局域网内的 Agent...")
    
    try:
        sock.sendto(beacon.encode(), ("255.255.255.255", port + 1))
        
        found = []
        while True:
            try:
                data, addr = sock.recvfrom(4096)
                msg = json.loads(data.decode())
                if msg.get("type") == "announce" and msg.get("agent_id") != agent_id:
                    found.append(msg)
                    print(f"  发现: {msg['agent_id']} @ {addr[0]}:{msg.get('port', '?')}")
            except socket.timeout:
                break
        
        if not found:
            print("  未发现其他 Agent")
        else:
            print(f"\n共发现 {len(found)} 个 Agent")
            # 自动配置第一个为 peer
            if found:
                peer_addr = f"{found[0].get('addr', '?')}:{found[0].get('port', DEFAULT_PORT)}"
                print(f"  可连接: python bridge.py connect {peer_addr}")
    
    except Exception as e:
        print(f"发现失败: {e}")
    finally:
        sock.close()

# ── 主入口 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Agent Bridge — Claude Code 跨机器通信工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python bridge.py status                    # 查看状态
  python bridge.py send "3DGS truck 跑完了"  # 发送消息
  python bridge.py recv                      # 读取消息
  python bridge.py sync MEMORY.md            # 同步文件
  python bridge.py file report.pdf           # 传输文件
  python bridge.py discover                  # LAN 发现
  python bridge.py start                     # 启动后台同步
  python bridge.py connect 192.168.1.50:9527 # 配置对端
        """
    )
    
    parser.add_argument("command", choices=["send", "recv", "sync", "file", "status", "start", "discover", "connect"],
                       help="命令")
    parser.add_argument("args", nargs="*", help="参数")
    parser.add_argument("--unread", action="store_true", default=True, help="只显示未读消息")
    
    args = parser.parse_args()
    config = get_config()
    
    if args.command == "status":
        show_status(config)
    
    elif args.command == "send":
        if not args.args:
            print("用法: python bridge.py send '消息内容'")
            return
        text = " ".join(args.args)
        send_message(text, config)
    
    elif args.command == "recv":
        recv_messages(unread_only=args.unread)
    
    elif args.command == "sync":
        if not args.args:
            print("用法: python bridge.py sync MEMORY.md")
            return
        sync_file(args.args[0], config)
    
    elif args.command == "file":
        if not args.args:
            print("用法: python bridge.py file report.pdf")
            return
        send_file(args.args[0], config)
    
    elif args.command == "start":
        print("启动后台同步服务...")
        print("按 Ctrl+C 停止")
        asyncio.run(start_sync_service(config))
    
    elif args.command == "discover":
        discover_lan(config)
    
    elif args.command == "connect":
        if not args.args:
            print("用法: python bridge.py connect 192.168.1.50:9527")
            return
        config["peer"] = args.args[0]
        CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"已配置对端: {args.args[0]}")
        print(f"启动同步: python bridge.py start")

if __name__ == "__main__":
    main()
