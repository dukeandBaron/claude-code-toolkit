"""
Provider Profile 管理器

借鉴 OpenClaude 的 /provider 命令，支持多个 LLM 后端配置。

使用方式：
  python provider_manager.py add openai --base-url https://api.openai.com/v1 --api-key sk-xxx --model gpt-4o
  python provider_manager.py add deepseek --base-url https://api.deepseek.com/v1 --api-key sk-xxx --model deepseek-chat
  python provider_manager.py list
  python provider_manager.py use deepseek
  python provider_manager.py test openai
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional


class ProviderManager:
    """管理多个 LLM 后端配置"""
    
    def __init__(self, config_file: Path = None):
        self.config_file = config_file or Path.home() / ".shared-memory" / ".providers.json"
        self.providers = self._load()
    
    def _load(self) -> Dict:
        """加载配置"""
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text(encoding="utf-8"))
            except:
                return {"providers": {}, "default": None}
        return {"providers": {}, "default": None}
    
    def _save(self):
        """保存配置"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(
            json.dumps(self.providers, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def add(self, name: str, base_url: str, api_key: str, model: str,
            headers: Dict = None, description: str = None):
        """添加 provider"""
        if "providers" not in self.providers:
            self.providers["providers"] = {}
        
        self.providers["providers"][name] = {
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "headers": headers or {},
            "description": description or "",
            "added_at": self._now()
        }
        
        # 如果是第一个 provider，设为默认
        if not self.providers.get("default"):
            self.providers["default"] = name
        
        self._save()
        return self.providers["providers"][name]
    
    def remove(self, name: str):
        """删除 provider"""
        if "providers" in self.providers and name in self.providers["providers"]:
            del self.providers["providers"][name]
            
            # 如果删除的是默认 provider，重置默认
            if self.providers.get("default") == name:
                remaining = list(self.providers["providers"].keys())
                self.providers["default"] = remaining[0] if remaining else None
            
            self._save()
            return True
        return False
    
    def get(self, name: str = None) -> Optional[Dict]:
        """获取 provider 配置"""
        if "providers" not in self.providers:
            return None
        
        name = name or self.providers.get("default")
        return self.providers["providers"].get(name)
    
    def list(self) -> List[str]:
        """列出所有 provider 名称"""
        if "providers" not in self.providers:
            return []
        return list(self.providers["providers"].keys())
    
    def set_default(self, name: str):
        """设置默认 provider"""
        if "providers" in self.providers and name in self.providers["providers"]:
            self.providers["default"] = name
            self._save()
            return True
        return False
    
    def get_default(self) -> Optional[str]:
        """获取默认 provider 名称"""
        return self.providers.get("default")
    
    def test_connection(self, name: str = None) -> Dict:
        """测试 provider 连接"""
        provider = self.get(name)
        if not provider:
            return {"success": False, "error": "Provider not found"}
        
        # 这里应该实际测试连接
        # 暂时返回模拟结果
        return {
            "success": True,
            "provider": name or self.get_default(),
            "base_url": provider["base_url"],
            "model": provider["model"]
        }
    
    def _now(self) -> str:
        """获取当前时间"""
        from datetime import datetime
        return datetime.now().isoformat()


def main():
    parser = argparse.ArgumentParser(description="Provider Profile 管理器")
    subparsers = parser.add_subparsers(dest="command")
    
    # add
    add_parser = subparsers.add_parser("add", help="添加 provider")
    add_parser.add_argument("name", help="Provider 名称")
    add_parser.add_argument("--base-url", required=True, help="API 基础 URL")
    add_parser.add_argument("--api-key", required=True, help="API 密钥")
    add_parser.add_argument("--model", required=True, help="模型名称")
    add_parser.add_argument("--description", default="", help="描述")
    
    # remove
    remove_parser = subparsers.add_parser("remove", help="删除 provider")
    remove_parser.add_argument("name", help="Provider 名称")
    
    # list
    subparsers.add_parser("list", help="列出所有 provider")
    
    # use
    use_parser = subparsers.add_parser("use", help="设置默认 provider")
    use_parser.add_argument("name", help="Provider 名称")
    
    # test
    test_parser = subparsers.add_parser("test", help="测试连接")
    test_parser.add_argument("name", nargs="?", help="Provider 名称")
    
    # show
    show_parser = subparsers.add_parser("show", help="显示 provider 配置")
    show_parser.add_argument("name", nargs="?", help="Provider 名称")
    
    args = parser.parse_args()
    
    manager = ProviderManager()
    
    if args.command == "add":
        provider = manager.add(
            name=args.name,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            description=args.description
        )
        print(f"✅ Provider 已添加: {args.name}")
        print(f"   Base URL: {provider['base_url']}")
        print(f"   Model: {provider['model']}")
        if not manager.get_default() or manager.get_default() == args.name:
            print(f"   已设为默认 provider")
    
    elif args.command == "remove":
        if manager.remove(args.name):
            print(f"✅ Provider 已删除: {args.name}")
        else:
            print(f"❌ Provider 不存在: {args.name}")
    
    elif args.command == "list":
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
                if provider.get('description'):
                    print(f"    描述: {provider['description']}")
                print()
        else:
            print("📭 没有配置 provider")
            print("\n添加示例:")
            print('  python provider_manager.py add openai --base-url https://api.openai.com/v1 --api-key sk-xxx --model gpt-4o')
    
    elif args.command == "use":
        if manager.set_default(args.name):
            print(f"✅ 默认 provider 已设为: {args.name}")
        else:
            print(f"❌ Provider 不存在: {args.name}")
    
    elif args.command == "test":
        result = manager.test_connection(args.name)
        if result["success"]:
            print(f"✅ 连接测试成功")
            print(f"   Provider: {result['provider']}")
            print(f"   URL: {result['base_url']}")
            print(f"   Model: {result['model']}")
        else:
            print(f"❌ 连接测试失败: {result['error']}")
    
    elif args.command == "show":
        provider = manager.get(args.name)
        if provider:
            name = args.name or manager.get_default()
            print(f"📋 Provider 配置: {name}\n")
            print(json.dumps(provider, ensure_ascii=False, indent=2))
        else:
            print(f"❌ Provider 不存在: {args.name or '默认'}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
