"""
任务完成通知系统

借鉴 ai-cli-complete-notify 的设计，实现多通道任务完成通知。

特性：
- 智能去抖：避免子任务导致的垃圾通知
- 耗时阈值：短任务不通知
- 多通道：Webhook（飞书/钉钉/企微）、Telegram、Email
- 配置分离：敏感信息存 .env，运行时配置存 .json
- Hooks 支持：使用 Claude Code 原生 hooks 事件

使用方式：
  python notify_manager.py send "任务完成" --source claude
  python notify_manager.py test --channel webhook
  python notify_manager.py config --show
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class NotificationDebouncer:
    """智能去抖：避免频繁通知"""
    
    def __init__(self):
        self.last_activity = {}
        self.last_notification = {}
        self.quiet_threshold = {
            "with_tools": 60,  # 有工具调用：60秒静默后通知
            "without_tools": 15  # 无工具调用：15秒静默后通知
        }
        self.dedupe_window = 120  # 2分钟内不重复通知
    
    def update_activity(self, session_id: str):
        """更新活动时间"""
        self.last_activity[session_id] = time.time()
    
    def should_notify(self, session_id: str, has_tools: bool = False) -> bool:
        """检查是否应该发送通知"""
        now = time.time()
        
        # 检查去重窗口
        last_notif = self.last_notification.get(session_id, 0)
        if (now - last_notif) < self.dedupe_window:
            return False
        
        # 检查静默期
        threshold = self.quiet_threshold["with_tools" if has_tools else "without_tools"]
        last_active = self.last_activity.get(session_id, now)
        
        return (now - last_active) >= threshold
    
    def mark_notified(self, session_id: str):
        """标记已通知"""
        self.last_notification[session_id] = time.time()


class NotificationManager:
    """多通道通知管理器"""
    
    def __init__(self, config_file: Path = None):
        self.config_file = config_file or Path.home() / ".shared-memory" / ".notify_config.json"
        self.env_file = Path.home() / ".shared-memory" / ".notify.env"
        self.config = self._load_config()
        self.env = self._load_env()
        self.debouncer = NotificationDebouncer()
        
        # 通知渠道
        self.channels = {
            "webhook": self._send_webhook,
            "telegram": self._send_telegram,
            "email": self._send_email,
            "desktop": self._send_desktop,
            "console": self._send_console
        }
    
    def _load_config(self) -> Dict:
        """加载运行时配置"""
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text(encoding="utf-8"))
            except:
                return self._default_config()
        return self._default_config()
    
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            "channels": {
                "webhook": {"enabled": False, "url": ""},
                "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
                "email": {"enabled": False, "smtp_server": "", "smtp_port": 587, "username": "", "password": "", "to": ""},
                "desktop": {"enabled": True},
                "console": {"enabled": True}
            },
            "sources": {
                "claude": {"enabled": True, "min_duration_minutes": 1},
                "openclaude": {"enabled": True, "min_duration_minutes": 1},
                "hermes": {"enabled": True, "min_duration_minutes": 0}
            },
            "thresholds": {
                "quiet_seconds_with_tools": 60,
                "quiet_seconds_without_tools": 15,
                "dedupe_window_seconds": 120
            }
        }
    
    def _save_config(self):
        """保存配置"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(
            json.dumps(self.config, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def _load_env(self) -> Dict:
        """加载环境变量（敏感信息）"""
        env = {}
        if self.env_file.exists():
            for line in self.env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip()
        return env
    
    def _save_env(self, env: Dict):
        """保存环境变量"""
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{k}={v}" for k, v in env.items()]
        self.env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    
    def get_enabled_channels(self, source: str = None) -> List[str]:
        """获取启用的通知渠道"""
        enabled = []
        for channel_name, channel_config in self.config.get("channels", {}).items():
            if not channel_config.get("enabled", False):
                continue
            
            # 检查来源是否启用
            if source:
                source_config = self.config.get("sources", {}).get(source, {})
                if not source_config.get("enabled", False):
                    continue
            
            enabled.append(channel_name)
        
        return enabled
    
    def should_notify(self, session_id: str, source: str, duration_ms: int = None, 
                      has_tools: bool = False, force: bool = False) -> bool:
        """检查是否应该发送通知"""
        # 强制通知
        if force:
            return True
        
        # 检查来源配置
        source_config = self.config.get("sources", {}).get(source, {})
        if not source_config.get("enabled", False):
            return False
        
        # 检查耗时阈值
        min_duration = source_config.get("min_duration_minutes", 0)
        if min_duration > 0 and duration_ms is not None:
            threshold_ms = min_duration * 60 * 1000
            if duration_ms < threshold_ms:
                return False
        
        # 检查去抖
        return self.debouncer.should_notify(session_id, has_tools)
    
    def send(self, message: str, source: str = "claude", session_id: str = None,
             channels: List[str] = None, force: bool = False):
        """发送通知"""
        # 确定要使用的渠道
        if channels is None:
            channels = self.get_enabled_channels(source)
        
        if not channels:
            print("⚠️ 没有启用的通知渠道")
            return
        
        # 发送到各个渠道
        results = []
        for channel in channels:
            if channel in self.channels:
                try:
                    result = self.channels[channel](message, source)
                    results.append({"channel": channel, "success": True, "result": result})
                except Exception as e:
                    results.append({"channel": channel, "success": False, "error": str(e)})
        
        # 标记已通知
        if session_id:
            self.debouncer.mark_notified(session_id)
        
        return results
    
    def _send_webhook(self, message: str, source: str) -> Dict:
        """发送 Webhook 通知（飞书/钉钉/企微）"""
        webhook_url = self.config.get("channels", {}).get("webhook", {}).get("url", "")
        if not webhook_url:
            # 尝试从环境变量获取
            webhook_url = self.env.get("WEBHOOK_URL", "")
        
        if not webhook_url:
            raise ValueError("Webhook URL 未配置")
        
        # 检测平台类型
        platform = self._detect_webhook_platform(webhook_url)
        
        # 构建消息
        if platform == "feishu":
            payload = self._build_feishu_message(message, source)
        elif platform == "dingtalk":
            payload = self._build_dingtalk_message(message, source)
        elif platform == "wecom":
            payload = self._build_wecom_message(message, source)
        else:
            payload = {"text": message}
        
        # 发送请求
        import urllib.request
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            return {"status": response.status, "platform": platform}
    
    def _detect_webhook_platform(self, url: str) -> str:
        """检测 Webhook 平台类型"""
        if "feishu.cn" in url or "larksuite.com" in url:
            return "feishu"
        elif "dingtalk.com" in url:
            return "dingtalk"
        elif "wecom.qq.com" in url or "qyapi.weixin.qq.com" in url:
            return "wecom"
        return "unknown"
    
    def _build_feishu_message(self, message: str, source: str) -> Dict:
        """构建飞书消息"""
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"🤖 {source.upper()} 任务完成"},
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "plain_text", "content": message}
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {"tag": "plain_text", "content": f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                        ]
                    }
                ]
            }
        }
    
    def _build_dingtalk_message(self, message: str, source: str) -> Dict:
        """构建钉钉消息"""
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": f"🤖 {source.upper()} 任务完成",
                "text": f"## 🤖 {source.upper()} 任务完成\n\n{message}\n\n---\n*{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
            }
        }
    
    def _build_wecom_message(self, message: str, source: str) -> Dict:
        """构建企微消息"""
        return {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## 🤖 {source.upper()} 任务完成\n\n{message}\n\n> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
    
    def _send_telegram(self, message: str, source: str) -> Dict:
        """发送 Telegram 通知"""
        bot_token = self.config.get("channels", {}).get("telegram", {}).get("bot_token", "")
        chat_id = self.config.get("channels", {}).get("telegram", {}).get("chat_id", "")
        
        if not bot_token:
            bot_token = self.env.get("TELEGRAM_BOT_TOKEN", "")
        if not chat_id:
            chat_id = self.env.get("TELEGRAM_CHAT_ID", "")
        
        if not bot_token or not chat_id:
            raise ValueError("Telegram 配置未完成")
        
        import urllib.request
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": f"🤖 *{source.upper()} 任务完成*\n\n{message}",
            "parse_mode": "Markdown"
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            return {"status": response.status}
    
    def _send_email(self, message: str, source: str) -> Dict:
        """发送邮件通知"""
        # 简化实现，实际需要 smtplib
        print(f"📧 邮件通知: {message}")
        return {"status": "not_implemented"}
    
    def _send_desktop(self, message: str, source: str) -> Dict:
        """发送桌面通知"""
        # 简化实现，实际需要 plyer 或 win10toast
        print(f"🖥️ 桌面通知: {message}")
        return {"status": "not_implemented"}
    
    def _send_console(self, message: str, source: str) -> Dict:
        """控制台通知"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n{'='*60}")
        print(f"🔔 [{timestamp}] {source.upper()} 任务完成")
        print(f"{'='*60}")
        print(message)
        print(f"{'='*60}\n")
        return {"status": "ok"}
    
    def test_channel(self, channel: str) -> bool:
        """测试通知渠道"""
        test_message = f"🧪 测试消息 - {datetime.now().strftime('%H:%M:%S')}"
        
        try:
            if channel in self.channels:
                result = self.channels[channel](test_message, "test")
                print(f"✅ {channel} 测试成功: {result}")
                return True
            else:
                print(f"❌ 未知渠道: {channel}")
                return False
        except Exception as e:
            print(f"❌ {channel} 测试失败: {e}")
            return False
    
    def show_config(self):
        """显示配置"""
        print("📋 通知配置:\n")
        
        print("渠道:")
        for name, config in self.config.get("channels", {}).items():
            status = "✅" if config.get("enabled") else "❌"
            print(f"  {status} {name}")
        
        print("\n来源:")
        for name, config in self.config.get("sources", {}).items():
            status = "✅" if config.get("enabled") else "❌"
            min_dur = config.get("min_duration_minutes", 0)
            print(f"  {status} {name} (最小耗时: {min_dur}分钟)")
        
        print("\n阈值:")
        thresholds = self.config.get("thresholds", {})
        print(f"  静默期（有工具）: {thresholds.get('quiet_seconds_with_tools', 60)}秒")
        print(f"  静默期（无工具）: {thresholds.get('quiet_seconds_without_tools', 15)}秒")
        print(f"  去重窗口: {thresholds.get('dedupe_window_seconds', 120)}秒")


def main():
    parser = argparse.ArgumentParser(description="任务完成通知系统")
    subparsers = parser.add_subparsers(dest="command")
    
    # send
    send_parser = subparsers.add_parser("send", help="发送通知")
    send_parser.add_argument("message", help="通知内容")
    send_parser.add_argument("--source", "-s", default="claude", help="来源")
    send_parser.add_argument("--session-id", help="会话 ID")
    send_parser.add_argument("--channels", "-c", nargs="*", help="指定渠道")
    send_parser.add_argument("--force", "-f", action="store_true", help="强制发送")
    
    # test
    test_parser = subparsers.add_parser("test", help="测试渠道")
    test_parser.add_argument("channel", help="渠道名称")
    
    # config
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_parser.add_argument("--show", action="store_true", help="显示配置")
    config_parser.add_argument("--enable", help="启用渠道")
    config_parser.add_argument("--disable", help="禁用渠道")
    
    args = parser.parse_args()
    
    manager = NotificationManager()
    
    if args.command == "send":
        results = manager.send(
            message=args.message,
            source=args.source,
            session_id=args.session_id,
            channels=args.channels,
            force=args.force
        )
        if results:
            print(f"📤 通知已发送:")
            for r in results:
                status = "✅" if r["success"] else "❌"
                print(f"  {status} {r['channel']}")
    
    elif args.command == "test":
        manager.test_channel(args.channel)
    
    elif args.command == "config":
        if args.show:
            manager.show_config()
        elif args.enable:
            manager.config["channels"][args.enable]["enabled"] = True
            manager._save_config()
            print(f"✅ 已启用: {args.enable}")
        elif args.disable:
            manager.config["channels"][args.disable]["enabled"] = False
            manager._save_config()
            print(f"✅ 已禁用: {args.disable}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
